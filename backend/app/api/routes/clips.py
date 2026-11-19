import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import clip_out
from app.core import storage
from app.core.db import get_db
from app.models import Clip, ClipStatus, SourceVideo
from app.schemas import BulkReview, ClipDetail, ClipOut, ClipUpdate, ReviewAction
from app.workers import dispatch

router = APIRouter(prefix="/api/clips", tags=["clips"])

RERENDER_FIELDS = {"start_sec", "end_sec", "hook", "layout", "caption_preset", "crop_track"}
EDITABLE = {ClipStatus.CANDIDATE, ClipStatus.RENDERED, ClipStatus.APPROVED, ClipStatus.REJECTED, ClipStatus.FAILED}


@router.get("", response_model=list[ClipOut])
async def list_clips(status: ClipStatus | None = None, channel_id: uuid.UUID | None = None,
                     min_score: float = 0, limit: int = 200, db: AsyncSession = Depends(get_db)):
    q = select(Clip).where(Clip.virality_score >= min_score).order_by(Clip.virality_score.desc()).limit(limit)
    if status:
        q = q.where(Clip.status == status)
    if channel_id:
        q = q.where(Clip.channel_id == channel_id)
    return [clip_out(c) for c in (await db.scalars(q)).all()]


@router.get("/{clip_id}", response_model=ClipDetail)
async def get_clip(clip_id: uuid.UUID, pad: float = 20.0, db: AsyncSession = Depends(get_db)):
    c = await db.get(Clip, clip_id)
    if not c:
        raise HTTPException(404)
    sv = await db.get(SourceVideo, c.source_video_id)
    lo, hi = max(c.start_sec - pad, 0), c.end_sec + pad
    words = []
    if sv.transcript_key:
        words = [w for w in json.loads(storage.get_bytes(sv.transcript_key))["words"] if lo <= w["s"] <= hi]
    return clip_out(c, ClipDetail, words=words, window_start=lo,
                    source_url=storage.presigned_get(sv.storage_key) if sv.storage_key else None)


@router.patch("/{clip_id}", response_model=ClipOut)
async def update_clip(clip_id: uuid.UUID, body: ClipUpdate, db: AsyncSession = Depends(get_db)):
    c = await db.get(Clip, clip_id)
    if not c:
        raise HTTPException(404)
    if c.status not in EDITABLE:
        raise HTTPException(409, f"clip is {c.status.value}; unschedule it before editing")
    changes = body.model_dump(exclude_unset=True)
    start, end = changes.get("start_sec", c.start_sec), changes.get("end_sec", c.end_sec)
    if end - start < 3 or end - start > 180:
        raise HTTPException(422, "clip must be 3-180 seconds")
    if {"start_sec", "end_sec"} & changes.keys() and "crop_track" not in changes:
        changes["crop_track"] = None  # timing changed → re-run speaker tracking
    for k, v in changes.items():
        setattr(c, k, v)
    needs_render = bool(RERENDER_FIELDS & changes.keys())
    if needs_render:
        c.status = ClipStatus.CANDIDATE
    await db.commit()
    if needs_render:
        dispatch.render_clip(str(c.id))
    return clip_out(c)


async def _review(db: AsyncSession, c: Clip, body: ReviewAction) -> None:
    if body.action == "approve":
        if c.status not in (ClipStatus.RENDERED, ClipStatus.REJECTED):
            raise HTTPException(409, f"cannot approve a {c.status.value} clip")
        c.status = ClipStatus.APPROVED
    else:
        c.status = ClipStatus.REJECTED
    c.review_note = body.note


@router.post("/{clip_id}/review", response_model=ClipOut)
async def review_clip(clip_id: uuid.UUID, body: ReviewAction, schedule: bool = True,
                      db: AsyncSession = Depends(get_db)):
    c = await db.get(Clip, clip_id)
    if not c:
        raise HTTPException(404)
    await _review(db, c, body)
    await db.commit()
    if schedule and body.action == "approve" and c.channel_id:
        dispatch.schedule_clips(str(c.channel_id), [str(c.id)])
    return clip_out(c)


@router.post("/bulk-review")
async def bulk_review(body: BulkReview, db: AsyncSession = Depends(get_db)):
    clips = (await db.scalars(select(Clip).where(Clip.id.in_(body.clip_ids)))).all()
    by_channel: dict[str, list[str]] = {}
    skipped = []
    for c in clips:
        try:
            await _review(db, c, body)
        except HTTPException:
            skipped.append(str(c.id))
            continue
        if body.action == "approve" and c.channel_id:
            by_channel.setdefault(str(c.channel_id), []).append(str(c.id))
    await db.commit()
    if body.schedule:
        for ch, ids in by_channel.items():
            dispatch.schedule_clips(ch, ids)
    return {"updated": len(clips) - len(skipped), "skipped": skipped}
