"""Module 1 agent: find 20+ standalone, high-retention short-form moments in a transcript."""
import math
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, Field

from app.pipeline import segment

from .llm import LLM

SYSTEM = """You are the head of short-form strategy for a media team that turns long videos into \
YouTube Shorts. You read a timestamped transcript (one numbered sentence per line) and choose the \
moments most likely to hold a cold viewer who is scrolling.

A strong moment:
- opens with a hook in its first sentence or two: a bold claim, a surprising number, tension, \
a question, or a story already in motion — never a preamble like "so, um, anyway";
- is self-contained: a viewer with no context understands it and gets a payoff (insight, laugh, \
twist, emotional beat) before it ends;
- ends on a natural landing, not mid-thought;
- fits in roughly {min_s}-{max_s} seconds of speech.

Score each sub-score from 0 to 100 and be discriminating — reserve 85+ for moments you would \
bet the channel on. Moments must not substantially overlap one another. The `hook` field is the \
on-screen text shown during the first 3 seconds: at most 8 words, punchy, and true to what is said."""


class MomentScores(BaseModel):
    hook_strength: int = Field(description="0-100: does the opening stop the scroll?")
    emotional_intensity: int = Field(description="0-100: energy, conflict, humour, vulnerability")
    standalone_value: int = Field(description="0-100: makes sense and pays off without context")
    retention_potential: int = Field(description="0-100: will viewers watch to the end / rewatch?")
    shareability: int = Field(description="0-100: would someone send this to a friend?")


class Moment(BaseModel):
    start_sentence: int = Field(description="index of the first sentence, from the [n] markers")
    end_sentence: int = Field(description="index of the last sentence (inclusive)")
    hook: str
    title_idea: str
    category: str = Field(description="e.g. insight, story, controversy, humor, tutorial, emotional")
    rationale: str = Field(description="one or two sentences on why this will perform")
    scores: MomentScores


class MomentList(BaseModel):
    moments: list[Moment]


def _clamp_scores(s: MomentScores) -> dict[str, float]:
    return {k: float(min(max(v, 0), 100)) for k, v in s.model_dump().items()}


def score_transcript(transcript: dict, *, target: int, niche: str | None, llm: LLM,
                     min_sec: float, max_sec: float, log=lambda *_a, **_k: None) -> list[dict]:
    sentences = segment.build_sentences(transcript["words"])
    wins = segment.windows(sentences)
    if not wins:
        return []
    # Over-generate (~1.6x) so de-duplication and length snapping still leave >= target.
    per_window = max(4, math.ceil(target * 1.6 / len(wins)))
    log(f"Scoring {len(sentences)} sentences across {len(wins)} window(s), {per_window} candidates each")

    system = SYSTEM.format(min_s=int(min_sec), max_s=int(max_sec))

    def run(window: list[segment.Sentence]) -> list[Moment]:
        prompt = (
            (f"Channel niche: {niche}\n\n" if niche else "")
            + f"Return the {per_window} best moments in this section.\n\n<transcript>\n"
            + segment.format_for_llm(window) + "\n</transcript>"
        )
        return llm.structured(system=system, content=prompt, schema=MomentList, effort="high").moments

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run, wins))

    candidates: list[dict] = []
    for moments in results:
        for m in moments:
            snapped = segment.snap(m.start_sentence, m.end_sentence, sentences, min_sec, max_sec)
            if snapped is None:
                continue
            a, b = snapped
            scores = _clamp_scores(m.scores)
            candidates.append({
                "start": sentences[a].start, "end": sentences[b].end,
                "transcript": " ".join(s.text for s in sentences[a:b + 1]),
                "hook": m.hook.strip(), "title_idea": m.title_idea, "category": m.category,
                "rationale": m.rationale, "scores": scores,
                "virality_score": segment.composite(scores),
            })
    kept = segment.dedupe(candidates)[:target]
    log(f"{len(candidates)} candidates → {len(kept)} after de-duplication", data={"target": target})
    return kept
