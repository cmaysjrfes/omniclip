"use client";
import { useCallback, useMemo, useRef, useState } from "react";
import type { Word } from "@/lib/types";
import { cn, fmtTime } from "@/lib/utils";

interface Props {
  words: Word[];
  windowStart: number;
  windowEnd: number;
  start: number;
  end: number;
  current?: number;
  onChange: (start: number, end: number) => void;
  onSeek?: (t: number) => void;
}

/**
 * Trim editor over the word-level transcript. Handles snap to word boundaries so a
 * clip never starts or ends mid-word; clicking a word seeks the preview there.
 */
export function TimelineEditor({ words, windowStart, windowEnd, start, end, current, onChange, onSeek }: Props) {
  const track = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<"start" | "end" | null>(null);
  const span = Math.max(windowEnd - windowStart, 1);
  const pct = (t: number) => ((t - windowStart) / span) * 100;

  const timeAt = useCallback((clientX: number) => {
    const r = track.current!.getBoundingClientRect();
    return windowStart + Math.min(Math.max((clientX - r.left) / r.width, 0), 1) * span;
  }, [windowStart, span]);

  const snap = useCallback((t: number, edge: "start" | "end") => {
    if (!words.length) return t;
    const key = edge === "start" ? "s" : "e";
    return words.reduce((best, w) => (Math.abs(w[key] - t) < Math.abs(best - t) ? w[key] : best), words[0][key]);
  }, [words]);

  const onMove = (e: React.PointerEvent) => {
    if (!drag) return;
    const t = snap(timeAt(e.clientX), drag);
    if (drag === "start" && t < end - 3) onChange(t, end);
    if (drag === "end" && t > start + 3) onChange(start, t);
  };

  const inClip = useMemo(() => words.filter((w) => w.s >= start && w.e <= end).map((w) => w.w).join(" "), [words, start, end]);
  const dur = end - start;

  return (
    <div className="select-none">
      <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground tabular-nums">
        <span>{fmtTime(start)} → {fmtTime(end)}</span>
        <span className={cn("font-medium", dur > 60 ? "text-warning" : "text-foreground")}>{dur.toFixed(1)}s {dur > 60 && "· long for a Short"}</span>
      </div>
      <div ref={track} onPointerMove={onMove} onPointerUp={() => setDrag(null)} onPointerLeave={() => setDrag(null)}
        className="relative h-20 overflow-hidden rounded-lg border bg-muted/40">
        {/* word blocks */}
        {words.map((w, i) => (
          <button key={i} type="button" title={w.w} onClick={() => onSeek?.(w.s)}
            className={cn("absolute top-3 h-6 rounded-[2px] transition-colors",
              w.s >= start && w.e <= end ? "bg-primary/45 hover:bg-primary/70" : "bg-foreground/15 hover:bg-foreground/30")}
            style={{ left: `${pct(w.s)}%`, width: `max(2px, ${pct(w.e) - pct(w.s) - 0.15}%)` }} />
        ))}
        {/* selection */}
        <div className="pointer-events-none absolute inset-y-0 border-y-2 border-primary bg-primary/5" style={{ left: `${pct(start)}%`, width: `${pct(end) - pct(start)}%` }} />
        {(["start", "end"] as const).map((edge) => (
          <div key={edge} role="slider" aria-label={`Clip ${edge}`} aria-valuenow={edge === "start" ? start : end} tabIndex={0}
            onPointerDown={(e) => { (e.target as HTMLElement).setPointerCapture(e.pointerId); setDrag(edge); }}
            onKeyDown={(e) => {
              const d = e.key === "ArrowLeft" ? -0.25 : e.key === "ArrowRight" ? 0.25 : 0;
              if (!d) return;
              if (edge === "start") onChange(snap(start + d, "start"), end); else onChange(start, snap(end + d, "end"));
            }}
            className="absolute inset-y-0 z-10 w-3 -translate-x-1/2 cursor-ew-resize rounded-sm bg-primary outline-none focus-visible:ring-2 focus-visible:ring-ring"
            style={{ left: `${pct(edge === "start" ? start : end)}%` }}>
            <div className="mx-auto mt-8 h-4 w-0.5 rounded bg-primary-foreground/60" />
          </div>
        ))}
        {current !== undefined && (
          <div className="pointer-events-none absolute inset-y-0 w-px bg-foreground" style={{ left: `${pct(current)}%` }} />
        )}
        <div className="absolute inset-x-0 bottom-1 flex justify-between px-2 text-[10px] text-muted-foreground tabular-nums">
          <span>{fmtTime(windowStart)}</span><span>{fmtTime(windowEnd)}</span>
        </div>
      </div>
      <p className="mt-3 max-h-24 overflow-y-auto text-sm leading-relaxed text-muted-foreground">{inClip}</p>
    </div>
  );
}
