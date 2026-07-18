# =====================================================================
# ASCII Data Flow Diagram
# =====================================================================
#
#  High-level flow of notify.py: load ITSM.py output, build Slack messages,
#  post to team channel + optionally DM the assigned engineer, then emit
#  JSON result to stdout.
#
#                  +-------------------+
#                  |   CLI Argument    |
#                  |   (input JSON)    |
#                  +---------+---------+
#                            |
#                            v
#                  +---------+---------+
#                  |    build_parser() |
#                  +---------+---------+
#                            |
#                            v
#                  +---------+---------+
#                  |      main()       |
#                  +---------+---------+
#                            |
#                            v
#                  +---------+---------+
#                  |  _load_payload()  |
#                  |  (JSON -> dict)   |
#                  +---------+---------+
#                            |
#                            v
#              +-------------+-------------+
#              |                           |
#              v                           v
#   +----------------------+   +----------------------+
#   | _build_team_message()|   | _build_dm_message()  |
#   +----------+-----------+   +----------+-----------+
#              |                           |
#              +-------------+-------------+
#                            |
#                            v
#                  +---------+---------+
#                  |   SlackNotifier   |
#                  +---------+---------+
#                            |
#              +-------------+-------------+
#              |                           |
#              v                           v
#   +----------------------+   +----------------------+
#   | post_team_message()  |   | post_direct_message()|
#   | (if slack_user_id)   |   | (if status Assigned) |
#   +----------+-----------+   +----------+-----------+
#              |                           |
#              +-------------+-------------+
#                            |
#                            v
#                  +---------+---------+
#                  |  JSON -> stdout  |
#                  | (result & links) |
#                  +------------------+
#
#  Note: _build_team_message() creates a multi-line summary for the
#  team channel, while _build_dm_message() creates a personalized
#  message for the assigned engineer's direct message.
# =====================================================================

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.integrations.slack_client import SlackNotifier


# Build the CLI argument parser for notify.py.
# Expects one positional argument: the path to the JSON payload file produced by ITSM.py.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send Slack notifications for an ITSM ticket payload.")
    parser.add_argument("input", help="Path to a JSON file matching ITSM.py output.")
    return parser


# Load the ITSM.py output JSON from disk and parse it into a Python dict.
# Uses pathlib to handle cross-platform path handling.
def _load_payload(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# Compose the multi-line message posted to the team Slack channel.
# Pulls ticket details (key, summary, severity, status) and the assigned engineer from the payload.
def _build_team_message(payload: dict) -> str:
    ticket = payload["ticket"]
    lines = [
        f"Incident update for {ticket['summary']}",
        f"Ticket: {ticket['key']} ({ticket['url']})",
        f"Severity: {ticket['severity']}",
        f"Status: {ticket['status']}",
    ]
    assigned_engineer = payload.get("assigned_engineer") or {}
    if assigned_engineer.get("name"):
        lines.append(f"Assigned engineer: {assigned_engineer['name']}")
    lines.append(f"Duplicate found: {payload.get('duplicate_found', False)}")
    return "\n".join(lines)


# Compose the personalized message sent as a DM to the assigned engineer.
# Only called when the ticket status is "Assigned" and a slack_user_id is present.
def _build_dm_message(payload: dict) -> str:
    ticket = payload["ticket"]
    engineer = payload["assigned_engineer"]
    return (
        f"You were assigned {ticket['key']}.\n"
        f"Severity: {ticket['severity']}\n"
        f"Summary: {ticket['summary']}\n"
        f"Ticket: {ticket['url']}\n"
        f"Hello {engineer['name']}, please take a look."
    )


# Orchestrator: parse CLI args, load ITSM payload, post team message to Slack,
# optionally DM the assigned engineer, and emit JSON result to stdout.
def main() -> int:
    args = build_parser().parse_args()
    payload = _load_payload(args.input)
    ticket = payload["ticket"]
    assigned_engineer = payload.get("assigned_engineer") or {}

    notifier = SlackNotifier()
    team_channel, team_permalink = notifier.post_team_message(text=_build_team_message(payload))
    dm_permalink = ""

    if ticket["status"] == "Assigned" and assigned_engineer.get("slack_user_id"):
        dm_permalink = notifier.post_direct_message(
            slack_user_id=assigned_engineer["slack_user_id"],
            text=_build_dm_message(payload),
        )

    print(
        json.dumps(
            {
                "ok": True,
                "team_channel": team_channel,
                "team_permalink": team_permalink,
                "dm_permalink": dm_permalink,
                "ticket_key": ticket["key"],
                "ticket_status": ticket["status"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
