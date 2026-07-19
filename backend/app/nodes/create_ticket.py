from app.integrations.jira_client import JiraTicketManager
from app.nodes._trace import trace_event
from app.nodes.assign_ticket import assign_engineer
from app.state import IncidentState


def _description(issue: dict, decision: dict, remediation: dict | None) -> str:
    lines = [
        f"Decision: {decision['path']} (confidence {decision['confidence']})",
        f"Policy reason: {decision['policy_reason']}",
        "",
        f"[{issue['severity'].upper()}] {issue['title']} ({issue['affected_service']})",
        issue["summary"],
    ]
    if remediation:
        lines += [
            f"Proposed fix: {remediation['fix_summary']}",
            f"Command: {remediation['suggested_command']}",
        ]
    if decision.get("matched_signals"):
        lines += ["", f"Matched signals: {', '.join(decision['matched_signals'])}"]
    return "\n".join(lines)


def create_ticket_node(state: IncidentState) -> dict:
    issues_by_id = {i["id"]: i for i in state.get("issues", []) or []}
    remediations_by_id = {r["issue_id"]: r for r in state.get("remediations", []) or []}
    manager = JiraTicketManager()

    tickets: list[dict] = []
    trace_lines: list[str] = []

    for decision in state.get("decisions", []) or []:
        issue = issues_by_id.get(decision["issue_id"])
        if issue is None:
            continue
        remediation = remediations_by_id.get(decision["issue_id"])
        title = decision["title"]
        description = _description(issue, decision, remediation)

        # De-dupe: reuse an existing open ticket with the same title instead of
        # creating a new one (works against real Jira; mock mode always creates).
        existing = manager.find_open_ticket_by_summary(summary=title)
        duplicate_found = existing is not None
        ticket = (
            manager.update_ticket(existing, note=description)
            if existing is not None
            else manager.create_ticket(summary=title, description=description, severity=decision["severity"])
        )

        # Every incident is assigned to an on-call engineer immediately,
        # remediative or investigative.
        ticket, engineer = assign_engineer(manager, ticket, issue, decision)

        tickets.append({
            "issue_id": decision["issue_id"],
            "title": title,
            "decision": decision,
            "ticket": ticket.model_dump(),
            "assigned_engineer": engineer.model_dump() if engineer else None,
            "duplicate_found": duplicate_found,
        })
        trace_lines.append(
            f"{'Reused' if duplicate_found else 'Created'} {ticket.key} ({title})"
            f"{f' -> {engineer.name}' if engineer else ''}"
        )

    return {
        "tickets": tickets,
        "trace": [
            trace_event(
                "create_ticket",
                "; ".join(trace_lines) or "No tickets created.",
                {"tickets": tickets},
            )
        ],
    }
