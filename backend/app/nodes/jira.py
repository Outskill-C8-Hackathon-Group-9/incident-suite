from app.state import IncidentState
from app.integrations.jira_client import MockJiraClient
from app.nodes._trace import trace_event

CRITICAL = {"critical", "high"}


def jira_node(state: IncidentState) -> dict:
    client = MockJiraClient()
    issues = [i for i in state.get("issues", []) if i["severity"] in CRITICAL]
    rem_by_id = {r["issue_id"]: r for r in state.get("remediations", [])}

    tickets = []
    for issue in issues:
        rem = rem_by_id.get(issue["id"])
        ticket = client.create_ticket(
            summary=issue["title"],
            severity=issue["severity"],
            issue_id=issue["id"],
            description=(
                f"{issue['summary']}\n\nAffected: {issue['affected_service']}\n"
                f"Proposed fix: {rem['fix_summary'] if rem else 'see checklist'}\n"
                f"Command: {rem['suggested_command'] if rem else 'n/a'}"
            ),
        )
        tickets.append(ticket.model_dump())

    return {
        "jira_tickets": tickets,
        "trace": [trace_event(
            "jira",
            f"Created {len(tickets)} JIRA ticket(s) for critical issues.",
            {"tickets": tickets},
        )],
    }
