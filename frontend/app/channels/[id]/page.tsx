"use client";
import { useParams } from "next/navigation";
import { useState } from "react";
import { CheckCircle2, Copy, ExternalLink, Loader2, RefreshCw, Youtube } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import type { Channel } from "@/lib/types";
import { cn } from "@/lib/utils";
import { AgentFeed } from "@/components/agent-feed";
import { PageHeader } from "@/components/page-header";
import { SlotHeatmap } from "@/components/slot-heatmap";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

function Copyable({ label, text }: { label: string; text?: string }) {
  if (!text) return null;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        {label}
        <button className="hover:text-foreground" aria-label={`Copy ${label}`} onClick={() => navigator.clipboard.writeText(text)}><Copy className="size-3.5" /></button>
      </div>
      <p className="rounded-md bg-muted/50 p-2.5 text-xs leading-relaxed">{text}</p>
    </div>
  );
}

export default function ChannelPage() {
  const { id } = useParams<{ id: string }>();
  const ch = useApi(() => api.channel(id), [id], 8000);
  const comp = useApi(() => api.competitors(id).catch(() => null), [id]);
  const cal = useApi(() => api.calendar(id), [id], 30000);
  const [busy, setBusy] = useState<string>();
  const c = ch.data;
  if (!c) return <div className="grid h-64 place-items-center"><Loader2 className="animate-spin text-muted-foreground" /></div>;

  const update = async (patch: Partial<Channel>) => ch.setData(await api.updateChannel(id, patch));
  const act = async (key: string, fn: () => Promise<unknown>) => { setBusy(key); try { await fn(); } finally { setBusy(undefined); } };
  const kit = c.brand_kit ?? {};
  const names = kit.name_ideas ?? [];
  const brandReady = names.length > 0;

  return (
    <>
      <PageHeader title={c.name} description={[c.category, c.sub_category, c.tone].filter(Boolean).join(" · ")}
        actions={<>
          <Button variant="outline" size="sm" disabled={!!busy} onClick={() => act("relaunch", () => api.relaunch(id))}>
            {busy === "relaunch" ? <Loader2 className="animate-spin" /> : <RefreshCw />} Re-run agents
          </Button>
          {c.youtube_channel_id ? (
            <Button size="sm" disabled={!!busy || !brandReady} onClick={() => act("apply", () => api.relaunch(id, true))}>
              <Youtube /> Apply brand to YouTube
            </Button>
          ) : (
            <Button size="sm" onClick={async () => { window.location.href = (await api.oauthStart(id)).url; }}><Youtube /> Connect YouTube</Button>
          )}
        </>} />

      {!brandReady && (
        <Card className="mb-6 border-primary/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Loader2 className="size-4 animate-spin text-primary" /> Agents are building this channel</CardTitle>
            <CardDescription>Competitor analysis → brand design → schedule optimisation. Usually 1-3 minutes.</CardDescription>
          </CardHeader>
          <CardContent className="h-56"><AgentFeed className="h-full" limit={30} /></CardContent>
        </Card>
      )}

      <Tabs defaultValue="brand">
        <TabsList>
          <TabsTrigger value="brand">Brand</TabsTrigger>
          <TabsTrigger value="growth">Growth intel</TabsTrigger>
          <TabsTrigger value="calendar">Calendar</TabsTrigger>
          <TabsTrigger value="settings">Automation</TabsTrigger>
        </TabsList>

        <TabsContent value="brand" className="grid gap-6 lg:grid-cols-[1fr_380px]">
          <Card>
            <CardHeader><CardTitle>Name candidates</CardTitle><CardDescription>Scored for memorability, searchability and niche fit. Pick one to adopt it.</CardDescription></CardHeader>
            <CardContent className="space-y-2">
              {names.map((n) => (
                <button key={n.name} onClick={() => update({ name: n.name, handle: n.handle })}
                  className={cn("flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors hover:border-primary/50", c.name === n.name && "border-primary bg-primary/5")}>
                  <div className="w-10 shrink-0 text-lg font-semibold tabular-nums text-primary">{Math.round(n.score)}</div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 text-sm font-medium">{n.name}<span className="text-xs font-normal text-muted-foreground">@{n.handle}</span>
                      {c.name === n.name && <CheckCircle2 className="size-4 text-primary" />}</div>
                    <p className="mt-0.5 text-xs text-muted-foreground">{n.rationale}</p>
                  </div>
                </button>
              ))}
            </CardContent>
          </Card>
          <div className="space-y-6">
            <Card>
              <CardHeader><CardTitle>Brand kit</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  {[kit.primary_color, kit.secondary_color, kit.accent_color].filter(Boolean).map((col) => (
                    <div key={col} className="flex-1">
                      <div className="h-12 rounded-md border" style={{ background: col }} />
                      <div className="mt-1 text-center font-mono text-[11px] text-muted-foreground">{col}</div>
                    </div>
                  ))}
                </div>
                {kit.content_pillars && <div className="flex flex-wrap gap-1.5">{kit.content_pillars.map((p) => <Badge key={p} variant="outline">{p}</Badge>)}</div>}
                <Copyable label="Avatar prompt" text={kit.avatar_prompt} />
                <Copyable label="Banner prompt (2560×1440)" text={kit.banner_prompt} />
                <Copyable label="Voice guidelines" text={kit.voice_guidelines} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Channel description</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <p className="whitespace-pre-line text-sm text-muted-foreground">{c.description ?? "—"}</p>
                <div className="flex flex-wrap gap-1.5">{c.keywords.map((k) => <Badge key={k} variant="secondary">{k}</Badge>)}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>YouTube Studio checklist</CardTitle><CardDescription>The API can&apos;t set these — do them once by hand.</CardDescription></CardHeader>
              <CardContent className="space-y-1.5 text-sm">
                <a className="flex items-center gap-2 hover:text-primary" href="https://studio.youtube.com" target="_blank" rel="noreferrer">
                  Set name to <b>{c.name}</b> and handle <b>@{c.handle ?? "…"}</b> <ExternalLink className="size-3.5" />
                </a>
                <p className="text-muted-foreground">Upload the avatar generated from the prompt above.</p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="growth" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Best posting slots</CardTitle>
              <CardDescription>{c.timezone} · competitor timing prior, re-weighted daily by this channel&apos;s own 48h results.</CardDescription>
              <CardAction><Button variant="ghost" size="sm" onClick={() => api.relaunch(id)}><RefreshCw /> Recompute</Button></CardAction>
            </CardHeader>
            <CardContent><SlotHeatmap slots={c.posting_slots ?? []} /></CardContent>
          </Card>
          {comp.data?.playbook ? (
            <div className="grid gap-6 lg:grid-cols-2">
              <Card className="lg:col-span-2">
                <CardHeader><CardTitle>Competitor playbook</CardTitle><CardDescription>{comp.data.playbook.summary}</CardDescription></CardHeader>
              </Card>
              {([["Hook formats", comp.data.playbook.hook_formats], ["Title patterns", comp.data.playbook.title_patterns], ["Thumbnail patterns", comp.data.playbook.thumbnail_patterns]] as const).map(([title, items]) => (
                <Card key={title}>
                  <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
                  <CardContent className="space-y-3">
                    {items.map((p) => (
                      <div key={p.pattern} className="text-sm">
                        <div className="font-medium">{p.pattern}</div>
                        <div className="text-xs text-muted-foreground">{p.why_it_works}</div>
                        <div className="mt-1 text-xs italic text-muted-foreground/80">{p.examples.slice(0, 2).map((e) => `“${e}”`).join("  ")}</div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ))}
              <Card>
                <CardHeader><CardTitle>Content gaps to own</CardTitle></CardHeader>
                <CardContent><ul className="list-disc space-y-1.5 pl-4 text-sm">{comp.data.playbook.content_gaps.map((g) => <li key={g}>{g}</li>)}</ul></CardContent>
              </Card>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No competitor report yet (needs YOUTUBE_API_KEY).</p>
          )}
        </TabsContent>

        <TabsContent value="calendar">
          <Card>
            <CardHeader><CardTitle>Publishing calendar</CardTitle></CardHeader>
            <CardContent className="divide-y">
              {cal.data?.length === 0 && <p className="text-sm text-muted-foreground">Nothing scheduled. Approve clips in the workbench.</p>}
              {cal.data?.map((j) => (
                <div key={j.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                  <span className="tabular-nums">{new Date(j.scheduled_for + "Z").toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                  <a href={`/workbench/clip/${j.clip_id}`} className="truncate text-muted-foreground hover:text-foreground">clip {j.clip_id.slice(0, 8)}</a>
                  {j.youtube_video_id && <a className="text-xs text-primary" href={`https://youtube.com/shorts/${j.youtube_video_id}`} target="_blank" rel="noreferrer">View</a>}
                  <StatusBadge status={j.status} />
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="settings">
          <Card className="max-w-xl">
            <CardHeader><CardTitle>Automation</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {([["autopilot", "Autopilot", "Process every new source end-to-end and schedule the results."],
                 ["require_approval", "Require human approval", "Hold clips in the review queue before scheduling."]] as const).map(([key, label, hint]) => (
                <label key={key} className="flex cursor-pointer items-start gap-3 rounded-lg border p-3">
                  <input type="checkbox" className="mt-1 accent-[var(--primary)]" checked={c[key]} onChange={(e) => update({ [key]: e.target.checked })} />
                  <div><div className="text-sm font-medium">{label}</div><div className="text-xs text-muted-foreground">{hint}</div></div>
                </label>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </>
  );
}
