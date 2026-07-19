"""Decision engine: one remediative/investigative decision per detected issue.

Consumes the signals already produced upstream (issue rag_hits, cookbook item
rag_hits, remediation grounded_in) rather than re-parsing the log. Any
cookbook or RAG hit -> remediative (safe to auto-execute); zero hits ->
investigative (defer to a human on-call engineer).

Also derives a short, deterministic incident title per issue ("<ErrorSignature>
Error identified" / "[<service>] <ErrorSignature> identified") via a low-
temperature LLM call, falling back to a regex-based extractor if the LLM is
unavailable so title generation never blocks ticket creation.
"""
from __future__ import annotations

import re

from app.llm import get_llm
from app.models import Decision
from app.state import IncidentState

_ERROR_TOKEN = re.compile(
    r"[A-Za-z][\w.$]*(?:Exception|Error)"
    r"|connection refused|connection reset|connection pool exhausted"
    r"|upstream timeout|no route to host|502 bad gateway|504 gateway timeout|timeout",
    re.I,
)

TITLE_PROMPT = """Generate a short incident ticket title from this detected issue.

Style rules (pick exactly one):
- "[<service>] <ErrorSignature> identified" — ONLY when the evidence contains an
  exact code-level error name (a CamelCase exception/class like
  NullPointerException, or a dotted path like java.lang.OutOfMemoryError).
- "<ErrorSignature> Error identified" — for everything else: generic symptoms,
  phrases, or descriptions (e.g. "upstream timeout", "connection refused").
  Do NOT prefix this form with a service name.
Reply with ONLY the title text. No quotes, no trailing punctuation, no extra words.

Issue title: {title}
Category: {category}
Affected service: {service}
Summary: {summary}
Evidence:
{evidence}
"""


def _fallback_title(issue: dict) -> str:
    haystack = " ".join(
        [issue.get("title", ""), issue.get("summary", ""), *issue.get("evidence", [])]
    )
    match = _ERROR_TOKEN.search(haystack)
    signature = (match.group(0) if match else issue.get("title", "Unknown issue")).strip()
    service = issue.get("affected_service", "")
    if "." in signature or signature.endswith(("Exception", "Error")):
        prefix = f"[{service}] " if service else ""
        return f"{prefix}{signature} identified"
    return f"{signature} Error identified"


def generate_title(issue: dict, api_key: str | None = None) -> str:
    try:
        llm = get_llm(temperature=0.0, api_key=api_key)
        prompt = TITLE_PROMPT.format(
            title=issue.get("title", ""),
            category=issue.get("category", ""),
            service=issue.get("affected_service", ""),
            summary=issue.get("summary", ""),
            evidence="\n".join(f"- {e}" for e in (issue.get("evidence") or [])[:5]) or "- (none)",
        )
        title = str(llm.invoke(prompt).content).strip().strip('"').strip()
        if title:
            return title
    except Exception:
        pass
    return _fallback_title(issue)


def _issue_hits(issue: dict, cookbook_item: dict | None, remediation: dict | None) -> tuple[list[str], list[str]]:
    label = issue.get("title") or issue.get("id") or "issue"
    hit = issue.get("rag_hits") or (cookbook_item.get("rag_hits") if cookbook_item else None)
    cookbook_hits = [label] if hit == "cookbook" else []
    rag_hits = [label] if hit == "db" else []
    if remediation:
        rag_hits.extend(str(t) for t in remediation.get("grounded_in", []) or [])
    return cookbook_hits, rag_hits


def decide_issue(issue: dict, cookbook_item: dict | None, remediation: dict | None) -> Decision:
    cookbook_hits, rag_hits = _issue_hits(issue, cookbook_item, remediation)
    total = len(cookbook_hits) + len(rag_hits)
    matched_signals = cookbook_hits + rag_hits
    reference_sources = (
        [f"cookbook:{hit}" for hit in cookbook_hits] + [f"rag:{hit}" for hit in rag_hits]
    )

    if total > 0:
        path = "remediative"
        policy_reason = (
            f"Selected remediative path: {len(cookbook_hits)} cookbook hit(s) and "
            f"{len(rag_hits)} RAG hit(s) grounded a safe automated fix."
        )
        confidence = min(0.6 + 0.1 * total, 0.95)
    else:
        path = "investigative"
        policy_reason = (
            "Selected investigative path: no cookbook or RAG hits grounded a fix; "
            "a human on-call engineer must investigate. This is a new incident type — "
            "it will be added to the runbook knowledge base once resolved."
        )
        confidence = 0.5

    return Decision(
        path=path,
        severity=issue.get("severity", "info"),
        confidence=round(confidence, 2),
        policy_reason=policy_reason,
        matched_signals=matched_signals[:8],
        reference_sources=reference_sources[:8],
    )


def _match_cookbook_item(issue: dict, items: list[dict]) -> dict | None:
    for item in items:
        if item.get("title") == issue.get("title"):
            return item
    return None


def decide_all(state: IncidentState) -> list[dict]:
    """One Decision (+ title) per detected issue."""
    issues = state.get("issues", []) or []
    cookbook_items = (state.get("cookbook") or {}).get("items", []) or []
    remediations_by_id = {r["issue_id"]: r for r in state.get("remediations", []) or []}
    api_key = state.get("openrouter_api_key")

    results: list[dict] = []
    for issue in issues:
        cookbook_item = _match_cookbook_item(issue, cookbook_items)
        remediation = remediations_by_id.get(issue["id"])
        decision = decide_issue(issue, cookbook_item, remediation)
        entry = decision.model_dump()
        entry["issue_id"] = issue["id"]
        entry["title"] = generate_title(issue, api_key=api_key)
        results.append(entry)
    return results
