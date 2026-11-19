"""Deterministic transcript utilities around the LLM clip scorer.

The LLM picks moments by sentence index; everything here (sentence building, windowing,
boundary snapping, de-duplication, ranking) is plain code so it is testable and cheap.
"""
from dataclasses import dataclass

SENTENCE_END = (".", "?", "!", "…")

# Composite weights for the five 0-100 sub-scores the scorer returns.
SCORE_WEIGHTS = {
    "hook_strength": 0.30,
    "retention_potential": 0.25,
    "standalone_value": 0.20,
    "emotional_intensity": 0.15,
    "shareability": 0.10,
}


@dataclass
class Sentence:
    idx: int
    start: float
    end: float
    text: str
    w0: int  # first word index (inclusive)
    w1: int  # last word index (exclusive)


def build_sentences(words: list[dict], max_gap: float = 0.9, max_sec: float = 14.0) -> list[Sentence]:
    """Group words into sentence-ish units: split on punctuation, long pauses, or length."""
    out: list[Sentence] = []
    start_i = 0
    for i, w in enumerate(words):
        last = i == len(words) - 1
        gap = (words[i + 1]["s"] - w["e"]) if not last else 0.0
        too_long = w["e"] - words[start_i]["s"] >= max_sec
        if last or w["w"].endswith(SENTENCE_END) or gap >= max_gap or too_long:
            chunk = words[start_i:i + 1]
            out.append(Sentence(len(out), chunk[0]["s"], chunk[-1]["e"],
                                " ".join(x["w"] for x in chunk), start_i, i + 1))
            start_i = i + 1
    return out


def fmt_ts(sec: float) -> str:
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_for_llm(sentences: list[Sentence]) -> str:
    return "\n".join(f"[{s.idx}] ({fmt_ts(s.start)}) {s.text}" for s in sentences)


def windows(sentences: list[Sentence], window_sec: float = 1500, overlap_sec: float = 120) -> list[list[Sentence]]:
    """Split long transcripts so each LLM call sees a focused span; overlap avoids
    cutting a great moment in half at a window boundary."""
    if not sentences:
        return []
    out, i = [], 0
    while i < len(sentences):
        w_start = sentences[i].start
        j = i
        while j < len(sentences) and sentences[j].end - w_start <= window_sec:
            j += 1
        j = max(j, i + 1)
        out.append(sentences[i:j])
        if j >= len(sentences):
            break
        back_to = sentences[j - 1].end - overlap_sec
        k = j
        while k > i + 1 and sentences[k - 1].start > back_to:
            k -= 1
        i = k
    return out


def snap(start_idx: int, end_idx: int, sentences: list[Sentence], min_sec: float, max_sec: float) -> tuple[int, int] | None:
    """Clamp an LLM-proposed sentence range into [min_sec, max_sec], on sentence boundaries."""
    n = len(sentences)
    if n == 0:
        return None
    a, b = max(0, min(start_idx, end_idx)), min(n - 1, max(start_idx, end_idx))
    while b > a and sentences[b].end - sentences[a].start > max_sec:
        b -= 1
    if sentences[b].end - sentences[a].start > max_sec:  # one giant sentence
        return None
    while sentences[b].end - sentences[a].start < min_sec and b < n - 1 \
            and sentences[b + 1].end - sentences[a].start <= max_sec:
        b += 1
    if sentences[b].end - sentences[a].start < min_sec:
        return None
    return a, b


def composite(scores: dict[str, float]) -> float:
    return round(sum(scores.get(k, 0.0) * w for k, w in SCORE_WEIGHTS.items()), 2)


def iou(a: tuple[float, float], b: tuple[float, float]) -> float:
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0


def dedupe(cands: list[dict], threshold: float = 0.45) -> list[dict]:
    """Non-max suppression over time ranges: keep the best-scoring of overlapping clips."""
    kept: list[dict] = []
    for c in sorted(cands, key=lambda c: c["virality_score"], reverse=True):
        if all(iou((c["start"], c["end"]), (k["start"], k["end"])) < threshold for k in kept):
            kept.append(c)
    return kept
