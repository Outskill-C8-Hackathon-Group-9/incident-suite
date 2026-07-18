import json
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from app.graph import graph
from app.knowledge.runbook_store import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed the runbook vector DB once on startup (downloads embedding model first time).
    n = seed_if_empty()
    print(f"[startup] runbook store ready (added {n} docs).")
    yield


app = FastAPI(title="Incident Analysis Suite", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


def _jsonable(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, list):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    return obj


def _merge_update(final: dict, update: dict) -> None:
    """Fold a streamed node update into the accumulated final state."""
    for key, value in update.items():
        if key == "trace":
            final.setdefault("trace", []).extend(value or [])
        else:
            final[key] = value


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    raw = (await file.read()).decode("utf-8", errors="replace")
    thread_id = str(uuid.uuid4())
    run_config = {"configurable": {"thread_id": thread_id}}
    initial = {"raw_logs": raw, "filename": file.filename, "trace": []}

    async def event_stream():
        # Accumulate from streamed updates so the done event does not depend on
        # checkpoint deserialization (get_state) after the run.
        final = dict(initial)
        async for chunk in graph.astream(initial, run_config, stream_mode="updates"):
            for node_name, update in chunk.items():
                if not isinstance(update, dict):
                    continue
                _merge_update(final, update)
                payload = {"node": node_name, "update": _jsonable(update)}
                yield {"event": "node", "data": json.dumps(payload)}
        yield {"event": "done", "data": json.dumps(_jsonable(final))}

    return EventSourceResponse(event_stream())
