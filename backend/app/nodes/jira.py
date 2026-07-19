from app.state import IncidentState
from app.integrations.jira_client import MockJiraClient
from app.agent_logging import log_agent_io
from app.nodes._trace import trace_event

CRITICAL = {"critical", "high"}


def jira_node(state: IncidentState) -> dict:
    client = MockJiraClient()
    issues = [i for i in state.get("issues", []) if i["severity"] in CRITICAL]
    rem_by_id = {r["issue_id"]: r for r in state.get("remediations", [])}

    log_agent_io("jira", "request", {
        "critical_issues": issues,
        "remediations": [rem_by_id.get(i["id"]) for i in issues],
    })

    tickets = []
    for issue in issues:
        rem = rem_by_id.get(issue["id"])
        create_request = {
            "summary": issue["title"],
            "severity": issue["severity"],
            "issue_id": issue["id"],
            "description": (
                f"{issue['summary']}\n\nAffected: {issue['affected_service']}\n"
                f"Proposed fix: {rem['fix_summary'] if rem else 'see checklist'}\n"
                f"Command: {rem['suggested_command'] if rem else 'n/a'}"
            ),
        }
        log_agent_io("jira.create_ticket", "request", create_request)
        ticket = client.create_ticket(**create_request)
        ticket_data = ticket.model_dump()
        log_agent_io("jira.create_ticket", "response", ticket_data)
        tickets.append(ticket_data)

    response = {
        "jira_tickets": tickets,
        "trace": [trace_event(
            "jira",
            f"Created {len(tickets)} JIRA ticket(s) for critical issues.",
            {"tickets": tickets},
        )],
    }
    log_agent_io("jira", "response", {"tickets": tickets})
    return response
