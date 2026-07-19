# Multi-Agent DevOps Incident Analysis Suite — Build Spec (v2)

This supersedes `BUILD_GUIDE.md` for how the system actually works today. The
original guide's Section 3 diagram sketched a decision-engine/ITSM extension
that was never built out in its own Sections 5–6 (those only shipped the
5-node RAG pipeline: classifier → remediation → cookbook → jira → notifier,
with mocked Slack/JIRA). This document describes the merged, live system:
the RAG pipeline plus a real decision engine, real Jira/Slack integration,
per-issue ticketing, and a closed RAG feedback loop.

> **Stack (locked):** Python · **LangGraph** orchestration · **FastAPI**
> backend · **React (Vite + TypeScript)** frontend, behind **Clerk** auth ·
> **real Jira REST + Slack Web API** (mock fallback when creds absent) ·
> **OpenRouter → `openai/gpt-4o-mini`** LLM · **RAG** via **Chroma** vector
> DB + local `sentence-transformers` embeddings · format-agnostic log parsing.

---

## 1. What changed vs. the original guide

| Area | Original guide | This build |
|---|---|---|
| Ticketing | One mock ticket for critical/high issues only | One real ticket **per detected issue**, always created |
| Decision | None (severity-only routing to JIRA) | Deterministic decision engine: cookbook/RAG hit-count → remediative vs investigative |
| Titles | N/A | LLM-generated (`temperature=0`) per-issue title, e.g. `[user-service] NullPointerException identified`, regex fallback |
| Assignment | Never | Every ticket assigned to an on-call engineer immediately (specialty match → round-robin fallback) |
| Notification | Mock Slack, channel only | Real Slack: team channel message + DM to the assigned engineer, every incident |
| Duplicates | N/A | Existing open ticket with the same title is reused/updated, not re-created |
| RAG feedback | Static seed corpus only | Resolved incidents are ingested back into the vector store, so repeat issues become hits next time |
| RAG retrieval | Unfiltered top-k (always a "hit") | Distance-thresholded (`RAG_MAX_DISTANCE`) so genuinely novel issues get zero hits and go investigative |
| Integrations | `MockSlackClient` / `MockJiraClient`, hardcoded | Real `JiraTicketManager` / `SlackNotifier` (REST + Web API), mock fallback only when creds missing |
| Frontend | Single self-contained `App.jsx` | Full TS app behind Clerk auth: dashboard grid, agent swarm panel, per-ticket results, orchestrator/Slack side panels |

---

## 2. Architecture & data flow

```
                 ┌────────────────────────────┐
                 │  React Upload UI (Vite)     │
                 │  behind Clerk auth          │
                 └──────────────┬─────────────┘
                                │ POST /api/analyze (multipart, SSE response)
                                ▼
                 ┌────────────────────────────┐
                 │  FastAPI (SSE stream)       │
                 │  seeds Chroma on startup    │
                 └──────────────┬─────────────┘
                                │ graph.astream(initial_state)
 ┌─────────────────────────── LangGraph ────────────────────────────────────┐
 │ START                                                                    │
 │   │                                                                      │
 │   ▼                                                                      │
 │ classifier        Parse → cluster → LLM → DetectedIssue[]               │
 │   │                                                                      │
 │   ▼                                                                      │
 │ remediation ◄──► Chroma (RAG)   retrieve runbooks per issue,             │
 │   │               distance-thresholded (RAG_MAX_DISTANCE)                │
 │   ▼                                                                      │
 │ cookbook          LLM → ordered checklist, rag_hits tagged per item      │
 │   │                                                                      │
 │   ▼                                                                      │
 │ decide_response   Decision engine: 1 Decision + 1 title PER ISSUE        │
 │   │                (cookbook/RAG hits present → remediative;             │
 │   │                 zero hits → investigative)                          │
 │   ▼                                                                      │
 │ create_ticket     Per issue: reuse open ticket by title (dedupe) or      │
 │   │                create; ALWAYS assign an on-call engineer            │
 │   ▼                                                                      │
 │ execute_cookbook  Remediative tickets only — auto-run cookbook steps    │
 │   ▼                                                                      │
 │ verify_outcome    Remediative tickets only — pass unless a remediation  │
 │   │                requires human approval                              │
 │   ▼                                                                      │
 │ close_ticket      Close on verified success; ingest resolved incident   │
 │   │                into the RAG store (add_runbook)                     │
 │   ▼                                                                      │
 │ notify_slack      Team channel message (all tickets) + DM to every       │
 │                    assigned engineer                                     │
 │ END                                                                      │
 │                                                                           │
 │ Every node appends to state.trace (streamed live via SSE to the UI)      │
 └───────────────────────────────────────────────────────────────────────────┘
```

`execute_cookbook` / `verify_outcome` / `close_ticket` are straight graph
edges, not conditional ones — each node loops over `state["tickets"]`
internally and skips entries whose `decision.path != "remediative"`. This
keeps per-issue branching (a single run can have both remediative and
investigative incidents) without LangGraph-level conditional routing.

---

## 3. File manifest (current)

```
incident-suite/
├── backend/
│   ├── requirements.txt
│   ├── .env                                 # real Jira/Slack/OpenRouter creds + engineer roster
│   ├── run_cli.py                           # run the graph without the UI
│   └── app/
│       ├── config.py                        # env loading incl. multiline ENGINEER_MAPPING JSON parser
│       ├── llm.py                           # get_llm() — OpenRouter/gpt-4o-mini, per-request api_key override
│       ├── models.py                        # Pydantic schemas (Issue, Remediation, Cookbook, Decision, JiraTicket, Engineer, ...)
│       ├── state.py                         # IncidentState — plain-dict LangGraph state
│       ├── parsing.py                       # deterministic log parser
│       ├── decision_engine.py               # per-issue Decision + title generation
│       ├── graph.py                         # StateGraph — 9 nodes, straight edges
│       ├── main.py                          # FastAPI: /api/analyze (SSE), /health, static SPA serving
│       ├── knowledge/
│       │   ├── runbook_seed.py              # curated runbook corpus (RAG source data)
│       │   └── runbook_store.py             # Chroma: seed, retrieve (distance-thresholded), add_runbook
│       ├── nodes/
│       │   ├── _trace.py
│       │   ├── classifier.py                # log reader/classifier agent
│       │   ├── remediation.py               # RAG-grounded remediation agent
│       │   ├── cookbook.py                  # checklist synthesizer
│       │   ├── decide_response.py           # calls decision_engine.decide_all
│       │   ├── create_ticket.py             # per-issue create-or-reuse + always-assign
│       │   ├── assign_ticket.py             # specialty inference + engineer selection (helper, not a graph node)
│       │   ├── execute_cookbook.py          # remediative-only: run cookbook steps
│       │   ├── verify_outcome.py            # remediative-only: pass/needs-approval
│       │   ├── close_ticket.py              # close + RAG ingestion on success
│       │   └── notify_slack.py              # team message + per-engineer DM
│       └── integrations/
│           ├── jira_client.py               # JiraTicketManager — real REST, mock fallback
│           └── slack_client.py              # SlackNotifier — real Web API/webhook, mock fallback
├── frontend/
│   └── src/
│       ├── main.tsx, AppRouter.tsx           # Clerk-gated routing
│       ├── App.tsx                           # dashboard grid, run orchestration
│       ├── api.ts                            # SSE client for /api/analyze
│       ├── types.ts                          # shared domain types incl. TicketEntry[]
│       └── components/
│           ├── AppHeader.tsx, LoginPage.tsx
│           ├── LeftPanel.tsx                 # API key, upload, agent swarm status
│           ├── TerminalWindow.tsx            # live trace stream
│           ├── Results.tsx                   # issues / remediations / cookbook / per-ticket cards
│           └── RightPanel.tsx                # orchestrator + Slack preview panels
└── samples/
    ├── deployment_regression.log
    ├── memory_leak.log
    └── db_exhaustion.log
```

`backend/chroma_db/` is created at runtime by Chroma; not committed.

---

## 4. State shape (`IncidentState`)

```python
raw_logs: str
filename: str
openrouter_api_key: str          # per-request override from the frontend

entries: list[dict]              # parsed log lines
clusters: list[dict]             # error/warning clusters
issues: list[dict]               # DetectedIssue[] from classifier

remediations: list[dict]         # Remediation[], RAG-grounded
cookbook: dict                   # Cookbook — title + ordered ChecklistItem[]

decisions: list[dict]            # one Decision (+ title) per issue
tickets: list[dict]              # one entry per issue:
                                  #   {issue_id, title, decision, ticket,
                                  #    assigned_engineer, duplicate_found,
                                  #    execution?, verification?}
notification: dict               # NotificationResult — channel + team/DM permalinks

trace: list[dict]                # append-only audit trail (operator.add reducer)
```

---

## 5. Decision engine

`app/decision_engine.py` computes one `Decision` per issue from signals
already produced upstream — it never re-parses the log:

- **cookbook hit**: the issue's (or its matching cookbook item's) `rag_hits`
  field is `"cookbook"`.
- **RAG hit**: `rag_hits == "db"`, or the issue's remediation lists any
  `grounded_in` runbook titles.
- `total hits > 0` → **remediative** (confidence scales with hit count, capped
  at 0.95); `total hits == 0` → **investigative** (confidence 0.5, deferred
  to a human).

**Title generation** (`generate_title`): a `temperature=0` LLM call per issue,
constrained to two title styles —
`"[<service>] <ErrorSignature> identified"` only for exact code-level error
names (CamelCase exception / dotted class path), otherwise
`"<ErrorSignature> Error identified"`. Falls back to a regex extractor
(`_fallback_title`) if the LLM call fails, so ticket creation never blocks on
title generation.

---

## 6. ITSM flow

- **`create_ticket`**: for every issue's `Decision`, calls
  `JiraTicketManager.find_open_ticket_by_summary(title)` first. If an open
  ticket with that exact title exists, it's reused (`update_ticket`) instead
  of creating a duplicate. Otherwise a new ticket is created. Either way, an
  on-call engineer is assigned immediately (`assign_ticket.assign_engineer`)
  — **every** incident gets an owner, remediative or investigative.
- **Engineer selection**: `infer_specialty` matches issue category / title /
  summary / matched signals against each engineer's `expertise` from
  `ENGINEER_MAPPING`; falls back to Jira-history-aware round robin
  (`next_round_robin_engineer`) if no specialty match.
- **`execute_cookbook` / `verify_outcome` / `close_ticket`**: run only for
  tickets whose decision was remediative. Verification passes unless the
  matched remediation is flagged `requires_approval`. On successful close,
  the resolved incident is ingested into the RAG store
  (`runbook_store.add_runbook`) — the next occurrence of the same error
  becomes a hit instead of a miss.
- **`notify_slack`**: posts one consolidated team-channel message listing
  every ticket (path, status, verification), then DMs every assigned
  engineer individually.

`JiraTicketManager` / `SlackNotifier` (`app/integrations/`) hit real Jira
REST / Slack Web API when `JIRA_BASE_URL`+`JIRA_USER_EMAIL`+`JIRA_API_TOKEN`
/ `SLACK_BOT_TOKEN` are set, and fall back to a printed mock otherwise —
same call signatures either way, so nodes never branch on which mode is
active.

---

## 7. RAG layer

- **Source**: `knowledge/runbook_seed.py` (curated corpus) plus anything
  ingested via `add_runbook` after a successful close.
- **Retrieval**: `retrieve()` uses `similarity_search_with_score` and drops
  any result with distance above `RAG_MAX_DISTANCE` (default `1.1`,
  calibrated against on-topic ~0.6 vs off-topic ~1.5 L2 distances). Without
  this, Chroma's plain `similarity_search` always returns `k` results
  regardless of relevance, making every issue a "hit" and the investigative
  path unreachable — this was a real bug found and fixed during the merge.
- **Feedback loop**: closing a remediative ticket successfully feeds its
  issue summary + fix back into the store, so recurring incidents are
  grounded rather than routed to a human every time.

---

## 8. Running everything

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in OPENROUTER_API_KEY; JIRA_*/SLACK_* optional (mock fallback)
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev   # http://localhost:5173, behind Clerk sign-in

# No-UI sanity check
cd backend && source .venv/bin/activate
python run_cli.py ../samples/deployment_regression.log
```

Required env vars beyond the original guide's OpenRouter/Chroma set:

```bash
# Jira (optional — mock fallback if unset)
JIRA_BASE_URL=... JIRA_USER_EMAIL=... JIRA_API_TOKEN=...
JIRA_PROJECT_KEY=INC JIRA_ISSUE_TYPE=Task JIRA_DONE_TRANSITION_ID=...

# Slack (optional — mock fallback if unset)
SLACK_BOT_TOKEN=... SLACK_CHANNEL_ID=...

# On-call roster (JSON, can span multiple lines)
ENGINEER_MAPPING={"Name": {"email": "...", "slack_user_id": "...", "jira_account_id": "...", "expertise": "database"}, ...}

# RAG relevance threshold
RAG_MAX_DISTANCE=1.1
```

---

## 9. Demo script

1. Upload `samples/deployment_regression.log`. Two distinct issues get
   detected and merged into two tickets: `[user-service]
   NullPointerException identified` and `upstream timeout Error identified`.
2. Watch the trace: `decide_response` shows both as remediative (RAG hits
   found) → each auto-executes its cookbook step → verification passes or
   flags for approval → engineer assigned + Slack DM sent either way.
3. Re-upload the same log: `create_ticket` reuses the existing open tickets
   instead of creating duplicates.
4. Upload a log with a genuinely novel error (no seeded runbook covers it):
   decision goes investigative, ticket still created and assigned, no
   auto-execution — a human takes it from here.
5. Once that ticket is resolved and closed through the remediative path,
   the incident is folded into the RAG store — the same error next time is
   a hit, not a miss.
