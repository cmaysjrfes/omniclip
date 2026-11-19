"""Module 2 agent: niche → channel name candidates (scored), description, keywords, brand kit."""
import re
from typing import Literal

from pydantic import BaseModel, Field

from .llm import LLM

SYSTEM = """You are a YouTube brand strategist who has launched channels that grew past 1M \
subscribers. Given a niche definition (and, when available, a competitor analysis), you design a \
channel brand that is distinctive in that niche, easy to remember and say aloud, and searchable.

Names: avoid names already used by the competitors listed, trademarked brands, and generic \
"<Topic> TV/Hub/Daily" patterns unless the twist is genuinely clever. Score each name honestly; \
the scores are used to rank them.

Description: the first 150 characters show in search, so lead with the viewer promise. Keep the \
whole description under 1000 characters and write it in the requested tone.

Art prompts are for an image model: be concrete about composition, palette (use the brand \
colours), typography area and safe zones (banner: 2560x1440 with a 1546x423 centre safe area)."""


class NameIdea(BaseModel):
    name: str
    handle: str = Field(description="suggested @handle without the @, 3-30 chars, letters/digits/._-")
    rationale: str
    memorability: int = Field(description="0-100")
    searchability: int = Field(description="0-100")
    niche_fit: int = Field(description="0-100")


class BrandKit(BaseModel):
    primary_color: str = Field(description="hex #RRGGBB")
    secondary_color: str = Field(description="hex #RRGGBB")
    accent_color: str = Field(description="hex #RRGGBB")
    font_pairing: str
    caption_preset: Literal["bold_pop", "minimal", "neon"]
    avatar_prompt: str
    banner_prompt: str
    thumbnail_style: str
    voice_guidelines: str
    content_pillars: list[str]


class BrandPackage(BaseModel):
    names: list[NameIdea] = Field(description="10-15 candidates")
    description: str
    keywords: list[str] = Field(description="10-20 channel keywords / short phrases")
    brand_kit: BrandKit


def _handle(h: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "", h.lstrip("@"))[:30]


def generate_brand(niche: dict, competitor_report: dict | None, llm: LLM) -> dict:
    lines = [f"Category: {niche['category']}"]
    for key, label in [("sub_category", "Sub-category"), ("niche_description", "Niche"),
                       ("tone", "Tone"), ("target_audience", "Audience")]:
        if niche.get(key):
            lines.append(f"{label}: {niche[key]}")
    prompt = "<niche>\n" + "\n".join(lines) + "\n</niche>"
    if competitor_report:
        prompt += f"\n\n<competitor_analysis>\n{competitor_report}\n</competitor_analysis>"
    prompt += "\n\nDesign the channel brand."

    pkg = llm.structured(system=SYSTEM, content=prompt, schema=BrandPackage, effort="high")
    names = []
    for n in pkg.names:
        score = round(0.4 * n.memorability + 0.3 * n.niche_fit + 0.3 * n.searchability, 1)
        names.append({**n.model_dump(), "handle": _handle(n.handle), "score": score})
    names.sort(key=lambda n: n["score"], reverse=True)
    return {
        "names": names,
        "recommended": names[0] if names else None,
        "description": pkg.description[:1000],
        "keywords": pkg.keywords[:20],
        "brand_kit": pkg.brand_kit.model_dump(),
    }
