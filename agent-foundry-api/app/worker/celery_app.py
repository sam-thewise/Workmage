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

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "process-mint-payments-avalanche": {
        "task": "app.worker.tasks.process_mint_payments_for_network",
        "schedule": 60.0,  # every 60 seconds
        "args": ["avalanche"],
    },
    "process-mint-payments-fuji": {
        "task": "app.worker.tasks.process_mint_payments_for_network",
        "schedule": 60.0,
        "args": ["fuji"],
    },
    "run-x-authority-scheduled": {
        "task": "app.worker.tasks.run_x_authority_scheduled",
        "schedule": 86400.0,  # daily
    },
}

# Ensure tasks are registered when app loads (required for run_chain_task, run_agent_task)
from app.worker import tasks  # noqa: F401, E402
