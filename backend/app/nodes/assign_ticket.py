from app.config import config
from app.integrations.jira_client import JiraTicketManager
from app.nodes._trace import trace_event
from app.state import IncidentState


def _pick_engineer(ticket_key: str):
    engineers = config.oncall_engineers
    suffix = ticket_key.split("-")[-1]
    try:
        index = int(suffix) % len(engineers)
    except ValueError:
        index = 0
    return engineers[index]


def assign_ticket_node(state: IncidentState) -> dict:
    manager = JiraTicketManager()
    engineer = _pick_engineer(state["ticket"].key)
    ticket = manager.assign_ticket(state["ticket"], engineer)
    return {
        "ticket": ticket,
        "assigned_engineer": engineer,
        "trace": [
            trace_event(
                "assign_ticket",
                f"Assigned {ticket.key} to {engineer.name}.",
                {"ticket": ticket.model_dump(), "assigned_engineer": engineer.model_dump()},
            )
        ],
    }
