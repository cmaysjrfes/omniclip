"""SQLAlchemy mapping of the tables defined in db/prisma/schema.prisma.

Prisma owns migrations; this file must mirror it. IDs, created_at and enum types
are created by the database (gen_random_uuid(), now(), CREATE TYPE ...).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _pg_enum(py_enum: type[enum.Enum], name: str) -> Enum:
    return Enum(py_enum, name=name, create_type=False, values_callable=lambda e: [m.value for m in e])


class VideoStatus(str, enum.Enum):
    QUEUED = "QUEUED"; DOWNLOADING = "DOWNLOADING"; TRANSCRIBING = "TRANSCRIBING"
    ANALYZING = "ANALYZING"; READY = "READY"; FAILED = "FAILED"


class ClipStatus(str, enum.Enum):
    CANDIDATE = "CANDIDATE"; RENDERING = "RENDERING"; RENDERED = "RENDERED"; APPROVED = "APPROVED"
    REJECTED = "REJECTED"; SCHEDULED = "SCHEDULED"; PUBLISHED = "PUBLISHED"; FAILED = "FAILED"


class AgentKind(str, enum.Enum):
    CLIP_SCORER = "CLIP_SCORER"; BRAND_ARCHITECT = "BRAND_ARCHITECT"; COMPETITOR_ANALYST = "COMPETITOR_ANALYST"
    SCHEDULE_OPTIMIZER = "SCHEDULE_OPTIMIZER"; METADATA_WRITER = "METADATA_WRITER"; AUTOPILOT = "AUTOPILOT"


class RunStatus(str, enum.Enum):
    PENDING = "PENDING"; RUNNING = "RUNNING"; SUCCEEDED = "SUCCEEDED"; FAILED = "FAILED"


class PublishStatus(str, enum.Enum):
    PENDING = "PENDING"; UPLOADING = "UPLOADING"; SCHEDULED = "SCHEDULED"; PUBLISHED = "PUBLISHED"; FAILED = "FAILED"


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def _created() -> Mapped[datetime]:
    return mapped_column("created_at", DateTime, server_default=func.now())


def _updated() -> Mapped[datetime]:
    return mapped_column("updated_at", DateTime, server_default=func.now(), onupdate=func.now())


class Channel(Base):
    __tablename__ = "channels"
    id: Mapped[uuid.UUID] = _id()
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    sub_category: Mapped[str | None] = mapped_column(String)
    niche_description: Mapped[str | None] = mapped_column(String)
    tone: Mapped[str | None] = mapped_column(String)
    target_audience: Mapped[str | None] = mapped_column(String)
    handle: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}")
    brand_kit: Mapped[dict | None] = mapped_column(JSONB)
    youtube_channel_id: Mapped[str | None] = mapped_column(String, unique=True)
    oauth_token_enc: Mapped[str | None] = mapped_column(String)
    autopilot: Mapped[bool] = mapped_column(Boolean, server_default="false")
    require_approval: Mapped[bool] = mapped_column(Boolean, server_default="true")
    posts_per_day: Mapped[int] = mapped_column(Integer, server_default="3")
    posting_slots: Mapped[list | None] = mapped_column(JSONB)
    timezone: Mapped[str] = mapped_column(String, server_default="UTC")
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class SourceVideo(Base):
    __tablename__ = "source_videos"
    id: Mapped[uuid.UUID] = _id()
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"))
    title: Mapped[str | None] = mapped_column(String)
    source_url: Mapped[str | None] = mapped_column(String)
    storage_key: Mapped[str | None] = mapped_column(String)
    duration_sec: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    fps: Mapped[float | None] = mapped_column(Float)
    status: Mapped[VideoStatus] = mapped_column(_pg_enum(VideoStatus, "video_status"), default=VideoStatus.QUEUED)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String)
    transcript_key: Mapped[str | None] = mapped_column(String)
    language: Mapped[str | None] = mapped_column(String)
    target_clips: Mapped[int] = mapped_column(Integer, default=24)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    clips: Mapped[list["Clip"]] = relationship(back_populates="source_video", order_by="Clip.rank")


class Clip(Base):
    __tablename__ = "clips"
    id: Mapped[uuid.UUID] = _id()
    source_video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_videos.id", ondelete="CASCADE"))
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"))
    rank: Mapped[int] = mapped_column(Integer)
    start_sec: Mapped[float] = mapped_column(Float)
    end_sec: Mapped[float] = mapped_column(Float)
    hook: Mapped[str] = mapped_column(String)
    transcript: Mapped[str] = mapped_column(String)
    virality_score: Mapped[float] = mapped_column(Float)
    scores: Mapped[dict] = mapped_column(JSONB)
    rationale: Mapped[str | None] = mapped_column(String)
    category: Mapped[str | None] = mapped_column(String)
    layout: Mapped[str] = mapped_column(String, default="auto")
    caption_preset: Mapped[str] = mapped_column(String, default="bold_pop")
    crop_track: Mapped[list | None] = mapped_column(JSONB)
    render_key: Mapped[str | None] = mapped_column(String)
    thumbnail_key: Mapped[str | None] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    status: Mapped[ClipStatus] = mapped_column(_pg_enum(ClipStatus, "clip_status"), default=ClipStatus.CANDIDATE)
    review_note: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    source_video: Mapped[SourceVideo] = relationship(back_populates="clips")


class PublishJob(Base):
    __tablename__ = "publish_jobs"
    id: Mapped[uuid.UUID] = _id()
    clip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clips.id", ondelete="CASCADE"))
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[PublishStatus] = mapped_column(_pg_enum(PublishStatus, "publish_status"), default=PublishStatus.PENDING)
    youtube_video_id: Mapped[str | None] = mapped_column(String)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class ClipMetric(Base):
    __tablename__ = "clip_metrics"
    id: Mapped[uuid.UUID] = _id()
    clip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clips.id", ondelete="CASCADE"))
    captured_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    avg_view_pct: Mapped[float | None] = mapped_column(Float)
    subscribers_net: Mapped[int | None] = mapped_column(Integer)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[uuid.UUID] = _id()
    kind: Mapped[AgentKind] = mapped_column(_pg_enum(AgentKind, "agent_kind"))
    status: Mapped[RunStatus] = mapped_column(_pg_enum(RunStatus, "run_status"), default=RunStatus.PENDING)
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"))
    source_video_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    input: Mapped[dict | None] = mapped_column(JSONB)
    output: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(String)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = _created()


class AgentEvent(Base):
    __tablename__ = "agent_events"
    id: Mapped[uuid.UUID] = _id()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    level: Mapped[str] = mapped_column(String, default="info")
    message: Mapped[str] = mapped_column(String)
    data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()


class CompetitorReport(Base):
    __tablename__ = "competitor_reports"
    id: Mapped[uuid.UUID] = _id()
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    report: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()
