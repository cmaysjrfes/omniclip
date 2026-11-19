"use client";
import { useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleDot, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import type { AgentEvent } from "@/lib/types";
import { cn, timeAgo } from "@/lib/utils";

const ICON = { info: CircleDot, success: CheckCircle2, warn: AlertTriangle, error: XCircle };
const TONE = { info: "text-muted-foreground", success: "text-success", warn: "text-warning", error: "text-destructive" };

/** Live agent activity: backfills recent history, then streams new events over SSE. */
export function AgentFeed({ limit = 60, className }: { limit?: number; className?: string }) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [live, setLive] = useState(false);
  const list = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.recentEvents(limit).then(setEvents).catch(() => {});
    const es = new EventSource(api.eventStreamUrl());
    es.onopen = () => setLive(true);
    es.onerror = () => setLive(false);
    es.onmessage = (m) => setEvents((prev) => [...prev, JSON.parse(m.data) as AgentEvent].slice(-limit));
    return () => es.close();
  }, [limit]);

  // Scroll only the feed's own container (scrollIntoView would also scroll the page).
  useEffect(() => {
    const el = list.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events.length]);

  return (
    <div className={cn("flex flex-col", className)}>
      <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
        <span className={cn("size-2 rounded-full", live ? "bg-success animate-pulse" : "bg-muted-foreground/40")} />
        {live ? "Live" : "Reconnecting…"}
      </div>
      <div ref={list} className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1 font-mono text-xs">
        {events.length === 0 && <p className="text-muted-foreground">No agent activity yet.</p>}
        {events.map((e, i) => {
          const Icon = ICON[e.level] ?? CircleDot;
          return (
            <div key={e.id ?? `${e.run_id}-${i}`} className="flex gap-2">
              <Icon className={cn("mt-0.5 size-3.5 shrink-0", TONE[e.level])} />
              <div className="min-w-0">
                <span className="mr-2 text-muted-foreground/70">{timeAgo((e.created_at ?? e.at)!)}</span>
                {e.kind && <span className="mr-2 text-primary/80">{e.kind.toLowerCase().replace(/_/g, " ")}</span>}
                <span className="break-words">{e.message}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
