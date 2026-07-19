# =====================================================================
# ASCII Data Flow Diagram
# =====================================================================
#
#  CLI flow: parse arguments (--summary, --severity, --service, --host,
#  optional --signals JSON), validate Jira config, optionally invoke
#  the new decision engine on the signals to pick a path, then create
#  or reuse a Jira ticket, round-robin assign an engineer, and print
#  a JSON summary to stdout.
#
#                  +------------------------+
#                  |     CLI Arguments      |
#                  |  --summary             |
#                  |  --severity            |
#                  |  --service             |
#                  |  --host                |
#                  |  --signals (optional)  |
#                  +-----------+------------+
#                              |
#                              v
#                  +-----------+------------+
#                  |     build_parser()     |
#                  +-----------+------------+
#                              |
#                              v
#                  +-----------+------------+
#                  |         main()         |
#                  +-----------+------------+
#                              |
#                              v
#                  +-----------+------------+
#                  |  Config validation     |   checks JIRA_BASE_URL,
#                  |  (JIRA_* env vars)     |   JIRA_USER_EMAIL,
#                  +-----------+------------+   JIRA_API_TOKEN,
#                              |                JIRA_PROJECT_KEY
#                              v
#                  +-----------+------------+
#                  |   _load_signals()      |   (only if --signals
#                  |   + _coerce_signals()  |    is supplied)
#                  |   + decide()           |
#                  +-----------+------------+
#                              |
#                              v
#                  +-----------+------------+
#                  |    DecisionBlock       |
#                  | (path, confidence,     |
#                  |  policy_reason, hits)  |
#                  +-----------+------------+
#                              |
#                              v
#                  +-----------+------------+
#                  |  build_description()   |
#                  |  (embeds decision)     |
#                  +-----------+------------+
#                              |
#                              v
#                  +-----------+------------+
#                  |   JiraTicketManager    |
#                  +-----------+------------+
#                              |
#                  +-----------+------------+
#                  |                          |
#                  v                          v
#   +-------------------------+   +-------------------------+
#   | find_open_ticket_by_    |   |     create_ticket       |
#   | summary(summary)        |   | (with decision info)    |
#   +------------+------------+   +------------+-------------+
#                |                           |
#                +-------------+-------------+
#                              |
#                              v
#                   +----------+----------+
#                   |   ticket object    |
#                   +----------+----------+
#                              |
#                              v
#             +----------------+----------------+
#             | next_round_robin_engineer()    |
#             +----------------+----------------+
#                              |
#                              v
#                   +----------+----------+
#                   |   assign_ticket     |
#                   +----------+----------+
#                              |
#                              v
#                  +----------+----------+
#                  |   JSON -> stdout    |
#                  | (ticket, decision,  |
#                  |  engineer, etc.)    |
#                  +---------------------+
#
#  Note: build_description() appends the decision path, confidence, and
#  policy_reason to the Jira ticket body so the on-call engineer has
#  full context (and so the audit trail is preserved in Jira itself).
# =====================================================================

from __future__ import annotations

import argparse
import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

from app.config import config
from app.decision_engine import _coerce_signals, decide
from app.integrations.jira_client import JiraTicketManager
from app.models import Engineer


# Build the command-line argument parser for the Incident Bot CLI.
# Defines five optional flags: --summary, --severity, --service, --host,
# and --signals (path to a cookbook/RAG signals JSON consumed by the
# decision engine before the ticket is created).
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create one Jira incident ticket for the hackathon flow."
    )
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
    parser.add_argument(
        "--signals",
        default=None,
        help=(
            "Optional path to a signals JSON file (cookbook_hits, "
            "rag_hits, severity, summary). When supplied, the new "
            "decision engine picks remediative vs investigative "
            "based on hit presence."
        ),
    )
    return parser


# Load the signals JSON from disk and return a dict, or None if no
# --signals path was provided. Raises a clear error if the path is
# supplied but the file cannot be read.
def _load_signals(path: Optional[str]) -> Optional[dict]:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


SPECIALTY_KEYWORDS = {
    "incident_dispatcher": ("incident_dispatcher", "dispatch", "router", "triage"),
    "memory_leak": ("memory_leak", "memory leak", "oom", "heap", "gc"),
    "deployment_regression": ("deployment_regression", "deployment", "deploy", "rollback", "release"),
    "database": ("database", "db", "sql", "connection pool", "postgres", "mysql"),
    "network": ("network", "dns", "packet", "route", "connectivity"),
    "cpu_saturation": ("cpu_saturation", "cpu", "utilization", "load", "throttle"),
    "timeout": ("timeout", "latency", "504", "502", "upstream timeout"),
}


def _infer_specialty(summary: str, service: str, signals_payload: Optional[dict]) -> str:
    texts = [summary, service]
    if signals_payload:
        texts.append(str(signals_payload.get("summary") or ""))
        for key in (
            "cookbook_hits",
            "cookbook_matches",
            "hardcoded_cookbook_hits",
            "rag_hits",
            "rag_matches",
            "retrieved_runbooks",
        ):
            value = signals_payload.get(key)
            if isinstance(value, list):
                texts.extend(str(item) for item in value)
            elif value:
                texts.append(str(value))
        for remediation in signals_payload.get("remediations", []) or []:
            if isinstance(remediation, dict):
                texts.extend(str(item) for item in remediation.get("grounded_in", []) or [])

    haystack = " ".join(texts).lower()
    for engineer in config.oncall_engineers:
        expertise = engineer.expertise.strip().lower()
        if expertise and expertise in haystack:
            return expertise
    for specialty, keywords in SPECIALTY_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return specialty
    return ""


def _select_engineer_for_specialty(specialty: str) -> Engineer | None:
    engineers = config.oncall_engineers
    if not engineers:
        return None
    if specialty:
        for engineer in engineers:
            if engineer.expertise.strip().lower() == specialty.strip().lower():
                return engineer
    return engineers[0]


# Compose the human-readable Jira ticket description body.
# Pulls the supplied summary/severity/service/host together with a
# UTC timestamp, and (when a decision is available) appends the
# chosen path, confidence score, and policy reason so the on-call
# engineer has full context in Jira.
def build_description(
    *,
    summary: str,
    severity: str,
    service: str,
    host: str,
    decision=None,
) -> str:
    now = datetime.now(UTC).isoformat()
    lines = [
        "This incident was created by the hackathon Incident Bot.",
        "",
        f"Summary: {summary}",
        f"Severity: {severity}",
        f"Service: {service}",
        f"Host: {host}",
        f"Created at: {now}",
    ]
    if decision is not None:
        lines.extend(
            [
                "",
                f"Decision path: {decision.path}",
                f"Confidence: {decision.confidence}",
                f"Policy reason: {decision.policy_reason}",
            ]
        )
    return "\n".join(lines) + "\n"


# Orchestrator: validate config, optionally run the decision engine
# on the supplied signals, look for an existing open ticket, create
# one if missing, round-robin assign an on-call engineer, and emit
# a JSON summary (including the decision) to stdout.
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
        print(
            json.dumps(
                {"ok": False, "error": f"Missing required config: {', '.join(missing)}"},
                indent=2,
            )
        )
        return 1

    # Run the new decision engine if signals were supplied; the engine
    # only inspects hit presence, so a missing/empty payload still works.
    decision = None
    signals_payload = _load_signals(args.signals)
    if signals_payload is not None:
        decision = decide(_coerce_signals(signals_payload))

    specialty = _infer_specialty(args.summary, args.service, signals_payload)

    manager = JiraTicketManager()
    existing_ticket = manager.find_open_ticket_by_summary(summary=args.summary)
    assigned_engineer = None
    created_in_jira = False
    duplicate_found = existing_ticket is not None

    if existing_ticket is not None:
        ticket = existing_ticket
        assigned_engineer = config.engineer_by_name(ticket.assignee or "")
    else:
        ticket = manager.create_ticket(
            summary=args.summary,
            severity=args.severity,
            description=build_description(
                summary=args.summary,
                severity=args.severity,
                service=args.service,
                host=args.host,
                decision=decision,
            ),
        )
        created_in_jira = manager.last_create_was_real
        if config.use_real_jira and not created_in_jira:
            print(json.dumps({"ok": False, "error": "Failed to create a real Jira ticket."}, indent=2))
            return 1

        assigned_engineer = _select_engineer_for_specialty(specialty)
        if assigned_engineer is not None:
            ticket = manager.assign_ticket(ticket, assigned_engineer)
            if config.use_real_jira and not manager.last_assign_was_real:
                print(json.dumps({"ok": False, "error": "Failed to assign the real Jira ticket."}, indent=2))
                return 1

    if assigned_engineer is None and ticket.assignee:
        assigned_engineer = config.engineer_by_name(ticket.assignee)

    if assigned_engineer is None:
        assigned_engineer = _select_engineer_for_specialty(specialty)

    if assigned_engineer is None:
        print(json.dumps({"ok": False, "error": "No assignee could be determined for this incident."}, indent=2))
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "project_key": config.JIRA_PROJECT_KEY,
                "ticket": ticket.model_dump(),
                "duplicate_found": duplicate_found,
                "assigned_engineer": assigned_engineer.model_dump() if assigned_engineer else None,
                "specialty": specialty,
                "used_real_jira_config": config.use_real_jira,
                "created_in_jira": created_in_jira,
                "decision": decision.model_dump() if decision is not None else None,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
