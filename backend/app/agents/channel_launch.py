"""LangGraph workflow for Modules 2+3: niche → competitor intel → brand → schedule → YouTube.

    START → analyze_competitors → design_brand → optimize_schedule ─┬→ apply_branding → END
                                                                     └→ END (not connected / needs review)

Each node is a pure function of the state; persistence happens in the Celery task that
invokes the graph, so the graph is easy to unit-test with a fake LLM / YouTube client.
"""
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from . import brand_architect, competitor, schedule_optimizer
from .llm import LLM


class LaunchState(TypedDict, total=False):
    niche: dict
    timezone: str
    youtube_connected: bool
    auto_apply: bool
    competitor: dict | None
    brand: dict
    slots: list[dict]
    applied: bool


def build_graph(llm: LLM, log: Callable[..., None], apply_fn: Callable[[dict], None]):
    def analyze_competitors(state: LaunchState) -> dict[str, Any]:
        n = state["niche"]
        queries = [q for q in [
            " ".join(filter(None, [n.get("sub_category"), n["category"]])),
            n.get("niche_description", "")[:80],
            n["category"],
        ] if q]
        try:
            report = competitor.analyze_niche(queries, llm, log=log)
            log(f"Playbook: {report['playbook']['summary'][:160]}…", data={"channels": len(report["aggregate"]["channels"])})
            return {"competitor": report}
        except Exception as exc:  # no API key / quota exhausted — the brand agent still works without it
            log(f"Competitor analysis skipped: {exc}", level="warn")
            return {"competitor": None}

    def design_brand(state: LaunchState) -> dict[str, Any]:
        playbook = (state.get("competitor") or {}).get("playbook")
        brand = brand_architect.generate_brand(state["niche"], playbook, llm)
        top = brand["recommended"]
        log(f"Top name: {top['name']} (@{top['handle']}, score {top['score']})" if top else "No names generated",
            data={"names": [n["name"] for n in brand["names"][:5]]})
        return {"brand": brand}

    def optimize_schedule(state: LaunchState) -> dict[str, Any]:
        uploads = (state.get("competitor") or {}).get("uploads", [])
        slots = schedule_optimizer.rank_slots(uploads, [], state.get("timezone", "UTC"))
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        log("Best slots: " + ", ".join(f"{days[s['weekday']]} {s['hour']:02d}:00" for s in slots[:5]))
        return {"slots": slots}

    def route(state: LaunchState) -> str:
        return "apply_branding" if state.get("youtube_connected") and state.get("auto_apply") else END

    def apply_branding(state: LaunchState) -> dict[str, Any]:
        apply_fn(state["brand"])
        log("Applied description and keywords to the YouTube channel")
        return {"applied": True}

    g = StateGraph(LaunchState)
    g.add_node("analyze_competitors", analyze_competitors)
    g.add_node("design_brand", design_brand)
    g.add_node("optimize_schedule", optimize_schedule)
    g.add_node("apply_branding", apply_branding)
    g.add_edge(START, "analyze_competitors")
    g.add_edge("analyze_competitors", "design_brand")
    g.add_edge("design_brand", "optimize_schedule")
    g.add_conditional_edges("optimize_schedule", route, {"apply_branding": "apply_branding", END: END})
    g.add_edge("apply_branding", END)
    return g.compile()
