# incident-suite — Antigravity Agent Rules

## Project Context

This is a **DevOps Incident Analysis Suite** — a React + Vite frontend backed by a
FastAPI + LangGraph Python backend. The system streams real-time agent traces via SSE.

## General Rules

1. **Frontend**: Always use the `ui-design` skill when touching anything in `frontend/`.
2. **Styling**: Use only Vanilla CSS (via `index.css` design tokens). No Tailwind, no
   CSS-in-JS, no inline `style={{}}` unless the value is dynamic/computed.
3. **No new npm packages** without asking: the frontend intentionally has zero runtime
   dependencies beyond React. Prefer CSS + SVG solutions.
4. **Backend**: Python only. Never introduce new package managers. Use pip/requirements.txt.
5. **Secrets**: Never hardcode API keys. All secrets live in `backend/.env`.
6. **Streaming**: The SSE streaming contract in `frontend/src/api.js` is stable — only
   modify it if fixing a confirmed bug.

## UI Quality Bar

Every UI change must score **10/10** on visual quality. The app is a hackathon demo —
it must wow judges. Mediocre styling is not acceptable.

## File Organization

- New frontend components → `frontend/src/components/`
- New backend nodes → `backend/app/nodes/`
- New backend integrations → `backend/app/integrations/`
