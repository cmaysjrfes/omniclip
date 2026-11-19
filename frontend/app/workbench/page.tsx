"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { ClipCard } from "@/components/clip-card";
import { PageHeader } from "@/components/page-header";
import { SourceTable } from "@/components/source-table";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function Workbench() {
  const { data: sources } = useApi(() => api.sources(), [], 5000);
  const queue = useApi(() => api.clips({ status: "RENDERED", limit: "60" }), [], 10000);
  const [busy, setBusy] = useState(false);

  const review = async (id: string, action: "approve" | "reject") => {
    queue.setData((cs) => cs?.filter((c) => c.id !== id));
    await api.review(id, action).catch(queue.refresh);
  };
  const approveTop = async () => {
    const ids = (queue.data ?? []).filter((c) => c.virality_score >= 75).map((c) => c.id);
    if (!ids.length) return;
    setBusy(true);
    await api.bulkReview(ids, "approve").finally(() => { setBusy(false); queue.refresh(); });
  };

  return (
    <>
      <PageHeader title="Clipping Workbench" description="Review AI-selected moments, trim, restyle and approve for publishing."
        actions={<Button asChild><Link href="/uploads">Add videos</Link></Button>} />
      <Tabs defaultValue="queue">
        <TabsList>
          <TabsTrigger value="queue">Review queue {queue.data ? `(${queue.data.length})` : ""}</TabsTrigger>
          <TabsTrigger value="sources">Source videos</TabsTrigger>
        </TabsList>
        <TabsContent value="queue">
          <div className="mb-4 flex items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">Highest virality score first. Approved clips are scheduled into the channel&apos;s best slots.</p>
            <Button variant="outline" size="sm" disabled={busy} onClick={approveTop}>Approve all ≥ 75</Button>
          </div>
          {queue.data?.length === 0 && <p className="py-16 text-center text-sm text-muted-foreground">Nothing waiting for review.</p>}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {queue.data?.map((c) => <ClipCard key={c.id} clip={c} onReview={review} />)}
          </div>
        </TabsContent>
        <TabsContent value="sources"><SourceTable sources={sources ?? []} /></TabsContent>
      </Tabs>
    </>
  );
}
