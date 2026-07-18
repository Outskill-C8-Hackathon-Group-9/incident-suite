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

    # classifier node
    entries: list[dict[str, Any]]
    clusters: list[dict[str, Any]]
    issues: list[dict[str, Any]]

    # later nodes
    remediations: list[dict[str, Any]]
    cookbook: dict[str, Any]
    jira_tickets: list[dict[str, Any]]
    slack_result: dict[str, Any]

    # audit trail (reducer = list concat so nodes append, not overwrite)
    trace: Annotated[list[dict], operator.add]
