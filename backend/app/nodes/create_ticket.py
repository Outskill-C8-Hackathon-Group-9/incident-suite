from app.integrations.jira_client import JiraTicketManager
from app.nodes._trace import trace_event
from app.state import IncidentState


def _build_description(state: IncidentState) -> str:
    incident = state["incident"]
    decision = state["decision"]
    steps = "\n".join(f"- {item.step}. {item.action}" for item in incident.cookbook.items)
    return (
        f"Summary: {incident.summary}\n"
        f"Severity: {incident.severity}\n"
        f"Host: {incident.host}\n"
        f"Service: {incident.service}\n"
        f"Decision: {decision.path}\n"
        f"Cookbook: {incident.cookbook.title}\n"
        f"Steps:\n{steps}"
    )


def create_ticket_node(state: IncidentState) -> dict:
    incident = state["incident"]
    manager = JiraTicketManager()
    ticket = manager.create_ticket(
        summary=f"{incident.severity.upper()} incident on {incident.service}",
        description=_build_description(state),
        severity=incident.severity,
    )
    return {
        "ticket": ticket,
        "trace": [
            trace_event(
                "create_ticket",
                f"Created ticket {ticket.key}.",
                {"ticket": ticket.model_dump()},
            )
        ],
    }
