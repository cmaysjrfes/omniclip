import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("API_KEY", "test-key")


def make_words(text: str, start: float = 0.0, step: float = 0.4) -> list[dict]:
    return [{"w": w, "s": round(start + i * step, 3), "e": round(start + i * step + step * 0.85, 3)}
            for i, w in enumerate(text.split())]
