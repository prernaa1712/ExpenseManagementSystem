
import os
import sys
import uuid
from functools import wraps

from flask import (
    Flask, request, jsonify, send_from_directory, session
)
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
UPLOAD_DIR = os.path.join(FRONTEND_DIR, "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)

from backend.models import db, User, Expense
from ml.predictor import prepare_data, predict_next_month
from bot.bot import chatbot_response

app = Flask(__name__)

# Application and session configuration
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "change-this-development-secret-key"
)
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" +
    os.path.join(BASE_DIR, "database", "expenses.db").replace("\\", "/")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

db.init_app(app)

with app.app_context():
    db.create_all()


# -----------------------------------
# Authentication helper
# -----------------------------------

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

    if len(password) < 6:
        return jsonify({
            "error": "Password must contain at least 6 characters."
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

    db.session.delete(expense)
    db.session.commit()

    return jsonify({
        "message": "Expense deleted successfully."
    })


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
