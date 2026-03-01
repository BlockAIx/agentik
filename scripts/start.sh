#!/usr/bin/env bash
# ── agentik quick-start script ─────────────────────────────────────────────────
#
# Builds the Docker image (if needed) and starts the web UI.
#
# Usage:
#   ./scripts/start.sh                 # web UI (default)
#   ./scripts/start.sh --pipeline      # interactive pipeline mode
#   ./scripts/start.sh --build-only    # just build the image
#
# Environment:
#   Copy .env.example to .env and fill in your API keys before running.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_NAME="agentik"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"

cd "$PROJECT_ROOT"

# ── Helpers ────────────────────────────────────────────────────────────────────

info()  { printf "\033[1;34m▸\033[0m %s\n" "$*"; }
ok()    { printf "\033[1;32m✔\033[0m %s\n" "$*"; }

# Print error, pause for the user to read, then exit.
die() {
    printf "\n\033[1;31m✗ %s\033[0m\n" "$*" >&2
    printf "\033[1;31mPress Enter to close...\033[0m\n" >&2
    read -r _
    exit 1
}

# Keep the terminal open on any uncaught error.
_on_error() {
    local exit_code=$?
    printf "\n\033[1;31m✗ Script failed (exit code %s). Press Enter to close...\033[0m\n" "$exit_code" >&2
    read -r _
}
trap '_on_error' ERR

ensure_env() {
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            info "Created .env from .env.example — edit it with your API keys."
        else
            info "No .env file found. Create one with your API keys (see .env.example)."
        fi
    fi
}

check_docker() {
    if ! command -v docker &>/dev/null; then
        die "Docker is not installed. Get it at https://docs.docker.com/get-docker/"
    fi
    if ! docker info &>/dev/null 2>&1; then
        die "Docker daemon is not running. Start Docker Desktop or the docker service."
    fi
}

# ── Main ───────────────────────────────────────────────────────────────────────

check_docker
ensure_env

# Create projects directory if it doesn't exist.
mkdir -p projects

MODE="${1:-}"

case "$MODE" in
    --build-only)
        info "Building Docker image..."
        docker compose -f "$COMPOSE_FILE" build
        ok "Image built successfully."
        ;;
    --pipeline)
        info "Starting agentik pipeline (interactive)..."
        docker compose -f "$COMPOSE_FILE" run --rm agentik --pipeline
        ;;
    --detach|-d)
        info "Starting agentik web UI (detached)..."
        docker compose -f "$COMPOSE_FILE" up -d --build
        ok "Web UI running at http://localhost:${AGENTIK_PORT:-8420}"
        ;;
    --down|--stop)
        info "Stopping agentik..."
        docker compose -f "$COMPOSE_FILE" down
        ok "Stopped."
        ;;
    ""|--web)
        info "Starting agentik web UI..."
        docker compose -f "$COMPOSE_FILE" up --build
        ;;
    *)
        info "Passing arguments to agentik: $*"
        docker compose -f "$COMPOSE_FILE" run --rm agentik "$@"
        ;;
esac
