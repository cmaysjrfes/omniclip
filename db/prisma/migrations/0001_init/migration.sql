-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "public";

-- CreateEnum
CREATE TYPE "public"."video_status" AS ENUM ('QUEUED', 'DOWNLOADING', 'TRANSCRIBING', 'ANALYZING', 'READY', 'FAILED');

-- CreateEnum
CREATE TYPE "public"."clip_status" AS ENUM ('CANDIDATE', 'RENDERING', 'RENDERED', 'APPROVED', 'REJECTED', 'SCHEDULED', 'PUBLISHED', 'FAILED');

-- CreateEnum
CREATE TYPE "public"."agent_kind" AS ENUM ('CLIP_SCORER', 'BRAND_ARCHITECT', 'COMPETITOR_ANALYST', 'SCHEDULE_OPTIMIZER', 'METADATA_WRITER', 'AUTOPILOT');

-- CreateEnum
CREATE TYPE "public"."run_status" AS ENUM ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED');

-- CreateEnum
CREATE TYPE "public"."publish_status" AS ENUM ('PENDING', 'UPLOADING', 'SCHEDULED', 'PUBLISHED', 'FAILED');

-- CreateTable
CREATE TABLE "public"."users" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "email" TEXT NOT NULL,
    "name" TEXT,
    "role" TEXT NOT NULL DEFAULT 'editor',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."channels" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name" TEXT NOT NULL,
    "category" TEXT NOT NULL,
    "sub_category" TEXT,
    "niche_description" TEXT,
    "tone" TEXT,
    "target_audience" TEXT,
    "handle" TEXT,
    "description" TEXT,
    "keywords" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "brand_kit" JSONB,
    "youtube_channel_id" TEXT,
    "oauth_token_enc" TEXT,
    "autopilot" BOOLEAN NOT NULL DEFAULT false,
    "require_approval" BOOLEAN NOT NULL DEFAULT true,
    "posts_per_day" INTEGER NOT NULL DEFAULT 3,
    "posting_slots" JSONB,
    "timezone" TEXT NOT NULL DEFAULT 'UTC',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "channels_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."source_videos" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "channel_id" UUID,
    "title" TEXT,
    "source_url" TEXT,
    "storage_key" TEXT,
    "duration_sec" DOUBLE PRECISION,
    "width" INTEGER,
    "height" INTEGER,
    "fps" DOUBLE PRECISION,
    "status" "public"."video_status" NOT NULL DEFAULT 'QUEUED',
    "progress" INTEGER NOT NULL DEFAULT 0,
    "error" TEXT,
    "transcript_key" TEXT,
    "language" TEXT,
    "target_clips" INTEGER NOT NULL DEFAULT 24,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "source_videos_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."clips" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "source_video_id" UUID NOT NULL,
    "channel_id" UUID,
    "rank" INTEGER NOT NULL,
    "start_sec" DOUBLE PRECISION NOT NULL,
    "end_sec" DOUBLE PRECISION NOT NULL,
    "hook" TEXT NOT NULL,
    "transcript" TEXT NOT NULL,
    "virality_score" DOUBLE PRECISION NOT NULL,
    "scores" JSONB NOT NULL,
    "rationale" TEXT,
    "category" TEXT,
    "layout" TEXT NOT NULL DEFAULT 'auto',
    "caption_preset" TEXT NOT NULL DEFAULT 'bold_pop',
    "crop_track" JSONB,
    "render_key" TEXT,
    "thumbnail_key" TEXT,
    "title" TEXT,
    "description" TEXT,
    "tags" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "status" "public"."clip_status" NOT NULL DEFAULT 'CANDIDATE',
    "review_note" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "clips_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."publish_jobs" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "clip_id" UUID NOT NULL,
    "channel_id" UUID NOT NULL,
    "scheduled_for" TIMESTAMP(3) NOT NULL,
    "status" "public"."publish_status" NOT NULL DEFAULT 'PENDING',
    "youtube_video_id" TEXT,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "error" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "publish_jobs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."clip_metrics" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "clip_id" UUID NOT NULL,
    "captured_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "views" INTEGER NOT NULL DEFAULT 0,
    "likes" INTEGER NOT NULL DEFAULT 0,
    "comments" INTEGER NOT NULL DEFAULT 0,
    "avg_view_pct" DOUBLE PRECISION,
    "subscribers_net" INTEGER,

    CONSTRAINT "clip_metrics_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."agent_runs" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "kind" "public"."agent_kind" NOT NULL,
    "status" "public"."run_status" NOT NULL DEFAULT 'PENDING',
    "channel_id" UUID,
    "source_video_id" UUID,
    "input" JSONB,
    "output" JSONB,
    "error" TEXT,
    "input_tokens" INTEGER NOT NULL DEFAULT 0,
    "output_tokens" INTEGER NOT NULL DEFAULT 0,
    "started_at" TIMESTAMP(3),
    "finished_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "agent_runs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."agent_events" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "run_id" UUID NOT NULL,
    "level" TEXT NOT NULL DEFAULT 'info',
    "message" TEXT NOT NULL,
    "data" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "agent_events_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."competitor_reports" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "channel_id" UUID NOT NULL,
    "report" JSONB NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "competitor_reports_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "public"."users"("email");

-- CreateIndex
CREATE UNIQUE INDEX "channels_youtube_channel_id_key" ON "public"."channels"("youtube_channel_id");

-- CreateIndex
CREATE INDEX "source_videos_channel_id_idx" ON "public"."source_videos"("channel_id");

-- CreateIndex
CREATE INDEX "clips_source_video_id_rank_idx" ON "public"."clips"("source_video_id", "rank");

-- CreateIndex
CREATE INDEX "clips_status_idx" ON "public"."clips"("status");

-- CreateIndex
CREATE INDEX "publish_jobs_status_scheduled_for_idx" ON "public"."publish_jobs"("status", "scheduled_for");

-- CreateIndex
CREATE INDEX "clip_metrics_clip_id_captured_at_idx" ON "public"."clip_metrics"("clip_id", "captured_at");

-- CreateIndex
CREATE INDEX "agent_runs_created_at_idx" ON "public"."agent_runs"("created_at");

-- CreateIndex
CREATE INDEX "agent_events_run_id_created_at_idx" ON "public"."agent_events"("run_id", "created_at");

-- AddForeignKey
ALTER TABLE "public"."source_videos" ADD CONSTRAINT "source_videos_channel_id_fkey" FOREIGN KEY ("channel_id") REFERENCES "public"."channels"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."clips" ADD CONSTRAINT "clips_source_video_id_fkey" FOREIGN KEY ("source_video_id") REFERENCES "public"."source_videos"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."clips" ADD CONSTRAINT "clips_channel_id_fkey" FOREIGN KEY ("channel_id") REFERENCES "public"."channels"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."publish_jobs" ADD CONSTRAINT "publish_jobs_clip_id_fkey" FOREIGN KEY ("clip_id") REFERENCES "public"."clips"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."publish_jobs" ADD CONSTRAINT "publish_jobs_channel_id_fkey" FOREIGN KEY ("channel_id") REFERENCES "public"."channels"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."clip_metrics" ADD CONSTRAINT "clip_metrics_clip_id_fkey" FOREIGN KEY ("clip_id") REFERENCES "public"."clips"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."agent_runs" ADD CONSTRAINT "agent_runs_channel_id_fkey" FOREIGN KEY ("channel_id") REFERENCES "public"."channels"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."agent_events" ADD CONSTRAINT "agent_events_run_id_fkey" FOREIGN KEY ("run_id") REFERENCES "public"."agent_runs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."competitor_reports" ADD CONSTRAINT "competitor_reports_channel_id_fkey" FOREIGN KEY ("channel_id") REFERENCES "public"."channels"("id") ON DELETE CASCADE ON UPDATE CASCADE;

