from app.state import IncidentState
from app.models import RemediationOutput
from app.llm import get_llm, invoke_llm
from app.agent_logging import log_agent_io
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
- category: the category of the issue (must match one of the categories in the ISSUES section) else put it as Unknown as a category
- title: the title of the issue must be the same as the title of the issue in the ISSUES section else put it with some relevant title based on the issue.

ISSUES:
{issues}

RETRIEVED RUNBOOKS:
{runbooks}
"""

_DANGEROUS = ("rm -rf", "drop database", "delete from", "terminate all", "mkfs", "> /dev")


def remediation_node(state: IncidentState) -> dict:
    issues = state.get("issues", [])
    retrieved_runbooks = state.get("retrieved_runbooks") or {}
    runbook_titles = state.get("runbook_titles") or []
    contents = state.get("retrieved_runbook_contents") or {}
    log_agent_io("remediation", "request", {
        "issues": issues,
        "retrieved_runbooks": retrieved_runbooks,
        "runbook_titles": runbook_titles,
    })

    if not issues:
        response = {
            "remediations": [],
            "retrieved_runbooks": retrieved_runbooks,
            "runbook_titles": runbook_titles,
            "trace": [trace_event("remediation", "No issues to remediate.")],
        }
        log_agent_io("remediation", "response", {
            "remediations": [],
            "retrieved_runbooks": retrieved_runbooks,
            "runbook_titles": runbook_titles,
        })
        return response

    runbooks_text = "\n\n".join(f"[{title}]\n{content}" for title, content in contents.items()) \
        or "No matching runbooks found."

    issues_text = "\n".join(
        f"- id={i['id']} | {i['severity'].upper()} | {i['category']} | "
        f"{i['affected_service']} | {i['summary']}"
        for i in issues
    )

    prompt = REMEDIATION_PROMPT.format(issues=issues_text, runbooks=runbooks_text)
    llm = get_llm(temperature=0.2).with_structured_output(RemediationOutput, method="function_calling")
    result: RemediationOutput = invoke_llm("remediation.llm", llm, prompt)

    # safety net on top of the prompt-level ban
    safe = [
        r.model_dump()
        for r in result.remediations
        if not any(bad in r.suggested_command.lower() for bad in _DANGEROUS)
    ]

    response = {
        "remediations": safe,
        "retrieved_runbooks": retrieved_runbooks,
        "runbook_titles": runbook_titles,
        "trace": [trace_event(
            "remediation",
            f"Proposed {len(safe)} remediation(s), grounded in "
            f"{len(runbook_titles)} retrieved runbook(s).",
            {
                "remediations": safe,
                "retrieved_runbooks": retrieved_runbooks,
                "runbook_titles": runbook_titles,
            },
        )],
    }
    log_agent_io("remediation", "response", {
        "remediations": safe,
        "retrieved_runbooks": retrieved_runbooks,
        "runbook_titles": runbook_titles,
    })
    return response
