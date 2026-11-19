import asyncio
import uuid
from datetime import datetime, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.runlog import EVENTS_CHANNEL
from app.core.config import get_settings
from app.core.db import get_db
from app.models import AgentEvent, AgentKind, AgentRun, Channel, Clip, ClipMetric, ClipStatus, SourceVideo
from app.schemas import AgentEventOut, AgentRunOut

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/agents/runs", response_model=list[AgentRunOut])
async def runs(kind: AgentKind | None = None, channel_id: uuid.UUID | None = None, limit: int = 50,
               db: AsyncSession = Depends(get_db)):
    q = select(AgentRun).order_by(AgentRun.created_at.desc()).limit(limit)
    if kind:
        q = q.where(AgentRun.kind == kind)
    if channel_id:
        q = q.where(AgentRun.channel_id == channel_id)
    return (await db.scalars(q)).all()


@router.get("/agents/runs/{run_id}/events", response_model=list[AgentEventOut])
async def run_events(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    if not await db.get(AgentRun, run_id):
        raise HTTPException(404)
    return (await db.scalars(select(AgentEvent).where(AgentEvent.run_id == run_id)
                             .order_by(AgentEvent.created_at))).all()


@router.get("/agents/events/recent", response_model=list[AgentEventOut])
async def recent_events(limit: int = 100, db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(AgentEvent).order_by(AgentEvent.created_at.desc()).limit(limit))).all()
    return list(reversed(rows))


@router.get("/agents/events/stream")
async def stream(request: Request):
    """Server-Sent Events: live agent activity for the dashboard feed."""
    async def gen():
        r = aioredis.from_url(get_settings().redis_url)
        pubsub = r.pubsub()
        await pubsub.subscribe(EVENTS_CHANNEL)
        try:
            yield "retry: 3000\n\n"
            while not await request.is_disconnected():
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15)
                if msg:
                    yield f"data: {msg['data'].decode()}\n\n"
                else:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(0)
        finally:
            await pubsub.unsubscribe(EVENTS_CHANNEL)
            await r.aclose()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/analytics/overview")
async def overview(db: AsyncSession = Depends(get_db)):
    by_status = dict((s.value, n) for s, n in (await db.execute(
        select(Clip.status, func.count()).group_by(Clip.status))).all())
    week_ago = datetime.utcnow() - timedelta(days=7)
    latest = (select(ClipMetric.clip_id, func.max(ClipMetric.views).label("views"))
              .group_by(ClipMetric.clip_id).subquery())
    total_views = (await db.scalar(select(func.coalesce(func.sum(latest.c.views), 0)))) or 0
    top = (await db.execute(select(Clip.id, Clip.title, Clip.hook, latest.c.views)
                            .join(latest, latest.c.clip_id == Clip.id)
                            .order_by(latest.c.views.desc()).limit(5))).all()
    runs_7d = await db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.created_at >= week_ago))
    tokens_7d = await db.scalar(select(func.coalesce(func.sum(AgentRun.input_tokens + AgentRun.output_tokens), 0))
                                .where(AgentRun.created_at >= week_ago))
    return {
        "channels": await db.scalar(select(func.count()).select_from(Channel)),
        "sources": await db.scalar(select(func.count()).select_from(SourceVideo)),
        "clips_by_status": by_status,
        "awaiting_review": by_status.get(ClipStatus.RENDERED.value, 0),
        "total_views": int(total_views),
        "top_clips": [{"id": str(i), "title": t or h, "views": v} for i, t, h, v in top],
        "agent_runs_7d": runs_7d,
        "tokens_7d": int(tokens_7d or 0),
    }
