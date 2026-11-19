"use client";
import Link from "next/link";
import { ArrowRight, Bot, Clapperboard, Eye, Radio, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { fmtNum } from "@/lib/utils";
import { AgentFeed } from "@/components/agent-feed";
import { PageHeader } from "@/components/page-header";
import { SourceTable } from "@/components/source-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

function Stat({ label, value, icon: Icon, hint }: { label: string; value: string | number; icon: typeof Eye; hint?: string }) {
  return (
    <Card className="gap-2 py-4">
      <CardContent className="px-4">
        <div className="flex items-center justify-between text-xs text-muted-foreground">{label}<Icon className="size-4" /></div>
        <div className="mt-1.5 text-2xl font-semibold tabular-nums">{value}</div>
        {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
      </CardContent>
    </Card>
  );
}

export default function CommandCenter() {
  const { data: o } = useApi(api.overview, [], 15000);
  const { data: channels } = useApi(api.channels);
  const { data: sources } = useApi(() => api.sources(), [], 5000);

  return (
    <>
      <PageHeader title="Channel Command Center" description="Every channel, pipeline and agent at a glance."
        actions={<>
          <Button variant="outline" asChild><Link href="/channels/new"><Sparkles /> Launch channel</Link></Button>
          <Button asChild><Link href="/uploads">Upload video</Link></Button>
        </>} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Awaiting review" value={o?.awaiting_review ?? "–"} icon={Clapperboard} hint="rendered clips" />
        <Stat label="Scheduled" value={o?.clips_by_status?.SCHEDULED ?? 0} icon={Radio} hint={`${o?.clips_by_status?.PUBLISHED ?? 0} published`} />
        <Stat label="Views (tracked)" value={o ? fmtNum(o.total_views) : "–"} icon={Eye} hint="last 30 days of uploads" />
        <Stat label="Agent runs · 7d" value={o?.agent_runs_7d ?? "–"} icon={Bot} hint={o ? `${fmtNum(o.tokens_7d)} tokens` : undefined} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_380px]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Channels</CardTitle>
              <CardDescription>Niche, automation mode and YouTube connection.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              {channels?.length === 0 && <p className="text-sm text-muted-foreground">No channels yet — launch one to let the agents design the brand.</p>}
              {channels?.map((c) => (
                <Link key={c.id} href={`/channels/${c.id}`} className="group rounded-lg border p-3.5 transition-colors hover:border-primary/50">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <div className="size-8 rounded-md" style={{ background: c.brand_kit?.primary_color ?? "var(--muted)" }} />
                      <div>
                        <div className="text-sm font-medium">{c.name}</div>
                        <div className="text-xs text-muted-foreground">{c.sub_category ?? c.category}</div>
                      </div>
                    </div>
                    <ArrowRight className="size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <Badge variant={c.youtube_channel_id ? "success" : "secondary"}>{c.youtube_channel_id ? "YouTube connected" : "Not connected"}</Badge>
                    {c.autopilot && <Badge variant="outline">{c.require_approval ? "Autopilot · review" : "Hands-free"}</Badge>}
                    <Badge variant="outline">{c.posts_per_day}/day</Badge>
                  </div>
                </Link>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Pipelines</CardTitle>
              <CardDescription>Long-form videos moving through ingest → transcribe → score → render.</CardDescription>
              <CardAction><Button variant="ghost" size="sm" asChild><Link href="/workbench">All <ArrowRight /></Link></Button></CardAction>
            </CardHeader>
            <CardContent><SourceTable sources={(sources ?? []).slice(0, 6)} /></CardContent>
          </Card>
        </div>

        <Card className="h-[640px] lg:sticky lg:top-6">
          <CardHeader>
            <CardTitle>Agent activity</CardTitle>
            <CardAction><Button variant="ghost" size="sm" asChild><Link href="/agents">Open</Link></Button></CardAction>
          </CardHeader>
          <CardContent className="min-h-0 flex-1"><AgentFeed className="h-full" limit={40} /></CardContent>
        </Card>
      </div>
    </>
  );
}
