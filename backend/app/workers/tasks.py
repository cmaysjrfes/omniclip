"""Pipeline daemon.

Source video flow (Celery canvas, each step durable and retryable on its own queue):

  media.ingest → media.transcribe → agents.score_clips → agents.fanout_render
      → chord( media.render_clip × N ) → agents.finalize_source
            → metadata → (autopilot) approve → schedule → PublishJobs

Beat: publish.dispatch_due (every minute) uploads jobs entering the lead window with a
YouTube publishAt; publish.collect_metrics (hourly) snapshots stats for the optimiser.
"""
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from celery import chain, chord, group
from sqlalchemy import select

from app.agents import channel_launch, clip_scorer, metadata_writer
from app.agents.llm import LLM
from app.agents.runlog import agent_run
from app.agents.schedule_optimizer import next_publish_times, rank_slots
from app.core import storage
from app.core.config import get_settings
from app.core.db import worker_session
from app.core.security import decrypt
from app.integrations import youtube
from app.models import (AgentKind, Channel, Clip, ClipMetric, ClipStatus, CompetitorReport, PublishJob,
                        PublishStatus, SourceVideo, VideoStatus)
from app.pipeline import captions, ingest, reframe, render, transcribe

from .celery_app import celery

AUTO_APPROVE_MIN_SCORE = 70.0
PUBLISH_LEAD = timedelta(hours=2)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _work(*parts) -> Path:
    p = Path(get_settings().work_dir, *map(str, parts))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _update_source(source_id: str, **fields) -> None:
    with worker_session() as db:
        sv = db.get(SourceVideo, source_id)
        for k, v in fields.items():
            setattr(sv, k, v)


def _local_source(source_id: str) -> Path:
    """Media workers cache the source locally; renders of 20+ clips reuse one download."""
    path = _work("sources", source_id) / "source.mp4"
    if not path.exists():
        with worker_session() as db:
            key = db.get(SourceVideo, source_id).storage_key
        storage.download_file(key, path)
    return path


def _transcript(source_id: str) -> dict:
    cache = _work("sources", source_id) / "transcript.json"
    if cache.exists():
        return json.loads(cache.read_text())
    with worker_session() as db:
        key = db.get(SourceVideo, source_id).transcript_key
    data = json.loads(storage.get_bytes(key))
    cache.write_text(json.dumps(data))
    return data


def start_source_pipeline(source_id: str) -> None:
    chain(ingest_source.si(source_id), transcribe_source.si(source_id),
          score_clips.si(source_id), fanout_render.si(source_id)).apply_async()


# ---------------------------------------------------------------- media queue

@celery.task(name="media.ingest", bind=True, max_retries=3, default_retry_delay=30)
def ingest_source(self, source_id: str) -> None:
    try:
        with worker_session() as db:
            sv = db.get(SourceVideo, source_id)
            url, key = sv.source_url, sv.storage_key
        local = _work("sources", source_id) / "source.mp4"
        if not key:
            _update_source(source_id, status=VideoStatus.DOWNLOADING, progress=2)
            downloaded = ingest.download_url(url, local.parent)
            if downloaded != local:
                shutil.move(downloaded, local)
            key = storage.upload_file(local, f"sources/{source_id}/source.mp4", "video/mp4")
        elif not local.exists():
            storage.download_file(key, local)
        meta = ingest.probe(local)
        _update_source(source_id, storage_key=key, duration_sec=meta["duration"], width=meta["width"],
                       height=meta["height"], fps=meta["fps"], progress=10)
    except Exception as exc:
        _update_source(source_id, status=VideoStatus.FAILED, error=f"ingest: {exc}")
        raise self.retry(exc=exc)


@celery.task(name="media.transcribe")
def transcribe_source(source_id: str) -> None:
    _update_source(source_id, status=VideoStatus.TRANSCRIBING, progress=12)
    src = _local_source(source_id)
    with worker_session() as db:
        duration = db.get(SourceVideo, source_id).duration_sec or 0
    audio = ingest.extract_audio(src, src.with_name("audio.wav"))

    last = [0]
    def progress(frac: float) -> None:
        pct = 12 + int(frac * 40)
        if pct - last[0] >= 3:
            last[0] = pct
            _update_source(source_id, progress=pct)

    data = transcribe.transcribe(audio, duration, on_progress=progress)
    (src.parent / "transcript.json").write_text(json.dumps(data))
    key = storage.put_bytes(f"sources/{source_id}/transcript.json", json.dumps(data).encode())
    _update_source(source_id, transcript_key=key, language=data["language"], progress=52)


@celery.task(name="media.render_clip", bind=True, max_retries=2, default_retry_delay=20)
def render_clip(self, clip_id: str) -> str:
    s = get_settings()
    with worker_session() as db:
        clip = db.get(Clip, clip_id)
        clip.status = ClipStatus.RENDERING
        sv = db.get(SourceVideo, clip.source_video_id)
        source_id, start, end = str(sv.id), clip.start_sec, clip.end_sec
        src_w, src_h = sv.width, sv.height
        layout, track, preset, hook = clip.layout, clip.crop_track, clip.caption_preset, clip.hook
    try:
        src = _local_source(source_id)
        if track is None or layout == "auto":
            analysis = reframe.analyze(src, start, end)
            track = analysis["track"]
            layout = analysis["layout"] if layout == "auto" else layout
        words = _transcript(source_id)["words"]
        out_dir = _work("renders", clip_id)
        ass = out_dir / "captions.ass"
        ass.write_text(captions.build_ass(words, start, end, preset, hook=hook,
                                          width=s.render_width, height=s.render_height))
        out = render.render_clip(src=src, out=out_dir / "short.mp4", start=start, end=end, src_w=src_w,
                                 src_h=src_h, layout=layout, track=track, ass_path=ass,
                                 width=s.render_width, height=s.render_height, gpu=s.ffmpeg_gpu)
        thumb = render.thumbnail(out, out_dir / "thumb.jpg", at=min(1.5, (end - start) / 2))
        render_key = storage.upload_file(out, f"clips/{clip_id}/short.mp4", "video/mp4")
        thumb_key = storage.upload_file(thumb, f"clips/{clip_id}/thumb.jpg", "image/jpeg")
        with worker_session() as db:
            clip = db.get(Clip, clip_id)
            clip.render_key, clip.thumbnail_key, clip.crop_track = render_key, thumb_key, track
            clip.layout = layout
            clip.status = ClipStatus.RENDERED
        shutil.rmtree(out_dir, ignore_errors=True)
        return clip_id
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            with worker_session() as db:
                c = db.get(Clip, clip_id)
                c.status, c.review_note = ClipStatus.FAILED, f"render failed: {exc}"[:500]
            return clip_id
        raise self.retry(exc=exc)


# ---------------------------------------------------------------- agents queue

@celery.task(name="agents.score_clips")
def score_clips(source_id: str) -> None:
    s = get_settings()
    _update_source(source_id, status=VideoStatus.ANALYZING, progress=55)
    with worker_session() as db:
        sv = db.get(SourceVideo, source_id)
        target, channel_id = sv.target_clips, sv.channel_id
        ch = db.get(Channel, channel_id) if channel_id else None
        niche = " / ".join(filter(None, [ch.category, ch.sub_category, ch.niche_description])) if ch else None

    llm = LLM()
    with agent_run(AgentKind.CLIP_SCORER, channel_id=channel_id, source_video_id=source_id,
                   input={"target": target}) as (log, result):
        moments = clip_scorer.score_transcript(_transcript(source_id), target=target, niche=niche, llm=llm,
                                               min_sec=s.clip_min_sec, max_sec=s.clip_max_sec, log=log.log)
        with worker_session() as db:
            for old in db.scalars(select(Clip).where(Clip.source_video_id == source_id,
                                                     Clip.status == ClipStatus.CANDIDATE)):
                db.delete(old)
            for rank, m in enumerate(moments, 1):
                db.add(Clip(source_video_id=source_id, channel_id=channel_id, rank=rank,
                            start_sec=m["start"], end_sec=m["end"], hook=m["hook"], transcript=m["transcript"],
                            virality_score=m["virality_score"], scores=m["scores"], rationale=m["rationale"],
                            category=m["category"], title=m["title_idea"],
                            caption_preset=(ch.brand_kit or {}).get("caption_preset", "bold_pop") if ch else "bold_pop"))
        result.update(output={"clips": len(moments)}, input_tokens=llm.usage.input_tokens,
                      output_tokens=llm.usage.output_tokens)
    _update_source(source_id, progress=65)


@celery.task(name="agents.fanout_render")
def fanout_render(source_id: str) -> None:
    with worker_session() as db:
        ids = [str(c.id) for c in db.scalars(select(Clip).where(Clip.source_video_id == source_id,
                                                                Clip.status == ClipStatus.CANDIDATE))]
    if not ids:
        _update_source(source_id, status=VideoStatus.READY, progress=100)
        return
    chord(group(render_clip.si(cid) for cid in ids))(finalize_source.si(source_id))


@celery.task(name="agents.finalize_source")
def finalize_source(source_id: str) -> None:
    with worker_session() as db:
        sv = db.get(SourceVideo, source_id)
        ch = db.get(Channel, sv.channel_id) if sv.channel_id else None
        clips = list(db.scalars(select(Clip).where(Clip.source_video_id == source_id,
                                                   Clip.status == ClipStatus.RENDERED)))
        payload = [{"id": str(c.id), "hook": c.hook, "transcript": c.transcript} for c in clips]
        channel = ({"name": ch.name, "category": ch.category, "sub_category": ch.sub_category, "tone": ch.tone}
                   if ch else {"name": "Untitled", "category": "General"})
        report = db.scalars(select(CompetitorReport).where(CompetitorReport.channel_id == sv.channel_id)
                            .order_by(CompetitorReport.created_at.desc()).limit(1)).first() if ch else None
        playbook = report.report.get("playbook") if report else None

    if payload:
        llm = LLM()
        with agent_run(AgentKind.METADATA_WRITER, channel_id=ch.id if ch else None,
                       source_video_id=source_id) as (log, result):
            meta = metadata_writer.write_metadata(payload, channel, playbook, llm)
            with worker_session() as db:
                for cid, m in meta.items():
                    c = db.get(Clip, cid)
                    if c:
                        c.title, c.description, c.tags = m["title"], m["description"], m["tags"]
            log.log(f"Wrote titles, descriptions and tags for {len(meta)} clips")
            result.update(output={"clips": len(meta)}, input_tokens=llm.usage.input_tokens,
                          output_tokens=llm.usage.output_tokens)

    _update_source(source_id, status=VideoStatus.READY, progress=100)

    if ch and ch.autopilot and ch.youtube_channel_id:
        with worker_session() as db:
            approved = []
            for c in db.scalars(select(Clip).where(Clip.source_video_id == source_id,
                                                   Clip.status == ClipStatus.RENDERED)):
                if not ch.require_approval and c.virality_score >= AUTO_APPROVE_MIN_SCORE:
                    c.status = ClipStatus.APPROVED
                    approved.append(str(c.id))
        if approved:
            schedule_clips.delay(str(ch.id), approved)


@celery.task(name="agents.schedule_clips")
def schedule_clips(channel_id: str, clip_ids: list[str]) -> list[str]:
    with worker_session() as db:
        ch = db.get(Channel, channel_id)
        taken = [j.scheduled_for for j in db.scalars(select(PublishJob).where(
            PublishJob.channel_id == ch.id, PublishJob.scheduled_for > _utcnow(),
            PublishJob.status.in_([PublishStatus.PENDING, PublishStatus.UPLOADING, PublishStatus.SCHEDULED])))]
        clips = sorted((db.get(Clip, cid) for cid in clip_ids), key=lambda c: -c.virality_score)
        times = next_publish_times(ch.posting_slots or [], tz=ch.timezone, count=len(clips), after=_utcnow(),
                                   taken=taken, posts_per_day=ch.posts_per_day)
        for clip, when in zip(clips, times):  # best clips get the earliest best slots
            db.add(PublishJob(clip_id=clip.id, channel_id=ch.id, scheduled_for=when))
            clip.status = ClipStatus.SCHEDULED
        return [t.isoformat() for t in times]


@celery.task(name="agents.channel_launch")
def run_channel_launch(channel_id: str, auto_apply: bool = False) -> None:
    with worker_session() as db:
        ch = db.get(Channel, channel_id)
        niche = {"category": ch.category, "sub_category": ch.sub_category,
                 "niche_description": ch.niche_description, "tone": ch.tone, "target_audience": ch.target_audience}
        state = {"niche": niche, "timezone": ch.timezone, "auto_apply": auto_apply,
                 "youtube_connected": bool(ch.youtube_channel_id and ch.oauth_token_enc)}
        yt_id, token = ch.youtube_channel_id, ch.oauth_token_enc

    def apply(brand: dict) -> None:
        youtube.apply_branding(youtube.credentials(decrypt(token)), yt_id,
                               description=brand["description"], keywords=brand["keywords"])

    llm = LLM()
    with agent_run(AgentKind.BRAND_ARCHITECT, channel_id=channel_id, input=niche) as (log, result):
        final = channel_launch.build_graph(llm, log.log, apply).invoke(state)
        brand = final["brand"]
        with worker_session() as db:
            ch = db.get(Channel, channel_id)
            ch.description, ch.keywords = brand["description"], brand["keywords"]
            ch.brand_kit = {**brand["brand_kit"], "name_ideas": brand["names"]}
            if brand["recommended"] and not ch.youtube_channel_id:
                ch.handle = brand["recommended"]["handle"]
            ch.posting_slots = final["slots"]
            if final.get("competitor"):
                db.add(CompetitorReport(channel_id=ch.id, report={
                    k: final["competitor"][k] for k in ("aggregate", "top_videos", "uploads", "playbook")}))
        result.update(output={"recommended": brand["recommended"], "slots": final["slots"][:7],
                              "applied": final.get("applied", False)},
                      input_tokens=llm.usage.input_tokens, output_tokens=llm.usage.output_tokens)


# ---------------------------------------------------------------- publish queue

@celery.task(name="publish.dispatch_due")
def dispatch_due() -> int:
    with worker_session() as db:
        jobs = list(db.scalars(select(PublishJob).where(
            PublishJob.status == PublishStatus.PENDING,
            PublishJob.scheduled_for <= _utcnow() + PUBLISH_LEAD).with_for_update(skip_locked=True)))
        for j in jobs:
            j.status = PublishStatus.UPLOADING
        ids = [str(j.id) for j in jobs]
    for jid in ids:
        publish_job.delay(jid)
    return len(ids)


@celery.task(name="publish.upload", bind=True, max_retries=5, default_retry_delay=300)
def publish_job(self, job_id: str) -> None:
    with worker_session() as db:
        job = db.get(PublishJob, job_id)
        clip, ch = db.get(Clip, job.clip_id), db.get(Channel, job.channel_id)
        job.attempts += 1
        payload = {"render_key": clip.render_key, "title": clip.title or clip.hook,
                   "description": clip.description or "", "tags": clip.tags or [],
                   "token": ch.oauth_token_enc, "when": job.scheduled_for, "clip_id": str(clip.id)}
    try:
        local = _work("publish", job_id) / "short.mp4"
        storage.download_file(payload["render_key"], local)
        when = payload["when"]
        publish_at = when.isoformat(timespec="seconds") + "Z" if when > _utcnow() + timedelta(minutes=15) else None
        vid = youtube.upload_short(youtube.credentials(decrypt(payload["token"])), local, title=payload["title"],
                                   description=payload["description"], tags=payload["tags"],
                                   publish_at_iso=publish_at)
        with worker_session() as db:
            job = db.get(PublishJob, job_id)
            job.youtube_video_id = vid
            job.status = PublishStatus.SCHEDULED if publish_at else PublishStatus.PUBLISHED
            db.get(Clip, payload["clip_id"]).status = ClipStatus.PUBLISHED
        shutil.rmtree(local.parent, ignore_errors=True)
    except Exception as exc:
        with worker_session() as db:
            job = db.get(PublishJob, job_id)
            job.error = str(exc)[:1000]
            if self.request.retries >= self.max_retries:
                job.status = PublishStatus.FAILED
        raise self.retry(exc=exc)


@celery.task(name="publish.collect_metrics")
def collect_metrics() -> int:
    with worker_session() as db:
        rows = db.execute(select(PublishJob, Channel).join(Channel, Channel.id == PublishJob.channel_id).where(
            PublishJob.youtube_video_id.is_not(None),
            PublishJob.scheduled_for > _utcnow() - timedelta(days=30))).all()
    by_channel: dict[str, list] = {}
    for job, ch in rows:
        by_channel.setdefault(ch.oauth_token_enc, []).append(job)
    n = 0
    for token, jobs in by_channel.items():
        stats = youtube.video_statistics(youtube.credentials(decrypt(token)), [j.youtube_video_id for j in jobs])
        with worker_session() as db:
            for j in jobs:
                st = stats.get(j.youtube_video_id)
                if st:
                    db.add(ClipMetric(clip_id=j.clip_id, views=int(st.get("viewCount", 0)),
                                      likes=int(st.get("likeCount", 0)), comments=int(st.get("commentCount", 0))))
                    n += 1
    return n


@celery.task(name="agents.reoptimize_schedule")
def reoptimize_schedule(channel_id: str) -> None:
    """Feed the channel's own 48h results back into the slot ranking."""
    with worker_session() as db:
        ch = db.get(Channel, channel_id)
        report = db.scalars(select(CompetitorReport).where(CompetitorReport.channel_id == ch.id)
                            .order_by(CompetitorReport.created_at.desc()).limit(1)).first()
        own = []
        for job in db.scalars(select(PublishJob).where(PublishJob.channel_id == ch.id,
                                                       PublishJob.youtube_video_id.is_not(None))):
            m = db.scalars(select(ClipMetric).where(
                ClipMetric.clip_id == job.clip_id,
                ClipMetric.captured_at <= job.scheduled_for + timedelta(hours=50))
                .order_by(ClipMetric.captured_at.desc()).limit(1)).first()
            if m:
                own.append({"published_at": job.scheduled_for.isoformat() + "+00:00", "views_48h": m.views})
        uploads = [{"published_at": v["published_at"], "views_per_day": v["views_per_day"]}
                   for v in (report.report.get("uploads", []) if report else [])]
        ch.posting_slots = rank_slots(uploads, own, ch.timezone)


@celery.task(name="agents.reoptimize_all")
def reoptimize_all() -> None:
    with worker_session() as db:
        ids = [str(c.id) for c in db.scalars(select(Channel).where(Channel.youtube_channel_id.is_not(None)))]
    for cid in ids:
        reoptimize_schedule.delay(cid)
