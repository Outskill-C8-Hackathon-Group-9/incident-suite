"""Confidence evaluation after RAG retrieval.

If the top rerank score is below threshold, rewrite the query once and
re-retrieve. Keeps the better of the two result sets.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

from langchain_core.documents import Document

from app.config import config
from app.llm import get_llm
from app.knowledge.runbook_store import retrieve_with_scores

logger = logging.getLogger(__name__)

REWRITE_PROMPT = """You rewrite search queries for an incident knowledge base (runbooks, security playbooks, ops SOPs).

Original query retrieved poorly. Write ONE improved search query that:
- keeps key error terms, services, and categories
- adds synonyms used in ops/security docs (e.g. brute force, WAF, OOM, pool exhaustion)
- stays under 40 words
- contains no explanation — reply with the query text only

Issue title: {title}
Category: {category}
Service: {service}
Summary: {summary}
Evidence: {evidence}
Original query: {query}
"""


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-float(x)))


def score_docs(scored: list[tuple[Document, float]]) -> dict[str, float]:
    """Normalize cross-encoder logits to 0-1 confidence metrics."""
    if not scored:
        return {"top": 0.0, "mean": 0.0, "count": 0.0}
    norms = [_sigmoid(s) for _, s in scored]
    return {
        "top": round(max(norms), 4),
        "mean": round(sum(norms) / len(norms), 4),
        "count": float(len(norms)),
    }


def rewrite_query(issue: dict[str, Any], original_query: str) -> str:
    """LLM rewrite of a low-confidence retrieval query."""
    evidence = issue.get("evidence") or []
    ev_text = "; ".join(str(e) for e in evidence[:2]) if isinstance(evidence, list) else str(evidence)
    prompt = REWRITE_PROMPT.format(
        title=issue.get("title", ""),
        category=issue.get("category", ""),
        service=issue.get("affected_service", ""),
        summary=issue.get("summary", ""),
        evidence=ev_text,
        query=original_query,
    )
    try:
        resp = get_llm(temperature=0.2).invoke(prompt)
        text = (resp.content or "").strip().strip('"').strip("'")
        return text or original_query
    except Exception as e:
        logger.warning("Query rewrite failed: %s", e)
        return original_query


def retrieve_with_confidence(
    query: str,
    issue: dict[str, Any],
    k: int | None = None,
    filters: Optional[dict[str, str]] = None,
) -> tuple[list[Document], dict[str, Any]]:
    """Retrieve; if confidence is low, rewrite query and retrieve once more.

    Returns (documents, meta) where meta includes scores and whether rewrite ran.
    """
    top_k = k or config.RAG_TOP_K
    threshold = config.RAG_CONFIDENCE_THRESHOLD

    scored = retrieve_with_scores(
        query,
        k=top_k,
        filters=filters,
        use_hybrid=config.RAG_USE_HYBRID,
        use_rerank=config.RAG_USE_RERANK,
    )
    metrics = score_docs(scored)
    meta: dict[str, Any] = {
        "original_query": query[:240],
        "confidence": metrics,
        "threshold": threshold,
        "rewritten": False,
        "final_query": query[:240],
    }

    if (
        config.RAG_CONFIDENCE_REWRITE
        and metrics["top"] < threshold
    ):
        new_query = rewrite_query(issue, query)
        if new_query.strip() and new_query.strip() != query.strip():
            scored2 = retrieve_with_scores(
                new_query,
                k=top_k,
                filters=filters,
                use_hybrid=config.RAG_USE_HYBRID,
                use_rerank=config.RAG_USE_RERANK,
            )
            metrics2 = score_docs(scored2)
            meta["rewritten"] = True
            meta["rewrite_query"] = new_query[:240]
            meta["confidence_after_rewrite"] = metrics2
            # Keep the better set by top confidence.
            if metrics2["top"] >= metrics["top"]:
                scored = scored2
                metrics = metrics2
                meta["final_query"] = new_query[:240]
                meta["used_rewrite_results"] = True
            else:
                meta["used_rewrite_results"] = False

    meta["final_confidence"] = metrics
    docs = [d for d, _ in scored]
    return docs, meta
