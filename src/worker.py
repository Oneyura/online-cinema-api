from celery import Celery  # type: ignore

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

# Use the beat schedule from tasks.py
celery.conf.beat_schedule = src.tasks.celery.conf.beat_schedule

if __name__ == "__main__":
    celery.start()
