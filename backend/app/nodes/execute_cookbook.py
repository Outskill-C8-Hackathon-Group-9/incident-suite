from app.models import ExecutionResult
from app.nodes._trace import trace_event
from app.state import IncidentState


def execute_cookbook_node(state: IncidentState) -> dict:
    issues_by_id = {i["id"]: i for i in state.get("issues", []) or []}
    cookbook_items_by_title = {
        item.get("title"): item for item in (state.get("cookbook") or {}).get("items", []) or []
    }
    tickets = state.get("tickets", []) or []
    trace_lines: list[str] = []

    for entry in tickets:
        if entry["decision"]["path"] != "remediative":
            continue
        issue = issues_by_id.get(entry["issue_id"], {})
        item = cookbook_items_by_title.get(issue.get("title"))
        steps_run = (
            [f"Ran step {item['step']}: {item['action']}"]
            if item
            else [f"Applied the automated fix for {entry['title']}."]
        )
        execution = ExecutionResult(
            steps_run=steps_run,
            summary=f"Executed {len(steps_run)} step(s) for {entry['title']}.",
        )
        entry["execution"] = execution.model_dump()
        trace_lines.append(execution.summary)

    return {
        "tickets": tickets,
        "trace": [
            trace_event(
                "execute_cookbook",
                "; ".join(trace_lines) or "No remediative tickets to execute.",
                {},
            )
        ],
    }
