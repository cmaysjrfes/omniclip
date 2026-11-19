"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export interface NicheValue {
  category: string; sub_category: string; niche_description: string; tone: string; target_audience: string;
}

const TONES = ["Educational", "Energetic", "Calm & premium", "Witty", "Contrarian", "Inspirational"];

/** Tier 1 category → tier 2 sub-category chips, plus free-form niche, tone and audience. */
export function NicheSelector({ value, onChange }: { value: NicheValue; onChange: (v: NicheValue) => void }) {
  const [tree, setTree] = useState<Record<string, string[]>>({});
  useEffect(() => { api.taxonomy().then(setTree).catch(() => {}); }, []);
  const set = (patch: Partial<NicheValue>) => onChange({ ...value, ...patch });

  return (
    <div className="space-y-6">
      <div>
        <Label className="mb-2.5">Category</Label>
        <div className="flex flex-wrap gap-2">
          {Object.keys(tree).map((c) => (
            <button key={c} type="button" onClick={() => set({ category: c, sub_category: "" })}
              className={cn("rounded-full border px-3 py-1.5 text-sm transition-colors hover:border-primary/60",
                value.category === c && "border-primary bg-primary/10 text-primary")}>{c}</button>
          ))}
        </div>
      </div>
      {value.category && (
        <div>
          <Label className="mb-2.5">Sub-category</Label>
          <div className="flex flex-wrap gap-2">
            {(tree[value.category] ?? []).map((s) => (
              <button key={s} type="button" onClick={() => set({ sub_category: s })}
                className={cn("rounded-full border px-3 py-1 text-xs transition-colors hover:border-primary/60",
                  value.sub_category === s && "border-primary bg-primary/10 text-primary")}>{s}</button>
            ))}
          </div>
        </div>
      )}
      <div className="space-y-2">
        <Label htmlFor="niche">Describe the exact niche</Label>
        <Textarea id="niche" rows={4} value={value.niche_description} onChange={(e) => set({ niche_description: e.target.value })}
          placeholder="e.g. Index-fund investing for people in their 20s who feel behind — myth-busting, simple maths, no hype." />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label>Tone</Label>
          <div className="flex flex-wrap gap-1.5">
            {TONES.map((t) => (
              <button key={t} type="button" onClick={() => set({ tone: t })}
                className={cn("rounded-md border px-2.5 py-1 text-xs", value.tone === t && "border-primary text-primary")}>{t}</button>
            ))}
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="aud">Target audience</Label>
          <Input id="aud" value={value.target_audience} onChange={(e) => set({ target_audience: e.target.value })}
            placeholder="22-30, early career, US/UK" />
        </div>
      </div>
    </div>
  );
}
