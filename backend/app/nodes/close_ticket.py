from app.integrations.jira_client import JiraTicketManager
from app.nodes._trace import trace_event
from app.state import IncidentState


def close_ticket_node(state: IncidentState) -> dict:
    manager = JiraTicketManager()
    verification = state["verification"]
    ticket = manager.close_ticket(state["ticket"], note=verification.details)
    return {
        "ticket": ticket,
        "trace": [
            trace_event(
                "close_ticket",
                f"Closed ticket {ticket.key}.",
                {"ticket": ticket.model_dump()},
            )
        ],
    }
