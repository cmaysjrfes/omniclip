"""API-side task dispatch by name, so the API process never imports the heavy worker stack
(OpenCV, Whisper, LangGraph)."""
from celery import chain

from .celery_app import celery


def _sig(name: str, *args):
    return celery.signature(name, args=args, immutable=True)


def process_source(source_id: str) -> None:
    chain(_sig("media.ingest", source_id), _sig("media.transcribe", source_id),
          _sig("agents.score_clips", source_id), _sig("agents.fanout_render", source_id)).apply_async()


def rescore_source(source_id: str) -> None:
    chain(_sig("agents.score_clips", source_id), _sig("agents.fanout_render", source_id)).apply_async()


def render_clip(clip_id: str) -> None:
    _sig("media.render_clip", clip_id).apply_async()


def schedule_clips(channel_id: str, clip_ids: list[str]) -> None:
    _sig("agents.schedule_clips", channel_id, clip_ids).apply_async()


def channel_launch(channel_id: str, auto_apply: bool) -> None:
    _sig("agents.channel_launch", channel_id, auto_apply).apply_async()


def reoptimize_schedule(channel_id: str) -> None:
    _sig("agents.reoptimize_schedule", channel_id).apply_async()
