"""YouTube Data API v3 integration: OAuth, uploads (with scheduled publishAt), branding, stats.

API realities to plan around:
* Channels cannot be *created* via the API. A team member creates the channel (or Brand
  Account) once in YouTube Studio and connects it here via OAuth; agents then manage it.
  Channel name, handle and avatar are also Studio-only; the brand agent outputs them as a
  checklist, and the API applies description, keywords and banner.
* Uploads from an unverified Google Cloud project are locked to private. Complete the
  YouTube API Services audit before relying on automated public publishing.
* videos.insert costs ~1,600 quota units (default quota 10,000/day ≈ 6 uploads/day/project).
  Request a quota increase for 20+ shorts/day.
"""
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.core.config import get_settings

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _flow(state: str | None = None) -> Flow:
    s = get_settings()
    config = {"web": {"client_id": s.youtube_client_id, "client_secret": s.youtube_client_secret,
                      "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": TOKEN_URI,
                      "redirect_uris": [s.youtube_redirect_uri]}}
    flow = Flow.from_client_config(config, scopes=SCOPES, state=state)
    flow.redirect_uri = s.youtube_redirect_uri
    return flow


def authorization_url(state: str) -> str:
    url, _ = _flow(state).authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    return url


def exchange_code(code: str, state: str) -> tuple[str, str, str]:
    """Returns (refresh_token, youtube_channel_id, channel_title)."""
    flow = _flow(state)
    flow.fetch_token(code=code)
    creds = flow.credentials
    me = build("youtube", "v3", credentials=creds).channels().list(part="snippet", mine=True).execute()
    item = me["items"][0]
    return creds.refresh_token, item["id"], item["snippet"]["title"]


def credentials(refresh_token: str) -> Credentials:
    s = get_settings()
    return Credentials(None, refresh_token=refresh_token, token_uri=TOKEN_URI,
                       client_id=s.youtube_client_id, client_secret=s.youtube_client_secret, scopes=SCOPES)


def client(creds: Credentials):
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def public_client():
    key = get_settings().youtube_api_key
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY is not set")
    return build("youtube", "v3", developerKey=key, cache_discovery=False)


def upload_short(creds: Credentials, path: Path, *, title: str, description: str, tags: list[str],
                 publish_at_iso: str | None, category_id: str = "22") -> str:
    """Resumable upload. With publish_at_iso the video stays private and YouTube flips it public
    at that time — so we can upload ahead and let YouTube own the exact timing."""
    status = {"selfDeclaredMadeForKids": False}
    if publish_at_iso:
        status |= {"privacyStatus": "private", "publishAt": publish_at_iso}
    else:
        status |= {"privacyStatus": "public"}
    body = {"snippet": {"title": title[:100], "description": description, "tags": tags,
                        "categoryId": category_id}, "status": status}
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = client(creds).videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = req.next_chunk()
    return response["id"]


def apply_branding(creds: Credentials, channel_id: str, *, description: str, keywords: list[str],
                   banner_path: Path | None = None) -> None:
    yt = client(creds)
    branding = {"channel": {"description": description,
                            "keywords": " ".join(f'"{k}"' if " " in k else k for k in keywords)}}
    if banner_path:
        res = yt.channelBanners().insert(media_body=MediaFileUpload(str(banner_path))).execute()
        branding["image"] = {"bannerExternalUrl": res["url"]}
    yt.channels().update(part="brandingSettings", body={"id": channel_id, "brandingSettings": branding}).execute()


def video_statistics(creds: Credentials, video_ids: list[str]) -> dict[str, dict]:
    out = {}
    yt = client(creds)
    for i in range(0, len(video_ids), 50):
        res = yt.videos().list(part="statistics", id=",".join(video_ids[i:i + 50])).execute()
        out |= {v["id"]: v["statistics"] for v in res.get("items", [])}
    return out
