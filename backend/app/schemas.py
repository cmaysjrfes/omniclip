import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- channels
class ChannelCreate(BaseModel):
    name: str = "Untitled channel"
    category: str
    sub_category: str | None = None
    niche_description: str | None = None
    tone: str | None = None
    target_audience: str | None = None
    timezone: str = "UTC"
    posts_per_day: int = Field(3, ge=1, le=12)
    autopilot: bool = False
    require_approval: bool = True


class ChannelUpdate(BaseModel):
    name: str | None = None
    handle: str | None = None
    description: str | None = None
    keywords: list[str] | None = None
    tone: str | None = None
    timezone: str | None = None
    posts_per_day: int | None = Field(None, ge=1, le=12)
    autopilot: bool | None = None
    require_approval: bool | None = None


class ChannelOut(ORM):
    id: uuid.UUID
    name: str
    category: str
    sub_category: str | None
    niche_description: str | None
    tone: str | None
    target_audience: str | None
    handle: str | None
    description: str | None
    keywords: list[str]
    brand_kit: dict | None
    youtube_channel_id: str | None
    autopilot: bool
    require_approval: bool
    posts_per_day: int
    posting_slots: list | None
    timezone: str
    created_at: datetime


# ---------- sources
class SourceCreate(BaseModel):
    url: str | None = None
    storage_key: str | None = None
    channel_id: uuid.UUID | None = None
    title: str | None = None
    target_clips: int = Field(24, ge=1, le=60)

    @model_validator(mode="after")
    def one_source(self):
        if bool(self.url) == bool(self.storage_key):
            raise ValueError("provide exactly one of url or storage_key")
        return self


class UploadUrlRequest(BaseModel):
    filename: str
    content_type: str = "video/mp4"


class SourceOut(ORM):
    id: uuid.UUID
    channel_id: uuid.UUID | None
    title: str | None
    source_url: str | None
    duration_sec: float | None
    status: str
    progress: int
    error: str | None
    target_clips: int
    created_at: datetime


# ---------- clips
class ClipOut(ORM):
    id: uuid.UUID
    source_video_id: uuid.UUID
    channel_id: uuid.UUID | None
    rank: int
    start_sec: float
    end_sec: float
    hook: str
    transcript: str
    virality_score: float
    scores: dict
    rationale: str | None
    category: str | None
    layout: str
    caption_preset: str
    crop_track: list | None
    title: str | None
    description: str | None
    tags: list[str]
    status: str
    review_note: str | None
    video_url: str | None = None
    thumbnail_url: str | None = None


class ClipDetail(ClipOut):
    source_url: str | None = None
    words: list[dict] = []          # transcript words around the clip for the timeline editor
    window_start: float = 0.0


class ClipUpdate(BaseModel):
    start_sec: float | None = None
    end_sec: float | None = None
    hook: str | None = None
    title: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=5000)
    tags: list[str] | None = None
    layout: Literal["auto", "track", "fit_blur"] | None = None
    caption_preset: Literal["bold_pop", "minimal", "neon"] | None = None
    crop_track: list[dict] | None = None


class ReviewAction(BaseModel):
    action: Literal["approve", "reject"]
    note: str | None = None


class BulkReview(ReviewAction):
    clip_ids: list[uuid.UUID]
    schedule: bool = True


# ---------- agents
class AgentRunOut(ORM):
    id: uuid.UUID
    kind: str
    status: str
    channel_id: uuid.UUID | None
    source_video_id: uuid.UUID | None
    output: dict | None
    error: str | None
    input_tokens: int
    output_tokens: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class AgentEventOut(ORM):
    id: uuid.UUID
    run_id: uuid.UUID
    level: str
    message: str
    data: dict | None
    created_at: datetime


class PublishJobOut(ORM):
    id: uuid.UUID
    clip_id: uuid.UUID
    channel_id: uuid.UUID
    scheduled_for: datetime
    status: str
    youtube_video_id: str | None
    error: str | None
