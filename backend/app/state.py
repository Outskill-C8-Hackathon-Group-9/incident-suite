from __future__ import annotations
import operator
from typing import Annotated, Any, TypedDict


class IncidentState(TypedDict, total=False):
    """Graph state uses plain JSON-serializable values only.

    Pydantic models are used at LLM / parsing boundaries, then dumped to dicts
    before writing into state so LangGraph checkpointing stays msgpack-safe.
    """

    # inputs
    raw_logs: str
    filename: str
    openrouter_api_key: str  # passed per-request from the frontend

    # classifier node
    entries: list[dict[str, Any]]
    clusters: list[dict[str, Any]]
    issues: list[dict[str, Any]]

    # later nodes
    remediations: list[dict[str, Any]]
    cookbook: dict[str, Any]

    # decision engine: one Decision (+ title) per issue
    decisions: list[dict[str, Any]]

    # ITSM: one entry per issue — {issue_id, title, decision, ticket,
    # assigned_engineer, duplicate_found, execution?, verification?}
    tickets: list[dict[str, Any]]

    notification: dict[str, Any]

    # audit trail (reducer = list concat so nodes append, not overwrite)
    trace: Annotated[list[dict], operator.add]
