"use client";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { fmtNum, timeAgo } from "@/lib/utils";
import { AgentFeed } from "@/components/agent-feed";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const AGENTS = [
  { kind: "CLIP_SCORER", name: "Clip Scorer", desc: "Finds 20+ high-retention, standalone moments per video" },
  { kind: "BRAND_ARCHITECT", name: "Brand Architect", desc: "Competitor intel → names, brand kit, posting slots" },
  { kind: "METADATA_WRITER", name: "Metadata Writer", desc: "High-CTR titles, descriptions and tags" },
  { kind: "SCHEDULE_OPTIMIZER", name: "Schedule Optimizer", desc: "Blends competitor timing with your own results" },
];

function duration(a: string | null, b: string | null) {
  if (!a || !b) return "—";
  const s = (new Date(b).getTime() - new Date(a).getTime()) / 1000;
  return s < 60 ? `${s.toFixed(0)}s` : `${(s / 60).toFixed(1)}m`;
}

export default function Agents() {
  const { data: runs } = useApi(() => api.runs(100), [], 5000);
  const by = (k: string) => (runs ?? []).filter((r) => r.kind === k);

  return (
    <>
      <PageHeader title="Agent Activity & Analytics" description="What every agent is doing, what it produced, and what it cost." />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {AGENTS.map((a) => {
          const rs = by(a.kind);
          const ok = rs.filter((r) => r.status === "SUCCEEDED").length;
          return (
            <Card key={a.kind} className="gap-2 py-4">
              <CardContent className="px-4">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">{a.name}</div>
                  {rs.some((r) => r.status === "RUNNING") && <span className="size-2 animate-pulse rounded-full bg-warning" />}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{a.desc}</p>
                <div className="mt-3 flex gap-4 text-xs tabular-nums">
                  <span><b className="text-foreground">{rs.length}</b> runs</span>
                  <span><b className="text-foreground">{rs.length ? Math.round((ok / rs.length) * 100) : 0}%</b> success</span>
                  <span><b className="text-foreground">{fmtNum(rs.reduce((n, r) => n + r.input_tokens + r.output_tokens, 0))}</b> tok</span>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_420px]">
        <Card>
          <CardHeader><CardTitle>Runs</CardTitle><CardDescription>Most recent first.</CardDescription></CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr className="border-b"><th className="py-2 font-medium">Agent</th><th className="font-medium">Status</th><th className="font-medium">Result</th><th className="font-medium">Tokens</th><th className="font-medium">Time</th><th className="text-right font-medium">When</th></tr>
              </thead>
              <tbody className="divide-y">
                {runs?.map((r) => (
                  <tr key={r.id}>
                    <td className="py-2.5">{r.kind.toLowerCase().replace(/_/g, " ")}</td>
                    <td><StatusBadge status={r.status} /></td>
                    <td className="max-w-[220px] truncate text-xs text-muted-foreground" title={r.error ?? JSON.stringify(r.output)}>
                      {r.error ?? (r.output ? Object.entries(r.output).slice(0, 2).map(([k, v]) => `${k}: ${typeof v === "object" ? "…" : v}`).join(" · ") : "—")}
                    </td>
                    <td className="tabular-nums">{fmtNum(r.input_tokens + r.output_tokens)}</td>
                    <td className="tabular-nums">{duration(r.started_at, r.finished_at)}</td>
                    <td className="text-right text-xs text-muted-foreground">{timeAgo(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
        <Card className="h-[680px]">
          <CardHeader><CardTitle>Live feed</CardTitle></CardHeader>
          <CardContent className="min-h-0 flex-1"><AgentFeed className="h-full" limit={150} /></CardContent>
        </Card>
      </div>
    </>
  );
}
