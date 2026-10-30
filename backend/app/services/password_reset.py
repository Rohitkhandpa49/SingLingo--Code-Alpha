import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.config import Settings


class PasswordResetDeliveryError(RuntimeError):
    pass


def send_password_reset_email(email: str, token: str, settings: Settings) -> None:
    if settings.smtp_host is None or settings.smtp_from_email is None:
        raise PasswordResetDeliveryError("Password reset email is not configured")
    if settings.smtp_username is not None and not settings.smtp_starttls:
        raise PasswordResetDeliveryError("SMTP credentials require STARTTLS")

    reset_url = f"{str(settings.frontend_origin).rstrip('/')}/reset-password?{urlencode({'token': token})}"
    message = EmailMessage()
    message["Subject"] = "Reset your SignLingo password"
    message["From"] = str(settings.smtp_from_email)
    message["To"] = email
    message.set_content(
        "A password reset was requested for your SignLingo account.\n\n"
        f"Use this one-time link within {settings.password_reset_token_expire_minutes} "
        f"minutes:\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        ) as server:
            server.ehlo()
            if settings.smtp_starttls:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            if settings.smtp_username is not None and settings.smtp_password is not None:
                server.login(
                    settings.smtp_username,
                    settings.smtp_password.get_secret_value(),
                )
            refused_recipients = server.send_message(message)
            if refused_recipients:
                raise smtplib.SMTPRecipientsRefused(refused_recipients)
    except (OSError, smtplib.SMTPException) as error:
        raise PasswordResetDeliveryError("Password reset email delivery failed") from error
