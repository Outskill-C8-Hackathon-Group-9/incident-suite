from app.state import IncidentState
from app.models import IssueEvaluations
from app.integrations.slack_client import MockSlackClient
from app.llm import get_llm
from app.nodes._trace import trace_event


def _format_message(state: IncidentState) -> str:
    issues = state.get("issues", [])
    tickets = {t["issue_id"]: t for t in state.get("jira_tickets", [])}
    lines = [f":rotating_light: *Incident Analysis — {len(issues)} issue(s) detected*", ""]
    for i in issues:
        link = (
            f" — <{tickets[i['id']]['url']}|{tickets[i['id']]['key']}>"
            if i["id"] in tickets
            else ""
        )
        lines.append(
            f"*{i['severity'].upper()}* `{i['affected_service']}` — {i['title']}{link}"
        )
        lines.append(f"    ↳ {i['summary']}")
    cb = state.get("cookbook")
    if cb:
        lines += ["", f":clipboard: *Runbook:* {cb['title']} ({len(cb['items'])} steps)"]
    return "\n".join(lines)


def notifier_node(state: IncidentState) -> dict:
    client = MockSlackClient()
    text = _format_message(state)
    result = client.post_message(text=text)
    result_data = result.model_dump()
    issues = state.get("issues", [])

    # LLM-based re-evaluation before posting final trace: use KNOWN_CATEGORIES in the prompt
    llm_eval_prompt = """You are an SRE auditor. Use the KNOWN CATEGORIES below as the canonical taxonomy when judging categories.
Known categories: memory_leak, deployment_regression, database, network, cpu_saturation, timeout, auth, config, unknown.

For each DetectedIssue below, return an evaluation with:
- id (must match)
- confidence: number between 0.0 and 1.0
- reasoning: one-sentence justification for this confidence (mention if the category matches the known categories)

ISSUES:
{issues}

Return a JSON matching the model IssueEvaluations.issue_evals list.
"""
    trace_data: dict = {}
    try:
        if issues:
            llm_eval = get_llm(temperature=0.0).with_structured_output(IssueEvaluations, method="function_calling")
            issues_text = "\n".join(
                f"- id={i['id']} | title={i['title']} | category={i['category']} | severity={i['severity']} | service={i['affected_service']} | summary={i['summary']}"
                for i in issues
            )
            eval_result: IssueEvaluations = llm_eval.invoke(llm_eval_prompt.format(issues=issues_text))
            for ev in eval_result.issue_evals:
                for issue in issues:
                    if issue["id"] == ev.id:
                        issue["confidence"] = ev.confidence
                        issue.setdefault("evaluation", {})["notifier_llm_reasoning"] = ev.reasoning
            trace_data["llm_evaluated"] = True
    except Exception as exc:
        trace_data["llm_eval_error"] = str(exc)

    avg_confidence = round(
        sum(i.get("confidence", 0.0) for i in issues) / len(issues),
        2,
    ) if issues else 0.0
    evaluation = {
        "issue_count": len(issues),
        "avg_issue_confidence": avg_confidence,
        "has_critical_jira_links": any(i.get("severity") in {"critical", "high"} for i in issues),
    }
    return {
        "slack_result": result_data,
        "trace": [trace_event(
            "notifier",
            f"Posted summary to {result.channel}, avg issue confidence {avg_confidence:.2f}.",
            {"slack": result_data, "evaluation": evaluation, **trace_data},
        )],
    }
