"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { NicheSelector, type NicheValue } from "@/components/niche-selector";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const MODES = [
  { id: "review", label: "Autopilot with review", desc: "Agents clip, write and schedule; a human approves each short.", autopilot: true, require_approval: true },
  { id: "hands_free", label: "Hands-free", desc: "Clips scoring 70+ are approved and published automatically.", autopilot: true, require_approval: false },
  { id: "manual", label: "Manual", desc: "Agents suggest; you decide everything.", autopilot: false, require_approval: true },
];

export default function NewChannel() {
  const router = useRouter();
  const [niche, setNiche] = useState<NicheValue>({ category: "", sub_category: "", niche_description: "", tone: "", target_audience: "" });
  const [mode, setMode] = useState("review");
  const [postsPerDay, setPostsPerDay] = useState(3);
  const [tz] = useState(() => Intl.DateTimeFormat().resolvedOptions().timeZone);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const submit = async () => {
    setBusy(true);
    setError(undefined);
    const m = MODES.find((x) => x.id === mode)!;
    try {
      const ch = await api.createChannel({
        ...niche, sub_category: niche.sub_category || null, name: "Untitled channel", timezone: tz,
        posts_per_day: postsPerDay, autopilot: m.autopilot, require_approval: m.require_approval,
      });
      router.push(`/channels/${ch.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Launch a channel" description="Define the niche. Agents analyse competitors, then design the name, brand kit and posting schedule." />
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <Card>
          <CardHeader><CardTitle>Niche</CardTitle><CardDescription>The more specific, the sharper the brand.</CardDescription></CardHeader>
          <CardContent><NicheSelector value={niche} onChange={setNiche} /></CardContent>
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Automation</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {MODES.map((m) => (
                <button key={m.id} type="button" onClick={() => setMode(m.id)}
                  className={cn("w-full rounded-lg border p-3 text-left transition-colors", mode === m.id && "border-primary bg-primary/5")}>
                  <div className="text-sm font-medium">{m.label}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">{m.desc}</div>
                </button>
              ))}
              <div className="space-y-2 pt-3">
                <Label htmlFor="ppd">Shorts per day</Label>
                <Input id="ppd" type="number" min={1} max={12} value={postsPerDay} onChange={(e) => setPostsPerDay(Number(e.target.value))} />
                <p className="text-xs text-muted-foreground">Schedule in {tz}.</p>
              </div>
            </CardContent>
          </Card>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button className="w-full" size="lg" disabled={!niche.category || busy} onClick={submit}>
            {busy ? <Loader2 className="animate-spin" /> : <Sparkles />} Run brand agents
          </Button>
        </div>
      </div>
    </>
  );
}
