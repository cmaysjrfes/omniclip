export type ClipStatus = "CANDIDATE" | "RENDERING" | "RENDERED" | "APPROVED" | "REJECTED" | "SCHEDULED" | "PUBLISHED" | "FAILED";
export type VideoStatus = "QUEUED" | "DOWNLOADING" | "TRANSCRIBING" | "ANALYZING" | "READY" | "FAILED";

export type ScoreKey = "hook_strength" | "emotional_intensity" | "standalone_value" | "retention_potential" | "shareability";

export interface Clip {
  id: string; source_video_id: string; channel_id: string | null; rank: number;
  start_sec: number; end_sec: number; hook: string; transcript: string;
  virality_score: number; scores: Record<ScoreKey, number>; rationale: string | null; category: string | null;
  layout: "auto" | "track" | "fit_blur"; caption_preset: "bold_pop" | "minimal" | "neon";
  crop_track: { t: number; cx: number }[] | null;
  title: string | null; description: string | null; tags: string[];
  status: ClipStatus; review_note: string | null; video_url: string | null; thumbnail_url: string | null;
}

export interface Word { w: string; s: number; e: number; p?: number }
export interface ClipDetail extends Clip { source_url: string | null; words: Word[]; window_start: number }

export interface Source {
  id: string; channel_id: string | null; title: string | null; source_url: string | null;
  duration_sec: number | null; status: VideoStatus; progress: number; error: string | null;
  target_clips: number; created_at: string;
}

export interface Slot { weekday: number; hour: number; minute: number; score: number }
export interface NameIdea { name: string; handle: string; rationale: string; score: number; memorability: number; searchability: number; niche_fit: number }

export interface Channel {
  id: string; name: string; category: string; sub_category: string | null; niche_description: string | null;
  tone: string | null; target_audience: string | null; handle: string | null; description: string | null;
  keywords: string[];
  brand_kit: (Record<string, unknown> & { name_ideas?: NameIdea[]; primary_color?: string; secondary_color?: string; accent_color?: string; content_pillars?: string[]; avatar_prompt?: string; banner_prompt?: string; voice_guidelines?: string }) | null;
  youtube_channel_id: string | null; autopilot: boolean; require_approval: boolean; posts_per_day: number;
  posting_slots: Slot[] | null; timezone: string; created_at: string;
}

export interface AgentRun {
  id: string; kind: string; status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED";
  channel_id: string | null; source_video_id: string | null; output: Record<string, unknown> | null; error: string | null;
  input_tokens: number; output_tokens: number; started_at: string | null; finished_at: string | null; created_at: string;
}

export interface AgentEvent {
  id?: string; run_id: string; kind?: string; level: "info" | "warn" | "error" | "success";
  message: string; data?: Record<string, unknown> | null; created_at?: string; at?: string;
}

export interface PublishJob { id: string; clip_id: string; channel_id: string; scheduled_for: string; status: string; youtube_video_id: string | null; error: string | null }

export interface Overview {
  channels: number; sources: number; clips_by_status: Partial<Record<ClipStatus, number>>; awaiting_review: number;
  total_views: number; top_clips: { id: string; title: string; views: number }[]; agent_runs_7d: number; tokens_7d: number;
}

export interface Playbook {
  summary: string;
  hook_formats: { pattern: string; examples: string[]; why_it_works: string }[];
  title_patterns: { pattern: string; examples: string[]; why_it_works: string }[];
  thumbnail_patterns: { pattern: string; examples: string[]; why_it_works: string }[];
  pacing_and_structure: string[]; content_gaps: string[]; recommended_shorts_ratio: number;
}
