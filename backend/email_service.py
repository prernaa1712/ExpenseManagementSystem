
import os
import logging
import base64

from html import escape
from email.message import EmailMessage

from backend.gmail_auth import get_gmail_service


logger = logging.getLogger(__name__)


def send_budget_alert(
    user,
    month,
    budget_amount,
    total_spent,
    percentage_used,
    alert_type
):
    """
    Send monthly budget notification using Gmail API OAuth 2.0.

    alert_type:
        "80"  -> Budget warning
        "100" -> Budget exceeded
    """

    # This must match the Gmail account authorized through OAuth.
    sender_email = os.getenv(
        "GMAIL_SENDER_EMAIL",
        "expenseflowmanagement@gmail.com"
    ).strip()

    if not all([sender_email, user.email]):
        logger.error("Gmail sender or recipient email is missing.")
        return False

    # Calculate remaining amount
    remaining = budget_amount - total_spent
    exceeded = max(total_spent - budget_amount, 0)

    # Format amounts in Indian Rupees
    budget_text = f"₹{budget_amount:,.2f}"
    spent_text = f"₹{total_spent:,.2f}"
    remaining_text = f"₹{max(remaining, 0):,.2f}"
    exceeded_text = f"₹{exceeded:,.2f}"

    month_text = month

    # Select email content
    if alert_type == "80":
        subject = (
            "⚠️ ExpenseFlow: You've used 80% "
            "of your monthly budget!"
        )

        heading = "Your monthly budget is running low!"
        message = (
            "You have used 80% or more of your monthly budget. "
            "Review your spending and plan your remaining expenses."
        )
        status = "Budget Warning"

    elif alert_type == "100":
        subject = (
            "🚨 ExpenseFlow: Your monthly budget "
            "has been exceeded!"
        )

        heading = "Your monthly budget has been reached or exceeded!"
        message = (
            "Your spending has reached or exceeded your allocated "
            "monthly budget. Review your expenses and reduce "
            "non-essential spending where possible."
        )
        status = "Budget Exceeded"

    else:
        logger.error("Invalid budget alert type: %s", alert_type)
        return False

    # Escape user-provided values for HTML
    safe_name = escape(str(user.name))
    safe_month = escape(str(month_text))
    safe_heading = escape(heading)
    safe_message = escape(message)
    safe_status = escape(status)

    # Create email
    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = sender_email
    email["To"] = user.email

    # Plain-text version
    email.set_content(
        f"""
Hello {user.name},

{heading}

{message}

MONTHLY BUDGET SUMMARY

Month: {month_text}
Monthly Budget: {budget_text}
Total Spent: {spent_text}
Remaining Budget: {remaining_text}
Amount Exceeded: {exceeded_text}
Budget Utilization: {percentage_used:.2f}%

Keep tracking your expenses with ExpenseFlow!

Regards,
ExpenseFlow Team
Your Personal Expense Management Assistant
"""
    )

    # HTML email version
    html_content = f"""
    <html>
    <body style="
        margin: 0;
        padding: 25px;
        background-color: #f4f5fb;
        font-family: Arial, sans-serif;
        color: #333333;
    ">
        <div style="
            max-width: 600px;
            margin: auto;
            background: white;
            border-radius: 12px;
            overflow: hidden;
        ">
            <div style="
                background: #635bff;
                color: white;
                padding: 24px;
                text-align: center;
            ">
                <h1 style="margin: 0;">ExpenseFlow</h1>
                <p style="margin-bottom: 0;">
                    Monthly Budget Notification
                </p>
            </div>

            <div style="padding: 28px;">
                <h2>{safe_heading}</h2>

                <p>Hello {safe_name},</p>

                <p>{safe_message}</p>

                <h3>Monthly Budget Summary</h3>

                <table style="
                    width: 100%;
                    border-collapse: collapse;
                ">
                    <tr>
                        <td style="padding: 10px;">Month</td>
                        <td style="padding: 10px;">
                            <b>{safe_month}</b>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 10px;">Monthly Budget</td>
                        <td style="padding: 10px;">
                            <b>{budget_text}</b>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 10px;">Total Spent</td>
                        <td style="padding: 10px;">
                            <b>{spent_text}</b>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 10px;">Remaining Budget</td>
                        <td style="padding: 10px;">
                            <b>{remaining_text}</b>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 10px;">Amount Exceeded</td>
                        <td style="padding: 10px;">
                            <b>{exceeded_text}</b>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 10px;">
                            Budget Utilization
                        </td>
                        <td style="padding: 10px;">
                            <b>{percentage_used:.2f}%</b>
                        </td>
                    </tr>
                </table>

                <div style="
                    margin-top: 24px;
                    padding: 15px;
                    background: #f4f5fb;
                    border-radius: 8px;
                ">
                    <b>{safe_status}</b>
                    <p style="margin-bottom: 0;">
                        Keep tracking. Stay financially smart!
                    </p>
                </div>

                <p style="margin-top: 28px;">
                    Regards,<br>
                    <b>ExpenseFlow Team</b><br>
                    Your Personal Expense Management Assistant
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    email.add_alternative(html_content, subtype="html")

    # Send email using Gmail API and OAuth 2.0
    try:
        service = get_gmail_service()

        encoded_message = base64.urlsafe_b64encode(
            email.as_bytes()
        ).decode("utf-8")

        result = service.users().messages().send(
            userId="me",
            body={"raw": encoded_message}
        ).execute()

        logger.info(
            "Budget alert email sent to %s for alert type %s. Message ID: %s",
            user.email,
            alert_type,
            result.get("id")
        )

        return True

    except Exception:
        logger.exception("Unable to send budget alert email through Gmail API.")
        return False
