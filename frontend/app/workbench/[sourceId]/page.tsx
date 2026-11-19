"use client";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { Check, X } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import type { ClipStatus } from "@/lib/types";
import { fmtTime } from "@/lib/utils";
import { ClipCard } from "@/components/clip-card";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

const FILTERS: (ClipStatus | "ALL")[] = ["ALL", "RENDERED", "APPROVED", "SCHEDULED", "PUBLISHED", "REJECTED", "RENDERING", "FAILED"];

export default function SourceClips() {
  const { sourceId } = useParams<{ sourceId: string }>();
  const { data: source } = useApi(() => api.source(sourceId), [sourceId], 4000);
  const clips = useApi(() => api.sourceClips(sourceId), [sourceId], 6000);
  const [filter, setFilter] = useState<ClipStatus | "ALL">("ALL");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const shown = useMemo(() => (clips.data ?? []).filter((c) => filter === "ALL" || c.status === filter), [clips.data, filter]);
  const toggle = (id: string) => setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const bulk = async (action: "approve" | "reject") => {
    await api.bulkReview([...selected], action);
    setSelected(new Set());
    clips.refresh();
  };
  const review = async (id: string, action: "approve" | "reject") => { await api.review(id, action); clips.refresh(); };

  return (
    <>
      <PageHeader title={source?.title ?? "Source video"}
        description={source ? `${source.duration_sec ? fmtTime(source.duration_sec) + " · " : ""}${clips.data?.length ?? 0} of ${source.target_clips} target shorts` : undefined}
        actions={source && <StatusBadge status={source.status} />} />
      {source && source.status !== "READY" && source.status !== "FAILED" && <Progress value={source.progress} className="mb-6" />}
      {source?.error && <p className="mb-6 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{source.error}</p>}

      <div className="sticky top-0 z-10 -mx-1 mb-4 flex flex-wrap items-center gap-2 bg-background/90 px-1 py-2 backdrop-blur">
        {FILTERS.map((f) => (
          <Button key={f} size="sm" variant={filter === f ? "secondary" : "ghost"} onClick={() => setFilter(f)}>
            {f === "ALL" ? "All" : f === "RENDERED" ? "Needs review" : f.charAt(0) + f.slice(1).toLowerCase()}
          </Button>
        ))}
        {selected.size > 0 && (
          <div className="ml-auto flex items-center gap-2">
            <span className="text-sm text-muted-foreground">{selected.size} selected</span>
            <Button size="sm" variant="outline" onClick={() => bulk("reject")}><X /> Reject</Button>
            <Button size="sm" onClick={() => bulk("approve")}><Check /> Approve &amp; schedule</Button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {shown.map((c) => <ClipCard key={c.id} clip={c} selected={selected.has(c.id)} onSelect={toggle} onReview={review} />)}
      </div>
    </>
  );
}
