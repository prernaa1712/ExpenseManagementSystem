import math
from dotenv import load_dotenv
from datetime import datetime, timedelta
import re
import secrets
import os
import sys
import ssl
import uuid
from functools import wraps

from flask import (
    Flask, request, jsonify, send_from_directory, session
)
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError


sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
UPLOAD_DIR = os.path.join(FRONTEND_DIR, "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)

from backend.models import (
    db,
    User,
    Expense,
    Budget,
    BudgetAlert,
    PasswordResetOTP
)
from backend.email_service import (
    send_budget_alert,
    send_password_reset_otp
)
from ml.predictor import prepare_data, predict_next_month
from bot.bot import chatbot_response

app = Flask(__name__)


# Application and session configuration

SECRET_KEY = os.environ.get("SECRET_KEY")

# Never allow an insecure fallback in production.
if not SECRET_KEY:
    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError(
            "SECRET_KEY environment variable must be configured."
        )

    # Generate a temporary secure key for local development.
    SECRET_KEY = secrets.token_hex(32)

app.config["SECRET_KEY"] = SECRET_KEY

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("FLASK_ENV") == "production"
)

# Database configuration
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql+pg8000://",
            1
        )
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgresql://",
            "postgresql+pg8000://",
            1
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "connect_args": {
            "ssl_context": ssl.create_default_context(
                cafile=os.path.join(BASE_DIR, "supabase-ca.crt")
            )
        }
    }

else:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///" +
        os.path.join(BASE_DIR, "database", "expenses.db").replace("\\", "/")
    )

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True
    }

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Initialize SQLAlchemys
db.init_app(app)
# Create any missing database tables, including password_reset_otp.
# Existing tables and records are preserved.
with app.app_context():
    db.create_all()

# -----------------------------------
# Authentication helper
# -----------------------------------

def is_strong_password(password):
    """
    Password must have:
    - At least 8 characters
    - One uppercase letter
    - One lowercase letter
    - One digit
    - One special character
    """

    if len(password) < 8:
        return False

    if not re.search(r"[A-Z]", password):
        return False

    if not re.search(r"[a-z]", password):
        return False

    if not re.search(r"\d", password):
        return False

    if not re.search(r"[^A-Za-z0-9]", password):
        return False

    return True


def is_valid_email(email):
    """Basic email-format validation."""

    return bool(
        re.fullmatch(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            email
        )
    )

def login_required(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")

        if not user_id:
            return jsonify({"error": "Please log in first."}), 401

        user = db.session.get(User, user_id)

        if not user:
            session.clear()
            return jsonify({"error": "User session not found."}), 401

        return function(*args, **kwargs)

    return decorated_function


def get_logged_in_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    return db.session.get(User, user_id)


def check_and_send_budget_alert(user_id, month):
    """
    Check monthly spending and send each budget alert only once
    per user, per month.
    """

    # Find the user's budget for the selected month
    budget = Budget.query.filter_by(
        user_id=user_id,
        month=month
    ).first()

    if not budget:
        return

    # Find the registered user
    user = User.query.get(user_id)

    if not user:
        return

    # Calculate total expenses for this user and month
    expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date.like(f"{month}-%")
    ).all()

    total_spent = sum(float(expense.amount) for expense in expenses)

    budget_amount = float(budget.amount)

    if budget_amount <= 0:
        return

    percentage_used = (total_spent / budget_amount) * 100

    # Determine which alerts are applicable
    alert_types = []

    if percentage_used >= 80:
        alert_types.append("80")

    if percentage_used >= 100:
        alert_types.append("100")

    for alert_type in alert_types:

        # Check whether this notification was already sent
        existing_alert = BudgetAlert.query.filter_by(
            user_id=user_id,
            month=month,
            alert_type=alert_type
        ).first()

        if existing_alert:
            continue

        # Send the email
        email_sent = send_budget_alert(
            user=user,
            month=month,
            budget_amount=budget_amount,
            total_spent=total_spent,
            percentage_used=percentage_used,
            alert_type=alert_type
        )

        # Record the alert only if the email was sent successfully
        if email_sent:
            try:
                alert = BudgetAlert(
                    user_id=user_id,
                    month=month,
                    alert_type=alert_type
                )

                db.session.add(alert)
                db.session.commit()

            except IntegrityError:
                db.session.rollback()
                app.logger.warning(
                    "Budget alert already recorded for user %s, month %s, type %s",
                    user_id,
                    month,
                    alert_type
                )

# -----------------------------------
# Frontend routes
# -----------------------------------

@app.route("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def frontend_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# -----------------------------------
# Registration
# -----------------------------------

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({
            "error": "Name, email and password are required."
        }), 400

    if len(name) > 100:
        return jsonify({
            "error": "Name cannot exceed 100 characters."
        }), 400

    if len(email) > 255 or not is_valid_email(email):
        return jsonify({
            "error": "Please enter a valid email address."
        }), 400

    if not is_strong_password(password):
        return jsonify({
            "error": (
                "Password must contain at least 8 characters, "
                "including uppercase, lowercase, number and special character."
            )
        }), 400

    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        return jsonify({
            "error": "An account with this email already exists."
        }), 409

    user = User(
        name=name,
        email=email,
        role="user"
    )
    user.set_password(password)

    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Email is already registered."}), 409

    session.clear()
    session["user_id"] = user.id

    return jsonify({
        "message": "Registration successful.",
        "user": user.to_dict()
    }), 201


# -----------------------------------
# Login
# -----------------------------------

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({
            "error": "Email and password are required."
        }), 400

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({
            "error": "Invalid email or password."
        }), 401

    session.clear()
    session["user_id"] = user.id

    return jsonify({
        "message": "Login successful.",
        "user": user.to_dict()
    })



# -----------------------------------
# Forgot Password - Request OTP
# -----------------------------------

@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()

    generic_message = (
        "If an account exists for this email, "
        "a verification code will be sent."
    )

    if not email or len(email) > 255 or not is_valid_email(email):
        return jsonify({"message": generic_message}), 200

    user = User.query.filter_by(email=email).first()

    # Do not reveal whether an account exists.
    if not user:
        return jsonify({"message": generic_message}), 200

    now = datetime.utcnow()

    reset_record = PasswordResetOTP.query.filter_by(
        user_id=user.id
    ).first()

    # Prevent repeated OTP requests within 60 seconds.
    if reset_record:
        elapsed = (now - reset_record.created_at).total_seconds()

        if elapsed < 60:
            return jsonify({"message": generic_message}), 200

    # Generate a secure six-digit OTP.
    otp = f"{secrets.randbelow(1000000):06d}"

    if reset_record:
        reset_record.set_otp(otp)
        reset_record.expires_at = now + timedelta(minutes=10)
        reset_record.attempts = 0
        reset_record.verified_at = None
        reset_record.created_at = now
    else:
        reset_record = PasswordResetOTP(
            user_id=user.id,
            expires_at=now + timedelta(minutes=10),
            attempts=0
        )
        reset_record.set_otp(otp)
        db.session.add(reset_record)

    try:
        db.session.commit()

        email_sent = send_password_reset_otp(user, otp)

        if not email_sent:
            db.session.delete(reset_record)
            db.session.commit()
            app.logger.error(
                "Password reset email could not be sent for user %s",
                user.id
            )

    except Exception:
        db.session.rollback()
        app.logger.exception("Forgot password request failed.")

    return jsonify({"message": generic_message}), 200


# -----------------------------------
# Forgot Password - Verify OTP
# -----------------------------------

@app.route("/api/verify-reset-otp", methods=["POST"])
def verify_reset_otp():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    otp = (data.get("otp") or "").strip()

    if not email or not otp or not is_valid_email(email):
        return jsonify({
            "error": "Please enter your email and verification code."
        }), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({
            "error": "Invalid or expired verification code."
        }), 400

    reset_record = PasswordResetOTP.query.filter_by(
        user_id=user.id
    ).first()

    if not reset_record:
        return jsonify({
            "error": "Invalid or expired verification code."
        }), 400

    if datetime.utcnow() > reset_record.expires_at:
        db.session.delete(reset_record)
        db.session.commit()

        return jsonify({
            "error": "Verification code has expired. Request a new one."
        }), 400

    if reset_record.attempts >= 5:
        return jsonify({
            "error": "Too many incorrect attempts. Request a new code."
        }), 429

    reset_record.attempts += 1

    if not reset_record.check_otp(otp):
        db.session.commit()

        return jsonify({
            "error": "Incorrect verification code."
        }), 400

    reset_record.verified_at = datetime.utcnow()
    session["password_reset_user_id"] = user.id
    db.session.commit()

    return jsonify({
        "message": "Email verification successful. You can reset your password."
    }), 200


# -----------------------------------
# Forgot Password - Set New Password
# -----------------------------------

@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    new_password = data.get("new_password") or ""
    confirm_password = data.get("confirm_password") or ""

    if not email or not is_valid_email(email):
        return jsonify({"error": "Please enter a valid email address."}), 400

    if new_password != confirm_password:
        return jsonify({"error": "Passwords do not match."}), 400

    if not is_strong_password(new_password):
        return jsonify({
            "error": (
                "Password must contain at least 8 characters, "
                "including uppercase, lowercase, number and special character."
            )
        }), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({
            "error": "Password reset verification is invalid or expired."
        }), 400

    reset_record = PasswordResetOTP.query.filter_by(
        user_id=user.id
    ).first()

    if (
        not reset_record
        or not reset_record.verified_at
        or session.get("password_reset_user_id") != user.id
    ):
        return jsonify({
            "error": "Please verify your OTP before resetting your password."
        }), 400

    now = datetime.utcnow()

    if now > reset_record.expires_at:
        db.session.delete(reset_record)
        db.session.commit()
        session.pop("password_reset_user_id", None)

        return jsonify({
            "error": "Verification has expired. Request a new OTP."
        }), 400

    # Update the password using the existing secure hashing method.
    user.set_password(new_password)

    # OTP must not be reusable.
    db.session.delete(reset_record)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Password reset failed.")

        return jsonify({
            "error": "Unable to reset password. Please try again."
        }), 500

    return jsonify({
        "message": "Password reset successful. Please log in."
    }), 200

# -----------------------------------
# Current logged-in user
# -----------------------------------

@app.route("/api/me", methods=["GET"])
def current_user():
    user = get_logged_in_user()

    if not user:
        return jsonify({"authenticated": False})

    return jsonify({
        "authenticated": True,
        "user": user.to_dict()
    })


# -----------------------------------
# Logout
# -----------------------------------

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()

    return jsonify({
        "message": "Logged out successfully."
    })


# -----------------------------------
# Expense routes
# -----------------------------------

@app.route("/api/expenses", methods=["GET"])
@login_required
def get_expenses():
    user_id = session["user_id"]

    expenses = (
        Expense.query
        .filter_by(user_id=user_id)
        .order_by(Expense.id.desc())
        .all()
    )

    return jsonify([expense.to_dict() for expense in expenses])


@app.route("/api/expenses", methods=["POST"])
@login_required
def add_expense():
    data = request.get_json(silent=True) or {}

    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"error": "Enter a valid amount."}), 400

    category = (data.get("category") or "").strip()
    date = (data.get("date") or "").strip()
    description = (data.get("description") or "").strip()

    if amount <= 0 or not category or not date:
        return jsonify({
            "error": "Enter a valid amount, category and date."
        }), 400

    expense = Expense(
        amount=amount,
        category=category,
        date=date,
        description=description,
        user_id=session["user_id"]
    )

    db.session.add(expense)
    db.session.commit()
    check_and_send_budget_alert(
        session["user_id"],
        expense.date[:7]
    )

    return jsonify(expense.to_dict()), 201


@app.route("/api/expenses/<int:expense_id>", methods=["PUT"])
@login_required
def update_expense(expense_id):
    expense = Expense.query.filter_by(
        id=expense_id,
        user_id=session["user_id"]
    ).first()

    if expense is None:
        return jsonify({"error": "Expense not found."}), 404
    old_month = expense.date[:7]
    data = request.get_json(silent=True) or {}

    if "amount" in data:
        try:
            amount = float(data["amount"])
            if amount <= 0:
                raise ValueError
            expense.amount = amount
        except (TypeError, ValueError):
            return jsonify({"error": "Enter a valid amount."}), 400

    if "category" in data:
        expense.category = str(data["category"]).strip()

    if "date" in data:
        expense.date = str(data["date"]).strip()

    if "description" in data:
        expense.description = str(data["description"]).strip()

    db.session.commit()
    # NEW: Check the old and new months
    new_month = expense.date[:7]
    user_id = session["user_id"]

    check_and_send_budget_alert(user_id, old_month)

    if new_month != old_month:
        check_and_send_budget_alert(user_id, new_month)
    return jsonify(expense.to_dict())


@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.filter_by(
        id=expense_id,
        user_id=session["user_id"]
    ).first()

    if expense is None:
        return jsonify({"error": "Expense not found."}), 404
    expense_month = expense.date[:7]
    db.session.delete(expense)
    db.session.commit()
    # NEW: Recalculate budget usage
    check_and_send_budget_alert(
        session["user_id"],
        expense_month
    )
    return jsonify({
        "message": "Expense deleted successfully."
    })

# -----------------------------------
# Monthly Budget routes
# -----------------------------------

def validate_budget_month(month):
    try:
        if not isinstance(month, str) or len(month) != 7:
            return False

        datetime.strptime(month, "%Y-%m")
        return True

    except ValueError:
        return False


@app.route("/api/budgets", methods=["GET"])
@login_required
def get_budget():

    user_id = session["user_id"]

    month = request.args.get(
        "month",
        datetime.now().strftime("%Y-%m")
    )

    if not validate_budget_month(month):
        return jsonify({
            "error": "Invalid month format. Use YYYY-MM."
        }), 400

    budget = Budget.query.filter_by(
        user_id=user_id,
        month=month
    ).first()

    total_spent = db.session.query(
        db.func.coalesce(db.func.sum(Expense.amount), 0)
    ).filter(
        Expense.user_id == user_id,
        Expense.date.like(f"{month}-%")
    ).scalar()

    total_spent = float(total_spent or 0)

    budget_amount = (
        float(budget.amount) if budget else 0
    )

    remaining = budget_amount - total_spent

    percentage_used = (
        (total_spent / budget_amount) * 100
        if budget_amount > 0 else 0
    )

    return jsonify({
        "month": month,
        "budget": budget_amount,
        "total_spent": round(total_spent, 2),
        "remaining": round(remaining, 2),
        "percentage_used": round(percentage_used, 2),
        "has_budget": budget is not None
    })


@app.route("/api/budgets/history", methods=["GET"])
@login_required
def get_budget_history():

    user_id = session["user_id"]

    # Fetch all monthly budgets belonging to the logged-in user
    budgets = Budget.query.filter_by(
        user_id=user_id
    ).order_by(
        Budget.month.desc()
    ).all()

    history = []

    for budget in budgets:

        budget_amount = float(budget.amount)

        # Calculate actual spending for this month
        total_spent = db.session.query(
            db.func.coalesce(db.func.sum(Expense.amount), 0)
        ).filter(
            Expense.user_id == user_id,
            Expense.date.like(f"{budget.month}-%")
        ).scalar()

        total_spent = float(total_spent)

        remaining = budget_amount - total_spent
        percentage_used = (total_spent / budget_amount) * 100

        # Determine monthly budget status
        if percentage_used >= 100:
            status = "Exceeded"
        elif percentage_used >= 80:
            status = "Warning"
        else:
            status = "Under Budget"

        history.append({
            "month": budget.month,
            "budget": budget_amount,
            "total_spent": total_spent,
            "remaining": max(remaining, 0),
            "exceeded_amount": max(-remaining, 0),
            "percentage_used": round(percentage_used, 2),
            "status": status
        })

    return jsonify({
        "history": history,
        "total_months": len(history)
    }), 200


@app.route("/api/budgets", methods=["POST"])
@login_required
def save_budget():

    data = request.get_json(silent=True) or {}

    month = data.get(
        "month",
        datetime.now().strftime("%Y-%m")
    )

    if not validate_budget_month(month):
        return jsonify({
            "error": "Invalid month format. Use YYYY-MM."
        }), 400

    try:
        amount = float(data.get("amount"))

        if not math.isfinite(amount) or amount <= 0:
            raise ValueError

    except (TypeError, ValueError):
        return jsonify({
            "error": "Enter a valid budget amount greater than zero."
        }), 400

    user_id = session["user_id"]

    budget = Budget.query.filter_by(
        user_id=user_id,
        month=month
    ).first()

    if budget:
        budget.amount = amount
    else:
        budget = Budget(
            user_id=user_id,
            month=month,
            amount=amount
        )
        db.session.add(budget)

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()
        app.logger.exception("Budget save failed")

        return jsonify({
            "error": "Unable to save budget."
        }), 500
    # NEW: Check budget thresholds and send email alerts
    check_and_send_budget_alert(user_id, month)

    return jsonify({
        "message": "Monthly budget saved successfully.",
        "budget": budget.to_dict()
    }), 201

# -----------------------------------
# Machine learning routes
# -----------------------------------

@app.route("/api/ml/test", methods=["GET"])
@login_required
def ml_test():
    df = prepare_data(session["user_id"])
    return df.to_json(orient="records")


@app.route("/api/ml/predict", methods=["GET"])
@login_required
def predict_expense():
    result = predict_next_month(session["user_id"])
    return jsonify(result)


# -----------------------------------
# Chatbot route
# -----------------------------------

@app.route("/api/chatbot", methods=["POST"])
@login_required
def chatbot():
    data = request.get_json(silent=True) or {}

    message = data.get("message", "")
    response = chatbot_response(
        message,
        session["user_id"]
    )

    return jsonify({"response": response})


# -----------------------------------
# Profile picture upload
# -----------------------------------

@app.route("/api/profile-picture", methods=["POST"])
@login_required
def upload_profile_picture():
    if "profile_picture" not in request.files:
        return jsonify({"error": "No image was uploaded."}), 400

    file = request.files["profile_picture"]

    if not file or not file.filename:
        return jsonify({"error": "Please select an image."}), 400

    extension = file.filename.rsplit(".", 1)[-1].lower()

    allowed_extensions = {"jpg", "jpeg", "png", "webp"}
    allowed_mimetypes = {
        "image/jpeg",
        "image/png",
        "image/webp"
    }

    if extension not in allowed_extensions or file.mimetype not in allowed_mimetypes:
        return jsonify({
            "error": "Only JPG, JPEG, PNG and WEBP images are allowed."
        }), 400

    user = get_logged_in_user()

    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    try:
        file.stream.seek(0)

        image = Image.open(file.stream)
        image.verify()

        file.stream.seek(0)

    except (UnidentifiedImageError, OSError, ValueError):
        return jsonify({
            "error": "Invalid image file. Please upload a valid image."
        }), 400

    file.save(file_path)

    picture_url = f"/uploads/{unique_filename}"
    user.profile_picture = picture_url

    db.session.commit()

    return jsonify({
        "message": "Profile picture updated successfully.",
        "profile_picture": picture_url
    })


if __name__ == "__main__":
    app.run(debug=True)
