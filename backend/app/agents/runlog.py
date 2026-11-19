"""AgentRun bookkeeping + live event fan-out (Postgres for history, Redis pub/sub for the UI feed)."""
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import redis

from app.core.config import get_settings
from app.core.db import worker_session
from app.models import AgentEvent, AgentKind, AgentRun, RunStatus

EVENTS_CHANNEL = "omniclip:agent-events"
_redis = redis.Redis.from_url(get_settings().redis_url)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RunLogger:
    def __init__(self, run_id: uuid.UUID, kind: AgentKind) -> None:
        self.run_id, self.kind = run_id, kind

    def log(self, message: str, level: str = "info", data: dict | None = None) -> None:
        with worker_session() as db:
            db.add(AgentEvent(run_id=self.run_id, level=level, message=message, data=data))
        _redis.publish(EVENTS_CHANNEL, json.dumps({
            "run_id": str(self.run_id), "kind": self.kind.value, "level": level,
            "message": message, "data": data, "at": _now().isoformat() + "Z",
        }, default=str))


@contextmanager
def agent_run(kind: AgentKind, *, channel_id=None, source_video_id=None, input: dict | None = None):
    with worker_session() as db:
        run = AgentRun(kind=kind, status=RunStatus.RUNNING, channel_id=channel_id,
                       source_video_id=source_video_id, input=input, started_at=_now())
        db.add(run)
        db.flush()
        run_id = run.id
    logger = RunLogger(run_id, kind)
    logger.log(f"{kind.value.replace('_', ' ').title()} started")
    result: dict = {}
    try:
        yield logger, result
    except Exception as exc:
        with worker_session() as db:
            r = db.get(AgentRun, run_id)
            r.status, r.error, r.finished_at = RunStatus.FAILED, str(exc)[:2000], _now()
        logger.log(f"Failed: {exc}", level="error")
        raise
    with worker_session() as db:
        r = db.get(AgentRun, run_id)
        r.status, r.finished_at = RunStatus.SUCCEEDED, _now()
        r.output = result.get("output")
        r.input_tokens = result.get("input_tokens", 0)
        r.output_tokens = result.get("output_tokens", 0)
    logger.log("Completed", level="success")
