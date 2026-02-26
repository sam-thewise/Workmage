"""Celery application."""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "agent_foundry",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.worker.tasks"],
)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.timezone = "UTC"
celery_app.conf.enable_utc = True

# Ensure tasks are registered when app loads (required for run_chain_task, run_agent_task)
from app.worker import tasks  # noqa: F401, E402
