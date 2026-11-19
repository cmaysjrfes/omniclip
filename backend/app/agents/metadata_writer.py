"""Module 3 agent: high-CTR titles, search-optimised descriptions and tags for each clip.

Runs on the fast model in batches of up to 12 clips per call; limits are enforced in code
(YouTube: title <= 100 chars, tags <= 500 chars total) rather than trusted to the model.
"""
from pydantic import BaseModel, Field

from .llm import LLM

SYSTEM = """You write YouTube Shorts metadata that earns clicks honestly. Titles: under 60 \
characters when possible, curiosity or payoff-led, no clickbait the clip does not deliver, no \
ALL-CAPS sentences, at most one emoji. Descriptions: 1-3 short lines that expand the hook and \
include the main search phrase naturally, then 3-5 relevant hashtags ending with #Shorts. Tags: \
8-15 specific search phrases a viewer would type. Match the channel's tone."""


class ClipMeta(BaseModel):
    clip_id: str
    title: str
    description: str
    tags: list[str] = Field(description="8-15 search phrases")


class ClipMetaBatch(BaseModel):
    items: list[ClipMeta]


def clamp_tags(tags: list[str], budget: int = 480) -> list[str]:
    out, used = [], 0
    for t in dict.fromkeys(t.strip().lstrip("#") for t in tags if t.strip()):
        cost = len(t) + (2 if " " in t else 0) + 1  # YouTube counts quotes around multi-word tags
        if used + cost > budget:
            break
        out.append(t)
        used += cost
    return out


def write_metadata(clips: list[dict], channel: dict, playbook: dict | None, llm: LLM) -> dict[str, dict]:
    results: dict[str, dict] = {}
    ctx = (f"Channel: {channel.get('name')} | niche: {channel.get('category')} / "
           f"{channel.get('sub_category') or ''} | tone: {channel.get('tone') or 'neutral'}")
    if playbook:
        ctx += "\nTitle patterns that work in this niche:\n" + "\n".join(
            f"- {p['pattern']} (e.g. {', '.join(p['examples'][:2])})" for p in playbook.get("title_patterns", [])[:6])
    for i in range(0, len(clips), 12):
        batch = clips[i:i + 12]
        listing = "\n\n".join(
            f"<clip id=\"{c['id']}\">\nHook: {c['hook']}\nTranscript: {c['transcript'][:1500]}\n</clip>" for c in batch)
        out = llm.structured(system=SYSTEM, content=f"{ctx}\n\n{listing}\n\nWrite metadata for every clip.",
                             schema=ClipMetaBatch, effort="low", fast=True, max_tokens=16000)
        for m in out.items:
            results[m.clip_id] = {"title": m.title.strip()[:100], "description": m.description.strip()[:4900],
                                  "tags": clamp_tags(m.tags)}
    return results
