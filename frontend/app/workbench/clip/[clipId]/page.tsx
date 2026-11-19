"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Check, Loader2, RotateCcw, Save, X } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import type { Clip, ClipDetail } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ScoreBreakdown, ViralityRing } from "@/components/score-breakdown";
import { StatusBadge } from "@/components/status-badge";
import { TimelineEditor } from "@/components/timeline-editor";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

const PRESETS: { id: Clip["caption_preset"]; label: string; swatch: string }[] = [
  { id: "bold_pop", label: "Bold pop", swatch: "#FFD400" },
  { id: "minimal", label: "Minimal", swatch: "#7DD3FC" },
  { id: "neon", label: "Neon", swatch: "#39FF14" },
];
const LAYOUTS: { id: Clip["layout"]; label: string; hint: string }[] = [
  { id: "auto", label: "Auto", hint: "Track speaker, fall back to blur-fill" },
  { id: "track", label: "Speaker tracking", hint: "Face-tracked 9:16 crop" },
  { id: "fit_blur", label: "Blur fill", hint: "Full frame over blurred background" },
];

export default function ClipEditor() {
  const { clipId } = useParams<{ clipId: string }>();
  const { data: clip, refresh, setData } = useApi<ClipDetail>(() => api.clip(clipId), [clipId]);
  const [draft, setDraft] = useState<Partial<Clip>>({});
  const [saving, setSaving] = useState(false);
  const [current, setCurrent] = useState<number>();
  const [tagText, setTagText] = useState<string>();
  const srcVideo = useRef<HTMLVideoElement>(null);

  // Poll while a re-render is in flight.
  useEffect(() => {
    if (!clip || !["CANDIDATE", "RENDERING"].includes(clip.status)) return;
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [clip, refresh]);

  if (!clip) return <div className="grid h-64 place-items-center"><Loader2 className="animate-spin text-muted-foreground" /></div>;

  const v = { ...clip, ...draft };
  const dirty = Object.keys(draft).length > 0;
  const windowEnd = Math.max(clip.words.at(-1)?.e ?? clip.end_sec + 20, v.end_sec + 1);
  const set = (p: Partial<Clip>) => setDraft((d) => ({ ...d, ...p }));

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api.updateClip(clip.id, draft);
      setData({ ...clip, ...updated });
      setDraft({});
      setTagText(undefined);
    } finally { setSaving(false); }
  };
  const review = async (action: "approve" | "reject") => {
    const updated = await api.review(clip.id, action);
    setData({ ...clip, ...updated });
  };

  // Loop the source preview inside the trim range.
  const onTime = () => {
    const el = srcVideo.current!;
    setCurrent(el.currentTime);
    if (el.currentTime >= v.end_sec || el.currentTime < v.start_sec - 0.5) el.currentTime = v.start_sec;
  };

  return (
    <>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="sm" asChild><Link href={`/workbench/${clip.source_video_id}`}><ArrowLeft /> Clips</Link></Button>
        <StatusBadge status={clip.status} />
        {clip.category && <Badge variant="outline">{clip.category}</Badge>}
        <div className="ml-auto flex gap-2">
          {dirty && <Button variant="ghost" size="sm" onClick={() => { setDraft({}); setTagText(undefined); }}><RotateCcw /> Discard</Button>}
          <Button variant="outline" size="sm" disabled={!dirty || saving} onClick={save}>
            {saving ? <Loader2 className="animate-spin" /> : <Save />} Save{draft.start_sec !== undefined || draft.end_sec !== undefined || draft.hook || draft.layout || draft.caption_preset ? " & re-render" : ""}
          </Button>
          <Button variant="outline" size="sm" className="text-destructive" onClick={() => review("reject")}><X /> Reject</Button>
          <Button size="sm" disabled={!["RENDERED", "REJECTED"].includes(clip.status) || dirty} onClick={() => review("approve")}><Check /> Approve</Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        {/* Preview */}
        <div className="space-y-3">
          <Tabs defaultValue="render">
            <TabsList className="w-full">
              <TabsTrigger value="render">Rendered short</TabsTrigger>
              <TabsTrigger value="source">Source trim</TabsTrigger>
            </TabsList>
            <TabsContent value="render">
              <div className="relative aspect-[9/16] overflow-hidden rounded-xl border bg-black">
                {clip.status === "RENDERING" || clip.status === "CANDIDATE" ? (
                  <div className="grid size-full place-items-center text-sm text-muted-foreground">
                    <div className="flex items-center gap-2"><Loader2 className="size-4 animate-spin" /> Rendering…</div>
                  </div>
                ) : clip.video_url ? (
                  <video key={clip.video_url} src={clip.video_url} controls playsInline className="size-full" />
                ) : (
                  <div className="grid size-full place-items-center px-6 text-center text-sm text-muted-foreground">
                    {clip.status === "FAILED" ? clip.review_note ?? "Render failed" : "No render available"}
                  </div>
                )}
              </div>
            </TabsContent>
            <TabsContent value="source">
              <div className="aspect-video overflow-hidden rounded-xl border bg-black">
                {clip.source_url && (
                  <video ref={srcVideo} src={`${clip.source_url}#t=${v.start_sec}`} controls playsInline className="size-full" onTimeUpdate={onTime} />
                )}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">Plays and loops the selected range from the original video.</p>
            </TabsContent>
          </Tabs>
        </div>

        <div className="min-w-0 space-y-6">
          <Card>
            <CardHeader><CardTitle>Timeline</CardTitle></CardHeader>
            <CardContent>
              <TimelineEditor words={clip.words} windowStart={clip.window_start} windowEnd={windowEnd}
                start={v.start_sec} end={v.end_sec} current={current}
                onChange={(s, e) => set({ start_sec: s, end_sec: e })}
                onSeek={(t) => { if (srcVideo.current) srcVideo.current.currentTime = t; }} />
            </CardContent>
          </Card>

          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader className="grid-cols-[1fr_auto]">
                <div>
                  <CardTitle>AI score breakdown</CardTitle>
                  <p className="mt-1 text-xs text-muted-foreground">Rank #{clip.rank} from this video</p>
                </div>
                <ViralityRing value={clip.virality_score} />
              </CardHeader>
              <CardContent><ScoreBreakdown scores={clip.scores} rationale={clip.rationale} /></CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>Style</CardTitle></CardHeader>
              <CardContent className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="hook">On-screen hook (first 3s)</Label>
                  <Input id="hook" value={v.hook} maxLength={60} onChange={(e) => set({ hook: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label>Captions</Label>
                  <div className="grid grid-cols-3 gap-2">
                    {PRESETS.map((p) => (
                      <button key={p.id} type="button" onClick={() => set({ caption_preset: p.id })}
                        className={cn("rounded-lg border p-2.5 text-left text-xs transition-colors", v.caption_preset === p.id && "border-primary bg-primary/5")}>
                        <div className="mb-1.5 text-sm font-black tracking-tight">THE <span style={{ color: p.swatch }}>WORD</span></div>
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Framing</Label>
                  <div className="space-y-1.5">
                    {LAYOUTS.map((l) => (
                      <label key={l.id} className={cn("flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-sm", v.layout === l.id && "border-primary bg-primary/5")}>
                        <input type="radio" name="layout" className="accent-[var(--primary)]" checked={v.layout === l.id} onChange={() => set({ layout: l.id })} />
                        <span className="font-medium">{l.label}</span><span className="text-xs text-muted-foreground">{l.hint}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader><CardTitle>Publishing metadata</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex justify-between"><Label htmlFor="title">Title</Label><span className="text-xs text-muted-foreground tabular-nums">{(v.title ?? "").length}/100</span></div>
                <Input id="title" value={v.title ?? ""} maxLength={100} onChange={(e) => set({ title: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="desc">Description</Label>
                <Textarea id="desc" rows={4} value={v.description ?? ""} onChange={(e) => set({ description: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tags">Tags (comma-separated)</Label>
                <Input id="tags" value={tagText ?? v.tags.join(", ")} onChange={(e) => {
                  setTagText(e.target.value);
                  set({ tags: e.target.value.split(",").map((t) => t.trim()).filter(Boolean) });
                }} />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
