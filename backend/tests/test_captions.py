from app.pipeline import captions
from conftest import make_words


def test_hex_to_ass_is_bgr():
    assert captions.hex_to_ass("#FFD400") == "&H0000D4FF"


def test_ass_time():
    assert captions.ass_time(3725.456) == "1:02:05.46"


def test_build_ass_highlights_each_word_once_and_is_clip_relative():
    words = make_words("one two three four five six", start=100.0)
    ass = captions.build_ass(words, 100.0, 103.0, "bold_pop", hook="Watch this")
    dialogue = [l for l in ass.splitlines() if l.startswith("Dialogue: 0")]
    assert len(dialogue) == 6
    assert dialogue[0].split(",")[1] == "0:00:00.00"         # relative to clip start
    assert all(l.count("\\fscx118") == 1 for l in dialogue)   # exactly one popped word per event
    assert "ONE" in dialogue[0]                               # bold_pop uppercases
    assert "Hook,,0,0,0,,{\\fad(120,220)}Watch this" in ass


def test_text_escaping_blocks_override_injection():
    words = [{"w": "{\\b1}hi", "s": 0.0, "e": 0.5}]
    ass = captions.build_ass(words, 0, 1, "minimal")
    assert "{\\b1}" not in ass.split("[Events]")[1]
