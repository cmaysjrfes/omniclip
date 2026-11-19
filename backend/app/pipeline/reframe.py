"""Smart 9:16 reframing: face detection, active-speaker selection, camera smoothing.

Output is a small list of keyframes [{t, cx}] (cx = normalised speaker centre, 0..1),
which the renderer turns into a per-frame FFmpeg crop expression. Keyframes are stored
on the Clip so editors can nudge them in the workbench without re-running detection.
"""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Face:
    x: float  # normalised box, 0..1
    y: float
    w: float
    h: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2


class _Detector:
    """YuNet DNN detector (cv2.FaceDetectorYN) when its ONNX model is present — robust to
    profile views and small faces. Falls back to the Haar cascade bundled with OpenCV."""

    def __init__(self) -> None:
        from app.core.config import get_settings

        model = Path(get_settings().face_model_path)
        self._yunet = None
        if model.exists():
            self._yunet = cv2.FaceDetectorYN.create(str(model), "", (640, 360), 0.6, 0.3, 50)
        else:
            self._haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def __call__(self, frame_bgr: np.ndarray) -> list[Face]:
        h, w = frame_bgr.shape[:2]
        if self._yunet is not None:
            self._yunet.setInputSize((w, h))
            _, dets = self._yunet.detect(frame_bgr)
            return [Face(d[0] / w, d[1] / h, d[2] / w, d[3] / h) for d in (dets if dets is not None else [])]
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        boxes = self._haar.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(int(h * 0.08),) * 2)
        return [Face(x / w, y / h, bw / w, bh / h) for (x, y, bw, bh) in boxes]


def _mouth_motion(prev: np.ndarray | None, cur: np.ndarray, f: Face) -> float:
    """Active-speaker proxy: pixel change in the lower third of the face box."""
    if prev is None:
        return 0.0
    H, W = cur.shape[:2]
    x0, x1 = int(f.x * W), int((f.x + f.w) * W)
    y0, y1 = int((f.y + f.h * 0.62) * H), int((f.y + f.h) * H)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return float(cv2.absdiff(prev[y0:y1, x0:x1], cur[y0:y1, x0:x1]).mean())


def detect_track(video: Path, start: float, end: float, sample_fps: float = 4.0) -> tuple[list[tuple[float, float | None]], float]:
    """Returns ([(t_rel, cx|None)], face_coverage)."""
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    detect = _Detector()
    raw: list[tuple[float, float | None]] = []
    prev_gray, current = None, None
    next_t = start
    while True:
        ok = cap.grab()
        if not ok:
            break
        t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        if t > end:
            break
        if t < next_t:
            continue
        next_t += 1 / sample_fps
        _, frame = cap.retrieve()
        small = cv2.resize(frame, (640, int(640 * frame.shape[0] / frame.shape[1])))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        faces = detect(small)
        if not faces:
            raw.append((t - start, None))
        else:
            def score(f: Face) -> float:
                return _mouth_motion(prev_gray, gray, f) * 0.7 + f.w * f.h * 100 * 0.3
            best = max(faces, key=score)
            # Hysteresis: stay on the current speaker unless another is clearly more active.
            if current is not None:
                near = min(faces, key=lambda f: abs(f.cx - current))
                if abs(near.cx - current) < 0.08 and score(best) < score(near) * 1.35:
                    best = near
            current = best.cx
            raw.append((t - start, best.cx))
        prev_gray = gray
    cap.release()
    coverage = sum(1 for _, c in raw if c is not None) / len(raw) if raw else 0.0
    return raw, coverage


def smooth_track(raw: list[tuple[float, float | None]], dead_zone: float = 0.05, alpha: float = 0.3) -> list[tuple[float, float]]:
    """Virtual camera operator: hold still while the subject stays inside a dead zone,
    ease towards them when they leave it. Gaps are filled from neighbours."""
    if not raw:
        return []
    vals = [c for _, c in raw]
    first = next((c for c in vals if c is not None), 0.5)
    filled, last = [], first
    for c in vals:
        last = c if c is not None else last
        filled.append(last)
    out, cam, target = [], filled[0], filled[0]
    for (t, _), c in zip(raw, filled):
        if abs(c - cam) > dead_zone:
            target = c
        cam = cam + alpha * (target - cam)
        out.append((t, round(cam, 4)))
    return out


def simplify(points: list[tuple[float, float]], tol: float = 0.01) -> list[tuple[float, float]]:
    """Ramer–Douglas–Peucker: keep only keyframes that matter (keeps FFmpeg expressions short)."""
    if len(points) < 3:
        return points
    (t0, x0), (t1, x1) = points[0], points[-1]
    def dist(p):
        if t1 == t0:
            return abs(p[1] - x0)
        return abs(p[1] - (x0 + (x1 - x0) * (p[0] - t0) / (t1 - t0)))
    idx, dmax = max(((i, dist(p)) for i, p in enumerate(points[1:-1], 1)), key=lambda z: z[1])
    if dmax <= tol:
        return [points[0], points[-1]]
    return simplify(points[: idx + 1], tol)[:-1] + simplify(points[idx:], tol)


def analyze(video: Path, start: float, end: float) -> dict:
    raw, coverage = detect_track(video, start, end)
    track = simplify(smooth_track(raw))
    return {
        "layout": "track" if coverage >= 0.4 else "fit_blur",
        "face_coverage": round(coverage, 3),
        "track": [{"t": round(t, 3), "cx": cx} for t, cx in track] or [{"t": 0.0, "cx": 0.5}],
    }


def crop_x_expr(track: list[dict], src_w: int, crop_w: int) -> str:
    """Piecewise-linear FFmpeg expression in t for the crop window's left edge."""
    max_x = src_w - crop_w
    xs = [(k["t"], min(max(k["cx"] * src_w - crop_w / 2, 0), max_x)) for k in track]
    if len(xs) == 1 or all(abs(x - xs[0][1]) < 1 for _, x in xs):
        return str(int(xs[0][1]))
    expr = f"{xs[-1][1]:.1f}"
    for (ta, xa), (tb, xb) in reversed(list(zip(xs, xs[1:]))):
        span = max(tb - ta, 1e-3)
        expr = f"if(lt(t,{tb:.3f}),{xa:.1f}+({xb - xa:.1f})*(t-{ta:.3f})/{span:.3f},{expr})"
    return f"if(lt(t,{xs[0][0]:.3f}),{xs[0][1]:.1f},{expr})"
