
import sqlite3
from pathlib import Path
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, text

from backend.app import app, db


BASE_DIR = Path(__file__).resolve().parent
SQLITE_DB = BASE_DIR / "database" / "expenses.db"

TABLES = ["user", "expense", "budget", "budget_alert"]


def migrate():
    if not SQLITE_DB.exists():
        raise FileNotFoundError(f"Local database not found: {SQLITE_DB}")

    local = sqlite3.connect(SQLITE_DB)
    local.row_factory = sqlite3.Row

    try:
        with app.app_context():

            print("Destination:", db.engine.dialect.name)

            if db.engine.dialect.name != "postgresql":
                raise RuntimeError("Destination is not PostgreSQL!")

            # Read all local records.
            records = {}

            for table_name in TABLES:
                rows = local.execute(
                    f'SELECT * FROM "{table_name}" ORDER BY id'
                ).fetchall()

                records[table_name] = [dict(row) for row in rows]

                print(f"Local {table_name}: {len(rows)} records")

            # Convert SQLite values to SQLAlchemy-compatible values.
            for table_name, rows in records.items():
                table = db.metadata.tables[table_name]

                for row in rows:
                    for column in table.columns:
                        value = row.get(column.name)

                        if value is None:
                            continue

                        if isinstance(column.type, DateTime):
                            if isinstance(value, str):
                                row[column.name] = datetime.fromisoformat(value)

                        elif isinstance(column.type, Numeric):
                            row[column.name] = Decimal(str(value))

            # Insert everything atomically.
            with db.engine.begin() as connection:

                # Never overwrite existing Supabase records.
                for table_name in TABLES:
                    count = connection.execute(
                        text(f'SELECT COUNT(*) FROM "{table_name}"')
                    ).scalar()

                    if count != 0:
                        raise RuntimeError(
                            f"Supabase table {table_name} is not empty. "
                            "Migration cancelled."
                        )

                # Preserve foreign-key relationships.
                for table_name in TABLES:
                    table = db.metadata.tables[table_name]
                    rows = records[table_name]

                    if rows:
                        connection.execute(table.insert(), rows)

                    print(
                        f"Transferred {table_name}: {len(rows)} records"
                    )

                # Reset PostgreSQL ID sequences.
                for table_name in TABLES:
                    connection.execute(
                        text(
                            f"""
                            SELECT setval(
                                pg_get_serial_sequence(:table_name, 'id'),
                                COALESCE(MAX(id), 1),
                                MAX(id) IS NOT NULL
                            )
                            FROM "{table_name}"
                            """
                        ),
                        {"table_name": f'"{table_name}"'}
                    )
            print("\nMIGRATION COMPLETED SUCCESSFULLY!")

    finally:
        local.close()


if __name__ == "__main__":
    migrate()
