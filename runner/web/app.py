"""app.py — FastAPI web application for agentik runner dashboard."""

import asyncio
import json
import re
import subprocess
import threading
from pathlib import Path

try:
    import uvicorn
    from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
except ImportError:
    raise ImportError(
        "Web UI requires fastapi and uvicorn. Install with:\n"
        "  pip install fastapi uvicorn[standard]"
    )

from runner.config import (
    MAX_ATTEMPTS,
    MAX_PARALLEL_AGENTS,
    MONTHLY_LIMIT_TOKENS,
    PROJECTS_ROOT,
    ROADMAP_FILENAME,
    _console,
)

app = FastAPI(title="agentik", docs_url="/api/docs")

# WebSocket connections for live updates.
_ws_clients: list[WebSocket] = []
_pipeline_lock = threading.Lock()
_pipeline_running = False
_pipeline_thread: threading.Thread | None = None


# ── Broadcast helper ───────────────────────────────────────────────────────────


async def _broadcast(event: str, data: dict) -> None:
    """Send a JSON event to all connected WebSocket clients."""
    msg = json.dumps({"event": event, **data})
    disconnected = []
    for ws in _ws_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _ws_clients.remove(ws)


def broadcast_sync(event: str, data: dict) -> None:
    """Thread-safe sync wrapper for broadcasting WebSocket events."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_broadcast(event, data))
        else:
            loop.run_until_complete(_broadcast(event, data))
    except RuntimeError:
        pass


# ── API Routes ─────────────────────────────────────────────────────────────────


@app.get("/api/projects")
def list_projects() -> list[dict]:
    """List all projects with status info."""
    from runner.roadmap import get_tasks  # noqa: PLC0415
    from runner.state import (  # noqa: PLC0415
        _completed_tasks,
        _raw_state,
        load_project_budget,
    )
    from runner.workspace import _project_status
    from runner.workspace import list_projects as _list  # noqa: PLC0415

    projects = _list()
    result = []
    for proj in projects:
        badge, detail = _project_status(proj)
        all_tasks = get_tasks(proj)
        state = _raw_state(proj)
        done_set = _completed_tasks(state)
        budget = load_project_budget(proj)
        result.append(
            {
                "name": proj.name,
                "path": str(proj),
                "status": badge,
                "detail": detail,
                "tasks_total": len(all_tasks),
                "tasks_done": len(done_set),
                "total_tokens": budget.get("total_tokens", 0),
                "total_calls": budget.get("total_calls", 0),
            }
        )
    return result


@app.get("/api/projects/{name}")
def get_project(name: str) -> dict:
    """Get detailed project info including ROADMAP and state."""
    project_dir = PROJECTS_ROOT / name
    if not project_dir.exists():
        raise HTTPException(404, f"Project '{name}' not found")

    from runner.roadmap import (  # noqa: PLC0415
        _load_roadmap,
        get_task_agent,
        get_task_layers,
        get_tasks,
        parse_task_graph,
    )
    from runner.state import (  # noqa: PLC0415
        _completed_tasks,
        _raw_state,
        load_project_budget,
    )

    roadmap = _load_roadmap(project_dir)
    all_tasks = get_tasks(project_dir)
    graph = parse_task_graph(project_dir)
    state = _raw_state(project_dir)
    done_set = _completed_tasks(state)
    budget = load_project_budget(project_dir)
    layers = get_task_layers(all_tasks, graph, project_dir)

    # Per-task token usage.
    task_tokens: dict[str, int] = {}
    for session in budget.get("sessions", []):
        t = session.get("task", "")
        task_tokens[t] = task_tokens.get(t, 0) + session.get("tokens", 0)

    tasks_info = []
    for task in all_tasks:
        m = re.match(r"^## (\d{3}) - (.+)$", task)
        task_id = int(m.group(1)) if m else 0
        deps = graph.get(task, [])
        all_deps_done = all(d in done_set for d in deps)
        status = (
            "done" if task in done_set else ("ready" if all_deps_done else "blocked")
        )
        agent = get_task_agent(task, project_dir)
        tokens = task_tokens.get(task, 0)

        tasks_info.append(
            {
                "id": task_id,
                "heading": task,
                "title": m.group(2) if m else task,
                "status": status,
                "agent": agent,
                "tokens": tokens,
                "deps": [
                    (dm.group(1) if (dm := re.match(r"^## (\d{3})", d)) else d)
                    for d in deps
                ],
            }
        )

    # Layer info.
    layer_info = []
    for i, layer in enumerate(layers):
        layer_info.append(
            {
                "index": i,
                "tasks": [
                    (tm.group(1) if (tm := re.match(r"^## (\d{3})", t)) else t)
                    for t in layer
                ],
            }
        )

    return {
        "name": roadmap.get("name", name),
        "ecosystem": roadmap.get("ecosystem", "unknown"),
        "preamble": roadmap.get("preamble", ""),
        "tasks": tasks_info,
        "layers": layer_info,
        "budget": {
            "total_tokens": budget.get("total_tokens", 0),
            "total_calls": budget.get("total_calls", 0),
            "sessions": budget.get("sessions", [])[-50:],  # Last 50 sessions.
        },
        "state": {
            "current_task": state.get("current_task"),
            "attempt": state.get("attempt", 0),
            "completed": len(done_set),
            "total": len(all_tasks),
            "failed": state.get("failed", []),
        },
        "review_enabled": roadmap.get("review", False),
        "min_coverage": roadmap.get("min_coverage"),
        "notify": roadmap.get("notify"),
    }


@app.get("/api/projects/{name}/roadmap")
def get_roadmap(name: str) -> dict:
    """Get raw ROADMAP.json content."""
    project_dir = PROJECTS_ROOT / name
    roadmap_path = project_dir / ROADMAP_FILENAME
    if not roadmap_path.exists():
        raise HTTPException(404, "ROADMAP.json not found")
    return json.loads(roadmap_path.read_text(encoding="utf-8"))


@app.put("/api/projects/{name}/roadmap")
async def update_roadmap(name: str, request: Request) -> dict:
    """Update ROADMAP.json and validate it."""
    project_dir = PROJECTS_ROOT / name
    roadmap_path = project_dir / ROADMAP_FILENAME

    body = await request.json()
    roadmap_path.write_text(json.dumps(body, indent=2), encoding="utf-8")

    # Validate.
    from helpers.check_roadmap import run_checks  # noqa: PLC0415

    rc = run_checks(roadmap_path)
    return {"saved": True, "valid": rc == 0}


@app.get("/api/projects/{name}/logs")
def get_logs(name: str) -> list[dict]:
    """List all log directories and files for a project."""
    project_dir = PROJECTS_ROOT / name
    log_dir = project_dir / "logs"
    if not log_dir.exists():
        return []

    result = []
    for task_dir in sorted(log_dir.iterdir()):
        if task_dir.is_dir():
            logs = []
            for log_file in sorted(task_dir.glob("*.log")):
                logs.append(
                    {
                        "name": log_file.name,
                        "path": log_file.relative_to(project_dir).as_posix(),
                        "size": log_file.stat().st_size,
                    }
                )
            # Include failure report if present.
            report = task_dir / "failure_report.json"
            failure = None
            if report.exists():
                try:
                    failure = json.loads(report.read_text(encoding="utf-8"))
                except Exception:
                    pass
            result.append(
                {
                    "task_slug": task_dir.name,
                    "logs": logs,
                    "failure_report": failure,
                }
            )
    return result


@app.get("/api/projects/{name}/logs/{task_slug}/{log_name}")
def get_log_content(name: str, task_slug: str, log_name: str) -> dict:
    """Get the content of a specific log file."""
    project_dir = PROJECTS_ROOT / name
    log_path = project_dir / "logs" / task_slug / log_name
    if not log_path.exists():
        raise HTTPException(404, "Log file not found")
    content = log_path.read_text(encoding="utf-8", errors="replace")
    return {"content": content, "name": log_name, "task_slug": task_slug}


@app.post("/api/projects/{name}/validate")
def validate_roadmap(name: str) -> dict:
    """Validate the project's ROADMAP.json."""
    project_dir = PROJECTS_ROOT / name
    roadmap_path = project_dir / ROADMAP_FILENAME
    if not roadmap_path.exists():
        raise HTTPException(404, "ROADMAP.json not found")
    from helpers.check_roadmap import run_checks  # noqa: PLC0415

    rc = run_checks(roadmap_path)
    return {"valid": rc == 0}


@app.post("/api/projects/{name}/run")
async def run_pipeline(name: str, request: Request) -> dict:
    """Start the pipeline for a project (non-blocking)."""
    global _pipeline_running, _pipeline_thread

    if _pipeline_running:
        raise HTTPException(409, "Pipeline already running")

    project_dir = PROJECTS_ROOT / name
    if not project_dir.exists():
        raise HTTPException(404, f"Project '{name}' not found")

    def _run() -> None:
        global _pipeline_running
        try:
            _pipeline_running = True
            # We can't fully automate the interactive prompts in a thread,
            # but we can signal the state.
            broadcast_sync("pipeline_started", {"project": name})
        finally:
            _pipeline_running = False
            broadcast_sync("pipeline_stopped", {"project": name})

    _pipeline_thread = threading.Thread(target=_run, daemon=True)
    _pipeline_thread.start()
    return {"started": True}


@app.post("/api/projects/{name}/stop")
def stop_pipeline(name: str) -> dict:
    """Request pipeline stop (sets flag for graceful shutdown)."""
    global _pipeline_running
    _pipeline_running = False
    return {"stopped": True}


@app.post("/api/projects/{name}/generate-roadmap")
async def generate_roadmap_api(name: str, request: Request) -> dict:
    """Generate a ROADMAP.json from a natural language description."""
    body = await request.json()
    description = body.get("description", "")
    ecosystem = body.get("ecosystem", "python")

    if not description:
        raise HTTPException(400, "Description is required")

    from runner.plan import _call_architect  # noqa: PLC0415

    full_desc = f"Project: {name}\nEcosystem: {ecosystem}\n\n{description}"
    result = _call_architect(full_desc, name)

    if result is None:
        raise HTTPException(500, "Failed to generate ROADMAP")

    try:
        roadmap = json.loads(result)
        return {"roadmap": roadmap}
    except json.JSONDecodeError:
        raise HTTPException(500, "Generated invalid JSON")


@app.post("/api/projects/{name}/review/{action}")
def handle_review(name: str, action: str) -> dict:
    """Handle human-in-the-loop review decision (approve/reject)."""
    if action not in ("approve", "reject"):
        raise HTTPException(400, "Action must be 'approve' or 'reject'")
    # This would integrate with a review queue in a full implementation.
    return {"action": action, "acknowledged": True}


@app.get("/api/projects/{name}/diff")
def get_diff(name: str) -> dict:
    """Get the current git diff for the project."""
    project_dir = PROJECTS_ROOT / name
    result = subprocess.run(
        f'git -C "{project_dir}" diff',
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    status = subprocess.run(
        f'git -C "{project_dir}" status --short',
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "diff": result.stdout,
        "status": status.stdout,
    }


@app.get("/api/projects/{name}/dryrun")
def api_dry_run(name: str) -> dict:
    """Run a dry-run cost estimation for the project."""
    project_dir = PROJECTS_ROOT / name
    if not project_dir.exists():
        raise HTTPException(404, f"Project '{name}' not found")
    from runner.dryrun import dry_run  # noqa: PLC0415

    return dry_run(project_dir)


@app.get("/api/budget")
def get_global_budget() -> dict:
    """Get global budget status."""
    from runner.state import (  # noqa: PLC0415
        _load_budget_state,
        _month_key,
        get_token_stats,
    )

    stats = get_token_stats()
    state = _load_budget_state()
    month = _month_key()
    baseline = (
        state.get("baseline_stats", {k: 0 for k in stats})
        if state.get("month") == month
        else {k: 0 for k in stats}
    )
    spent = {k: max(0, stats[k] - baseline.get(k, 0)) for k in stats}
    return {
        "monthly_limit": MONTHLY_LIMIT_TOKENS,
        "spent_tokens": spent["total"],
        "remaining_tokens": max(0, MONTHLY_LIMIT_TOKENS - spent["total"]),
        "max_attempts": MAX_ATTEMPTS,
        "max_parallel": MAX_PARALLEL_AGENTS,
    }


# ── WebSocket ──────────────────────────────────────────────────────────────────


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for live pipeline updates."""
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            # Keep connection alive; client can send ping.
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))
    except WebSocketDisconnect:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


# ── Static frontend ───────────────────────────────────────────────────────────

_STATIC_DIR = Path(__file__).resolve().parent / "static"

_ASSETS_DIR = _STATIC_DIR / "assets"


def _read_index() -> str:
    """Return the React index.html content."""
    index = _STATIC_DIR / "index.html"
    if index.is_file():
        return index.read_text(encoding="utf-8")
    return (
        "<h1>agentik — frontend not built</h1>"
        "<p>Run <code>cd runner/web/frontend && npm run build</code> "
        "to generate the static assets.</p>"
    )


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    """Serve the React SPA index.html."""
    return HTMLResponse(_read_index())


# Mount static assets with correct MIME types.  Mounts are checked by
# Starlette *after* explicit routes, so no catch-all route should exist
# that would shadow these paths.
if _ASSETS_DIR.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_ASSETS_DIR)),
        name="frontend-assets",
    )


# SPA fallback: return index.html for any unmatched GET request (client-side
# routing).  Using an exception handler instead of a catch-all route avoids
# shadowing the /assets StaticFiles mount.
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402


@app.exception_handler(StarletteHTTPException)
async def _spa_or_error(request: Request, exc: StarletteHTTPException):  # type: ignore[override]
    """Return index.html for 404 GETs (SPA routing), otherwise raise."""
    if exc.status_code == 404 and request.method == "GET":
        return HTMLResponse(_read_index())
    return HTMLResponse(content=str(exc.detail), status_code=exc.status_code)


def start_server(host: str = "127.0.0.1", port: int = 8420) -> None:
    """Start the web UI server."""
    _console.print("\n[bold]🌐 agentik Web UI[/]")
    _console.print(f"   [cyan]http://{host}:{port}[/]\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")
