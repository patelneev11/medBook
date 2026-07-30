from celery import Celery

from mednotebook_backend.config import settings

celery_app = Celery(
    "mednotebook",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,
    task_time_limit=360,
)

celery_app.conf.imports = ("tasks.document_tasks",)