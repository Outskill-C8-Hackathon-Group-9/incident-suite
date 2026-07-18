from app.state import IncidentState
from app.models import RemediationOutput
from app.llm import get_llm
from app.knowledge.runbook_store import retrieve
from app.config import config
from app.nodes._trace import trace_event

REMEDIATION_PROMPT = """You are an SRE proposing remediations for detected incidents.

Use the RETRIEVED RUNBOOKS below as authoritative guidance. Prefer their recommended steps.
For EACH issue, propose exactly one remediation with:
- issue_id (must match)
- fix_summary
- rationale: why this addresses the ROOT CAUSE (reference the runbook guidance where relevant)
- suggested_command: a concrete, SAFE command or config change
  (e.g. 'kubectl rollout undo deployment/user-service'). NEVER propose destructive commands
  (no 'rm -rf', 'drop database', 'DELETE FROM', 'terminate all').
- risk_level (low/medium/high)
- requires_approval: true for anything high-risk
- grounded_in: the titles of the runbooks you actually used for this issue

ISSUES:
{issues}

RETRIEVED RUNBOOKS:
{runbooks}
"""

_DANGEROUS = ("rm -rf", "drop database", "delete from", "terminate all", "mkfs", "> /dev")


def remediation_node(state: IncidentState) -> dict:
    issues = state.get("issues", [])
    if not issues:
        return {"remediations": [], "trace": [trace_event("remediation", "No issues to remediate.")]}

    # ---- RAG retrieval: pull matching runbooks per issue ----
    seen: dict[str, str] = {}          # title -> content (dedupe across issues)
    grounding_by_issue: dict[str, list[str]] = {}
    for i in issues:
        query = f"{i['title']} {i['category']} {i['affected_service']} {i['summary']}"
        docs = retrieve(query, k=config.RAG_TOP_K)
        titles = []
        for d in docs:
            title = d.metadata.get("title", "runbook")
            seen[title] = d.page_content
            titles.append(title)
        grounding_by_issue[i["id"]] = titles

    runbooks_text = "\n\n".join(f"[{title}]\n{content}" for title, content in seen.items()) \
        or "No matching runbooks found."

    issues_text = "\n".join(
        f"- id={i['id']} | {i['severity'].upper()} | {i['category']} | "
        f"{i['affected_service']} | {i['summary']}"
        for i in issues
    )

    llm = get_llm(temperature=0.2).with_structured_output(RemediationOutput, method="function_calling")
    result: RemediationOutput = llm.invoke(
        REMEDIATION_PROMPT.format(issues=issues_text, runbooks=runbooks_text)
    )

    # safety net on top of the prompt-level ban
    safe = [
        r.model_dump()
        for r in result.remediations
        if not any(bad in r.suggested_command.lower() for bad in _DANGEROUS)
    ]

    return {
        "remediations": safe,
        "trace": [trace_event(
            "remediation",
            f"Proposed {len(safe)} remediation(s), grounded in "
            f"{len(seen)} retrieved runbook(s).",
            {
                "remediations": safe,
                "retrieved_runbooks": grounding_by_issue,
            },
        )],
    }
