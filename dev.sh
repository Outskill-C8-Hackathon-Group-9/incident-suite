#!/usr/bin/env bash
# dev.sh — Start backend + frontend concurrently for local development.
# Usage: ./dev.sh

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# ── colours ──────────────────────────────────────────────────────────────────
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # no colour

echo -e "${CYAN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       incident-suite dev server           ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════╝${NC}"
echo ""

# ── backend ──────────────────────────────────────────────────────────────────
ACTIVATE="$ROOT/.venv/bin/activate"
if [ ! -f "$ACTIVATE" ]; then
  ACTIVATE="$BACKEND/.venv/bin/activate"
fi

if [ ! -f "$ACTIVATE" ]; then
  echo -e "${YELLOW}⚠  No .venv found. Run: python -m venv .venv && pip install -r backend/requirements.txt${NC}"
  exit 1
fi

echo -e "${GREEN}▶ Starting backend  (http://localhost:8000)${NC}"
(
  source "$ACTIVATE"
  cd "$BACKEND"
  uvicorn app.main:app --reload --port 8000
) &
BACKEND_PID=$!

# ── frontend ─────────────────────────────────────────────────────────────────
echo -e "${GREEN}▶ Starting frontend (http://localhost:5173)${NC}"
(
  cd "$FRONTEND"
  npm run dev
) &
FRONTEND_PID=$!

echo ""
echo -e "  Backend  PID: ${BACKEND_PID}"
echo -e "  Frontend PID: ${FRONTEND_PID}"
echo -e "  Press ${YELLOW}Ctrl-C${NC} to stop both."
echo ""

# ── graceful shutdown ─────────────────────────────────────────────────────────
_cleanup() {
  echo ""
  echo -e "${YELLOW}Shutting down…${NC}"
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  echo -e "${GREEN}Done.${NC}"
}
trap _cleanup INT TERM

wait "$BACKEND_PID" "$FRONTEND_PID"
