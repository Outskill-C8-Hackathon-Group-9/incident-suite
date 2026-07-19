"""Engineer assignment helpers, used by create_ticket_node.

Every ticket is assigned an on-call engineer immediately on creation
(remediative or investigative) — not a standalone graph node.
"""
from app.config import config
from app.integrations.jira_client import JiraTicketManager
from app.models import Engineer, JiraTicket

SPECIALTY_KEYWORDS = {
    "memory_leak": ("memory_leak", "memory leak", "oom", "heap", "gc"),
    "deployment_regression": ("deployment_regression", "deployment", "deploy", "rollback", "release"),
    "database": ("database", "db", "sql", "connection pool", "postgres", "mysql"),
    "network": ("network", "dns", "packet", "route", "connectivity"),
    "cpu_saturation": ("cpu_saturation", "cpu", "utilization", "load", "throttle"),
    "timeout": ("timeout", "latency", "504", "502", "upstream timeout"),
}


def infer_specialty(issue: dict, decision: dict) -> str:
    texts = [
        decision.get("policy_reason", ""),
        issue.get("category", ""),
        issue.get("title", ""),
        issue.get("summary", ""),
        *(decision.get("matched_signals") or []),
    ]
    haystack = " ".join(texts).lower()
    for engineer in config.oncall_engineers:
        expertise = engineer.expertise.strip().lower()
        if expertise and expertise in haystack:
            return expertise
    for specialty, keywords in SPECIALTY_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return specialty
    return ""


def select_engineer(manager: JiraTicketManager, specialty: str) -> Engineer | None:
    engineers = config.oncall_engineers
    if not engineers:
        return None
    if specialty:
        for engineer in engineers:
            if engineer.expertise.strip().lower() == specialty:
                return engineer
    return manager.next_round_robin_engineer(engineers) or engineers[0]


def assign_engineer(
    manager: JiraTicketManager, ticket: JiraTicket, issue: dict, decision: dict
) -> tuple[JiraTicket, Engineer | None]:
    specialty = infer_specialty(issue, decision)
    engineer = select_engineer(manager, specialty)
    if engineer is None:
        return ticket, None
    return manager.assign_ticket(ticket, engineer), engineer
