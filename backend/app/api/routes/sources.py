import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import clip_out
from app.core import storage
from app.core.db import get_db
from app.models import Clip, SourceVideo, VideoStatus
from app.schemas import ClipOut, SourceCreate, SourceOut, UploadUrlRequest
from app.workers import dispatch

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.post("/upload-url")
async def upload_url(body: UploadUrlRequest):
    """Step 1 of a file upload: browser PUTs the file straight to object storage."""
    key = f"uploads/{uuid.uuid4()}/{body.filename.replace('/', '_')}"
    return {"storage_key": key, "upload_url": storage.presigned_put(key, body.content_type)}


@router.post("", response_model=SourceOut, status_code=201)
async def create_source(body: SourceCreate, db: AsyncSession = Depends(get_db)):
    """Step 2: register a YouTube/URL link or an uploaded storage_key and start the pipeline."""
    sv = SourceVideo(source_url=body.url, storage_key=body.storage_key, channel_id=body.channel_id,
                     title=body.title or body.url or body.storage_key.rsplit("/", 1)[-1],
                     target_clips=body.target_clips, status=VideoStatus.QUEUED, progress=0)
    db.add(sv)
    await db.commit()
    await db.refresh(sv)
    dispatch.process_source(str(sv.id))
    return sv


@router.get("", response_model=list[SourceOut])
async def list_sources(channel_id: uuid.UUID | None = None, limit: int = 50, db: AsyncSession = Depends(get_db)):
    q = select(SourceVideo).order_by(SourceVideo.created_at.desc()).limit(limit)
    if channel_id:
        q = q.where(SourceVideo.channel_id == channel_id)
    return (await db.scalars(q)).all()


@router.get("/{source_id}", response_model=SourceOut)
async def get_source(source_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    sv = await db.get(SourceVideo, source_id)
    if not sv:
        raise HTTPException(404)
    return sv


@router.get("/{source_id}/clips", response_model=list[ClipOut])
async def source_clips(source_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    clips = (await db.scalars(select(Clip).where(Clip.source_video_id == source_id).order_by(Clip.rank))).all()
    return [clip_out(c) for c in clips]


@router.post("/{source_id}/rescore", status_code=202)
async def rescore(source_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    sv = await db.get(SourceVideo, source_id)
    if not sv or not sv.transcript_key:
        raise HTTPException(409, "source has no transcript yet")
    dispatch.rescore_source(str(source_id))
    return {"queued": True}


@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    sv = await db.get(SourceVideo, source_id)
    if sv:
        await db.delete(sv)
        await db.commit()
