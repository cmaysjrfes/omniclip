import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import encrypt
from app.integrations import youtube
from app.models import Channel, CompetitorReport, PublishJob
from app.schemas import ChannelCreate, ChannelOut, ChannelUpdate, PublishJobOut
from app.taxonomy import TAXONOMY
from app.workers import dispatch

router = APIRouter(prefix="/api/channels", tags=["channels"])
# Google redirects the browser here without our API key header; `state` binds it to a channel.
oauth_router = APIRouter(prefix="/api/channels", tags=["oauth"])


@router.get("/taxonomy")
async def taxonomy():
    """Multi-tier category tree for the niche selector."""
    return TAXONOMY


@router.post("", response_model=ChannelOut, status_code=201)
async def create_channel(body: ChannelCreate, launch: bool = True, db: AsyncSession = Depends(get_db)):
    ch = Channel(**body.model_dump())
    db.add(ch)
    await db.commit()
    await db.refresh(ch)
    if launch:  # competitor intel → brand → schedule, streamed to the agent feed
        dispatch.channel_launch(str(ch.id), auto_apply=False)
    return ch


@router.get("", response_model=list[ChannelOut])
async def list_channels(db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(Channel).order_by(Channel.created_at.desc()))).all()


@router.get("/{channel_id}", response_model=ChannelOut)
async def get_channel(channel_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ch = await db.get(Channel, channel_id)
    if not ch:
        raise HTTPException(404)
    return ch


@router.patch("/{channel_id}", response_model=ChannelOut)
async def update_channel(channel_id: uuid.UUID, body: ChannelUpdate, db: AsyncSession = Depends(get_db)):
    ch = await db.get(Channel, channel_id)
    if not ch:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(ch, k, v)
    await db.commit()
    await db.refresh(ch)
    return ch


@router.post("/{channel_id}/launch", status_code=202)
async def relaunch(channel_id: uuid.UUID, apply_to_youtube: bool = False):
    dispatch.channel_launch(str(channel_id), auto_apply=apply_to_youtube)
    return {"queued": True}


@router.post("/{channel_id}/reoptimize-schedule", status_code=202)
async def reoptimize(channel_id: uuid.UUID):
    dispatch.reoptimize_schedule(str(channel_id))
    return {"queued": True}


@router.get("/{channel_id}/competitors")
async def competitor_report(channel_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    r = (await db.scalars(select(CompetitorReport).where(CompetitorReport.channel_id == channel_id)
                          .order_by(CompetitorReport.created_at.desc()).limit(1))).first()
    if not r:
        raise HTTPException(404, "no competitor report yet")
    return {"created_at": r.created_at, **{k: v for k, v in r.report.items() if k != "uploads"}}


@router.get("/{channel_id}/calendar", response_model=list[PublishJobOut])
async def calendar(channel_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    jobs = (await db.scalars(select(PublishJob).where(PublishJob.channel_id == channel_id)
                             .order_by(PublishJob.scheduled_for))).all()
    return [PublishJobOut.model_validate(j).model_copy(update={"status": j.status.value}) for j in jobs]


# ----- YouTube OAuth (connect an existing channel / Brand Account)
@router.get("/{channel_id}/oauth/start")
async def oauth_start(channel_id: uuid.UUID):
    return {"url": youtube.authorization_url(state=str(channel_id))}


@oauth_router.get("/oauth/callback", include_in_schema=False)
async def oauth_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    refresh_token, yt_id, title = youtube.exchange_code(code, state)
    ch = await db.get(Channel, uuid.UUID(state))
    if not ch:
        raise HTTPException(404)
    ch.youtube_channel_id, ch.oauth_token_enc = yt_id, encrypt(refresh_token)
    if ch.name == "Untitled channel":
        ch.name = title
    await db.commit()
    return RedirectResponse(f"http://localhost:3000/channels/{state}?connected=1")
