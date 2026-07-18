# Contributing to Incident Suite

Thanks for contributing. This repo is a hackathon build of a **multi-agent DevOps incident analysis suite**: LangGraph orchestrates five agents that ingest ops logs, classify issues, ground remediations in a Chroma/RAG runbook store, and produce checklists plus mocked Slack/JIRA output.

Direct pushes to `main` are not allowed — open a pull request instead.

---

## Project layout

```
backend/          FastAPI + LangGraph agents, RAG (Chroma), integrations
frontend/         React (Vite) UI — log upload + live SSE progress
samples/          Example incident logs for local demos
BUILD_GUIDE.md    Full architecture / build spec (read before large changes)
```

**Stack (keep this locked unless a PR explicitly changes it):**
Python · LangGraph · FastAPI · React (Vite) · OpenRouter (`openai/gpt-4o-mini`) · Chroma + local `sentence-transformers` embeddings · mocked Slack/JIRA clients.

---

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- An [OpenRouter](https://openrouter.ai/) API key (`OPENROUTER_API_KEY`)

---

## Local setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # add your OPENROUTER_API_KEY
uvicorn app.main:app --reload --port 8000
```

First startup downloads the embedding model and seeds `backend/chroma_db/` (gitignored). You should see `[startup] runbook store ready`.

### Frontend

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

### Quick sanity check (no UI)

```bash
cd backend
source .venv/bin/activate
python run_cli.py ../samples/deployment_regression.log
```

Other sample logs: `samples/memory_leak.log`, `samples/db_exhaustion.log`.

---

## Development workflow

### 1. Sync and branch

```bash
git checkout main
git pull origin main
git checkout -b feat/<short-description>
```

Branch naming examples:
- `feat/human-approval-before-jira`
- `fix/classifier-cluster-threshold`
- `docs/demo-script-clarity`

### 2. Make focused changes

Prefer small PRs that touch one concern:
- A single agent node (`backend/app/nodes/`)
- Graph routing / state (`backend/app/graph.py`, `state.py`)
- RAG corpus or retrieval (`backend/app/knowledge/`)
- Slack/JIRA client (`backend/app/integrations/`)
- UI streaming / results panels (`frontend/src/`)

Do **not** commit:
- `backend/.env` or any real API keys
- `backend/.venv/`, `frontend/node_modules/`, `frontend/dist/`
- `backend/chroma_db/` (regenerated locally)

Keep `backend/.env.example` updated if you add new config keys.

### 3. Commit messages

Use concise, conventional messages:

```bash
git commit -m "feat(remediation): surface runbook ids used for grounding"
git commit -m "fix(graph): skip jira node when no high/critical issues"
```

Avoid vague messages like `update` or `fix stuff`.

### 4. Keep the branch current

```bash
git fetch origin
git merge origin/main
```

Resolve conflicts locally, then push.

### 5. Push and open a PR

```bash
git push -u origin HEAD
```

Open a PR against `main`. Title format:

```
<type>(<area>): <short summary>
```

Examples:
- `feat(rag): add service metadata filter on retrieval`
- `feat(ui): show severity dashboard from log entries`
- `chore(deps): pin sentence-transformers version`

---

## Review expectations

- At least **one approval** before merge.
- Prefer **squash and merge** so `main` stays readable.
- Reviewers will look for:
  - Pipeline still runs end-to-end on a sample log
  - RAG grounding still visible on remediations
  - Severity-based JIRA branch still correct
  - No secrets or large generated artifacts in the diff
