import os
from celery import Celery

app = Celery("supportflow", broker=os.environ.get("REDIS_URL", "redis://redis:6379/0"))
app.conf.update(
    task_serializer="json", accept_content=["json"], result_serializer="json",
    task_acks_late=True, task_reject_on_worker_lost=True, worker_prefetch_multiplier=1,
    beat_schedule={"drain-durable-jobs": {"task": "supportflow.drain", "schedule": 2.0}},
    broker_connection_retry_on_startup=True, task_ignore_result=True)


@app.task(name="supportflow.drain")
def drain():
    from .config import Settings
    from .db import Database
    from .worker import run_one
    settings = Settings.from_env()
    database = Database(settings.database_url)
    try:
        for _ in range(8):
            if not run_one(database, settings):
                break
    finally:
        database.close()
