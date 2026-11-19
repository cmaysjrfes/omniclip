"""FFmpeg renderer: trim → 9:16 reframe (tracked crop or blurred-fill) → captions → fades → loudnorm.

GPU path uses NVDEC decode + h264_nvenc encode; CPU path uses libx264.
"""
from pathlib import Path

import ffmpeg

from .reframe import crop_x_expr


def _even(n: float) -> int:
    return int(n) // 2 * 2


def render_clip(*, src: Path, out: Path, start: float, end: float, src_w: int, src_h: int,
                layout: str, track: list[dict], ass_path: Path | None, has_audio: bool = True,
                width: int = 1080, height: int = 1920, gpu: bool = False, fade: float = 0.2) -> Path:
    dur = end - start
    in_kwargs = {"ss": start, "t": dur}
    if gpu:
        in_kwargs["hwaccel"] = "cuda"
    inp = ffmpeg.input(str(src), **in_kwargs)
    v = inp.video

    target_aspect = width / height
    if layout == "track" and src_w / src_h > target_aspect:
        crop_w = _even(src_h * target_aspect)
        v = (v.filter("crop", crop_w, src_h, crop_x_expr(track, src_w, crop_w), 0)
              .filter("scale", width, height, flags="lanczos"))
    else:  # fit_blur: whole frame centred over a blurred, zoomed copy of itself
        split = v.filter_multi_output("split")
        # Blur at quarter resolution then upscale: same look, ~16x less blur work.
        bg = (split[0].filter("scale", width // 4, height // 4, force_original_aspect_ratio="increase")
              .filter("crop", width // 4, height // 4)
              .filter("boxblur", luma_radius=12, luma_power=2)
              .filter("scale", width, height).filter("eq", brightness=-0.08))
        fg = split[1].filter("scale", width, -2, flags="lanczos")
        v = ffmpeg.overlay(bg, fg, x=0, y="(H-h)/2")

    if ass_path is not None:
        v = v.filter("ass", str(ass_path))
    v = (v.filter("fade", type="in", st=0, d=fade)
          .filter("fade", type="out", st=max(dur - fade, 0), d=fade)
          .filter("fps", 30).filter("format", "yuv420p"))

    venc = ({"vcodec": "h264_nvenc", "preset": "p5", "rc": "vbr", "cq": 21, "b:v": "0"} if gpu
            else {"vcodec": "libx264", "preset": "veryfast", "crf": 20})
    streams = [v]
    aenc = {}
    if has_audio:
        a = (inp.audio.filter("afade", type="in", st=0, d=fade)
             .filter("afade", type="out", st=max(dur - fade, 0), d=fade)
             .filter("loudnorm", I=-14, TP=-1.5, LRA=11))  # YouTube normalises to ~-14 LUFS
        streams.append(a)
        aenc = {"acodec": "aac", "b:a": "192k", "ar": 48000}

    out.parent.mkdir(parents=True, exist_ok=True)
    (ffmpeg.output(*streams, str(out), movflags="+faststart", **venc, **aenc)
     .overwrite_output().run(quiet=True))
    return out


def thumbnail(video: Path, out: Path, at: float = 1.0) -> Path:
    (ffmpeg.input(str(video), ss=at).output(str(out), vframes=1, **{"q:v": 3})
     .overwrite_output().run(quiet=True))
    return out
