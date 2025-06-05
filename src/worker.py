from celery import Celery  # type: ignore
from celery.schedules import crontab  # type: ignore

# Initialize Celery
celery = Celery(
    "tasks",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0",
)

# Optional configuration
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Import tasks module to ensure tasks are registered
import src.tasks  # noqa

# Basic periodic task
celery.conf.beat_schedule = {
    "cleanup-old-files": {
        "task": "src.tasks.cleanup_old_files",
        "schedule": crontab(hour="3", minute="0"),  # Every day at 3:00 AM
    },
}

if __name__ == "__main__":
    celery.start()
