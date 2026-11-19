"""Module 3: algorithmic posting-time optimiser (deterministic — no LLM needed).

Scores each (weekday, hour) slot in the channel's timezone by blending:
  * a competitor prior: how well uploads in that slot performed (views/day, log-scaled), and
  * the channel's own results: 48h views of its published clips by slot,
with the own-data weight growing as evidence accumulates (empirical-Bayes style shrinkage).

Note: YouTube Studio's "When your viewers are on YouTube" heat-map is not exposed by the
public APIs, so we infer it from performance instead.
"""
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

PRIOR_STRENGTH = 8.0  # own-data samples needed before it outweighs the competitor prior


def _slot_means(samples: list[tuple[int, int, float]]) -> tuple[dict, dict]:
    sums, counts = defaultdict(float), defaultdict(int)
    for wd, hr, val in samples:
        sums[(wd, hr)] += val
        counts[(wd, hr)] += 1
    return {k: sums[k] / counts[k] for k in sums}, counts


def _smooth(means: dict[tuple[int, int], float]) -> dict[tuple[int, int], float]:
    """Neighbouring hours share signal (a great 18:00 says something about 17:00 and 19:00)."""
    if not means:
        return {}
    base = min(means.values())  # a hole counts as "no better than the worst observed slot"
    out = {}
    for wd in range(7):
        for hr in range(24):
            keys = [(wd, (hr + dh) % 24) for dh in (-1, 0, 1)]
            if any(k in means for k in keys):
                out[(wd, hr)] = sum(means.get(k, base) * w for k, w in zip(keys, (0.25, 0.5, 0.25)))
    return out


def to_local(ts_utc: datetime, tz: str) -> datetime:
    if ts_utc.tzinfo is None:
        ts_utc = ts_utc.replace(tzinfo=timezone.utc)
    return ts_utc.astimezone(ZoneInfo(tz))


def rank_slots(competitor_uploads: list[dict], own_results: list[dict], tz: str, top_n: int = 21) -> list[dict]:
    """competitor_uploads: [{published_at (iso), views_per_day}], own_results: [{published_at, views_48h}]"""
    comp = []
    for u in competitor_uploads:
        local = to_local(datetime.fromisoformat(u["published_at"]), tz)
        comp.append((local.weekday(), local.hour, math.log1p(u["views_per_day"])))
    own = []
    for r in own_results:
        local = to_local(datetime.fromisoformat(r["published_at"]), tz)
        own.append((local.weekday(), local.hour, math.log1p(r["views_48h"])))

    comp_means, _ = _slot_means(comp)
    own_means, own_counts = _slot_means(own)
    comp_s, own_s = _smooth(comp_means), _smooth(own_means)

    def norm(d: dict) -> dict:
        if not d:
            return {}
        lo, hi = min(d.values()), max(d.values())
        return {k: (v - lo) / (hi - lo) if hi > lo else 0.5 for k, v in d.items()}

    comp_n, own_n = norm(comp_s), norm(own_s)
    slots = []
    for wd in range(7):
        for hr in range(24):
            prior = comp_n.get((wd, hr), 0.0)
            n = own_counts.get((wd, hr), 0)
            w = n / (n + PRIOR_STRENGTH)
            score = (1 - w) * prior + w * own_n.get((wd, hr), prior)
            slots.append({"weekday": wd, "hour": hr, "minute": 0, "score": round(score * 100, 1),
                          "evidence": {"competitor": round(prior, 3), "own_samples": n}})
    slots.sort(key=lambda s: s["score"], reverse=True)
    return slots[:top_n]


def next_publish_times(slots: list[dict], *, tz: str, count: int, after: datetime,
                       taken: list[datetime] | None = None, posts_per_day: int = 3,
                       min_gap_hours: float = 3.0) -> list[datetime]:
    """Walk forward hour by hour from `after`, filling the best-scoring slots while respecting
    a daily cap and minimum spacing. Returns naive UTC datetimes."""
    if not slots:
        slots = [{"weekday": d, "hour": h, "minute": 0, "score": 50}
                 for d in range(7) for h in (12, 17, 20)]
    good = {(s["weekday"], s["hour"]): s for s in slots}
    zone = ZoneInfo(tz)
    taken_local = [to_local(t, tz) for t in (taken or [])]
    picked: list[datetime] = []
    cursor = to_local(after, tz).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    horizon = cursor + timedelta(days=60)
    while len(picked) < count and cursor < horizon:
        slot = good.get((cursor.weekday(), cursor.hour))
        if slot:
            candidate = cursor.replace(minute=slot.get("minute", 0))
            all_times = taken_local + picked
            same_day = sum(1 for t in all_times if t.date() == candidate.date())
            spaced = all(abs((t - candidate).total_seconds()) >= min_gap_hours * 3600 for t in all_times)
            if same_day < posts_per_day and spaced:
                picked.append(candidate)
        cursor += timedelta(hours=1)
    return [p.astimezone(timezone.utc).replace(tzinfo=None) for p in picked]
