
import os
import logging
import base64
from html import escape
from email.message import EmailMessage

from backend.gmail_auth import get_gmail_service

logger = logging.getLogger(__name__)


def send_email(email):
    """Send an email using the existing Gmail API OAuth connection."""
    try:
        service = get_gmail_service()

        encoded_message = base64.urlsafe_b64encode(
            email.as_bytes()
        ).decode("utf-8")

        result = service.users().messages().send(
            userId="me",
            body={"raw": encoded_message}
        ).execute()

        logger.info("Email sent successfully. Message ID: %s", result.get("id"))
        return True

    except Exception:
        logger.exception("Unable to send email.")
        return False


def send_budget_alert(
    user,
    month,
    budget_amount,
    total_spent,
    percentage_used,
    alert_type
):
    """Send a budget alert email to the user."""

    sender_email = os.getenv(
        "GMAIL_SENDER_EMAIL",
        "expenseflowmanagement@gmail.com"
    ).strip()

    if not sender_email or not user.email:
        logger.error("Gmail sender or recipient email is missing.")
        return False

    subject = f"ExpenseFlow - {alert_type.replace('_', ' ').title()}"

    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = sender_email
    email["To"] = user.email

    email.set_content(
        f"""Hello {user.name},

This is a budget alert for {month}.

Budget amount: ₹{budget_amount:,.2f}
Total spent: ₹{total_spent:,.2f}
Budget used: {percentage_used:.2f}%

Please review your expenses and manage your spending.

Regards,
ExpenseFlow Team
"""
    )

    safe_name = escape(str(user.name))
    safe_month = escape(str(month))
    safe_alert = escape(str(alert_type).replace("_", " ").title())

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background: #f4f5fb; padding: 25px;">
        <div style="max-width: 500px; margin: auto; background: white;
                    padding: 30px; border-radius: 12px;">
            <h2 style="color: #635bff;">ExpenseFlow</h2>
            <p>Hello {safe_name},</p>
            <h3>{safe_alert}</h3>
            <p>Budget summary for {safe_month}:</p>
            <p>Budget amount: ₹{budget_amount:,.2f}</p>
            <p>Total spent: ₹{total_spent:,.2f}</p>
            <h2 style="color: #635bff;">
                {percentage_used:.2f}% used
            </h2>
            <p>Please review your expenses and manage your spending.</p>
            <p>Regards,<br><b>ExpenseFlow Team</b></p>
        </div>
    </body>
    </html>
    """

    email.add_alternative(html_content, subtype="html")

    return send_email(email)


def send_password_reset_otp(user, otp):
    """Send a password-reset OTP using Gmail API OAuth."""

    sender_email = os.getenv(
        "GMAIL_SENDER_EMAIL",
        "expenseflowmanagement@gmail.com"
    ).strip()

    if not sender_email or not user.email:
        logger.error("Gmail sender or recipient email is missing.")
        return False

    email = EmailMessage()
    email["Subject"] = "ExpenseFlow - Password Reset Verification"
    email["From"] = sender_email
    email["To"] = user.email

    email.set_content(
        f"""Hello {user.name},

We received a request to reset your ExpenseFlow account password.

Your verification code is: {otp}

This code is valid for 10 minutes.

If you did not request a password reset, please ignore this email.

Regards,
ExpenseFlow Team
"""
    )

    safe_name = escape(str(user.name))
    safe_otp = escape(str(otp))

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background: #f4f5fb; padding: 25px;">
        <div style="max-width: 500px; margin: auto; background: white;
                    padding: 30px; border-radius: 12px;">
            <h2 style="color: #635bff;">ExpenseFlow</h2>
            <p>Hello {safe_name},</p>
            <p>Use the following verification code to reset your password:</p>
            <h1 style="letter-spacing: 8px; color: #635bff;">{safe_otp}</h1>
            <p>This code is valid for <b>10 minutes</b>.</p>
            <p>If you did not request this, please ignore this email.</p>
            <p>Regards,<br><b>ExpenseFlow Team</b></p>
        </div>
    </body>
    </html>
    """

    email.add_alternative(html_content, subtype="html")

    return send_email(email)
