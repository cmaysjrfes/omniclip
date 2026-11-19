"""Karaoke-style animated captions rendered as ASS (burned in by libass via FFmpeg).

Words are grouped into short punchy lines; one Dialogue event per active word shows
the whole line with the spoken word highlighted and "popped".
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CaptionPreset:
    font: str
    size: int
    primary: str      # hex #RRGGBB
    highlight: str
    outline: str
    outline_w: int
    shadow: int
    margin_v: int     # distance from bottom in a 1920px-tall frame
    uppercase: bool
    max_words: int
    pop: int          # % scale on the active word


PRESETS: dict[str, CaptionPreset] = {
    "bold_pop": CaptionPreset("Inter Black", 92, "#FFFFFF", "#FFD400", "#000000", 7, 0, 560, True, 3, 118),
    "minimal": CaptionPreset("Inter SemiBold", 72, "#FFFFFF", "#7DD3FC", "#000000", 4, 2, 420, False, 5, 100),
    "neon": CaptionPreset("Inter ExtraBold", 86, "#F5F5F5", "#39FF14", "#1A0033", 8, 0, 520, True, 2, 125),
}


def hex_to_ass(hex_rgb: str, alpha: int = 0) -> str:
    r, g, b = hex_rgb.lstrip("#")[0:2], hex_rgb.lstrip("#")[2:4], hex_rgb.lstrip("#")[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(sec: float) -> str:
    sec = max(sec, 0.0)
    cs = int(round(sec * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def group_words(words: list[dict], max_words: int, max_chars: int = 20, max_gap: float = 0.6) -> list[list[dict]]:
    lines: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        chars = sum(len(x["w"]) + 1 for x in cur) + len(w["w"])
        gap = w["s"] - cur[-1]["e"] if cur else 0
        if cur and (len(cur) >= max_words or chars > max_chars or gap > max_gap
                    or cur[-1]["w"].endswith((".", "?", "!", ","))):
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def build_ass(words: list[dict], clip_start: float, clip_end: float, preset_name: str = "bold_pop",
              hook: str | None = None, width: int = 1080, height: int = 1920) -> str:
    p = PRESETS.get(preset_name, PRESETS["bold_pop"])
    dur = clip_end - clip_start
    rel = [{"w": w["w"].upper() if p.uppercase else w["w"],
            "s": w["s"] - clip_start, "e": w["e"] - clip_start}
           for w in words if w["e"] > clip_start and w["s"] < clip_end]

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{p.font},{p.size},{hex_to_ass(p.primary)},{hex_to_ass(p.highlight)},{hex_to_ass(p.outline)},&H80000000,-1,0,0,0,100,100,0,0,1,{p.outline_w},{p.shadow},2,60,60,{p.margin_v},1
Style: Hook,{p.font},{int(p.size * 0.78)},{hex_to_ass("#111111")},{hex_to_ass("#111111")},{hex_to_ass("#FFFFFF")},{hex_to_ass("#FFFFFF")},-1,0,0,0,100,100,0,0,3,24,0,8,80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    if hook:
        events.append(f"Dialogue: 1,{ass_time(0)},{ass_time(min(2.8, dur))},Hook,,0,0,0,,"
                      f"{{\\fad(120,220)}}{_esc(hook)}")

    hl = hex_to_ass(p.highlight)
    lines = group_words(rel, p.max_words)
    for li, line in enumerate(lines):
        line_end = line[-1]["e"]
        next_start = lines[li + 1][0]["s"] if li + 1 < len(lines) else dur
        if next_start - line_end < 0.35:  # bridge tiny gaps so captions don't flicker
            line_end = next_start
        for wi, w in enumerate(line):
            start = w["s"]
            end = line[wi + 1]["s"] if wi + 1 < len(line) else line_end
            if end <= start:
                continue
            parts = []
            for j, x in enumerate(line):
                t = _esc(x["w"])
                if j == wi:
                    parts.append(f"{{\\c{hl}\\fscx{p.pop}\\fscy{p.pop}\\t(0,90,\\fscx100\\fscy100)}}{t}{{\\r}}")
                else:
                    parts.append(t)
            events.append(f"Dialogue: 0,{ass_time(max(start, 0))},{ass_time(min(end, dur))},Cap,,0,0,0,,"
                          + " ".join(parts))
    return header + "\n".join(events) + "\n"
