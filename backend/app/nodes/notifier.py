from app.state import IncidentState
from app.integrations.slack_client import MockSlackClient
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
    return {
        "slack_result": result_data,
        "trace": [trace_event(
            "notifier",
            f"Posted summary to {result.channel}.",
            {"slack": result_data},
        )],
    }
