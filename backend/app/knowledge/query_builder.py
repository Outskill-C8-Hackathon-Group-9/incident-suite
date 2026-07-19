"""Incident-aware query builder for RAG retrieval.

Builds richer queries from correlated issues in a single analysis run
instead of relying on one isolated log line or issue title.
"""

from __future__ import annotations

from typing import Any, Optional


def build_issue_query(
    issue: dict[str, Any],
    sibling_issues: Optional[list[dict[str, Any]]] = None,
) -> str:
    """Build a retrieval query for one issue, enriched with sibling context."""
    parts = [
        issue.get("title") or "",
        issue.get("category") or "",
        issue.get("affected_service") or "",
        issue.get("summary") or "",
    ]

    evidence = issue.get("evidence") or []
    if isinstance(evidence, list):
        parts.extend(str(e) for e in evidence[:2])

    if sibling_issues:
        siblings = [s for s in sibling_issues if s.get("id") != issue.get("id")]
        categories = sorted({s.get("category", "") for s in siblings if s.get("category")})
        services = sorted({
            s.get("affected_service", "") for s in siblings if s.get("affected_service")
        })
        titles = [s.get("title", "") for s in siblings[:3] if s.get("title")]
        if categories:
            parts.append("related_categories: " + " ".join(categories))
        if services:
            parts.append("related_services: " + " ".join(services))
        if titles:
            parts.append("correlated_incidents: " + "; ".join(titles))

    return " ".join(p for p in parts if p).strip()


def build_filters_for_issue(issue: dict[str, Any]) -> dict[str, str]:
    """Soft metadata filters derived from the issue (empty values omitted)."""
    filters: dict[str, str] = {}
    category = (issue.get("category") or "").strip()
    service = (issue.get("affected_service") or "").strip()
    if category and category != "unknown":
        filters["category"] = category
    if service and service not in ("unknown", "from-screenshot"):
        filters["service_hint"] = service
    return filters
