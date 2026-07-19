# =====================================================================
# ASCII Data Flow Diagram
# =====================================================================
#
#  Post-hackathon alignment (per reconvened team):
#
#    - Remediative path : the parsed log produced at least one hit in
#                          the hardcoded cookbook OR in the RAG store.
#    - Investigative path: the parsed log produced no hits in either
#                          source; a human must take over.
#
#  The decision engine does NOT parse the uploaded log itself. It only
#  consumes the results produced by the upstream parsing/lookup blocks
#  (cookbook match + RAG retrieval). Because the exact contract from
#  those blocks is still being finalized, this module depends on a
#  small, explicit SourceSignals input shape and tolerates missing
#  fields via _coerce_signals().
#
#  The DecisionBlock output is consumed by downstream blocks such as
#  JIRA.py (Jira ticket creation embeds the path + policy_reason in
#  the ticket description) and the Slack notifier (path drives the
#  message style).
#
#                  +----------------------+
#                  |   Upstream blocks    |
#                  |  (cookbook + RAG)    |
#                  +---------+------------+
#                            |
#                            v
#                  +---------+------------+
#                  |   SourceSignals      |
#                  |  (cookbook_hits,     |
#                  |   rag_hits,          |
#                  |   severity, summary) |
#                  +---------+------------+
#                            |
#                            v
#                  +---------+------------+
#                  |    decide()          |
#                  | (count total hits)   |
#                  +---------+------------+
#                            |
#                +-----------+-----------+
#                |                       |
#                v                       v
#       +-------------------+  +---------------------+
#       |  total > 0        |  |  total == 0         |
#       |  -> remediative   |  |  -> investigative   |
#       |  (higher conf.)   |  |  (low conf., defer  |
#       |                   |  |   to human)         |
#       +-------------------+  +---------------------+
#                |                       |
#                +-----------+-----------+
#                            |
#                            v
#                  +---------+------------+
#                  |   DecisionBlock      |
#                  | (path, confidence,   |
#                  |  policy_reason,      |
#                  |  matched_signals,    |
#                  |  reference_sources)  |
#                  +----------------------+
# =====================================================================

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Input contract
# ---------------------------------------------------------------------------
@dataclass
class SourceSignals:
    """Input contract consumed by the decision engine.

    Populated by the upstream parsing/lookup blocks. The decision engine
    only inspects whether hits exist; it does not parse the log itself.

    Attributes:
        cookbook_hits: Non-empty matches returned by the cookbook lookup.
        rag_hits:      Non-empty matches returned by the RAG retrieval.
        severity:      Optional severity carried through for reporting.
        summary:       Optional human-readable summary for context.
    """

    cookbook_hits: list[str] = field(default_factory=list)
    rag_hits: list[str] = field(default_factory=list)
    severity: str = "info"
    summary: str = ""

    def total_hits(self) -> int:
        # Sum of hits from both sources; drives the path decision.
        return len(self.cookbook_hits) + len(self.rag_hits)

    def has_any_hit(self) -> bool:
        # Convenience predicate: any hit at all -> remediative.
        return self.total_hits() > 0


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------
@dataclass
class DecisionBlock:
    """Outcome of the decision engine.

    path:            "remediative" (auto-execute cookbook) or
                     "investigative" (hand off to a human).
    severity:        Severity carried through from the source signals.
    confidence:      0.0-1.0 score; higher means more agreement.
    policy_reason:   Human-readable explanation of the chosen path.
    matched_signals: Combined cookbook+rag hits, capped.
    reference_sources: Hits tagged with their origin ("cookbook:" / "rag:").
    """

    path: str
    severity: str
    confidence: float
    policy_reason: str
    matched_signals: list[str] = field(default_factory=list)
    reference_sources: list[str] = field(default_factory=list)

    # Serialize the DecisionBlock attributes to a dictionary for JSON output.
    def model_dump(self) -> dict:
        return {
            "path": self.path,
            "severity": self.severity,
            "confidence": self.confidence,
            "policy_reason": self.policy_reason,
            "matched_signals": self.matched_signals,
            "reference_sources": self.reference_sources,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_string_list(value) -> list[str]:
    """Coerce an arbitrary value into a list[str], tolerating None / scalars.

    Keeps the engine robust to upstream payload changes (e.g., a future
    schema where a single string may be returned instead of a list).
    """
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _extract_hits(payload: dict, keys: tuple[str, ...]) -> list[str]:
    """Collect hits from any known key aliases in a payload."""
    hits: list[str] = []
    for key in keys:
        if key in payload:
            hits.extend(_safe_string_list(payload.get(key)))
    return hits


_SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def _is_meaningful_hit(value) -> bool:
    """True for a real hit value; false for empty/null/placeholder values.

    Cookbook items may carry a 'rag_hits' field that is itself a type-union
    placeholder (e.g. "CPU | cookbook | null") rather than an actual hit;
    those are recognizable by the '|' separator and must not be counted.
    """
    if not value:
        return False
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "n/a"}:
        return False
    return "|" not in text


def _unwrap_node_update(payload: dict) -> dict:
    """Unwrap a LangGraph SSE event ({"node": ..., "update": {...}}) to its update body."""
    update = payload.get("update")
    return update if isinstance(update, dict) else payload


def _extract_cookbook_items(node_payload: dict) -> tuple[dict, list[dict]]:
    """Return (cookbook_dict, items) from a cookbook-node update, or ({}, [])."""
    cookbook = node_payload.get("cookbook")
    if not isinstance(cookbook, dict):
        return {}, []
    items = cookbook.get("items")
    items = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    return cookbook, items


def _severity_from_items(items: list[dict]) -> str:
    """Highest-ranked severity across cookbook items, defaulting to 'info'."""
    best = "info"
    for item in items:
        sev = str(item.get("severity") or "").strip().lower()
        if sev in _SEVERITY_RANK and _SEVERITY_RANK[sev] > _SEVERITY_RANK[best]:
            best = sev
    return best


def _coerce_signals(payload: dict) -> SourceSignals:
    """Coerce an arbitrary dict (e.g., from JSON) into a SourceSignals object.

    Defaults missing fields so the engine stays decoupled from the exact
    upstream contract (which is still being finalized). Accepts either the
    flat cookbook_hits/rag_hits shape, or a LangGraph cookbook-node event
    (optionally wrapped as {"node": "cookbook", "update": {...}}) carrying
    a nested cookbook.items[] list, each item optionally holding its own
    title/action and rag_hits.
    """
    if not isinstance(payload, dict):
        payload = {}

    node_payload = _unwrap_node_update(payload)

    cookbook_hits = _extract_hits(
        node_payload,
        (
            "cookbook_hits",
            "cookbook_matches",
            "hardcoded_cookbook_hits",
            "hardcoded_runbook_hits",
            "runbook_hits",
        ),
    )
    rag_hits = _extract_hits(
        node_payload,
        (
            "rag_hits",
            "rag_matches",
            "retrieved_runbooks",
            "rag_results",
            "vector_hits",
        ),
    )

    cookbook, items = _extract_cookbook_items(node_payload)
    for item in items:
        hit = item.get("title") or item.get("action")
        if _is_meaningful_hit(hit):
            cookbook_hits.append(str(hit))
        if _is_meaningful_hit(item.get("rag_hits")):
            rag_hits.append(str(item["rag_hits"]))

    # If the remediation block surfaces grounded runbook titles, count those as RAG hits.
    for remediation in node_payload.get("remediations", []) or []:
        if isinstance(remediation, dict):
            rag_hits.extend(_safe_string_list(remediation.get("grounded_in")))

    severity = str(node_payload.get("severity") or "").strip() or _severity_from_items(items)
    summary = str(node_payload.get("summary") or "").strip() or str(cookbook.get("title") or "")

    return SourceSignals(
        cookbook_hits=cookbook_hits,
        rag_hits=rag_hits,
        severity=severity or "info",
        summary=summary,
    )


def decide_from_payload(payload: dict) -> DecisionBlock:
    """Convenience entrypoint for uncertain upstream payload shapes."""
    return decide(_coerce_signals(payload))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def decide(signals: SourceSignals) -> DecisionBlock:
    """Pick a response path based on whether the parsed log produced any hits.

    Rules (post-hackathon alignment):
      - Remediative  : at least one hit in cookbook OR RAG.
      - Investigative: zero hits in either source.

    Confidence is low when no signals are present (we defer to a human)
    and grows with the number of corroborating hits, capped at 0.95.
    """
    cookbook_hits = list(signals.cookbook_hits or [])
    rag_hits = list(signals.rag_hits or [])
    cookbook_count = len(cookbook_hits)
    rag_count = len(rag_hits)
    total = cookbook_count + rag_count

    # Combined list of "what matched" for downstream display / debugging.
    matched_signals = cookbook_hits + rag_hits
    # Tag every hit with its origin so the audit trail is unambiguous.
    reference_sources = (
        [f"cookbook:{hit}" for hit in cookbook_hits]
        + [f"rag:{hit}" for hit in rag_hits]
    )

    if total > 0:
        path = "remediative"
        policy_reason = (
            f"Selected remediative path: parsed log produced "
            f"{cookbook_count} cookbook hit(s) and {rag_count} RAG hit(s)."
        )
        # More corroborating hits -> higher confidence, capped at 0.95.
        confidence = min(0.6 + 0.1 * total, 0.95)
    else:
        path = "investigative"
        policy_reason = (
            "Selected investigative path: parsed log produced no hits "
            "in the cookbook or RAG; human investigation is required."
        )
        # No signals -> low confidence, defer to human.
        confidence = 0.5

    return DecisionBlock(
        path=path,
        severity=signals.severity or "info",
        confidence=round(confidence, 2),
        policy_reason=policy_reason,
        matched_signals=matched_signals[:8],
        reference_sources=reference_sources[:8],
    )
