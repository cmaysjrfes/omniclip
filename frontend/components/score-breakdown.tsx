import type { ScoreKey } from "@/lib/types";
import { cn } from "@/lib/utils";

const LABELS: { key: ScoreKey; label: string; weight: number }[] = [
  { key: "hook_strength", label: "Hook strength", weight: 30 },
  { key: "retention_potential", label: "Retention", weight: 25 },
  { key: "standalone_value", label: "Standalone value", weight: 20 },
  { key: "emotional_intensity", label: "Emotional intensity", weight: 15 },
  { key: "shareability", label: "Shareability", weight: 10 },
];

export function scoreTone(v: number) {
  return v >= 80 ? "text-success" : v >= 60 ? "text-primary" : v >= 40 ? "text-warning" : "text-destructive";
}

export function ViralityRing({ value, size = 56 }: { value: number; size?: number }) {
  const r = size / 2 - 4, c = 2 * Math.PI * r;
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} className="fill-none stroke-muted" strokeWidth={4} />
        <circle cx={size / 2} cy={size / 2} r={r} className={cn("fill-none stroke-current transition-all", scoreTone(value))}
          strokeWidth={4} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - value / 100)} />
      </svg>
      <span className={cn("absolute text-sm font-semibold tabular-nums", scoreTone(value))}>{Math.round(value)}</span>
    </div>
  );
}

export function ScoreBreakdown({ scores, rationale }: { scores: Record<ScoreKey, number>; rationale?: string | null }) {
  return (
    <div className="space-y-3">
      {LABELS.map(({ key, label, weight }) => {
        const v = scores[key] ?? 0;
        return (
          <div key={key}>
            <div className="mb-1 flex justify-between text-xs">
              <span className="text-muted-foreground">{label} <span className="opacity-60">· {weight}%</span></span>
              <span className={cn("font-medium tabular-nums", scoreTone(v))}>{v}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-current transition-all" style={{ width: `${v}%`, color: "var(--primary)", opacity: 0.35 + v / 160 }} />
            </div>
          </div>
        );
      })}
      {rationale && <p className="border-l-2 border-primary/50 pl-3 text-xs leading-relaxed text-muted-foreground">{rationale}</p>}
    </div>
  );
}
