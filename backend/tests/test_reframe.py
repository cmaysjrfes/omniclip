import subprocess

from app.pipeline import reframe


def test_smooth_track_fills_gaps_and_ignores_jitter():
    raw = [(0, None), (0.25, 0.5), (0.5, 0.52), (0.75, None), (1.0, 0.49)]
    out = reframe.smooth_track(raw, dead_zone=0.05)
    assert all(abs(x - 0.5) < 1e-9 for _, x in out)  # jitter inside dead zone → camera holds


def test_smooth_track_follows_big_moves():
    raw = [(i * 0.25, 0.2 if i < 4 else 0.8) for i in range(20)]
    out = reframe.smooth_track(raw)
    assert out[0][1] == 0.2 and out[-1][1] > 0.75


def test_simplify_keeps_endpoints_and_corners():
    pts = [(t, 0.2) for t in range(10)] + [(t, 0.8) for t in range(10, 20)]
    simp = reframe.simplify(pts)
    assert simp[0] == pts[0] and simp[-1] == pts[-1] and 2 < len(simp) < len(pts)


def test_crop_expr_is_clamped_and_valid_ffmpeg():
    track = [{"t": 0, "cx": 0.0}, {"t": 2, "cx": 1.0}, {"t": 4, "cx": 0.5}]
    expr = reframe.crop_x_expr(track, 1920, 606)
    assert "-" not in expr.split("if(lt(t,0.000),")[1].split(",")[0]  # first keyframe clamped at 0
    # FFmpeg itself must accept the expression.
    cmd = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=10:duration=1",
           "-vf", f"crop=606:1080:{expr.replace(',', chr(92) + ',')}:0", "-f", "null", "-"]
    assert subprocess.run(cmd, capture_output=True).returncode == 0


def test_constant_track_gives_constant_expr():
    assert reframe.crop_x_expr([{"t": 0, "cx": 0.5}], 1920, 606) == str(int(960 - 303))
