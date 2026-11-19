"""Module 3 agent: competitor & trend analysis.

Data comes from the official YouTube Data API (not HTML scraping — scraping violates YouTube's
ToS and breaks constantly). Quota note: search.list costs 100 units of the default 10,000/day,
so one analysis (~3 searches + cheap list calls) costs ~350 units.

Deterministic stats are computed in code; Claude (with vision on top thumbnails) turns them
into a playbook: hook formats, title patterns, thumbnail patterns, pacing, content gaps.
"""
import re
import statistics
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.integrations import youtube

from .llm import LLM

SYSTEM = """You are a YouTube growth analyst. You receive hard data about the top channels and \
their best recent videos in a niche, plus a sample of top thumbnails. Extract what is actually \
working — be specific and evidence-based (cite example titles), and call out content gaps a new \
channel could own. Do not invent numbers that are not in the data."""


class Pattern(BaseModel):
    pattern: str
    examples: list[str]
    why_it_works: str


class CompetitorPlaybook(BaseModel):
    summary: str
    hook_formats: list[Pattern]
    title_patterns: list[Pattern]
    thumbnail_patterns: list[Pattern]
    pacing_and_structure: list[str]
    content_gaps: list[str]
    recommended_shorts_ratio: float = Field(description="0-1 share of output that should be Shorts")


_ISO_DUR = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def iso_duration_sec(s: str) -> int:
    m = _ISO_DUR.fullmatch(s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def title_features(title: str) -> dict:
    return {
        "has_number": bool(re.search(r"\d", title)),
        "is_question": title.strip().endswith("?"),
        "has_caps_word": bool(re.search(r"\b[A-Z]{3,}\b", title)),
        "length": len(title),
    }


def video_stats(videos: list[dict], now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    out = []
    for v in videos:
        published = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
        age_days = max((now - published).total_seconds() / 86400, 0.5)
        views = int(v.get("statistics", {}).get("viewCount", 0))
        dur = iso_duration_sec(v.get("contentDetails", {}).get("duration", ""))
        out.append({
            "id": v["id"], "channel": v["snippet"]["channelTitle"], "title": v["snippet"]["title"],
            "published_at": published.isoformat(), "weekday": published.weekday(), "hour_utc": published.hour,
            "duration_sec": dur, "is_short": 0 < dur <= 180, "views": views,
            "views_per_day": round(views / age_days, 1),
            "likes": int(v.get("statistics", {}).get("likeCount", 0)),
            "comments": int(v.get("statistics", {}).get("commentCount", 0)),
            "thumbnail": v["snippet"].get("thumbnails", {}).get("high", {}).get("url"),
            **title_features(v["snippet"]["title"]),
        })
    return out


def analyze_niche(queries: list[str], llm: LLM, log=lambda *_a, **_k: None, max_channels: int = 12) -> dict:
    yt = youtube.public_client()
    channel_ids: list[str] = []
    for q in queries[:3]:
        res = yt.search().list(part="snippet", q=q, type="channel", maxResults=10, order="relevance").execute()
        channel_ids += [i["snippet"]["channelId"] for i in res.get("items", [])]
    channel_ids = list(dict.fromkeys(channel_ids))[:max_channels * 2]
    log(f"Found {len(channel_ids)} candidate channels for {queries[:3]}")

    chans = yt.channels().list(part="snippet,statistics,contentDetails", id=",".join(channel_ids)).execute()
    channels = sorted(chans.get("items", []), key=lambda c: int(c["statistics"].get("subscriberCount", 0)),
                      reverse=True)[:max_channels]

    video_ids: list[str] = []
    for c in channels:
        uploads = c["contentDetails"]["relatedPlaylists"]["uploads"]
        items = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=25).execute()
        video_ids += [i["contentDetails"]["videoId"] for i in items.get("items", [])]
    videos: list[dict] = []
    for i in range(0, len(video_ids), 50):
        videos += yt.videos().list(part="snippet,statistics,contentDetails",
                                   id=",".join(video_ids[i:i + 50])).execute().get("items", [])
    stats = video_stats(videos)
    log(f"Pulled stats for {len(stats)} recent videos across {len(channels)} channels")

    top = sorted(stats, key=lambda v: v["views_per_day"], reverse=True)[:40]
    shorts = [v for v in stats if v["is_short"]]
    aggregate = {
        "channels": [{"title": c["snippet"]["title"], "id": c["id"],
                      "subscribers": int(c["statistics"].get("subscriberCount", 0)),
                      "videos": int(c["statistics"].get("videoCount", 0))} for c in channels],
        "shorts_share": round(len(shorts) / len(stats), 2) if stats else 0,
        "median_short_views_per_day": statistics.median([v["views_per_day"] for v in shorts]) if shorts else 0,
        "median_title_length_top": statistics.median([v["length"] for v in top]) if top else 0,
    }

    table = "\n".join(
        f"- [{v['channel']}] \"{v['title']}\" | {v['views_per_day']}/day | {v['duration_sec']}s"
        f"{' | SHORT' if v['is_short'] else ''}" for v in top)
    content: list = [{"type": "text", "text": f"<aggregate>\n{aggregate}\n</aggregate>\n\n"
                                               f"<top_videos_by_views_per_day>\n{table}\n</top_videos_by_views_per_day>\n\n"
                                               "Thumbnails of the top 8 videos follow."}]
    for v in top[:8]:
        if v["thumbnail"]:
            content.append({"type": "image", "source": {"type": "url", "url": v["thumbnail"]}})
    content.append({"type": "text", "text": "Produce the competitor playbook."})

    playbook = llm.structured(system=SYSTEM, content=content, schema=CompetitorPlaybook, effort="high")
    return {"aggregate": aggregate, "top_videos": top, "uploads": stats, "playbook": playbook.model_dump()}
