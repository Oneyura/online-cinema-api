import asyncio
import os
from datetime import datetime, timezone

from celery import Celery  # type: ignore
from celery.schedules import crontab

from src.config.dependencies import get_settings
from src.database.models.accounts import ActivationTokenModel, UserModel
from src.database.session import AsyncSessionLocal
from src.notifications.emails import EmailSender

celery = Celery(
    "tasks",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0",
)

# Celery beat schedule configuration
celery.conf.beat_schedule = {
    "delete-expired-activation-tokens": {
        "task": "src.tasks.delete_expired_activation_tokens",
        "schedule": crontab(hour=2, minute=0),  # Щоденно о 2:00 ночі
    },
    "delete-expired-password-reset-tokens": {
        "task": "src.tasks.delete_expired_password_reset_tokens",
        "schedule": crontab(hour=2, minute=30),  # Щоденно о 2:30 ночі
    },
    "cleanup-old-cart-items": {
        "task": "src.tasks.cleanup_old_cart_items",
        "schedule": crontab(hour=3, minute=0),  # Щоденно о 3:00 ночі
    },
}

celery.conf.timezone = "UTC"


def run_async(coro):
    """Helper function to run async code in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def get_email_sender():
    """
    Get EmailSender instance with environment-specific configuration.
    This will automatically work with SendGrid on production and MailHog on development.
    """
    settings = get_settings()

    return EmailSender(
        hostname=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        email=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=settings.EMAIL_USE_TLS,
        template_dir="src/templates/email",
        activation_email_template_name="activation.html",
        activation_complete_email_template_name="activation_complete.html",
        password_email_template_name="password_reset.html",
        password_complete_email_template_name="password_reset_complete.html",
    )


@celery.task
def delete_expired_activation_tokens() -> str:
    """
    Periodic task to delete expired activation tokens.
    """

    async def _delete_expired_tokens():
        async with AsyncSessionLocal() as session:
            now = datetime.now(timezone.utc)

            # Use SQLAlchemy delete statement
            from sqlalchemy import delete

            stmt = delete(ActivationTokenModel).where(ActivationTokenModel.expires_at < now)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0

    deleted_count = run_async(_delete_expired_tokens())
    return f"Deleted {deleted_count} expired activation tokens"


@celery.task
def delete_expired_password_reset_tokens() -> str:
    """
    Periodic task to delete expired password reset tokens.
    """

    async def _delete_expired_tokens():
        async with AsyncSessionLocal() as session:
            now = datetime.now(timezone.utc)

            # Import here to avoid circular imports
            from sqlalchemy import delete

            from src.database.models.accounts import PasswordResetTokenModel

            stmt = delete(PasswordResetTokenModel).where(PasswordResetTokenModel.expires_at < now)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0

    deleted_count = run_async(_delete_expired_tokens())
    return f"Deleted {deleted_count} expired password reset tokens"


@celery.task
def cleanup_old_cart_items() -> str:
    """
    Clean up cart items that are older than 30 days for inactive users.
    This helps keep the database clean.
    """

    async def _cleanup_old_cart_items():
        async with AsyncSessionLocal() as session:
            from datetime import timedelta

            from sqlalchemy import delete

            from src.database.models.cart import CartItemModel

            # Delete cart items older than 30 days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)

            stmt = delete(CartItemModel).where(CartItemModel.added_at < cutoff_date)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0

    deleted_count = run_async(_cleanup_old_cart_items())
    return f"Cleaned up {deleted_count} old cart items"


@celery.task
def send_activation_email(user_id: int, activation_token: str) -> str:
    """
    Send activation email to user using EmailSender.
    Works with both MailHog (development) and SendGrid (production).
    """

    async def _send_activation_email():
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select

            # Get user data
            stmt = select(UserModel).where(UserModel.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return f"User {user_id} not found"

            # Get environment-specific EmailSender
            email_sender = get_email_sender()

            # Send activation email
            activation_link = f"https://fast-furious.work.gd/api/accounts/activate?token={activation_token}"
            await email_sender.send_activation_email(user.email, activation_link)

            # Log for debugging
            environment = os.getenv("ENVIRONMENT", "developing")
            print(f"Activation email sent to {user.email} via {environment} environment")

            return f"Activation email sent to {user.email}"

    result = run_async(_send_activation_email())
    return result


@celery.task
def send_activation_complete_email(user_id: int) -> str:
    """
    Send activation completion email to user.
    Works with both MailHog (development) and SendGrid (production).
    """

    async def _send_activation_complete_email():
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select

            # Get user data
            stmt = select(UserModel).where(UserModel.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return f"User {user_id} not found"

            # Get environment-specific EmailSender
            email_sender = get_email_sender()

            # Send activation complete email
            login_link = "https://fast-furious.work.gd/api/accounts/login/"
            await email_sender.send_activation_complete_email(user.email, login_link)

            # Log for debugging
            environment = os.getenv("ENVIRONMENT", "developing")
            print(f"Activation complete email sent to {user.email} via {environment} environment")

            return f"Activation complete email sent to {user.email}"

    result = run_async(_send_activation_complete_email())
    return result


@celery.task
def send_password_reset_email(user_id: int, reset_token: str) -> str:
    """
    Send password reset email to user.
    Works with both MailHog (development) and SendGrid (production).
    """

    async def _send_password_reset_email():
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select

            # Get user data
            stmt = select(UserModel).where(UserModel.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return f"User {user_id} not found"

            # Get environment-specific EmailSender
            email_sender = get_email_sender()

            # Send password reset email
            reset_link = f"https://fast-furious.work.gd/api/accounts/password-reset/confirm?token={reset_token}"
            await email_sender.send_password_reset_email(user.email, reset_link)

            # Log for debugging
            environment = os.getenv("ENVIRONMENT", "developing")
            print(f"Password reset email sent to {user.email} via {environment} environment")

            return f"Password reset email sent to {user.email}"

    result = run_async(_send_password_reset_email())
    return result
