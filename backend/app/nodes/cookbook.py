from app.state import IncidentState
from app.models import Cookbook
from app.llm import get_llm
from app.nodes._trace import trace_event

COOKBOOK_PROMPT = """You are writing an actionable incident-response checklist (runbook).

Given the detected issues and proposed remediations, produce an ORDERED checklist a first-responder
can follow end to end: contain first, then diagnose, then fix, then verify. Each step needs a step
number, an action, an owner_hint (role/team), and done_when (verification).

ISSUES:
{issues}

REMEDIATIONS:
{remediations}
"""


def cookbook_node(state: IncidentState) -> dict:
    issues = state.get("issues", [])
    rems = state.get("remediations", [])
    if not issues:
        return {"trace": [trace_event("cookbook", "No issues; skipped checklist.")]}

    llm = get_llm(temperature=0.3).with_structured_output(Cookbook, method="function_calling")
    cookbook: Cookbook = llm.invoke(COOKBOOK_PROMPT.format(
        issues="\n".join(f"- {i['title']} ({i['severity']})" for i in issues),
        remediations="\n".join(f"- {r['issue_id']}: {r['fix_summary']}" for r in rems),
    ))
    cookbook_data = cookbook.model_dump()
    return {
        "cookbook": cookbook_data,
        "trace": [trace_event(
            "cookbook",
            f"Built checklist with {len(cookbook.items)} step(s).",
            {"cookbook": cookbook_data},
        )],
    }
