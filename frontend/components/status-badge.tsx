import { Badge } from "@/components/ui/badge";

const MAP: Record<string, "success" | "warning" | "destructive" | "secondary" | "outline" | "default"> = {
  READY: "success", RENDERED: "default", APPROVED: "success", PUBLISHED: "success", SUCCEEDED: "success",
  SCHEDULED: "outline", CANDIDATE: "secondary", QUEUED: "secondary", PENDING: "secondary",
  RENDERING: "warning", DOWNLOADING: "warning", TRANSCRIBING: "warning", ANALYZING: "warning", RUNNING: "warning", UPLOADING: "warning",
  REJECTED: "destructive", FAILED: "destructive",
};
const LABEL: Record<string, string> = { RENDERED: "Needs review" };

export function StatusBadge({ status }: { status: string }) {
  return <Badge variant={MAP[status] ?? "outline"}>{LABEL[status] ?? status.charAt(0) + status.slice(1).toLowerCase()}</Badge>;
}
