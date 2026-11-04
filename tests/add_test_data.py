import sys
import os

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)
from backend.app import app
from backend.models import db, Expense


test_expenses = [

    # May 2026
    {
        "amount": 4200,
        "category": "Food",
        "date": "2026-05-15",
        "description": "May expenses"
    },

    # June 2026
    {
        "amount": 4800,
        "category": "Shopping",
        "date": "2026-06-15",
        "description": "June expenses"
    },

    # July 2026
    {
        "amount": 5100,
        "category": "Transport",
        "date": "2026-07-15",
        "description": "July expenses"
    },

    # August 2026
    {
        "amount": 5600,
        "category": "Bills",
        "date": "2026-08-15",
        "description": "August expenses"
    },

    # September 2026
    {
        "amount": 6000,
        "category": "Entertainment",
        "date": "2026-09-15",
        "description": "September expenses"
    },

    # October 2026
    {
        "amount": 6500,
        "category": "Food",
        "date": "2026-10-15",
        "description": "October expenses"
    }
]


with app.app_context():

    for data in test_expenses:

        expense = Expense(
            amount=data["amount"],
            category=data["category"],
            date=data["date"],
            description=data["description"]
        )

        db.session.add(expense)

    db.session.commit()

    print("Test expense data added successfully!")