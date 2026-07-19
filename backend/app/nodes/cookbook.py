from app.state import IncidentState
from app.models import Cookbook
from app.llm import get_llm, invoke_llm
from app.agent_logging import log_agent_io
from app.nodes._trace import trace_event

COOKBOOK_PROMPT = """You are writing an actionable incident-response checklist (runbook).

Given the detected issues, proposed remediations, and RETRIEVED RUNBOOKS, produce an ORDERED
checklist a first-responder can follow end to end: contain first, then diagnose, then fix, then
verify. Prefer the retrieved runbook guidance when sequencing steps. Each step needs a step
number, an action, an owner_hint (role/team), and done_when (verification).

ISSUES:
{issues}

REMEDIATIONS:
{remediations}

RETRIEVED RUNBOOKS:
{runbooks}
"""


def cookbook_node(state: IncidentState) -> dict:
    issues = state.get("issues", [])
    rems = state.get("remediations", [])
    retrieved_runbooks = state.get("retrieved_runbooks") or {}
    runbook_titles = state.get("runbook_titles") or []
    contents = state.get("retrieved_runbook_contents") or {}
    log_agent_io("cookbook", "request", {
        "issues": issues,
        "remediations": rems,
        "retrieved_runbooks": retrieved_runbooks,
        "runbook_titles": runbook_titles,
    })

    if not issues:
        response = {
            "retrieved_runbooks": retrieved_runbooks,
            "runbook_titles": runbook_titles,
            "trace": [trace_event("cookbook", "No issues; skipped checklist.")],
        }
        log_agent_io("cookbook", "response", {
            "skipped": True,
            "retrieved_runbooks": retrieved_runbooks,
            "runbook_titles": runbook_titles,
        })
        return response

    runbooks_text = "\n\n".join(f"[{title}]\n{content}" for title, content in contents.items()) \
        or "No matching runbooks found."

    prompt = COOKBOOK_PROMPT.format(
        issues="\n".join(f"- {i['title']} ({i['severity']})" for i in issues),
        remediations="\n".join(f"- {r['issue_id']}: {r['fix_summary']}" for r in rems),
        runbooks=runbooks_text,
    )
    llm = get_llm(temperature=0.3).with_structured_output(Cookbook, method="function_calling")
    cookbook: Cookbook = invoke_llm("cookbook.llm", llm, prompt)
    cookbook_data = cookbook.model_dump()
    merged = {
        **cookbook_data,
        "retrieved_runbooks": retrieved_runbooks,
        "runbook_titles": runbook_titles,
    }
    response = {
        "cookbook": cookbook_data,
        "retrieved_runbooks": retrieved_runbooks,
        "runbook_titles": runbook_titles,
        "trace": [trace_event(
            "cookbook",
            f"Built checklist with {len(cookbook.items)} step(s).",
            {"cookbook": cookbook_data, "runbook_titles": runbook_titles},
        )],
    }
    log_agent_io("cookbook", "response", merged)
    return response
