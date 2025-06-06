from datetime import datetime, timezone

from celery import Celery  # type: ignore

from src.database.models.accounts import ActivationTokenModel
from src.database.session import AsyncSessionLocal

celery = Celery(
    "tasks",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0",
)

@celery.task
async def delete_expired_activation_tokens() -> str:
    """
    Periodic task to delete expired activation tokens.
    """
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            ActivationTokenModel.__table__.delete().where(ActivationTokenModel.expires_at < now)
        )
        await session.commit()
        deleted_count = result.rowcount or 0
    return f"Deleted {deleted_count} expired activation tokens"


@celery.task
def check_expired_sessions() -> str:
    """
    Checks and deletes expired user sessions.
    """
    # TODO: Implement session cleanup logic
    return "Sessions checked and cleaned up"


@celery.task
def send_email_notification(user_id: int, subject: str, message: str) -> str:
    """
    Отправка email уведомления пользователю.
    """
    # Здесь нужно реализовать вызов EmailSender (через DI или импорт)
    # Пример заглушки:
    print(f"Sending email to user {user_id}: {subject} - {message}")
    # TODO: Реализовать реальную отправку через EmailSender
    return f"Email sent to user {user_id}"


@celery.task
def cleanup_old_files() -> str:
    """
    Clean up old files from storage.
    """
    # TODO: Implement actual file cleanup logic
    return "Old files cleaned up"


@celery.task
def process_video(video_id: int) -> str:
    """
    Process uploaded video.
    """
    # TODO: Implement actual video processing logic
    return f"Video {video_id} processed"


@celery.task
def generate_user_report(user_id: int, report_type: str) -> str:
    """
    Generate a report on user activity.
    """
    # TODO: Implement report generation logic
    return f"Report generated for user {user_id}"


@celery.task
def generate_thumbnails(video_id: int) -> str:
    """
    Generate thumbnails for video.
    """
    # TODO: Implement actual thumbnail generation logic
    return f"Thumbnails generated for video {video_id}"


@celery.task
def update_video_status(video_id: int, status: str) -> str:
    """
    Update video processing status.
    """
    # TODO: Implement actual status update logic
    return f"Status updated for video {video_id}"
