"""Source ingestion: YouTube/URL download (yt-dlp) and media probing (ffprobe).

Only ingest videos your team owns or has rights to repurpose. Downloading third-party
YouTube content violates YouTube's Terms of Service unless the rights holder permits it.
"""
from pathlib import Path

import ffmpeg


def download_url(url: str, out_dir: Path) -> Path:
    import yt_dlp  # lazy: heavy import, only needed on media workers

    out_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(out_dir / "source.%(ext)s"),
        "format": "bv*[height<=2160]+ba/b",
        "merge_output_format": "mp4",
        "quiet": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return Path(ydl.prepare_filename(info)).with_suffix(".mp4")


def probe(path: Path) -> dict:
    meta = ffmpeg.probe(str(path))
    v = next(s for s in meta["streams"] if s["codec_type"] == "video")
    num, den = (v.get("avg_frame_rate") or "30/1").split("/")
    return {
        "duration": float(meta["format"]["duration"]),
        "width": int(v["width"]),
        "height": int(v["height"]),
        "fps": float(num) / float(den or 1) if float(den or 1) else 30.0,
        "has_audio": any(s["codec_type"] == "audio" for s in meta["streams"]),
    }


def extract_audio(path: Path, out: Path) -> Path:
    """16 kHz mono WAV — what Whisper wants; avoids decoding video during ASR."""
    (ffmpeg.input(str(path)).output(str(out), ac=1, ar=16000, vn=None)
     .overwrite_output().run(quiet=True))
    return out
