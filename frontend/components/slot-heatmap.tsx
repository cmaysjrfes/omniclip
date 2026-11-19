import type { Slot } from "@/lib/types";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** Weekday × hour grid of the optimiser's best posting slots (channel-local time). */
export function SlotHeatmap({ slots }: { slots: Slot[] }) {
  const score = new Map(slots.map((s) => [`${s.weekday}-${s.hour}`, s.score]));
  return (
    <div className="overflow-x-auto">
      <div className="grid min-w-[560px] grid-cols-[36px_repeat(24,1fr)] gap-[3px] text-[10px] text-muted-foreground">
        <div />
        {Array.from({ length: 24 }, (_, h) => <div key={h} className="text-center">{h % 3 === 0 ? h : ""}</div>)}
        {DAYS.map((d, wd) => (
          <div key={d} className="contents">
            <div className="self-center">{d}</div>
            {Array.from({ length: 24 }, (_, h) => {
              const v = score.get(`${wd}-${h}`);
              return (
                <div key={h} title={v !== undefined ? `${d} ${h}:00 — score ${v}` : undefined}
                  className="aspect-square rounded-[3px] bg-muted"
                  style={v !== undefined ? { background: `color-mix(in srgb, var(--primary) ${15 + v * 0.85}%, var(--muted))` } : undefined} />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
