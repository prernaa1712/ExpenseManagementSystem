
import pandas as pd
from backend.models import Expense
from sklearn.linear_model import LinearRegression


def get_expense_data(user_id):
    expenses = Expense.query.filter_by(
        user_id=user_id
    ).all()

    data = []

    for expense in expenses:
        data.append({
            "id": expense.id,
            "amount": expense.amount,
            "category": expense.category,
            "date": expense.date,
            "description": expense.description
        })

    return pd.DataFrame(data)


def prepare_data(user_id):
    df = get_expense_data(user_id)

    if df.empty:
        return pd.DataFrame(columns=["month", "amount"])

    df["date"] = pd.to_datetime(
        df["date"], errors="coerce"
    )
    df["amount"] = pd.to_numeric(
        df["amount"], errors="coerce"
    )

    df = df.dropna(subset=["date", "amount"])

    if df.empty:
        return pd.DataFrame(columns=["month", "amount"])

    df["month"] = df["date"].dt.to_period("M")

    monthly_expenses = (
        df.groupby("month")["amount"]
        .sum()
        .reset_index()
        .sort_values("month")
    )

    monthly_expenses["month"] = (
        monthly_expenses["month"].astype(str)
    )

    return monthly_expenses


def predict_next_month(user_id):
    monthly_expenses = prepare_data(user_id)

    if len(monthly_expenses) < 2:
        return {
            "error": (
                "You need at least 2 months of expense "
                "data to predict next month's expenses."
            )
        }

    monthly_expenses["month_number"] = range(
        1, len(monthly_expenses) + 1
    )

    X = monthly_expenses[["month_number"]]
    y = monthly_expenses["amount"]

    model = LinearRegression()
    model.fit(X, y)

    next_month = [[len(monthly_expenses) + 1]]
    prediction = max(0, float(model.predict(next_month)[0]))

    average_expense = float(y.mean())

    if average_expense != 0:
        percentage_difference = (
            (prediction - average_expense) / average_expense
        ) * 100
    else:
        percentage_difference = 0

    if prediction > average_expense:
        trend = "Higher than your average monthly expense"
    elif prediction < average_expense:
        trend = "Lower than your average monthly expense"
    else:
        trend = "Almost equal to your average monthly expense"

    return {
        "predicted_expense": round(prediction, 2),
        "average_monthly_expense": round(average_expense, 2),
        "percentage_difference": round(
            percentage_difference, 2
        ),
        "trend": trend
    }
