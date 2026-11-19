from celery import Celery

from app.core.config import get_settings

celery = Celery("omniclip", broker=get_settings().redis_url, backend=get_settings().redis_url,
                include=["app.workers.tasks"])
celery.conf.update(
    task_acks_late=True,               # a crashed worker's task is redelivered, not lost
    worker_prefetch_multiplier=1,      # renders are long; don't hoard tasks on one worker
    task_default_queue="agents",
    task_routes={
        "media.*": {"queue": "media"},
        "agents.*": {"queue": "agents"},
        "publish.*": {"queue": "publish"},
    },
    beat_schedule={
        "dispatch-due-publishes": {"task": "publish.dispatch_due", "schedule": 60.0},
        "collect-metrics": {"task": "publish.collect_metrics", "schedule": 3600.0},
        "reoptimize-schedules": {"task": "agents.reoptimize_all", "schedule": 86400.0},
    },
    timezone="UTC",
)
app = celery
