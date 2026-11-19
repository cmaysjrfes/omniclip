"""Agent orchestration with a fake LLM — no network or API key needed."""
from app.agents import channel_launch, clip_scorer, competitor, metadata_writer
from app.agents.brand_architect import BrandKit, BrandPackage, NameIdea
from app.agents.clip_scorer import Moment, MomentList, MomentScores
from conftest import make_words


class FakeLLM:
    def __init__(self, responder):
        self.responder, self.calls = responder, []

    def structured(self, *, system, content, schema, **kw):
        self.calls.append((schema, content))
        return self.responder(schema, content)


def test_clip_scorer_snaps_dedupes_and_ranks():
    text = " ".join(f"Sentence number {i} is here." for i in range(300))
    transcript = {"words": make_words(text, step=0.5)}

    def responder(schema, content):
        assert schema is MomentList and "<transcript>" in content
        s = MomentScores(hook_strength=90, emotional_intensity=50, standalone_value=80,
                         retention_potential=70, shareability=60)
        weak = s.model_copy(update={"hook_strength": 10})
        return MomentList(moments=[
            Moment(start_sentence=10, end_sentence=20, hook="Big claim", title_idea="t", category="insight",
                   rationale="r", scores=s),
            Moment(start_sentence=11, end_sentence=21, hook="Dup", title_idea="t", category="insight",
                   rationale="r", scores=weak),
            Moment(start_sentence=100, end_sentence=101, hook="Short", title_idea="t", category="story",
                   rationale="r", scores=s),
        ])

    out = clip_scorer.score_transcript(transcript, target=20, niche="finance", llm=FakeLLM(responder),
                                       min_sec=15, max_sec=60)
    assert [c["hook"] for c in out] == ["Big claim", "Short"]      # duplicate suppressed
    assert all(15 <= c["end"] - c["start"] <= 60 for c in out)      # "Short" got extended
    assert out[0]["virality_score"] > 0


def test_metadata_tags_are_clamped():
    tags = [f"very long search phrase number {i}" for i in range(40)]
    assert sum(len(t) + 3 for t in metadata_writer.clamp_tags(tags)) <= 500


def test_iso_duration():
    assert competitor.iso_duration_sec("PT1M5S") == 65
    assert competitor.iso_duration_sec("PT2H") == 7200


def test_launch_graph_runs_end_to_end_without_youtube(monkeypatch):
    monkeypatch.setattr(competitor, "analyze_niche", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no key")))

    def responder(schema, content):
        assert schema is BrandPackage
        kit = BrandKit(primary_color="#111111", secondary_color="#222222", accent_color="#FFD400",
                       font_pairing="Inter / Inter", caption_preset="bold_pop", avatar_prompt="a",
                       banner_prompt="b", thumbnail_style="c", voice_guidelines="d", content_pillars=["x"])
        return BrandPackage(names=[
            NameIdea(name="Meh Money", handle="@meh money!", rationale="", memorability=40, searchability=40, niche_fit=40),
            NameIdea(name="Compound Club", handle="compoundclub", rationale="", memorability=90, searchability=70, niche_fit=95),
        ], description="d" * 1500, keywords=["k"] * 30, brand_kit=kit)

    events, applied = [], []
    graph = channel_launch.build_graph(FakeLLM(responder), lambda m, **k: events.append(m), applied.append)
    final = graph.invoke({"niche": {"category": "Business & Finance", "sub_category": "Investing"},
                          "timezone": "UTC", "youtube_connected": False, "auto_apply": True})
    assert final["brand"]["recommended"]["name"] == "Compound Club"
    assert final["brand"]["names"][1]["handle"] == "mehmoney"
    assert len(final["brand"]["description"]) == 1000 and len(final["brand"]["keywords"]) == 20
    assert len(final["slots"]) == 21 and not applied   # not connected → branding not applied
    assert any("skipped" in e for e in events)
