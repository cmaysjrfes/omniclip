"use client";
import Link from "next/link";
import type { Source } from "@/lib/types";
import { fmtTime, timeAgo } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import { StatusBadge } from "./status-badge";

const STAGE: Record<string, string> = {
  QUEUED: "Waiting for a worker", DOWNLOADING: "Downloading source", TRANSCRIBING: "Transcribing (word-level)",
  ANALYZING: "AI scoring moments → rendering", READY: "Clips ready", FAILED: "Failed",
};

export function SourceTable({ sources }: { sources: Source[] }) {
  if (!sources.length) return <p className="py-8 text-center text-sm text-muted-foreground">No videos yet. Upload one to start.</p>;
  return (
    <div className="divide-y rounded-lg border">
      {sources.map((s) => (
        <Link key={s.id} href={`/workbench/${s.id}`} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1.5 px-4 py-3 hover:bg-accent/50 sm:grid-cols-[1fr_180px_auto]">
          <div className="min-w-0">
            <div className="truncate text-sm font-medium">{s.title ?? s.source_url}</div>
            <div className="text-xs text-muted-foreground">
              {s.duration_sec ? fmtTime(s.duration_sec) + " · " : ""}{s.target_clips} shorts · {timeAgo(s.created_at)}
            </div>
          </div>
          <div className="order-last col-span-2 sm:order-none sm:col-span-1">
            {s.status !== "READY" && s.status !== "FAILED" ? (
              <><Progress value={s.progress} /><div className="mt-1 text-[11px] text-muted-foreground">{STAGE[s.status]}</div></>
            ) : s.error ? <div className="truncate text-xs text-destructive">{s.error}</div> : null}
          </div>
          <StatusBadge status={s.status} />
        </Link>
      ))}
    </div>
  );
}
