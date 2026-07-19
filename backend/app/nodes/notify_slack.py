from app.integrations.slack_client import SlackNotifier
from app.models import NotificationResult
from app.nodes._trace import trace_event
from app.state import IncidentState


def _team_message(state: IncidentState) -> str:
    tickets = state.get("tickets", []) or []
    lines = [f":rotating_light: *Incident Analysis — {len(tickets)} incident(s) detected*", ""]
    for entry in tickets:
        decision = entry["decision"]
        ticket = entry["ticket"]
        engineer = entry.get("assigned_engineer")
        lines.append(f"*{decision['severity'].upper()}* {entry['title']}{' (duplicate)' if entry.get('duplicate_found') else ''}")
        lines.append(
            f"    Ticket: {ticket['key']} ({ticket['url']}) · {decision['path']} · "
            f"assigned: {engineer['name'] if engineer else 'unassigned'}"
        )
        verification = entry.get("verification")
        if verification:
            lines.append(f"    Verification: {verification['details']}")
    return "\n".join(lines)


def _dm_message(entry: dict) -> str:
    ticket = entry["ticket"]
    engineer = entry["assigned_engineer"]
    decision = entry["decision"]
    return (
        f"You were assigned {ticket['key']}.\n"
        f"Severity: {decision['severity']}\n"
        f"Summary: {ticket['summary']}\n"
        f"Ticket: {ticket['url']}\n"
        f"Hello {engineer['name']}, please take a look."
    )


def notify_slack_node(state: IncidentState) -> dict:
    notifier = SlackNotifier()
    team_text = _team_message(state)
    channel, team_permalink = notifier.post_team_message(text=team_text)

    dm_permalink = ""
    dm_count = 0
    for entry in state.get("tickets", []) or []:
        engineer = entry.get("assigned_engineer")
        if not engineer:
            continue
        permalink = notifier.post_direct_message(
            slack_user_id=engineer.get("slack_user_id", ""),
            text=_dm_message(entry),
        )
        dm_count += 1
        dm_permalink = dm_permalink or permalink

    result = NotificationResult(
        channel=channel,
        team_permalink=team_permalink,
        dm_permalink=dm_permalink,
        text_preview=team_text,
    )
    return {
        "notification": result.model_dump(),
        "trace": [
            trace_event(
                "notify_slack",
                f"Posted team update to {channel}; sent {dm_count} DM(s).",
                {"notification": result.model_dump()},
            )
        ],
    }
