
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "database" / "expenses.db"
ADMIN_EMAIL = "prernaakadam20@gmail.com"

connection = sqlite3.connect(DB_PATH)

try:
    cursor = connection.cursor()

    # Check whether the role column already exists.
    user_columns = [
        row[1] for row in cursor.execute('PRAGMA table_info("user")')
    ]

    if not user_columns:
        raise RuntimeError(
            'The "user" table was not found. No changes were made.'
        )

    if "role" not in user_columns:
        cursor.execute(
            'ALTER TABLE "user" '
            "ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"
        )
        print("Added the role column.")

    # Find Prerna's existing account.
    admin = cursor.execute(
        'SELECT id, email FROM "user" WHERE lower(email) = lower(?)',
        (ADMIN_EMAIL,)
    ).fetchone()

    if admin is None:
        raise RuntimeError(
            "Prerna's account was not found. "
            "Check the registered email before continuing."
        )

    # Assign admin to Prerna and user to every other account.
    cursor.execute(
        'UPDATE "user" SET role = '
        "CASE WHEN lower(email) = lower(?) "
        "THEN 'admin' ELSE 'user' END",
        (ADMIN_EMAIL,)
    )

    # Preserve the existing shared expenses under Prerna.
    expense_columns = [
        row[1] for row in cursor.execute('PRAGMA table_info("expense")')
    ]

    if "user_id" not in expense_columns:
        raise RuntimeError(
            'The "expense" table has no user_id column. '
            "Stop and check the model/database before continuing."
        )

    cursor.execute(
        'UPDATE "expense" SET user_id = ? WHERE user_id IS NULL',
        (admin[0],)
    )

    connection.commit()

    print("Migration completed successfully.")
    print(f"Admin account: {admin[1]}")
    print(f"Expenses assigned to Prerna: {cursor.rowcount}")
    print("Other accounts remain regular users.")

except Exception:
    connection.rollback()
    raise

finally:
    connection.close()
