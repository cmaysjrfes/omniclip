"use client";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { PageHeader } from "@/components/page-header";
import { SourceTable } from "@/components/source-table";
import { UploadManager } from "@/components/upload-manager";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function Uploads() {
  const { data: channels } = useApi(api.channels);
  const sources = useApi(() => api.sources(), [], 4000);
  return (
    <>
      <PageHeader title="Bulk Upload Manager" description="Queue many long-form videos at once. Each becomes 20+ scored, captioned, vertical shorts." />
      <div className="grid gap-6 lg:grid-cols-[460px_1fr]">
        <Card>
          <CardHeader><CardTitle>Add videos</CardTitle><CardDescription>Files or links, routed to a channel.</CardDescription></CardHeader>
          <CardContent><UploadManager channels={channels ?? []} onQueued={sources.refresh} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Processing</CardTitle><CardDescription>Live pipeline status.</CardDescription></CardHeader>
          <CardContent><SourceTable sources={sources.data ?? []} /></CardContent>
        </Card>
      </div>
    </>
  );
}
