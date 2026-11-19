"use client";
import Link from "next/link";
import { Check, Film, X } from "lucide-react";
import type { Clip } from "@/lib/types";
import { cn, fmtTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "./status-badge";
import { ViralityRing } from "./score-breakdown";

export function ClipCard({ clip, selected, onSelect, onReview }: {
  clip: Clip; selected?: boolean; onSelect?: (id: string) => void;
  onReview?: (id: string, action: "approve" | "reject") => void;
}) {
  const reviewable = clip.status === "RENDERED" || clip.status === "REJECTED";
  return (
    <div className={cn("group relative flex flex-col overflow-hidden rounded-xl border bg-card transition-colors",
      selected && "border-primary ring-1 ring-primary")}>
      {onSelect && (
        <button aria-label="Select clip" onClick={() => onSelect(clip.id)}
          className={cn("absolute left-2 top-2 z-10 grid size-5 place-items-center rounded border bg-background/80 backdrop-blur",
            selected && "border-primary bg-primary text-primary-foreground")}>
          {selected && <Check className="size-3.5" />}
        </button>
      )}
      <Link href={`/workbench/clip/${clip.id}`} className="relative aspect-[9/16] bg-muted">
        {clip.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={clip.thumbnail_url} alt="" className="size-full object-cover" />
        ) : (
          <div className="grid size-full place-items-center text-muted-foreground"><Film className="size-8 opacity-40" /></div>
        )}
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent p-3 pt-10">
          <p className="line-clamp-2 text-sm font-semibold leading-snug text-white">{clip.hook}</p>
          <p className="mt-1 text-[11px] text-white/60 tabular-nums">#{clip.rank} · {fmtTime(clip.start_sec)} · {Math.round(clip.end_sec - clip.start_sec)}s</p>
        </div>
        <div className="absolute right-2 top-2 rounded-full bg-background/80 backdrop-blur"><ViralityRing value={clip.virality_score} size={44} /></div>
      </Link>
      <div className="flex items-center justify-between gap-2 p-2.5">
        <StatusBadge status={clip.status} />
        {onReview && reviewable && (
          <div className="flex gap-1">
            <Button size="icon" variant="ghost" className="size-7 text-destructive" aria-label="Reject" onClick={() => onReview(clip.id, "reject")}><X /></Button>
            <Button size="icon" variant="ghost" className="size-7 text-success" aria-label="Approve" onClick={() => onReview(clip.id, "approve")}><Check /></Button>
          </div>
        )}
      </div>
    </div>
  );
}
