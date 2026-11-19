"""Word-level transcription with faster-whisper (CTranslate2 Whisper, GPU-capable)."""
from functools import lru_cache
from pathlib import Path
from typing import Callable

from app.core.config import get_settings


@lru_cache
def _model():
    from faster_whisper import WhisperModel  # lazy: loads CUDA libs

    s = get_settings()
    return WhisperModel(s.whisper_model, device=s.whisper_device, compute_type=s.whisper_compute_type)


def transcribe(audio_path: Path, duration: float, on_progress: Callable[[float], None] | None = None) -> dict:
    """Returns {"language", "duration", "words": [{"w","s","e","p"}]}."""
    segments, info = _model().transcribe(
        str(audio_path), word_timestamps=True, vad_filter=True, beam_size=5,
        condition_on_previous_text=False,  # reduces hallucinated repetition on long inputs
    )
    words: list[dict] = []
    for seg in segments:  # generator: transcription happens while iterating
        for w in seg.words or []:
            words.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3),
                          "p": round(w.probability, 3)})
        if on_progress and duration:
            on_progress(min(seg.end / duration, 1.0))
    return {"language": info.language, "duration": duration, "words": [w for w in words if w["w"]]}
