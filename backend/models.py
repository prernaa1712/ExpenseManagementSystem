
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    profile_picture = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="user")

    expenses = db.relationship(
        "Expense",
        backref="owner",
        lazy=True
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "profile_picture": self.profile_picture
        }


class Expense(db.Model):
    __tablename__ = "expense"

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(200))

    # Nullable temporarily to preserve existing expenses
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True,
        index=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "amount": self.amount,
            "category": self.category,
            "date": self.date,
            "description": self.description
        }

class Budget(db.Model):
    __tablename__ = "budget"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True
    )

    # Format: YYYY-MM (example: 2026-11)
    month = db.Column(db.String(7), nullable=False)

    amount = db.Column(db.Numeric(10, 2), nullable=False)

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp()
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "month",
            name="unique_user_month_budget"
        ),
        db.CheckConstraint(
            "amount > 0",
            name="positive_budget_amount"
        )
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "month": self.month,
            "amount": float(self.amount)
        }