from datetime import datetime
from collections import defaultdict
import re

from sqlalchemy import func
from backend.models import Expense


# 1. Total expenses for the logged-in user
def get_total_expense(user_id):
    total = (
        Expense.query.with_entities(func.sum(Expense.amount))
        .filter(Expense.user_id == user_id)
        .scalar()
    )
    return float(total or 0)


# 2. Count expense records
def get_expense_count(user_id):
    return Expense.query.filter_by(user_id=user_id).count()


# 3. Category-wise expenses
def get_category_expenses(user_id):
    return (
        Expense.query.with_entities(
            Expense.category,
            func.sum(Expense.amount).label("total")
        )
        .filter(Expense.user_id == user_id)
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
        .all()
    )


# 4. Recent expenses
def get_recent_expenses(user_id):
    return (
        Expense.query
        .filter_by(user_id=user_id)
        .order_by(Expense.id.desc())
        .limit(5)
        .all()
    )


# 5. Monthly expenses
def get_monthly_expense(user_id, year, month):
    expenses = Expense.query.filter_by(user_id=user_id).all()
    total = 0.0

    for expense in expenses:
        try:
            expense_date = datetime.strptime(
                expense.date[:10], "%Y-%m-%d"
            )
            if expense_date.year == year and expense_date.month == month:
                total += float(expense.amount)
        except (ValueError, TypeError):
            continue

    return total


# 6. Monthly spending breakdown
def get_monthly_breakdown(user_id):
    expenses = Expense.query.filter_by(user_id=user_id).all()
    monthly_totals = defaultdict(float)

    for expense in expenses:
        try:
            expense_date = datetime.strptime(
                expense.date[:10], "%Y-%m-%d"
            )
            month_key = (expense_date.year, expense_date.month)
            monthly_totals[month_key] += float(expense.amount)
        except (ValueError, TypeError):
            continue

    return sorted(monthly_totals.items())


# 7. Find a category mentioned in the question
def find_category(message, user_id):
    categories = (
        Expense.query.with_entities(Expense.category)
        .filter(Expense.user_id == user_id)
        .distinct()
        .all()
    )

    for (category,) in categories:
        if category and re.search(
            rf"\b{re.escape(category.lower())}\b", message
        ):
            return category

    return None


# 8. Chatbot response
def chatbot_response(message, user_id):
    message = (message or "").lower().strip()
    words = message.replace("?", "").replace("!", "").replace(".", "").split()
    word_set = set(words)

    if not message:
        return "Please enter a question about your expenses."

    # Greetings
    if word_set.intersection({"hello", "hi", "hey", "namaste"}):
        if len(words) <= 4:
            return (
                "Hello! 👋 I'm your ExpenseFlow assistant.\n"
                "I can help you understand your spending, categories, "
                "monthly expenses and savings."
            )

    # Help and capabilities
    if (
        "help" in word_set
        or "capabilities" in word_set
        or "what can you do" in message
    ):
        return (
            "Here is what I can help you with:\n"
            "1. Total expenses\n"
            "2. Number of expense records\n"
            "3. Average expense\n"
            "4. Highest individual expense\n"
            "5. Category-specific spending\n"
            "6. Category-wise breakdown\n"
            "7. Recent expenses\n"
            "8. Monthly spending\n"
            "9. Monthly expense comparison\n"
            "10. Highest-spending month\n"
            "11. Money-saving tips\n\n"
            "Examples:\n"
            "- What is my total expense?\n"
            "- What is my average expense?\n"
            "- What is my highest expense?\n"
            "- How much have I spent on Food?\n"
            "- Show my category-wise expenses\n"
            "- Show my recent expenses\n"
            "- How much did I spend in August 2026?\n"
            "- Compare my monthly expenses\n"
            "- Which month had the highest spending?"
        )

    # Goodbye
    if word_set.intersection({"bye", "goodbye"}):
        return "Goodbye! 👋 Keep tracking your expenses regularly."

    # Money-saving tips
    if any(phrase in message for phrase in (
        "saving tips", "save money", "reduce my expenses",
        "reduce expenses", "manage my budget", "budget tips",
        "money-saving", "money saving"
    )):
        return (
            "Here are some practical money-saving tips:\n"
            "1. Set a monthly spending limit.\n"
            "2. Track every expense regularly.\n"
            "3. Reduce unnecessary shopping.\n"
            "4. Plan your food and transport expenses.\n"
            "5. Save a fixed amount every month.\n"
            "6. Review your highest-spending categories.\n"
            "7. Avoid unnecessary impulse purchases.\n\n"
            "Small savings every day can make a big difference!"
        )

    # Expense count
    if (
        ("how many" in message or "count" in word_set
         or "number of" in message)
        and any(word in word_set for word in (
            "expense", "expenses", "record", "records",
            "transaction", "transactions"
        ))
    ):
        count = get_expense_count(user_id)
        return f"You have {count} expense record(s)."

    # Monthly comparison
    if any(phrase in message for phrase in (
        "compare my monthly expenses",
        "compare monthly expenses",
        "monthly expense comparison",
        "compare my spending",
        "compare expenses by month"
    )):
        results = get_monthly_breakdown(user_id)

        if not results:
            return "You don't have any expenses recorded yet."

        lines = ["Your monthly spending comparison:"]

        for (year, month), amount in results:
            month_name = datetime(year, month, 1).strftime("%B %Y")
            lines.append(f"• {month_name}: ₹{amount:.2f}")

        return "\n".join(lines)

    # Highest-spending month
    if any(phrase in message for phrase in (
        "highest spending month",
        "month had the highest",
        "highest expense month",
        "most expensive month",
        "which month did i spend the most",
        "which month has the highest"
    )):
        results = get_monthly_breakdown(user_id)

        if not results:
            return "You don't have any expenses recorded yet."

        (year, month), amount = max(
            results, key=lambda item: item[1]
        )

        month_name = datetime(year, month, 1).strftime("%B %Y")

        return (
            f"Your highest-spending month was {month_name}, "
            f"with ₹{amount:.2f}."
        )

    # Month names and year, e.g. August 2026
    month_names = {
        name.lower(): number
        for number, name in enumerate([
            "", "January", "February", "March", "April",
            "May", "June", "July", "August", "September",
            "October", "November", "December"
        ])
        if name
    }

    for month_name, month_number in month_names.items():
        if month_name in words:
            year = next(
                (
                    int(word) for word in words
                    if word.isdigit() and len(word) == 4
                ),
                None
            )

            if year:
                total = get_monthly_expense(
                    user_id, year, month_number
                )

                return (
                    f"Your spending for {month_name.title()} "
                    f"{year} is ₹{total:.2f}."
                )

    # Current-month spending
    if any(phrase in message for phrase in (
        "this month", "current month", "spent this month",
        "expenses this month", "spending this month"
    )):
        now = datetime.now()
        total = get_monthly_expense(
            user_id, now.year, now.month
        )

        return (
            f"Your spending for {now.strftime('%B %Y')} "
            f"is ₹{total:.2f}."
        )

    # Category-specific spending
    category = find_category(message, user_id)

    if category and any(word in word_set for word in (
        "much", "spent", "spending", "expense", "expenses",
        "total", "amount"
    )):
        total = (
            Expense.query.with_entities(func.sum(Expense.amount))
            .filter(
                Expense.user_id == user_id,
                func.lower(Expense.category) == category.lower()
            )
            .scalar()
        )

        return (
            f"Your total spending on {category} is "
            f"₹{float(total or 0):.2f}."
        )

        # Category-wise breakdown
    if (
        any(word in word_set for word in (
            "category", "categories", "breakdown"
        ))
        or "by category" in message
        or "show my category-wise expenses" in message
    ):
        results = get_category_expenses(user_id)

        if not results:
            return "You don't have any expenses recorded yet."

        lines = ["Your spending by category:"]

        for category_name, amount in results:
            lines.append(
                f"• {category_name}: ₹{float(amount or 0):.2f}"
            )

        return "\n".join(lines)
    
    # Recent expenses
    if any(word in word_set for word in (
        "recent", "latest", "history"
    )) or "last expenses" in message:
        results = get_recent_expenses(user_id)

        if not results:
            return "You don't have any expenses recorded yet."

        lines = ["Your five most recently added expenses:"]

        for expense in results:
            line = (
                f"• {expense.date} | {expense.category} | "
                f"₹{float(expense.amount):.2f}"
            )

            if expense.description:
                line += f" | {expense.description}"

            lines.append(line)

        return "\n".join(lines)

    # Average expense per record
    if "average" in word_set or "average expense" in message:
        count = get_expense_count(user_id)

        if count == 0:
            return "You don't have any expenses recorded yet."

        average = get_total_expense(user_id) / count

        return (
            f"Your average expense per record is "
            f"₹{average:.2f}."
        )

    # Highest individual expense
    if any(word in word_set for word in (
        "highest", "largest", "maximum", "biggest"
    )) and any(word in word_set for word in (
        "expense", "expenses", "spending", "transaction"
    )):
        expense = (
            Expense.query
            .filter_by(user_id=user_id)
            .order_by(Expense.amount.desc())
            .first()
        )

        if expense is None:
            return "You don't have any expenses recorded yet."

        return (
            f"Your highest individual expense is "
            f"₹{expense.amount:.2f} for {expense.category} "
            f"on {expense.date}."
        )

    # Total spending
    if any(phrase in message for phrase in (
        "total expense", "total expenses", "total spending",
        "overall spending", "overall expense",
        "spent altogether", "my spending"
    )) or (
        "total" in word_set and "expense" in word_set
    ):
        total = get_total_expense(user_id)
        return f"Your total recorded spending is ₹{total:.2f}."

    return (
        "Sorry, I couldn't understand that question yet. "
        "Type 'help' to see what I can answer."
    )
