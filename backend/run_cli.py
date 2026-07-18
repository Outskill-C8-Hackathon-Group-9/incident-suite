from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from app.graph import graph
from app.models import IncidentInput


def _to_jsonable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def _print_state(label: str, value) -> None:
    print(f"\n[{label}]")
    print(json.dumps(_to_jsonable(value), indent=2))


async def main(path: str) -> None:
    raw = Path(path).read_text(encoding="utf-8")
    incident = IncidentInput.model_validate_json(raw)
    config = {"configurable": {"thread_id": "itsm-notify-demo"}}

    async for chunk in graph.astream({"incident": incident, "trace": []}, config, stream_mode="updates"):
        for node_name, update in chunk.items():
            trace_items = update.get("trace", [])
            if trace_items:
                print(f"\n[{node_name}] {trace_items[-1]['message']}")
            for key, value in update.items():
                if key == "trace":
                    continue
                _print_state(f"{node_name}:{key}", value)

    final_state = graph.get_state(config).values
    _print_state("final", final_state)


if __name__ == "__main__":
    default_path = Path(__file__).resolve().parent.parent / "samples" / "itsm_notify_demo.json"
    target = sys.argv[1] if len(sys.argv) > 1 else str(default_path)
    asyncio.run(main(target))
