#!/usr/bin/env bash
# ── agentik dev entrypoint ─────────────────────────────────────────────────────
#
# Starts both the Vite dev server (HMR) and the FastAPI backend (auto-reload)
# inside the Docker container.  Used by docker-compose.dev.yml.
#
# Frontend: http://localhost:5173  (Vite HMR, proxies /api + /ws → :8420)
# Backend:  http://localhost:8420  (uvicorn --reload)
#
set -euo pipefail

# Install frontend deps if vite is missing.
# Check for the binary rather than the directory: the anonymous volume at
# node_modules/ is created empty on first run, so the directory always exists.
if [ ! -f /app/web/frontend/node_modules/.bin/vite ]; then
    echo "▸ Installing frontend dependencies..."
    cd /app/web/frontend
    pnpm install
    cd /app
fi

echo "▸ Starting Vite dev server (HMR) on :5173..."
cd /app/web/frontend
pnpm dev --host 0.0.0.0 --port 5173 &
VITE_PID=$!
cd /app

echo "▸ Starting uvicorn (auto-reload) on :8420..."
python -m uvicorn web.app:app \
    --host 0.0.0.0 \
    --port 8420 \
    --reload \
    --reload-dir /app/web \
    --reload-dir /app/runner \
    --reload-dir /app/helpers \
    --log-level warning &
UVICORN_PID=$!

# Trap signals so both processes are cleaned up on Ctrl-C.
cleanup() {
    echo ""
    echo "▸ Shutting down..."
    kill "$VITE_PID" "$UVICORN_PID" 2>/dev/null || true
    wait "$VITE_PID" "$UVICORN_PID" 2>/dev/null || true
    echo "✔ Dev servers stopped."
}
trap cleanup EXIT INT TERM

echo ""
echo "═══════════════════════════════════════════════════"
echo "  agentik dev mode"
echo "  Frontend (HMR):  http://localhost:5173"
echo "  Backend (API):   http://localhost:8420"
echo "═══════════════════════════════════════════════════"
echo ""

# Wait for either process to exit.
wait -n "$VITE_PID" "$UVICORN_PID" 2>/dev/null || true
