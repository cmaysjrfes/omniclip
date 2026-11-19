import type { AgentEvent, AgentRun, Channel, Clip, ClipDetail, Overview, Playbook, PublishJob, Source } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", "X-API-Key": API_KEY, ...init.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, typeof body.detail === "string" ? body.detail : res.statusText);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  overview: () => req<Overview>("/api/analytics/overview"),

  taxonomy: () => req<Record<string, string[]>>("/api/channels/taxonomy"),
  channels: () => req<Channel[]>("/api/channels"),
  channel: (id: string) => req<Channel>(`/api/channels/${id}`),
  createChannel: (body: Partial<Channel>) => req<Channel>("/api/channels", { method: "POST", body: json(body) }),
  updateChannel: (id: string, body: Partial<Channel>) => req<Channel>(`/api/channels/${id}`, { method: "PATCH", body: json(body) }),
  relaunch: (id: string, apply = false) => req(`/api/channels/${id}/launch?apply_to_youtube=${apply}`, { method: "POST" }),
  competitors: (id: string) => req<{ playbook: Playbook; aggregate: Record<string, unknown>; created_at: string }>(`/api/channels/${id}/competitors`),
  calendar: (id: string) => req<PublishJob[]>(`/api/channels/${id}/calendar`),
  oauthStart: (id: string) => req<{ url: string }>(`/api/channels/${id}/oauth/start`),

  sources: (channelId?: string) => req<Source[]>(`/api/sources${channelId ? `?channel_id=${channelId}` : ""}`),
  source: (id: string) => req<Source>(`/api/sources/${id}`),
  sourceClips: (id: string) => req<Clip[]>(`/api/sources/${id}/clips`),
  uploadUrl: (filename: string, content_type: string) =>
    req<{ storage_key: string; upload_url: string }>("/api/sources/upload-url", { method: "POST", body: json({ filename, content_type }) }),
  createSource: (body: { url?: string; storage_key?: string; channel_id?: string | null; title?: string; target_clips?: number }) =>
    req<Source>("/api/sources", { method: "POST", body: json(body) }),

  clips: (params: Record<string, string> = {}) => req<Clip[]>(`/api/clips?${new URLSearchParams(params)}`),
  clip: (id: string) => req<ClipDetail>(`/api/clips/${id}`),
  updateClip: (id: string, body: Partial<Clip>) => req<Clip>(`/api/clips/${id}`, { method: "PATCH", body: json(body) }),
  review: (id: string, action: "approve" | "reject", note?: string) =>
    req<Clip>(`/api/clips/${id}/review`, { method: "POST", body: json({ action, note }) }),
  bulkReview: (clip_ids: string[], action: "approve" | "reject") =>
    req<{ updated: number; skipped: string[] }>("/api/clips/bulk-review", { method: "POST", body: json({ clip_ids, action }) }),

  runs: (limit = 50) => req<AgentRun[]>(`/api/agents/runs?limit=${limit}`),
  recentEvents: (limit = 100) => req<AgentEvent[]>(`/api/agents/events/recent?limit=${limit}`),
  eventStreamUrl: () => `${API_URL}/api/agents/events/stream?key=${encodeURIComponent(API_KEY)}`,
};

/** PUT a file to a presigned URL with progress (fetch has no upload progress, XHR does). */
export function putWithProgress(url: string, file: File, onProgress: (pct: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", file.type || "video/mp4");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => (xhr.status < 300 ? resolve() : reject(new Error(`upload failed (${xhr.status})`)));
    xhr.onerror = () => reject(new Error("network error during upload"));
    xhr.send(file);
  });
}
