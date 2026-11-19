from app.pipeline import segment
from conftest import make_words


def test_build_sentences_splits_on_punctuation_and_pauses():
    words = make_words("Hello there. This is great! Pause")
    words[-1]["s"] += 3; words[-1]["e"] += 3
    sents = segment.build_sentences(words)
    assert [s.text for s in sents] == ["Hello there.", "This is great!", "Pause"]
    assert sents[1].w0 == 2 and sents[1].w1 == 5


def test_snap_enforces_bounds():
    words = make_words(" ".join(f"word{i}." for i in range(200)), step=2.0)  # 2s sentences
    sents = segment.build_sentences(words)
    a, b = segment.snap(10, 11, sents, min_sec=15, max_sec=60)   # too short → extended
    assert sents[b].end - sents[a].start >= 15
    a, b = segment.snap(10, 80, sents, min_sec=15, max_sec=60)   # too long → trimmed
    assert sents[b].end - sents[a].start <= 60
    assert segment.snap(195, 199, sents, min_sec=15, max_sec=60) is None  # can't reach min at the end


def test_windows_cover_everything_with_overlap():
    words = make_words(" ".join(f"w{i}." for i in range(3000)), step=1.0)
    sents = segment.build_sentences(words)
    wins = segment.windows(sents, window_sec=600, overlap_sec=60)
    assert wins[0][0].idx == 0 and wins[-1][-1].idx == sents[-1].idx
    for prev, nxt in zip(wins, wins[1:]):
        assert nxt[0].idx < prev[-1].idx  # overlap


def test_dedupe_keeps_best_of_overlaps():
    cands = [{"start": 0, "end": 30, "virality_score": 50}, {"start": 2, "end": 31, "virality_score": 80},
             {"start": 100, "end": 130, "virality_score": 40}]
    kept = segment.dedupe(cands)
    assert [c["virality_score"] for c in kept] == [80, 40]


def test_composite_weights_sum_to_one():
    assert abs(sum(segment.SCORE_WEIGHTS.values()) - 1) < 1e-9
    assert segment.composite({k: 100 for k in segment.SCORE_WEIGHTS}) == 100
