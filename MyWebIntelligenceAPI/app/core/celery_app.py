"""
Configuration de l'application Celery
"""

from celery import Celery
from ..config import settings

celery_app = Celery("tasks")

celery_app.conf.broker_url = settings.CELERY_BROKER_URL
celery_app.conf.result_backend = settings.CELERY_RESULT_BACKEND

celery_app.autodiscover_tasks(["app.tasks"])

celery_app.conf.update(
    task_track_started=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    result_expires=3600,  # 1 hour
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)

autoscale_setting = settings.CELERY_AUTOSCALE
if autoscale_setting:
    try:
        parts = [int(value.strip()) for value in autoscale_setting.split(",", 1)]
        if len(parts) == 2 and all(part > 0 for part in parts):
            min_workers = min(parts)
            max_workers = max(parts)
            celery_app.conf.worker_autoscale = (max_workers, min_workers)
    except (ValueError, TypeError):
        pass
