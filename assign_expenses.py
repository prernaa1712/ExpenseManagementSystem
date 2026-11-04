
from backend.app import app
from backend.models import db, User, Expense

with app.app_context():

    email = input("Enter Prerna's registered email: ").strip().lower()

    user = User.query.filter_by(email=email).first()

    if user is None:
        print("ERROR: Prerna's account was not found.")

    else:
        count = Expense.query.filter_by(user_id=None).update(
            {"user_id": user.id}
        )

        db.session.commit()

        print("\nAssignment completed!")
        print("Account:", user.name)
        print("Email:", user.email)
        print("Expenses assigned:", count)

        print("\nTotal expenses now:", Expense.query.filter_by(user_id=user.id).count())
