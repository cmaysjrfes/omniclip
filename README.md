# OmniClip & Agentic YouTube Engine

[![CI](https://github.com/cmaysjrfes/omniclip/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/cmaysjrfes/omniclip/actions/workflows/ci.yml)

An internal platform that turns one long-form video into 20+ scored, face-tracked, captioned 9:16 Shorts. Agents also design channel brands, study competitors, pick posting times and publish to YouTube.

```
┌──────────────────────────── Next.js dashboard (frontend/) ────────────────────────────┐
│ Command Center · Clipping Workbench (timeline + score breakdown) · Agent Feed (SSE)  │
│ Bulk Upload Manager (presigned PUT → S3) · Channel launch / brand / growth / calendar │
└───────────────┬───────────────────────────────────────────────────────▲───────────────┘
                │ REST (X-API-Key)                                       │ SSE
┌───────────────▼──────────────── FastAPI (backend/app/main.py) ─────────┴───────────────┐
│ /api/sources  /api/clips  /api/channels  /api/agents  /api/analytics                 │
│ dispatches Celery tasks by name (the API never imports OpenCV/Whisper/LangGraph)      │
└───────┬──────────────────────────────┬───────────────────────────┬────────────────────┘
        │ Redis broker                 │ Redis pub/sub (live feed) │ PostgreSQL (Prisma schema)
┌───────▼─────── media queue (GPU) ──┐ ┌▼──────── agents queue ────┐ ┌▼──── publish queue + beat ─┐
│ ingest (yt-dlp / S3) → ffprobe     │ │ Clip Scorer (Claude)      │ │ dispatch_due  (every 1 min) │
│ faster-whisper word timestamps     │ │ Metadata Writer (Claude)  │ │ YouTube resumable upload    │
│ YuNet face track → smooth camera   │ │ Channel Launch (LangGraph)│ │   with publishAt scheduling │
│ ASS karaoke captions → FFmpeg NVENC│ │ Schedule Optimizer        │ │ collect_metrics (hourly)    │
└────────────────────────────────────┘ └───────────────────────────┘ └─────────────────────────────┘
                                   S3 / MinIO: sources, transcripts, renders, thumbnails
```

## Pipeline (Module 4)

```
media.ingest → media.transcribe → agents.score_clips → agents.fanout_render
    → chord(media.render_clip × N) → agents.finalize_source
        → metadata → [autopilot] approve ≥70 (or hold for review) → schedule → PublishJobs
```

Each step is its own Celery task, so it can retry on its own. `task_acks_late` means work from a crashed worker is redelivered, and the routing keeps GPU work off the LLM workers. Media workers download a source once and reuse it for all of its clip renders.

## Module map

| Module | Where | What it does |
|---|---|---|
| 1. Clipping engine | `backend/app/pipeline/` | `ingest` (yt-dlp, ffprobe), `transcribe` (faster-whisper, word-level), `segment` (sentences, windows, boundary snapping, NMS dedupe, composite score), `reframe` (YuNet/Haar faces, mouth-motion speaker pick with hysteresis, dead-zone camera smoothing, RDP keyframes → FFmpeg crop expression, blur-fill fallback), `captions` (ASS karaoke with active-word pop + hook banner), `render` (trim/crop/captions/fades/−14 LUFS, NVENC or x264) |
| | `backend/app/agents/clip_scorer.py` | Claude picks moments by sentence index with 5 sub-scores. Code over-generates by about 1.6×, snaps clips to 15–75 s, removes overlaps and ranks the rest. |
| 2. Brand architect | `agents/brand_architect.py`, `agents/channel_launch.py` | LangGraph: competitors → brand (10–15 scored names, handle, description, keywords, colours, art prompts, caption preset) → schedule → optional YouTube apply |
| 3. Growth intel | `agents/competitor.py`, `agents/schedule_optimizer.py`, `agents/metadata_writer.py` | YouTube Data API stats plus Claude vision on top thumbnails produce a playbook. Posting times use a competitor prior blended with the channel's own 48 h results (shrinkage). Titles, descriptions and tags come from the fast model, with limits enforced in code. |
| 4. Daemon | `backend/app/workers/` | Celery canvas, beat dispatcher, metrics collector, daily re-optimisation |
| 5. Dashboard | `frontend/` | Next.js 15 App Router, Tailwind v4, shadcn/ui primitives, Lucide |
| Data | `db/prisma/schema.prisma` | Source of truth. Prisma owns migrations, and `backend/app/models.py` mirrors it in SQLAlchemy |

## LLM usage

All agents go through `backend/app/agents/llm.py`:
- **Model:** `claude-opus-5-5` (`LLM_MODEL`) for reasoning-heavy agents, and `claude-haiku-5-5` (`LLM_FAST_MODEL`) for bulk metadata.
- **Output:** streaming, adaptive thinking, an explicit `effort` per agent, and Pydantic-validated structured outputs (`output_format=`). Truncation and refusal are checked before parsing.
- **Fallbacks:** server-side refusal fallbacks are on (`fallbacks="default"`, beta `server-side-fallback-2026-07-01`). If one model declines for policy reasons, the request is retried on another model inside the same call instead of failing the pipeline. Remove the `betas`/`fallbacks` kwargs in `llm.py` to turn this off.
- **Caching:** the system prompts are marked cacheable, so the transcript windows of one video share the cached prefix.
- **Tracking:** token usage is recorded on every `AgentRun` and shown on the Agents page.

## Quick start

```bash
cp .env.example .env            # fill ANTHROPIC_API_KEY, YOUTUBE_*, TOKEN_ENCRYPTION_KEY
docker compose up --build       # postgres, redis, minio, migrate, api, 2 worker pools, beat, web
# create the bucket once: MinIO console http://localhost:9001 (minio / minio12345) → bucket "omniclip"
open http://localhost:3000
```

Local development without Docker:

```bash
cd db && npm i && npx prisma migrate deploy
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --reload
celery -A app.workers.celery_app worker -Q media,agents,publish -l info   # + `celery ... beat`
cd frontend && npm i && cp .env.local.example .env.local && npm run dev
```

Without a GPU, set `FFMPEG_GPU=false WHISPER_DEVICE=cpu WHISPER_COMPUTE_TYPE=int8`.

Tests (no network, DB or API key needed: the LLM and YouTube are faked):

```bash
cd backend && pytest -q
```

## YouTube platform constraints (design around these)

- **Channels can't be created through the API.** Someone creates the channel or Brand Account once in YouTube Studio, then connects it with OAuth (`/api/channels/{id}/oauth/start`). The API also can't set the **name, handle or avatar**, so the dashboard shows a Studio checklist with the agent's picks. Agents do apply the description, keywords and banner.
- **Unverified API projects can only upload private videos.** Pass the YouTube API Services audit before you rely on hands-free public publishing.
- **Quota:** `videos.insert` costs about 1,600 units, and the default quota is 10,000 a day (about 6 uploads per project per day). Request an increase to publish 20+ Shorts a day. Competitor analysis costs about 350 units per run.
- **Competitor data comes from the official Data API, not scraping.** Scraping breaks the ToS and breaks often. Studio's "when your viewers are on YouTube" data isn't exposed by any API, so posting times are inferred from performance.
- **Only ingest videos your team owns or has rights to.** Downloading other people's YouTube videos breaks the ToS.

## Security notes

- The API uses a shared team key (`X-API-Key`, or `?key=` for SSE only, because EventSource can't send headers). Put the platform behind a VPN or SSO proxy, or swap `require_api_key` for OIDC, before any wider exposure.
- YouTube refresh tokens are encrypted with Fernet at rest (`TOKEN_ENCRYPTION_KEY`).
- The OAuth `state` parameter is the channel id. Before production, sign it (HMAC with expiry) so callbacks can't be forged.

## What's next

- Alembic-free migration check in CI: diff `schema.prisma` against `models.py`.
- Active-speaker detection from audio diarisation (pyannote) to complement mouth motion.
- B-roll and zoom-punch transitions from emphasis words. Thumbnail A/B tests for long-form videos.
- An eval set of human-rated clips to tune the scorer prompt and `SCORE_WEIGHTS`.
