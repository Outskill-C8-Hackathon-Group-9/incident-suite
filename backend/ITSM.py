# =====================================================================
# ASCII Data Flow Diagram
# =====================================================================
#
#  High-level flow of this CLI entrypoint for creating a Jira incident
#  ticket (or reusing an existing open one) via the Incident Bot.
#
#                  +-------------------+
#                  |   CLI Arguments   |
#                  |  --summary        |
#                  |  --severity       |
#                  |  --service        |
#                  |  --host           |
#                  +---------+---------+
#                            |
#                            v
#                      +-----+-----+        +----------------------+
#                      |  main()   |<------>|  build_parser()      |
#                      +----+-----+        |  (argparse builder)  |
#                           |              +----------------------+
#                           v
#                +----------+-----------+
#                | Config Validation    |   checks JIRA_BASE_URL,
#                | (JIRA_* env vars)    |   JIRA_USER_EMAIL,
#                +----------+-----------+   JIRA_API_TOKEN,
#                           |               JIRA_PROJECT_KEY
#                           v
#                  +--------+--------+
#                  | JiraTicketManager|
#                  +--------+--------+
#                           |
#              +------------+-------------+
#              |                          |
#              v                          v
#   +----------------------+   +------------------------+
#   | find_open_ticket_by_ |   |     create_ticket      |
#   | summary(summary)     |   | (summary, severity,    |
#   +----------+-----------+   |  description)          |
#              |              +-----------+------------+
#              |                          |
#              +-------------+------------+
#                            |
#                            v
#                   +--------+--------+
#                   |  ticket object  |
#                   +--------+--------+
#                            |
#                            v
#             +--------------+--------------+
#             | next_round_robin_engineer() |
#             +--------------+--------------+
#                            |
#                            v
#                   +--------+--------+
#                   |  assign_ticket  |
#                   +--------+--------+
#                            |
#                            v
#                  +---------+---------+
#                  |  JSON -> stdout  |
#                  | (ticket, dup,    |
#                  |  engineer, etc.) |
#                  +------------------+
#
#  Note: build_description() is invoked inside main() to compose the
#  human-readable description string consumed by create_ticket().
# =====================================================================

from __future__ import annotations

import argparse
import json
from datetime import datetime, UTC

from app.config import config
from app.integrations.jira_client import JiraTicketManager


# Build the command-line argument parser for the Incident Bot CLI.
# Defines four optional flags (--summary, --severity, --service, --host)
# with sensible defaults so the script can be run with no arguments.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create one Jira incident ticket for the hackathon flow.")
    parser.add_argument(
        "--summary",
        default="Test incident created via Incident Bot",
        help="Short Jira ticket summary.",
    )
    parser.add_argument(
        "--severity",
        default="high",
        choices=["critical", "high", "medium", "low", "info"],
        help="Severity label added to the ticket.",
    )
    parser.add_argument(
        "--service",
        default="incident-bot",
        help="Service name shown in the description.",
    )
    parser.add_argument(
        "--host",
        default="hackathon-cli",
        help="Host name shown in the description.",
    )
    return parser


# Compose the human-readable Jira ticket description body.
# Pulls the supplied summary/severity/service/host together with a
# UTC timestamp so the on-call engineer has full context in Jira.
def build_description(*, summary: str, severity: str, service: str, host: str) -> str:
    now = datetime.now(UTC).isoformat()
    return (
        "This incident was created by the hackathon Incident Bot.\n\n"
        f"Summary: {summary}\n"
        f"Severity: {severity}\n"
        f"Service: {service}\n"
        f"Host: {host}\n"
        f"Created at: {now}"
    )


# Orchestrator: validate config, look for an existing open ticket,
# create one if missing, round-robin assign an on-call engineer, and
# emit a JSON summary of the outcome to stdout.
def main() -> int:
    args = build_parser().parse_args()
    missing = [
        name
        for name, value in (
            ("JIRA_BASE_URL", config.JIRA_BASE_URL),
            ("JIRA_USER_EMAIL", config.JIRA_USER_EMAIL),
            ("JIRA_API_TOKEN", config.JIRA_API_TOKEN),
            ("JIRA_PROJECT_KEY", config.JIRA_PROJECT_KEY),
        )
        if not value
    ]
    if missing:
        print(json.dumps({"ok": False, "error": f"Missing required config: {', '.join(missing)}"}, indent=2))
        return 1

    manager = JiraTicketManager()
    existing_ticket = manager.find_open_ticket_by_summary(summary=args.summary)
    assigned_engineer = None
    created_in_jira = False
    duplicate_found = existing_ticket is not None

    if existing_ticket is not None:
        ticket = existing_ticket
    else:
        ticket = manager.create_ticket(
            summary=args.summary,
            severity=args.severity,
            description=build_description(
                summary=args.summary,
                severity=args.severity,
                service=args.service,
                host=args.host,
            ),
        )
        created_in_jira = manager.last_create_was_real
        assigned_engineer = manager.next_round_robin_engineer(config.oncall_engineers)
        if assigned_engineer is not None:
            ticket = manager.assign_ticket(ticket, assigned_engineer)

    print(
        json.dumps(
            {
                "ok": True,
                "project_key": config.JIRA_PROJECT_KEY,
                "ticket": ticket.model_dump(),
                "duplicate_found": duplicate_found,
                "assigned_engineer": assigned_engineer.model_dump() if assigned_engineer else None,
                "used_real_jira_config": config.use_real_jira,
                "created_in_jira": created_in_jira,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
