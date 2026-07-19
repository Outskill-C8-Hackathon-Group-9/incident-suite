from app.integrations.jira_client import JiraTicketManager
from app.knowledge.runbook_store import add_runbook
from app.models import JiraTicket
from app.nodes._trace import trace_event
from app.state import IncidentState


def close_ticket_node(state: IncidentState) -> dict:
    manager = JiraTicketManager()
    issues_by_id = {i["id"]: i for i in state.get("issues", []) or []}
    remediations_by_id = {r["issue_id"]: r for r in state.get("remediations", []) or []}
    tickets = state.get("tickets", []) or []
    trace_lines: list[str] = []

    for entry in tickets:
        verification = entry.get("verification")
        if not verification or not verification.get("success"):
            continue

        ticket = manager.close_ticket(JiraTicket(**entry["ticket"]), note=verification["details"])
        entry["ticket"] = ticket.model_dump()
        trace_lines.append(f"Closed {ticket.key}")

        # Feed the resolved incident back into the RAG store so the next
        # occurrence of this error is a cookbook/RAG hit, not a fresh miss.
        issue = issues_by_id.get(entry["issue_id"], {})
        remediation = remediations_by_id.get(entry["issue_id"])
        content = issue.get("summary", "")
        if remediation:
            content = (
                f"{content} Fix: {remediation.get('fix_summary', '')} "
                f"({remediation.get('suggested_command', '')})"
            ).strip()
        add_runbook(title=entry["title"], category=issue.get("category", "unknown"), content=content)

    return {
        "tickets": tickets,
        "trace": [
            trace_event("close_ticket", "; ".join(trace_lines) or "No tickets closed.", {})
        ],
    }
