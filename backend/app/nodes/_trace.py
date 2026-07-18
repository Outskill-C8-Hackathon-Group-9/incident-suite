import time


def trace_event(node: str, message: str, data: dict | None = None) -> dict:
    return {"node": node, "message": message, "ts": time.time(), "data": data or {}}