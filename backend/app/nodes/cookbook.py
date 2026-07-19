from app.state import IncidentState
from app.models import Cookbook
from app.llm import get_llm
from app.nodes._trace import trace_event

COOKBOOK_PROMPT = """You are writing an actionable incident-response checklist (runbook).

Given the detected issues and proposed remediations, produce an ORDERED checklist a first-responder
can follow end to end: contain first, then diagnose, then fix, then verify.

For each checklist step, include:
- step
- action
- owner_hint
- done_when
- title: the title of the issue this step relates to, or null if not issue-specific
- severity: the issue severity, or null if not issue-specific
- rag_hits: "cookbook", "db", or null depending on the issue grounding source

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

    llm = get_llm(temperature=0.3, api_key=state.get("openrouter_api_key")).with_structured_output(Cookbook, method="function_calling")
    cookbook: Cookbook = llm.invoke(COOKBOOK_PROMPT.format(
        issues="\n".join(
            f"- {i['title']} ({i['severity']}) [rag_hits={i.get('rag_hits')}]: {i['summary']}"
            for i in issues
        ),
        remediations="\n".join(f"- {r['issue_id']}: {r['fix_summary']}" for r in rems),
    ))
    cookbook_data = cookbook.model_dump()
    if len(cookbook_data.get("items", [])) == len(issues):
        for idx, item in enumerate(cookbook_data["items"]):
            issue = issues[idx]
            item.setdefault("title", issue.get("title"))
            item.setdefault("severity", issue.get("severity"))
            item.setdefault("rag_hits", issue.get("rag_hits"))
    return {
        "cookbook": cookbook_data,
        "trace": [trace_event(
            "cookbook",
            f"Built checklist with {len(cookbook.items)} step(s).",
            {"cookbook": cookbook_data},
        )],
    }
