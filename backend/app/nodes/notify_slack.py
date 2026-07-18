from app.integrations.slack_client import SlackNotifier
from app.models import NotificationResult
from app.nodes._trace import trace_event
from app.state import IncidentState


def _team_message(state: IncidentState) -> str:
    incident = state["incident"]
    decision = state["decision"]
    ticket = state["ticket"]
    lines = [
        f"Incident update for {incident.service} on {incident.host}",
        f"Severity: {incident.severity}",
        f"Path: {decision.path}",
        f"Ticket: {ticket.key} ({ticket.url})",
        f"Summary: {incident.summary}",
    ]
    if decision.path == "remediative":
        verification = state.get("verification")
        lines.append(f"Verification: {verification.details if verification else 'pending'}")
        lines.append(f"Final status: {ticket.status}")
    else:
        engineer = state.get("assigned_engineer")
        lines.append(f"Assigned engineer: {engineer.name if engineer else 'unassigned'}")
    return "\n".join(lines)


def _dm_message(state: IncidentState) -> str:
    incident = state["incident"]
    ticket = state["ticket"]
    return (
        f"You were assigned {ticket.key}.\n"
        f"Severity: {incident.severity}\n"
        f"Host: {incident.host}\n"
        f"Summary: {incident.summary}\n"
        f"Ticket: {ticket.url}"
    )


def notify_slack_node(state: IncidentState) -> dict:
    notifier = SlackNotifier()
    team_text = _team_message(state)
    channel, team_permalink = notifier.post_team_message(text=team_text)
    dm_permalink = ""
    if state["decision"].path == "investigative" and state.get("assigned_engineer"):
        engineer = state["assigned_engineer"]
        dm_permalink = notifier.post_direct_message(
            slack_user_id=engineer.slack_user_id,
            text=_dm_message(state),
        )

    result = NotificationResult(
        channel=channel,
        team_permalink=team_permalink,
        dm_permalink=dm_permalink,
        text_preview=team_text,
    )
    return {
        "notification": result,
        "trace": [
            trace_event(
                "notify_slack",
                f"Posted Slack update to {channel}.",
                {"notification": result.model_dump()},
            )
        ],
    }
