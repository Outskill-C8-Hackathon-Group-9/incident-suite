# Multi-Agent DevOps Incident Analysis Suite — End-to-End Build Spec

A complete, self-contained specification for a hackathon project: an app that ingests **live uploaded
ops logs**, runs them through a **LangGraph-orchestrated pipeline of five specialized agents**,
grounds its fixes in a **RAG runbook knowledge base backed by a Chroma vector DB**, and produces
**traceable, actionable output** — detected issues, grounded remediations, an actionable checklist, a
Slack notification, and JIRA tickets for critical issues.

> **Stack (locked):** Python · **LangGraph** orchestration · **FastAPI** backend · **React (Vite)**
> frontend · **mocked** Slack + JIRA (pluggable to real) · **OpenRouter → `openai/gpt-4o-mini`** LLM
> · **RAG** via **Chroma** vector DB + **local `sentence-transformers` embeddings** · format-agnostic
> log parsing.

---

## 0. How to use this document (generation contract)

**This document is a build spec, not just a guide.** It is written so that a single pass — by an AI
coding agent or a developer — produces the entire working project with no further input. Follow these
rules:

1. **Create every file listed in the [File Manifest](#2-file-manifest), at the exact path shown, with
   exactly the content given in [Section 5](#5-backend-source-every-file) and
   [Section 6](#6-frontend-source-every-file).** Code blocks are labeled with their target path on the
   line immediately above them (e.g. `FILE: backend/app/config.py`).
2. **Do not invent extra files, frameworks, or folders.** If something isn't in the manifest, it isn't
   part of the project.
3. **Backend dependencies go in one file:** `backend/requirements.txt`. Install with `pip` inside a
   `venv`. The React frontend uses `npm` and `frontend/package.json` (a separate ecosystem — it cannot
   live in `requirements.txt`).
4. **LLM = `openai/gpt-4o-mini` via OpenRouter.** The only secret required is `OPENROUTER_API_KEY`.
   Embeddings run **locally** (no key needed).
5. **Build order:** (a) create backend files → (b) `pip install -r requirements.txt` → (c) create
   frontend files → (d) create sample logs → (e) run backend, then frontend. See
   [Section 7](#7-running-everything).

Sections 1–4 give the mental model, architecture, and manifest. Sections 5–6 are the literal source.
Sections 7+ cover running, RAG internals, demo, and the concepts checklist.

---

## Table of Contents

1. [What you're building (requirement → component map)](#1-what-youre-building)
2. [File manifest](#2-file-manifest)
3. [Architecture & data flow](#3-architecture--data-flow)
4. [LangGraph mental model](#4-langgraph-mental-model)
5. [Backend source — every file](#5-backend-source-every-file)
6. [Frontend source — every file](#6-frontend-source-every-file)
7. [Running everything](#7-running-everything)
8. [How the RAG layer works](#8-how-the-rag-layer-works)
9. [Data & privacy model (what is / isn't stored)](#9-data--privacy-model)
10. [Demo script for judges](#10-demo-script-for-judges)
11. [Concepts & agentic patterns checklist](#11-concepts--agentic-patterns-checklist)
12. [Common pitfalls](#12-common-pitfalls)
13. [Stretch goals](#13-stretch-goals)

---

## 1. What you're building

| Requirement | Component | What it does |
|---|---|---|
| Log reader/classifier agent | `nodes/classifier.py` | Deterministically parses raw logs → structured entries, groups error signatures into clusters, then LLM-classifies clusters into `DetectedIssue`s (category, severity, service, evidence). |
| Remediation agent | `nodes/remediation.py` | **Retrieves matching runbooks from the Chroma vector DB (RAG)**, then for each issue produces a grounded fix + rationale + command + risk level. |
| Cookbook synthesizer agent | `nodes/cookbook.py` | Turns issues + remediations into one ordered, actionable checklist (runbook). |
| JIRA ticket agent | `nodes/jira.py` | Creates tickets **only for critical/high issues** (conditional branch). |
| Notification agent | `nodes/notifier.py` | Pushes a formatted summary (issues, fixes, JIRA links) to Slack. |
| Orchestrator (LangGraph) | `graph.py` | `StateGraph` wiring nodes with a severity-based conditional edge, shared typed state, checkpointing, streaming. |
| RAG knowledge base | `knowledge/` | Chroma vector DB seeded with a curated runbook/past-incident corpus; local embeddings. |
| "Upload logs for live analysis" | `main.py` (`/analyze` SSE) + React upload UI | User drops a log file; the graph runs; node-by-node progress streams live. |
| "Traceable, actionable output" | in-state `trace` + UI result panels | Every node appends to an audit trail; UI shows issues, remediations (with which runbooks grounded them), checklist, Slack preview, JIRA tickets. |

---

## 2. File manifest

Create exactly these files.

```
incident-suite/
├── backend/
│   ├── requirements.txt                     # all Python deps (pip)
│   ├── .env.example                         # config template
│   ├── run_cli.py                           # run the graph without the UI (sanity check)
│   └── app/
│       ├── __init__.py                      # empty
│       ├── config.py                        # env loading
│       ├── llm.py                           # get_llm() — OpenRouter/gpt-4o-mini
│       ├── models.py                        # Pydantic schemas
│       ├── state.py                         # IncidentState (LangGraph state)
│       ├── parsing.py                       # deterministic, format-agnostic log parser
│       ├── graph.py                         # builds & compiles the StateGraph (orchestrator)
│       ├── main.py                          # FastAPI: /analyze (SSE), /health; seeds runbooks on startup
│       ├── knowledge/
│       │   ├── __init__.py                  # empty
│       │   ├── runbook_seed.py              # curated runbook corpus (the RAG source data)
│       │   └── runbook_store.py             # Chroma vector store: seed + retrieve
│       ├── nodes/
│       │   ├── __init__.py                  # empty
│       │   ├── _trace.py                     # trace_event helper
│       │   ├── classifier.py                # log reader/classifier agent
│       │   ├── remediation.py               # remediation agent (RAG-grounded)
│       │   ├── cookbook.py                  # cookbook synthesizer agent
│       │   ├── jira.py                      # JIRA ticket agent
│       │   └── notifier.py                  # Slack notification agent
│       └── integrations/
│           ├── __init__.py                  # empty
│           ├── slack_client.py              # MockSlackClient
│           └── jira_client.py               # MockJiraClient
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── api.js                           # consumes the SSE stream
│       └── App.jsx                          # upload + live timeline + results (self-contained)
└── samples/
    ├── deployment_regression.log
    ├── memory_leak.log
    └── db_exhaustion.log
```

> `backend/chroma_db/` is created at runtime by Chroma (the persisted vector store). Do not create it
> by hand; add it to `.gitignore`.

---

## 3. Architecture & data flow

```
                 ┌────────────────────────────┐
                 │    React Upload UI (Vite)  │
                 │  drop .log / .txt / .json  │
                 └──────────────┬─────────────┘
                                │ POST /analyze (multipart)
                                ▼
                 ┌────────────────────────────┐
                 │    FastAPI (SSE Stream)    │
                 │ Seeds Chroma DB on startup │
                 └──────────────┬─────────────┘
                                │ graph.astream(initial_state)
     ┌────────────────────── LangGraph ───────────────────────────────────────┐
     │                                                                         │
     │ START                                                                   │
     │   │                                                                     │
     │   ▼                                                                     │
     │ ┌──────────────┐                                                        │
     │ │ Classifier   │ Parse → Cluster → LLM → DetectedIssue[]                │
     │ └──────┬───────┘                                                        │
     │        ▼                                                                │
     │ ┌──────────────┐        ┌──────────────────────────────┐                │
     │ │ Remediation  │◄──────►│ Chroma Vector DB (RAG)        │                │
     │ │              │        │ Runbooks / Past Incidents     │                │
     │ └──────┬───────┘        └──────────────────────────────┘                │
     │        ▼                                                                │
     │ ┌──────────────┐                                                        │
     │ │  Cookbook    │ LLM → Ordered Remediation Checklist                    │
     │ └──────┬───────┘                                                        │
     │        ▼                                                                │
     │ ┌──────────────┐                                                        │
     │ │ Decision     │ Determines:                                            │
     │ │ Engine       │ • Remediative / Investigative                          │
     │ │              │ • Severity • Confidence • Policy                       │
     │ └──────┬───────┘                                                        │
     │        │                                                                │
     │   ┌────┴──────────────────────────────┐                                 │
     │   │                                   │                                 │
     │   ▼                                   ▼                                 │
     │ Remediative                     Investigative                           │
     │   │                                   │                                 │
     │   ▼                                   ▼                                 │
     │ ┌──────────────┐               ┌──────────────┐                         │
     │ │ ITSM Service │               │ ITSM Service │                         │
     │ │ Create Ticket│               │ Create Ticket│                         │
     │ └──────┬───────┘               └──────┬───────┘                         │
     │        ▼                              ▼                                 │
     │ Execute Cookbook               Round Robin Assign                       │
     │        │                              │                                 │
     │        ▼                              ▼                                 │
     │ Verify Outcome                 Return Assignee                          │
     │        │                              │                                 │
     │        ▼                              ▼                                 │
     │ Close Ticket                  Slack Notification                        │
     │        │                              │                                 │
     │        └──────────────┬───────────────┘                                 │
     │                       ▼                                                 │
     │              Slack Notification Node                                    │
     │              • Team Channel                                             │
     │              • Assigned User DM (Investigative only)                    │
     │                                                                         │
     │ END                                                                     │
     │                                                                         │
     │ Every node appends to state.trace (streamed live via SSE to the UI)     │
     └─────────────────────────────────────────────────────────────────────────┘
```

**One-sentence flow:** raw text → structured entries → detected issues → **(RAG) runbook-grounded
remediations** → checklist → (critical? JIRA tickets) → Slack notification, with a trace accumulating
throughout. The **uploaded log is never written to the vector DB** — only the curated runbook corpus
lives there; the log is the *query*, not stored content.

---

## 4. LangGraph mental model

Three ideas power the whole orchestrator:

- **State** — one typed dict (`IncidentState`) flows through the graph. Each node returns a *partial*
  update; LangGraph merges it. A reducer (`Annotated[list, operator.add]`) makes `trace` **append**
  instead of overwrite.
- **Nodes** — functions `(state) -> partial_update`. Each of the five agents is a node.
- **Edges** — fixed edges (`A → B`) and **conditional edges** (a router inspects state and returns the
  next node's name). The severity router is how "only critical issues create JIRA tickets" works.

This is *not* the OpenAI Agents SDK handoff model — there are no `transfer_to_*` tools and no `Runner`.
Control flow is the explicit graph.

---

## 5. Backend source — every file

FILE: backend/requirements.txt
```
# Multi-Agent DevOps Incident Analysis Suite — backend dependencies
# Install (inside a venv):  pip install -r requirements.txt

# ---- LangGraph orchestration + LLM ----
langgraph>=0.2.0
langchain>=0.3.0
langchain-core>=0.3.0
langchain-openai>=0.2.0            # OpenRouter (OpenAI-compatible endpoint)

# ---- RAG: vector DB + local embeddings ----
langchain-chroma>=0.1.4           # Chroma vector store (pulls in chromadb)
langchain-huggingface>=0.1.0      # HuggingFaceEmbeddings wrapper
sentence-transformers>=3.0.0      # local embedding model (all-MiniLM-L6-v2)

# ---- web layer ----
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sse-starlette>=2.1.0              # Server-Sent Events for FastAPI
python-multipart>=0.0.9          # file uploads

# ---- config / models ----
python-dotenv>=1.0.0
pydantic>=2.0.0
```

> **Heads-up:** `sentence-transformers` pulls in PyTorch, so the first `pip install` is large
> (a few hundred MB) and the first *run* downloads the `all-MiniLM-L6-v2` model (~90 MB) once, then
> works offline. If you want a lighter path, `fastembed` + `langchain-community`'s `FastEmbedEmbeddings`
> avoids torch — but the sentence-transformers path below is the most reliable to generate and run.

FILE: backend/.env.example
```bash
# ---- LLM (OpenRouter → gpt-4o-mini) ----
OPENROUTER_API_KEY=your_openrouter_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o-mini
LLM_TEMPERATURE=0.1

# ---- RAG (local embeddings + Chroma) ----
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CHROMA_DIR=./chroma_db
RAG_TOP_K=3

# ---- Mock integrations (no real creds needed) ----
SLACK_CHANNEL=#incidents
JIRA_PROJECT_KEY=INC

# ---- Optional: LangSmith tracing ----
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=ls__your_key
# LANGCHAIN_PROJECT=incident-suite
```

FILE: backend/app/__init__.py
```python
```

FILE: backend/app/config.py
```python
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))

    SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#incidents")
    JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "INC")


config = Config()
assert config.OPENROUTER_API_KEY, "OPENROUTER_API_KEY must be set in .env"
```

FILE: backend/app/llm.py
```python
from langchain_openai import ChatOpenAI
from app.config import config


def get_llm(temperature: float | None = None) -> ChatOpenAI:
    """Chat model via OpenRouter (OpenAI-compatible). Model = openai/gpt-4o-mini.

    To use real OpenAI:  remove base_url, set api_key to an OpenAI key.
    To use Anthropic:    pip install langchain-anthropic and return ChatAnthropic(...).
    Only this function changes when swapping providers.
    """
    return ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
        temperature=config.LLM_TEMPERATURE if temperature is None else temperature,
    )
```

FILE: backend/app/models.py
```python
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low", "info"]
IssueCategory = Literal[
    "memory_leak", "deployment_regression", "database", "network",
    "cpu_saturation", "timeout", "auth", "config", "unknown",
]


# ---- parsing layer ----
class LogEntry(BaseModel):
    line_no: int
    timestamp: Optional[str] = None
    level: Optional[str] = None
    service: Optional[str] = None
    message: str
    raw: str


class ErrorCluster(BaseModel):
    signature: str
    count: int
    level: str
    example_service: Optional[str] = None
    sample_lines: list[str]
    line_numbers: list[int]


# ---- classifier output (LLM structured output) ----
class DetectedIssue(BaseModel):
    id: str = Field(description="short slug id, e.g. 'oom-order-service'")
    title: str
    category: IssueCategory
    severity: Severity
    affected_service: str
    summary: str = Field(description="1-2 sentence plain-English explanation")
    evidence: list[str] = Field(description="log lines that justify this issue")


class ClassifierOutput(BaseModel):
    issues: list[DetectedIssue]


# ---- remediation output (LLM structured output) ----
class Remediation(BaseModel):
    issue_id: str
    fix_summary: str
    rationale: str = Field(description="why this addresses the root cause")
    suggested_command: str = Field(description="a concrete, SAFE command or config change")
    risk_level: Literal["low", "medium", "high"]
    requires_approval: bool
    grounded_in: list[str] = Field(
        default_factory=list,
        description="titles of runbooks retrieved from the knowledge base that informed this fix",
    )


class RemediationOutput(BaseModel):
    remediations: list[Remediation]


# ---- cookbook output (LLM structured output) ----
class ChecklistItem(BaseModel):
    step: int
    action: str
    owner_hint: str = Field(description="which role/team, e.g. 'on-call SRE'")
    done_when: str = Field(description="how to know the step succeeded")


class Cookbook(BaseModel):
    title: str
    items: list[ChecklistItem]


# ---- integration results ----
class JiraTicket(BaseModel):
    key: str
    url: str
    summary: str
    severity: Severity
    issue_id: str


class SlackResult(BaseModel):
    channel: str
    ts: str
    permalink: str
    text_preview: str
```

FILE: backend/app/state.py
```python
from __future__ import annotations
import operator
from typing import Annotated, TypedDict
from app.models import (
    LogEntry, ErrorCluster, DetectedIssue, Remediation, Cookbook,
    JiraTicket, SlackResult,
)


class IncidentState(TypedDict, total=False):
    # inputs
    raw_logs: str
    filename: str

    # classifier node
    entries: list[LogEntry]
    clusters: list[ErrorCluster]
    issues: list[DetectedIssue]

    # later nodes
    remediations: list[Remediation]
    cookbook: Cookbook
    jira_tickets: list[JiraTicket]
    slack_result: SlackResult

    # audit trail (reducer = list concat so nodes append, not overwrite)
    trace: Annotated[list[dict], operator.add]
```

FILE: backend/app/parsing.py
```python
import re
from collections import defaultdict
from app.models import LogEntry, ErrorCluster

_TS = re.compile(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?Z?)")
_LEVEL = re.compile(r"\b(ERROR|ERR|FATAL|CRITICAL|WARN(?:ING)?|INFO|DEBUG|TRACE)\b", re.I)
_SERVICE = re.compile(r"[\[\s](?:svc=)?([a-z0-9]+-service|[a-z0-9]+-svc|api-gateway)[\]\s:]", re.I)

_ERROR_LEVELS = ("ERROR", "ERR", "FATAL", "CRITICAL", "WARN", "WARNING")


def parse_logs(raw: str) -> list[LogEntry]:
    entries: list[LogEntry] = []
    for i, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        ts = _TS.search(line)
        lvl = _LEVEL.search(line)
        svc = _SERVICE.search(line)
        entries.append(LogEntry(
            line_no=i,
            timestamp=ts.group(1) if ts else None,
            level=lvl.group(1).upper() if lvl else None,
            service=svc.group(1).lower() if svc else None,
            message=line.strip(),
            raw=line,
        ))
    return entries


def _signature(msg: str) -> str:
    s = re.sub(r"[0-9a-fA-F]{8,}", "<hex>", msg)
    s = re.sub(r"\b\d+\b", "<n>", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:160]


def cluster_errors(entries: list[LogEntry]) -> list[ErrorCluster]:
    buckets: dict[str, list[LogEntry]] = defaultdict(list)
    for e in entries:
        if e.level and e.level.upper() in _ERROR_LEVELS:
            buckets[_signature(e.message)].append(e)

    clusters: list[ErrorCluster] = []
    for sig, es in sorted(buckets.items(), key=lambda kv: len(kv[1]), reverse=True):
        clusters.append(ErrorCluster(
            signature=sig,
            count=len(es),
            level=es[0].level or "ERROR",
            example_service=next((e.service for e in es if e.service), None),
            sample_lines=[e.raw for e in es[:3]],
            line_numbers=[e.line_no for e in es[:20]],
        ))
    return clusters[:25]
```

FILE: backend/app/knowledge/__init__.py
```python
```

FILE: backend/app/knowledge/runbook_seed.py
```python
"""Curated runbook / past-incident corpus. This is the RAG source data.

Each entry is a short, self-contained runbook the remediation agent can ground its
fixes in. Add more entries to improve retrieval quality — this is your knowledge base,
NOT user-uploaded logs.
"""

RUNBOOKS: list[dict] = [
    {
        "title": "OOM / memory leak in a JVM service",
        "category": "memory_leak",
        "service_hint": "order-service",
        "content": (
            "Symptoms: steadily rising heap usage, long GC pauses, java.lang.OutOfMemoryError, "
            "container OOMKilled and restart loops. Downstream services see connection refused as "
            "the pod restarts. Resolution: (1) restart/scale the affected pod to restore service; "
            "(2) capture a heap dump before restart if possible; (3) raise the memory limit as a "
            "temporary mitigation; (4) identify the leak (unbounded caches, thread/connection leaks) "
            "and ship a fix; (5) add a heap-usage alert at 80%. Rollback the last release if the leak "
            "started right after a deploy."
        ),
    },
    {
        "title": "Bad deployment causing NullPointerException regression",
        "category": "deployment_regression",
        "service_hint": "user-service",
        "content": (
            "Symptoms: a spike of NullPointerException (or 5xx) immediately after a new version is "
            "deployed; upstream gateways report elevated latency and 502s. Resolution: (1) roll back "
            "to the previous known-good version with 'kubectl rollout undo deployment/<service>'; "
            "(2) confirm error rate returns to baseline; (3) reproduce in staging; (4) add a "
            "regression test for the null path; (5) re-deploy behind a canary. Fast rollback beats "
            "hotfixing under pressure."
        ),
    },
    {
        "title": "Database connection pool exhaustion",
        "category": "database",
        "service_hint": "database-proxy",
        "content": (
            "Symptoms: 'connection pool exhausted' / 'timeout acquiring connection' errors, rising "
            "query latency, cascading timeouts in dependent services. Resolution: (1) increase pool "
            "size as an immediate mitigation; (2) find and kill long-running or leaked connections; "
            "(3) ensure connections are released (check for missing close/finally); (4) add a "
            "connection-wait-time alert; (5) consider a read replica if read-heavy."
        ),
    },
    {
        "title": "Network partition isolating a service",
        "category": "network",
        "service_hint": "inventory-service",
        "content": (
            "Symptoms: sudden 'connection timed out' / 'no route to host' between specific services "
            "while others are healthy; one service becomes unreachable cluster-wide. Resolution: "
            "(1) check network policies, security groups, and CNI health; (2) verify DNS resolution; "
            "(3) restart the affected node/pod networking if degraded; (4) fail over to a healthy "
            "replica/zone; (5) add synthetic connectivity checks between critical service pairs."
        ),
    },
    {
        "title": "CPU saturation and request queue buildup",
        "category": "cpu_saturation",
        "service_hint": "payment-service",
        "content": (
            "Symptoms: CPU pinned near 100%, growing request queue, rising p99 latency and timeouts. "
            "Resolution: (1) scale out horizontally to add capacity; (2) shed or rate-limit "
            "non-critical traffic; (3) profile hot paths for a fix; (4) enable autoscaling on CPU; "
            "(5) verify no infinite/retry storm is amplifying load."
        ),
    },
    {
        "title": "Upstream timeout / latency cascade",
        "category": "timeout",
        "service_hint": "api-gateway",
        "content": (
            "Symptoms: gateway reports upstream latency spikes and 504/502; retries amplify load. "
            "Resolution: (1) identify the slow upstream from traces; (2) apply circuit breakers and "
            "sane timeouts; (3) reduce retry aggressiveness; (4) scale or roll back the slow upstream; "
            "(5) add p99 latency alerts per upstream."
        ),
    },
]
```

FILE: backend/app/knowledge/runbook_store.py
```python
import logging
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

from app.config import config
from app.knowledge.runbook_seed import RUNBOOKS

logger = logging.getLogger(__name__)

_embeddings: HuggingFaceEmbeddings | None = None
_store: Chroma | None = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        # First call downloads the model once (~90MB), then runs locally/offline.
        _embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
    return _embeddings


def get_store() -> Chroma:
    global _store
    if _store is None:
        _store = Chroma(
            collection_name="runbooks",
            embedding_function=_get_embeddings(),
            persist_directory=config.CHROMA_DIR,
        )
    return _store


def seed_if_empty() -> int:
    """Populate the vector DB with the curated runbook corpus if it's empty.

    Returns the number of documents added (0 if already seeded).
    """
    store = get_store()
    existing = store.get()  # {'ids': [...], ...}
    if existing and existing.get("ids"):
        logger.info("Runbook store already seeded (%d docs).", len(existing["ids"]))
        return 0

    docs = [
        Document(
            page_content=rb["content"],
            metadata={
                "title": rb["title"],
                "category": rb["category"],
                "service_hint": rb.get("service_hint", ""),
            },
        )
        for rb in RUNBOOKS
    ]
    store.add_documents(docs)
    logger.info("Seeded runbook store with %d docs.", len(docs))
    return len(docs)


def retrieve(query: str, k: int | None = None) -> list[Document]:
    """Return the top-k most similar runbooks for a query string."""
    store = get_store()
    return store.similarity_search(query, k=k or config.RAG_TOP_K)
```

FILE: backend/app/nodes/__init__.py
```python
```

FILE: backend/app/nodes/_trace.py
```python
import time


def trace_event(node: str, message: str, data: dict | None = None) -> dict:
    return {"node": node, "message": message, "ts": time.time(), "data": data or {}}
```

FILE: backend/app/nodes/classifier.py
```python
from app.state import IncidentState
from app.models import ClassifierOutput
from app.parsing import parse_logs, cluster_errors
from app.llm import get_llm
from app.nodes._trace import trace_event

CLASSIFY_PROMPT = """You are a senior SRE triaging a production incident from log clusters.

You are given error/warning clusters extracted from uploaded logs. Each cluster has a signature,
an occurrence count, the affected service, and sample lines.

For each DISTINCT underlying problem, produce a DetectedIssue with:
- a short slug id (e.g. 'oom-order-service')
- a clear title
- the best-fitting category
- a severity (critical/high/medium/low/info) reasoning about blast radius and user impact
- the affected service
- a 1-2 sentence plain-English summary
- evidence: the specific sample lines that justify the issue

Merge clusters that are symptoms of the same root cause into ONE issue.

CLUSTERS:
{clusters}
"""


def classifier_node(state: IncidentState) -> dict:
    entries = parse_logs(state["raw_logs"])
    clusters = cluster_errors(entries)

    if not clusters:
        return {
            "entries": entries,
            "clusters": [],
            "issues": [],
            "trace": [trace_event("classifier", "No error/warning clusters found.")],
        }

    clusters_text = "\n\n".join(
        f"[{c.count}x] level={c.level} service={c.example_service} sig={c.signature}\n"
        + "\n".join(f"  {ln}" for ln in c.sample_lines)
        for c in clusters
    )

    llm = get_llm().with_structured_output(ClassifierOutput, method="function_calling")
    result: ClassifierOutput = llm.invoke(CLASSIFY_PROMPT.format(clusters=clusters_text))

    return {
        "entries": entries,
        "clusters": clusters,
        "issues": result.issues,
        "trace": [trace_event(
            "classifier",
            f"Parsed {len(entries)} lines, {len(clusters)} clusters, "
            f"detected {len(result.issues)} issue(s).",
            {"issues": [i.model_dump() for i in result.issues]},
        )],
    }
```

FILE: backend/app/nodes/remediation.py
```python
from app.state import IncidentState
from app.models import RemediationOutput
from app.llm import get_llm
from app.knowledge.runbook_store import retrieve
from app.config import config
from app.nodes._trace import trace_event

REMEDIATION_PROMPT = """You are an SRE proposing remediations for detected incidents.

Use the RETRIEVED RUNBOOKS below as authoritative guidance. Prefer their recommended steps.
For EACH issue, propose exactly one remediation with:
- issue_id (must match)
- fix_summary
- rationale: why this addresses the ROOT CAUSE (reference the runbook guidance where relevant)
- suggested_command: a concrete, SAFE command or config change
  (e.g. 'kubectl rollout undo deployment/user-service'). NEVER propose destructive commands
  (no 'rm -rf', 'drop database', 'DELETE FROM', 'terminate all').
- risk_level (low/medium/high)
- requires_approval: true for anything high-risk
- grounded_in: the titles of the runbooks you actually used for this issue

ISSUES:
{issues}

RETRIEVED RUNBOOKS:
{runbooks}
"""

_DANGEROUS = ("rm -rf", "drop database", "delete from", "terminate all", "mkfs", "> /dev")


def remediation_node(state: IncidentState) -> dict:
    issues = state.get("issues", [])
    if not issues:
        return {"remediations": [], "trace": [trace_event("remediation", "No issues to remediate.")]}

    # ---- RAG retrieval: pull matching runbooks per issue ----
    seen: dict[str, str] = {}          # title -> content (dedupe across issues)
    grounding_by_issue: dict[str, list[str]] = {}
    for i in issues:
        query = f"{i.title} {i.category} {i.affected_service} {i.summary}"
        docs = retrieve(query, k=config.RAG_TOP_K)
        titles = []
        for d in docs:
            title = d.metadata.get("title", "runbook")
            seen[title] = d.page_content
            titles.append(title)
        grounding_by_issue[i.id] = titles

    runbooks_text = "\n\n".join(f"[{title}]\n{content}" for title, content in seen.items()) \
        or "No matching runbooks found."

    issues_text = "\n".join(
        f"- id={i.id} | {i.severity.upper()} | {i.category} | {i.affected_service} | {i.summary}"
        for i in issues
    )

    llm = get_llm(temperature=0.2).with_structured_output(RemediationOutput, method="function_calling")
    result: RemediationOutput = llm.invoke(
        REMEDIATION_PROMPT.format(issues=issues_text, runbooks=runbooks_text)
    )

    # safety net on top of the prompt-level ban
    safe = [
        r for r in result.remediations
        if not any(bad in r.suggested_command.lower() for bad in _DANGEROUS)
    ]

    return {
        "remediations": safe,
        "trace": [trace_event(
            "remediation",
            f"Proposed {len(safe)} remediation(s), grounded in "
            f"{len(seen)} retrieved runbook(s).",
            {
                "remediations": [r.model_dump() for r in safe],
                "retrieved_runbooks": grounding_by_issue,
            },
        )],
    }
```

FILE: backend/app/nodes/cookbook.py
```python
from app.state import IncidentState
from app.models import Cookbook
from app.llm import get_llm
from app.nodes._trace import trace_event

COOKBOOK_PROMPT = """You are writing an actionable incident-response checklist (runbook).

Given the detected issues and proposed remediations, produce an ORDERED checklist a first-responder
can follow end to end: contain first, then diagnose, then fix, then verify. Each step needs a step
number, an action, an owner_hint (role/team), and done_when (verification).

ISSUES:
{issues}

REMEDIATIONS:
{remediations}
"""


def cookbook_node(state: IncidentState) -> dict:
    issues = state.get("issues", [])
    rems = state.get("remediations", [])
    if not issues:
        return {"trace": [trace_event("cookbook", "No issues; skipped checklist.")]}

    llm = get_llm(temperature=0.3).with_structured_output(Cookbook, method="function_calling")
    cookbook: Cookbook = llm.invoke(COOKBOOK_PROMPT.format(
        issues="\n".join(f"- {i.title} ({i.severity})" for i in issues),
        remediations="\n".join(f"- {r.issue_id}: {r.fix_summary}" for r in rems),
    ))
    return {
        "cookbook": cookbook,
        "trace": [trace_event("cookbook", f"Built checklist with {len(cookbook.items)} step(s).",
                              {"cookbook": cookbook.model_dump()})],
    }
```

FILE: backend/app/nodes/jira.py
```python
from app.state import IncidentState
from app.integrations.jira_client import MockJiraClient
from app.nodes._trace import trace_event

CRITICAL = {"critical", "high"}


def jira_node(state: IncidentState) -> dict:
    client = MockJiraClient()
    issues = [i for i in state.get("issues", []) if i.severity in CRITICAL]
    rem_by_id = {r.issue_id: r for r in state.get("remediations", [])}

    tickets = []
    for issue in issues:
        rem = rem_by_id.get(issue.id)
        ticket = client.create_ticket(
            summary=issue.title,
            severity=issue.severity,
            issue_id=issue.id,
            description=(
                f"{issue.summary}\n\nAffected: {issue.affected_service}\n"
                f"Proposed fix: {rem.fix_summary if rem else 'see checklist'}\n"
                f"Command: {rem.suggested_command if rem else 'n/a'}"
            ),
        )
        tickets.append(ticket)

    return {
        "jira_tickets": tickets,
        "trace": [trace_event("jira", f"Created {len(tickets)} JIRA ticket(s) for critical issues.",
                              {"tickets": [t.model_dump() for t in tickets]})],
    }
```

FILE: backend/app/nodes/notifier.py
```python
from app.state import IncidentState
from app.integrations.slack_client import MockSlackClient
from app.nodes._trace import trace_event


def _format_message(state: IncidentState) -> str:
    issues = state.get("issues", [])
    tickets = {t.issue_id: t for t in state.get("jira_tickets", [])}
    lines = [f":rotating_light: *Incident Analysis — {len(issues)} issue(s) detected*", ""]
    for i in issues:
        link = f" — <{tickets[i.id].url}|{tickets[i.id].key}>" if i.id in tickets else ""
        lines.append(f"*{i.severity.upper()}* `{i.affected_service}` — {i.title}{link}")
        lines.append(f"    ↳ {i.summary}")
    cb = state.get("cookbook")
    if cb:
        lines += ["", f":clipboard: *Runbook:* {cb.title} ({len(cb.items)} steps)"]
    return "\n".join(lines)


def notifier_node(state: IncidentState) -> dict:
    client = MockSlackClient()
    text = _format_message(state)
    result = client.post_message(text=text)
    return {
        "slack_result": result,
        "trace": [trace_event("notifier", f"Posted summary to {result.channel}.",
                              {"slack": result.model_dump()})],
    }
```

FILE: backend/app/integrations/__init__.py
```python
```

FILE: backend/app/integrations/jira_client.py
```python
import itertools
from app.models import JiraTicket
from app.config import config


class MockJiraClient:
    """Drop-in mock. To go real: replace create_ticket() with a POST to
    /rest/api/3/issue (the `jira` package or httpx). Keep the JiraTicket return type."""

    _counter = itertools.count(101)

    def create_ticket(self, *, summary: str, severity: str, issue_id: str, description: str) -> JiraTicket:
        num = next(self._counter)
        key = f"{config.JIRA_PROJECT_KEY}-{num}"
        url = f"https://your-org.atlassian.net/browse/{key}"
        print(f"[MOCK JIRA] created {key}  ({severity})  {summary}")
        return JiraTicket(key=key, url=url, summary=summary, severity=severity, issue_id=issue_id)
```

FILE: backend/app/integrations/slack_client.py
```python
import time
import uuid
from app.models import SlackResult
from app.config import config


class MockSlackClient:
    """Drop-in mock. To go real: slack_sdk.WebClient(token=...).chat_postMessage(...).
    Keep the SlackResult return type."""

    def post_message(self, *, text: str, channel: str | None = None) -> SlackResult:
        ch = channel or config.SLACK_CHANNEL
        ts = f"{time.time():.6f}"
        permalink = f"https://your-workspace.slack.com/archives/CHANNEL/p{uuid.uuid4().hex[:12]}"
        print(f"[MOCK SLACK] -> {ch}\n{text}\n")
        return SlackResult(channel=ch, ts=ts, permalink=permalink, text_preview=text)
```

FILE: backend/app/graph.py
```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.state import IncidentState
from app.nodes.classifier import classifier_node
from app.nodes.remediation import remediation_node
from app.nodes.cookbook import cookbook_node
from app.nodes.jira import jira_node
from app.nodes.notifier import notifier_node

CRITICAL = {"critical", "high"}


def route_by_severity(state: IncidentState) -> str:
    """Conditional edge: go to JIRA only if there's a critical/high issue."""
    if any(i.severity in CRITICAL for i in state.get("issues", [])):
        return "jira"
    return "notifier"


def build_graph():
    g = StateGraph(IncidentState)

    g.add_node("classifier", classifier_node)
    g.add_node("remediation", remediation_node)
    g.add_node("cookbook", cookbook_node)
    g.add_node("jira", jira_node)
    g.add_node("notifier", notifier_node)

    g.add_edge(START, "classifier")
    g.add_edge("classifier", "remediation")
    g.add_edge("remediation", "cookbook")
    g.add_conditional_edges("cookbook", route_by_severity, {"jira": "jira", "notifier": "notifier"})
    g.add_edge("jira", "notifier")
    g.add_edge("notifier", END)

    return g.compile(checkpointer=MemorySaver())


graph = build_graph()
```

FILE: backend/app/main.py
```python
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


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    raw = (await file.read()).decode("utf-8", errors="replace")
    thread_id = str(uuid.uuid4())
    run_config = {"configurable": {"thread_id": thread_id}}
    initial = {"raw_logs": raw, "filename": file.filename, "trace": []}

    async def event_stream():
        async for chunk in graph.astream(initial, run_config, stream_mode="updates"):
            for node_name, update in chunk.items():
                payload = {"node": node_name, "update": _jsonable(update)}
                yield {"event": "node", "data": json.dumps(payload)}
        final = graph.get_state(run_config).values
        yield {"event": "done", "data": json.dumps(_jsonable(final))}

    return EventSourceResponse(event_stream())
```

FILE: backend/run_cli.py
```python
"""Run the graph without the UI — a quick sanity check.

Usage:  python run_cli.py ../samples/deployment_regression.log
"""
import asyncio
import sys

from app.graph import graph
from app.knowledge.runbook_store import seed_if_empty


async def main(path: str) -> None:
    seed_if_empty()
    raw = open(path, encoding="utf-8").read()
    cfg = {"configurable": {"thread_id": "cli-1"}}
    async for chunk in graph.astream({"raw_logs": raw, "trace": []}, cfg, stream_mode="updates"):
        for node, update in chunk.items():
            for ev in update.get("trace", []):
                print(f"[{node}] {ev['message']}")

    final = graph.get_state(cfg).values
    print("\n--- SLACK PREVIEW ---")
    if final.get("slack_result"):
        print(final["slack_result"].text_preview)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "../samples/deployment_regression.log"
    asyncio.run(main(target))
```

---

## 6. Frontend source — every file

FILE: frontend/package.json
```json
{
  "name": "incident-suite-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.0"
  }
}
```

FILE: frontend/vite.config.js
```javascript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
```

FILE: frontend/index.html
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>DevOps Incident Analysis Suite</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

FILE: frontend/src/main.jsx
```jsx
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

FILE: frontend/src/api.js
```javascript
const BASE = "http://localhost:8000";

export async function analyze(file, { onNode, onDone, onError }) {
  try {
    const form = new FormData();
    form.append("file", file);

    const res = await fetch(`${BASE}/analyze`, { method: "POST", body: form });
    if (!res.ok || !res.body) throw new Error(`Request failed: ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const frames = buffer.split("\n\n");
      buffer = frames.pop();
      for (const frame of frames) {
        const evt = frame.match(/^event: (.*)$/m)?.[1];
        const data = frame.match(/^data: (.*)$/m)?.[1];
        if (!data) continue;
        const parsed = JSON.parse(data);
        if (evt === "node") onNode?.(parsed);
        else if (evt === "done") onDone?.(parsed);
      }
    }
  } catch (err) {
    onError?.(err);
  }
}
```

FILE: frontend/src/App.jsx
```jsx
import { useState } from "react";
import { analyze } from "./api";

const NODES = ["classifier", "remediation", "cookbook", "jira", "notifier"];
const LABELS = {
  classifier: "Log Reader / Classifier",
  remediation: "Remediation (RAG)",
  cookbook: "Cookbook Synthesizer",
  jira: "JIRA Tickets",
  notifier: "Slack Notification",
};

export default function App() {
  const [file, setFile] = useState(null);
  const [active, setActive] = useState({});
  const [trace, setTrace] = useState([]);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    if (!file) return;
    setRunning(true);
    setActive({});
    setTrace([]);
    setResult(null);
    setError(null);
    await analyze(file, {
      onNode: ({ node, update }) => {
        setActive((a) => ({ ...a, [node]: true }));
        if (update?.trace) setTrace((t) => [...t, ...update.trace]);
      },
      onDone: (finalState) => {
        setResult(finalState);
        setRunning(false);
      },
      onError: (err) => {
        setError(String(err));
        setRunning(false);
      },
    });
  };

  return (
    <div style={{ maxWidth: 920, margin: "2rem auto", fontFamily: "system-ui", padding: "0 1rem" }}>
      <h1>DevOps Incident Analysis Suite</h1>
      <p style={{ color: "#6b7280" }}>
        Upload ops logs. Five LangGraph agents detect issues, retrieve matching runbooks (RAG),
        propose fixes, build a checklist, file JIRA tickets for critical issues, and notify Slack.
      </p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "1rem 0" }}>
        <input
          type="file"
          accept=".log,.txt,.json"
          onChange={(e) => setFile(e.target.files[0])}
        />
        <button onClick={run} disabled={!file || running}>
          {running ? "Analyzing…" : "Analyze logs"}
        </button>
      </div>

      {error && <div style={{ color: "#b91c1c" }}>Error: {error}</div>}

      <div style={{ display: "flex", gap: 8, margin: "1rem 0", flexWrap: "wrap" }}>
        {NODES.map((n) => (
          <div
            key={n}
            style={{
              padding: "6px 10px",
              borderRadius: 6,
              background: active[n] ? "#16a34a" : "#e5e7eb",
              color: active[n] ? "#fff" : "#374151",
              fontSize: 13,
            }}
          >
            {LABELS[n]}
          </div>
        ))}
      </div>

      <div
        style={{
          background: "#0b1020",
          color: "#9fe8ff",
          padding: 12,
          borderRadius: 8,
          fontFamily: "monospace",
          fontSize: 12,
          minHeight: 80,
        }}
      >
        {trace.length === 0 && <div style={{ opacity: 0.5 }}>Trace will stream here…</div>}
        {trace.map((t, i) => (
          <div key={i}>
            [{t.node}] {t.message}
          </div>
        ))}
      </div>

      {result && <Results state={result} />}
    </div>
  );
}

function Card({ children }) {
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12, margin: "8px 0" }}>
      {children}
    </div>
  );
}

function Results({ state }) {
  const tickets = state.jira_tickets || [];
  return (
    <div style={{ marginTop: 24 }}>
      <h2>Detected issues</h2>
      {(state.issues || []).map((i) => (
        <Card key={i.id}>
          <b>
            [{i.severity.toUpperCase()}] {i.title}
          </b>{" "}
          — <i>{i.affected_service}</i>
          <p style={{ margin: "6px 0 0" }}>{i.summary}</p>
        </Card>
      ))}

      <h2>Remediations (RAG-grounded)</h2>
      {(state.remediations || []).map((r) => (
        <Card key={r.issue_id}>
          <b>{r.issue_id}</b>: {r.fix_summary}
          <pre style={{ background: "#f3f4f6", padding: 8, overflowX: "auto" }}>
            {r.suggested_command}
          </pre>
          <div style={{ fontSize: 13, color: "#374151" }}>{r.rationale}</div>
          {r.grounded_in?.length > 0 && (
            <div style={{ fontSize: 12, color: "#2563eb", marginTop: 6 }}>
              grounded in: {r.grounded_in.join(", ")}
            </div>
          )}
        </Card>
      ))}

      {state.cookbook && (
        <>
          <h2>{state.cookbook.title}</h2>
          <ol>
            {state.cookbook.items.map((it) => (
              <li key={it.step} style={{ marginBottom: 6 }}>
                {it.action} <i>({it.owner_hint})</i>
                <br />
                <small style={{ color: "#6b7280" }}>done when: {it.done_when}</small>
              </li>
            ))}
          </ol>
        </>
      )}

      {tickets.length > 0 && (
        <>
          <h2>JIRA tickets created</h2>
          <ul>
            {tickets.map((t) => (
              <li key={t.key}>
                <a href={t.url} target="_blank" rel="noreferrer">
                  {t.key}
                </a>{" "}
                — {t.summary} ({t.severity})
              </li>
            ))}
          </ul>
        </>
      )}

      {state.slack_result && (
        <>
          <h2>Slack notification → {state.slack_result.channel}</h2>
          <pre
            style={{
              background: "#4a154b",
              color: "#fff",
              padding: 12,
              borderRadius: 8,
              whiteSpace: "pre-wrap",
            }}
          >
            {state.slack_result.text_preview}
          </pre>
        </>
      )}
    </div>
  );
}
```

---

### Sample logs

FILE: samples/deployment_regression.log
```
2025-05-01T10:02:11Z INFO  [api-gateway] request GET /checkout 200 45ms
2025-05-01T10:05:31Z INFO  [user-service] deployed version v2.5.0
2025-05-01T10:05:48Z ERROR [user-service] NullPointerException at UserProfileHandler.resolve(line 88)
2025-05-01T10:05:49Z ERROR [user-service] NullPointerException at UserProfileHandler.resolve(line 88)
2025-05-01T10:05:52Z ERROR [user-service] NullPointerException at UserProfileHandler.resolve(line 88)
2025-05-01T10:06:03Z WARN  [api-gateway] upstream user-service latency 4200ms (p99)
2025-05-01T10:06:20Z ERROR [api-gateway] 502 Bad Gateway from user-service
2025-05-01T10:06:41Z ERROR [user-service] NullPointerException at UserProfileHandler.resolve(line 88)
2025-05-01T10:07:10Z WARN  [order-service] retrying user lookup (attempt 3)
```

FILE: samples/memory_leak.log
```
2025-05-02T14:00:00Z INFO  [order-service] heap usage 512MB / 2048MB
2025-05-02T14:20:00Z WARN  [order-service] heap usage 1400MB / 2048MB
2025-05-02T14:35:00Z WARN  [order-service] GC pause 1200ms
2025-05-02T14:41:00Z ERROR [order-service] java.lang.OutOfMemoryError: Java heap space
2025-05-02T14:41:03Z FATAL [order-service] container OOMKilled, restarting
2025-05-02T14:41:30Z ERROR [payment-service] connection refused to order-service
2025-05-02T14:41:45Z ERROR [payment-service] connection refused to order-service
```

FILE: samples/db_exhaustion.log
```
2025-05-03T09:10:00Z INFO  [database-proxy] pool size 20, active 6
2025-05-03T09:22:14Z WARN  [database-proxy] pool size 20, active 19
2025-05-03T09:23:01Z ERROR [database-proxy] connection pool exhausted, timeout acquiring connection
2025-05-03T09:23:02Z ERROR [order-service] timeout acquiring connection from database-proxy
2025-05-03T09:23:05Z ERROR [payment-service] timeout acquiring connection from database-proxy
2025-05-03T09:23:20Z WARN  [api-gateway] upstream order-service latency 8100ms (p99)
2025-05-03T09:23:40Z ERROR [database-proxy] connection pool exhausted, timeout acquiring connection
```

---

## 7. Running everything

**Terminal 1 — backend**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate                  # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env                        # then paste your OPENROUTER_API_KEY
uvicorn app.main:app --reload --port 8000
```

On first startup you'll see the embedding model download once, then
`[startup] runbook store ready`. A `backend/chroma_db/` folder appears (the persisted vector DB).

**Terminal 2 — frontend**

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

Open the UI, drop `samples/deployment_regression.log`, click **Analyze logs**, and watch the five
agents light up, the trace stream, and the results panels fill in.

**No-UI sanity check:**

```bash
cd backend
source .venv/bin/activate
python run_cli.py ../samples/deployment_regression.log
```

---

## 8. How the RAG layer works

- **Source data:** `knowledge/runbook_seed.py` holds a curated corpus of runbooks/past incidents (you
  author these — they are reference knowledge, not user data).
- **Indexing:** on startup, `seed_if_empty()` embeds each runbook with a **local
  `sentence-transformers` model** and stores the vectors in **Chroma**, persisted to `CHROMA_DIR`. It
  runs once; subsequent startups detect the existing collection and skip re-seeding.
- **Retrieval:** in `remediation_node`, for each detected issue we build a query from its
  title/category/service/summary and call `retrieve()` for the top-`RAG_TOP_K` runbooks. Those
  runbook texts are injected into the remediation prompt as authoritative guidance, and the model
  records which runbooks it used in `grounded_in` (surfaced in the UI and the trace).
- **Why local embeddings:** OpenRouter is a chat gateway, not an embeddings provider, so embeddings run
  locally with no extra key. This keeps the "one key" setup and works offline after the first model
  download.
- **Reranking (optional):** for a larger corpus you could add a cross-encoder reranker over the
  retrieved set. Skip for the hackathon unless you have spare time — with a handful of runbooks,
  vector similarity alone is enough.

---

## 9. Data & privacy model

Be able to state this crisply — judges like a clear data story.

- **Uploaded logs are ephemeral.** They're read into memory, passed through the graph as `raw_logs`,
  held only in the in-RAM `MemorySaver` checkpointer for the run's lifetime, and discarded when the
  process ends. **They are never written to disk or to the vector DB.**
- **The vector DB holds only the curated runbook corpus** — reference material you author, not customer
  data. The uploaded log is the *query* against it, not stored content.
- **Consequence:** adding RAG did **not** turn this into a system that stores user logs. If you *wanted*
  a "we've seen this incident before" feature you could persist processed incidents too — but that's a
  deliberate step up in responsibility (retention, secret-scrubbing, PII), not a free side effect.

---

## 10. Demo script for judges

1. **Frame (20s):** "Ops teams drown in logs during incidents. Five specialized agents, orchestrated by
   LangGraph, detect issues, retrieve matching runbooks from a vector DB to ground the fixes, build a
   checklist, file JIRA tickets for the criticals, and notify Slack — all traceable."
2. **Upload (20s):** drop `deployment_regression.log`. "Raw, unstructured production logs."
3. **Watch it run (60s):** narrate as nodes light up — "classifier detected a critical NPE regression…
   the remediation agent **retrieved the 'bad deployment / NPE regression' runbook from Chroma** and
   grounded its rollback fix in it… cookbook built the runbook… because it's *critical*, the graph
   **branched** to JIRA…"
4. **Show the RAG grounding (20s):** point at the `grounded in: …` line under a remediation. "That fix
   isn't hallucinated — it's grounded in our knowledge base via vector retrieval."
5. **Show the branch (20s):** "A medium-severity log wouldn't create a ticket — the orchestrator routes
   on severity. That's a LangGraph conditional edge."
6. **Results tour (40s):** issue card → remediation + command → checklist → JIRA link → Slack message
   that includes the ticket link.
7. **Architecture slide (30s):** say the words — *StateGraph, typed shared state, conditional routing,
   RAG with Chroma + local embeddings, streaming, checkpointing, structured outputs.*
8. **Close (20s):** "Slack/JIRA are mocked but pluggable — two files to swap for the real SDKs. Uploaded
   logs are ephemeral; only the curated runbook corpus is persisted."

---

## 11. Concepts & agentic patterns checklist

Use this in your writeup — it's the "what did we demonstrate" list.

| Concept | Where |
|---|---|
| **Multi-agent orchestration (LangGraph)** | `graph.py` — StateGraph with 5 nodes |
| **Shared typed state + reducer** | `state.py` — `IncidentState`, `trace` append reducer |
| **Conditional routing** | `route_by_severity` — critical → JIRA branch |
| **Prompt chaining** | classifier → remediation → cookbook |
| **RAG (retrieval-augmented generation)** | `remediation_node` retrieves runbooks before proposing fixes |
| **Vector database** | Chroma, persisted, seeded from the runbook corpus |
| **Embeddings** | local `sentence-transformers` (all-MiniLM-L6-v2) |
| **Structured outputs** | `.with_structured_output(PydanticModel)` on every LLM call |
| **Tool use** | Slack/JIRA clients + deterministic parser |
| **Guardrails / safety** | destructive-command ban (prompt + code filter) |
| **Streaming** | `graph.astream(stream_mode="updates")` → SSE → live UI |
| **Checkpointing / state persistence** | `MemorySaver` |
| **Observability / traceability** | in-state `trace` + optional LangSmith |
| **Resource-aware design** | parse + cluster before the LLM (fewer tokens) |
| **Human-in-the-loop (stretch)** | `interrupt_before=["jira"]` |
| **Reranking (stretch)** | cross-encoder over retrieved runbooks |

---

## 12. Common pitfalls

- **Structured output failures on OpenRouter.** Always use `method="function_calling"` (already set).
  `openai/gpt-4o-mini` handles it well; some other models don't.
- **OpenRouter "no endpoints found" / 404.** Enable model/privacy access in the OpenRouter dashboard
  (Settings → Privacy). It's an account setting, not a code bug.
- **`trace` overwritten instead of appended.** You dropped the `Annotated[list, operator.add]` reducer
  on the state field.
- **First run is slow / downloads a lot.** `sentence-transformers` pulls torch (install) and downloads
  the embedding model (first run). Expected; it's cached afterward.
- **Chroma re-seeds every run.** You changed `CHROMA_DIR` or deleted the folder; `seed_if_empty()`
  re-seeds only when the collection is empty.
- **CORS error in the browser.** The frontend origin (`http://localhost:5173`) must be in the FastAPI
  `allow_origins` list.
- **Conditional edge returns an unknown key.** The router's return string must be a key in the mapping
  passed to `add_conditional_edges`.
- **Node returns the whole state.** Nodes must return only changed fields, or they clobber
  reducer-managed fields like `trace`.
- **SSE arrives all at once.** A buffering proxy; test directly against `:8000`.

---

## 13. Stretch goals

Pick one or two if time allows:

- **Human-in-the-loop approval** before JIRA/Slack: compile with `interrupt_before=["jira"]`, resume
  from the UI after the user approves. High "responsible AI" value.
- **Grow the runbook corpus** and add category/service metadata filtering to retrieval — shows the RAG
  scaling story.
- **Reranker** (cross-encoder) over retrieved runbooks.
- **Real Slack/JIRA** via `slack_sdk` / `jira` — swap the two client files, no node changes.
- **Persistent checkpointer** (`SqliteSaver`) so runs survive a restart and you can show run history.
- **Severity dashboard** in the UI from `state.entries`.

---

### Final note

Lead the demo with the two things that earn points here: **LangGraph orchestration made visible** (typed
state, five nodes, the severity conditional edge) and **RAG grounding** (Chroma vector DB + local
embeddings feeding the remediation agent). Keep Slack/JIRA mocked but polished, keep uploaded logs
ephemeral, and let the streaming timeline sell it. Good luck. 🚀
