"""Structured request/response logging for agent nodes.

Logs are emitted as single-line JSON objects so they are easy to grep and
pipe into log aggregators. Structured payloads (dicts, lists, Pydantic models)
are serialized with json.dumps; plain strings stay as strings.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger("incident_suite.agents")


def _to_jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, set):
        return [_to_jsonable(x) for x in obj]
    return str(obj)


def format_payload(payload: Any) -> Any:
    """Return a JSON-serializable value; parse JSON strings when possible."""
    if isinstance(payload, str):
        stripped = payload.strip()
        if stripped and stripped[0] in "{[":
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass
        return payload
    return _to_jsonable(payload)


def log_agent_io(
    agent: str,
    direction: str,
    payload: Any,
    *,
    extra: dict[str, Any] | None = None,
) -> None:
    """Log an agent request or response as structured JSON.

    direction: "request" | "response" | "error"
    """
    record: dict[str, Any] = {
        "agent": agent,
        "direction": direction,
        "payload": format_payload(payload),
    }
    if extra:
        record["extra"] = _to_jsonable(extra)

    line = json.dumps(record, ensure_ascii=False, default=str)
    if direction == "error":
        logger.error(line)
    else:
        logger.info(line)


def log_llm_exchange(
    agent: str,
    *,
    request: Any,
    response: Any | None = None,
    error: str | None = None,
    latency_ms: float | None = None,
    model: str | None = None,
) -> None:
    """Log a complete LLM request, then the matching response or error."""
    extra: dict[str, Any] = {}
    if model:
        extra["model"] = model
    log_agent_io(agent, "request", request, extra=extra or None)

    resp_extra: dict[str, Any] = {}
    if latency_ms is not None:
        resp_extra["latency_ms"] = round(latency_ms, 2)
    if model:
        resp_extra["model"] = model

    if error is not None:
        log_agent_io(agent, "error", {"error": error}, extra=resp_extra or None)
    else:
        log_agent_io(agent, "response", response, extra=resp_extra or None)


def timed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000
