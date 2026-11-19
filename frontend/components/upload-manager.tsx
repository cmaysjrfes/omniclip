"use client";
import { useCallback, useState } from "react";
import { FileVideo, Link2, Loader2, UploadCloud } from "lucide-react";
import { api, putWithProgress } from "@/lib/api";
import type { Channel } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";

interface QueueItem { id: string; name: string; progress: number; state: "uploading" | "queued" | "error"; error?: string }

/** Multi-file + multi-link ingestion. Files go browser → object storage via presigned PUT. */
export function UploadManager({ channels, onQueued }: { channels: Channel[]; onQueued?: () => void }) {
  const [channelId, setChannelId] = useState("");
  const [target, setTarget] = useState(24);
  const [links, setLinks] = useState("");
  const [items, setItems] = useState<QueueItem[]>([]);
  const [over, setOver] = useState(false);
  const patch = (id: string, p: Partial<QueueItem>) => setItems((xs) => xs.map((x) => (x.id === id ? { ...x, ...p } : x)));

  const uploadFiles = useCallback(async (files: File[]) => {
    const vids = files.filter((f) => f.type.startsWith("video/"));
    const queued = vids.map((f) => ({ id: crypto.randomUUID(), name: f.name, progress: 0, state: "uploading" as const }));
    setItems((xs) => [...queued, ...xs]);
    await Promise.all(vids.map(async (file, i) => {
      const id = queued[i].id;
      try {
        const { storage_key, upload_url } = await api.uploadUrl(file.name, file.type);
        await putWithProgress(upload_url, file, (p) => patch(id, { progress: p }));
        await api.createSource({ storage_key, channel_id: channelId || null, title: file.name, target_clips: target });
        patch(id, { state: "queued", progress: 100 });
        onQueued?.();
      } catch (e) {
        patch(id, { state: "error", error: (e as Error).message });
      }
    }));
  }, [channelId, target, onQueued]);

  const submitLinks = async () => {
    const urls = links.split(/\s+/).filter((u) => /^https?:\/\//.test(u));
    for (const url of urls) {
      const id = crypto.randomUUID();
      setItems((xs) => [{ id, name: url, progress: 100, state: "uploading" }, ...xs]);
      try {
        await api.createSource({ url, channel_id: channelId || null, target_clips: target });
        patch(id, { state: "queued" });
      } catch (e) {
        patch(id, { state: "error", error: (e as Error).message });
      }
    }
    setLinks("");
    onQueued?.();
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="ch">Publish to channel</Label>
          <select id="ch" value={channelId} onChange={(e) => setChannelId(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-input/30 px-3 text-sm">
            <option value="">No channel (clip only)</option>
            {channels.map((c) => <option key={c.id} value={c.id}>{c.name}{c.autopilot ? " · autopilot" : ""}</option>)}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="target">Shorts per video</Label>
          <Input id="target" type="number" min={1} max={60} value={target} onChange={(e) => setTarget(Number(e.target.value))} />
        </div>
      </div>

      <label onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); uploadFiles(Array.from(e.dataTransfer.files)); }}
        className={cn("flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors",
          over ? "border-primary bg-primary/5" : "hover:border-primary/50")}>
        <UploadCloud className="size-8 text-muted-foreground" />
        <div className="text-sm font-medium">Drop long-form videos here, or click to browse</div>
        <div className="text-xs text-muted-foreground">MP4 / MOV / MKV · multiple files · uploaded directly to storage</div>
        <input type="file" accept="video/*" multiple className="hidden" onChange={(e) => uploadFiles(Array.from(e.target.files ?? []))} />
      </label>

      <div className="space-y-2">
        <Label htmlFor="links" className="gap-1.5"><Link2 className="size-3.5" /> Or paste links (one per line)</Label>
        <Textarea id="links" rows={3} value={links} onChange={(e) => setLinks(e.target.value)}
          placeholder="https://www.youtube.com/watch?v=… (videos your team owns or has rights to)" />
        <Button onClick={submitLinks} disabled={!links.trim()} size="sm">Queue links</Button>
      </div>

      {items.length > 0 && (
        <ul className="divide-y rounded-lg border">
          {items.map((it) => (
            <li key={it.id} className="flex items-center gap-3 px-3 py-2.5 text-sm">
              {it.state === "uploading" ? <Loader2 className="size-4 animate-spin text-muted-foreground" /> : <FileVideo className="size-4 text-muted-foreground" />}
              <div className="min-w-0 flex-1">
                <div className="truncate">{it.name}</div>
                {it.state === "uploading" && <Progress value={it.progress} className="mt-1.5" />}
                {it.error && <div className="text-xs text-destructive">{it.error}</div>}
              </div>
              <span className={cn("text-xs", it.state === "queued" ? "text-success" : "text-muted-foreground")}>
                {it.state === "queued" ? "In pipeline" : it.state === "error" ? "Failed" : `${it.progress}%`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
