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
    from fastapi.responses import FileResponse, HTMLResponse
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


@app.on_event("startup")
def _mount_static() -> None:
    """Mount the React build output if it exists."""
    if _STATIC_DIR.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_STATIC_DIR / "assets")),
            name="frontend-assets",
        )


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    """Serve the React SPA index.html, falling back to inline HTML."""
    index = _STATIC_DIR / "index.html"
    if index.is_file():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse(_FALLBACK_HTML)


@app.get("/{path:path}", response_model=None)
def spa_fallback(path: str) -> HTMLResponse | FileResponse:
    """SPA catch-all: serve static files or fall back to index.html."""
    # Try exact static file first.
    candidate = _STATIC_DIR / path
    if candidate.is_file() and _STATIC_DIR in candidate.resolve().parents:
        return FileResponse(str(candidate))
    # Fall back to SPA index.
    index = _STATIC_DIR / "index.html"
    if index.is_file():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse(_FALLBACK_HTML)


def start_server(host: str = "127.0.0.1", port: int = 8420) -> None:
    """Start the web UI server."""
    _console.print("\n[bold]🌐 agentik Web UI[/]")
    _console.print(f"   [cyan]http://{host}:{port}[/]\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")


# ── Fallback inline HTML (shown when React build is not present) ───────────────

_FALLBACK_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>agentik — Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
:root {
    --bg: #0f172a;
    --surface: #1e293b;
    --surface2: #334155;
    --border: #475569;
    --text: #e2e8f0;
    --text-dim: #94a3b8;
    --accent: #38bdf8;
    --green: #22c55e;
    --yellow: #eab308;
    --red: #ef4444;
    --blue: #3b82f6;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Layout */
.app { display: flex; height: 100vh; }
.sidebar { width: 260px; background: var(--surface); border-right: 1px solid var(--border); overflow-y: auto; flex-shrink: 0; }
.main { flex: 1; overflow-y: auto; padding: 2rem; }

/* Sidebar */
.sidebar-header { padding: 1.2rem; border-bottom: 1px solid var(--border); }
.sidebar-header h1 { font-size: 1.2rem; display: flex; align-items: center; gap: 0.5rem; }
.sidebar-header h1 span { font-size: 1.4rem; }
.project-list { list-style: none; padding: 0.5rem 0; }
.project-item { padding: 0.7rem 1.2rem; cursor: pointer; border-left: 3px solid transparent; transition: all 0.15s; }
.project-item:hover { background: var(--surface2); }
.project-item.active { border-left-color: var(--accent); background: var(--surface2); }
.project-name { font-weight: 600; font-size: 0.95rem; }
.project-meta { font-size: 0.8rem; color: var(--text-dim); margin-top: 0.2rem; }

/* Cards */
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 0.75rem; padding: 1.2rem; }
.card-label { font-size: 0.8rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; }
.card-value { font-size: 1.6rem; font-weight: 700; margin-top: 0.3rem; }
.card-value.green { color: var(--green); }
.card-value.blue { color: var(--accent); }
.card-value.yellow { color: var(--yellow); }

/* Section */
.section { margin-bottom: 2rem; }
.section-title { font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }

/* Graph */
#graph-container { background: var(--surface); border-radius: 0.75rem; padding: 1.5rem; overflow: auto; min-height: 300px; }

/* Task table */
.task-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.task-table th { text-align: left; padding: 0.6rem; color: var(--text-dim); border-bottom: 1px solid var(--border); font-weight: 500; }
.task-table td { padding: 0.6rem; border-bottom: 1px solid var(--surface2); }
.badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 0.3rem; font-size: 0.75rem; font-weight: 600; }
.badge.done { background: var(--green); color: #000; }
.badge.ready { background: var(--yellow); color: #000; }
.badge.blocked { background: var(--surface2); color: var(--text-dim); }
.badge.failed { background: var(--red); color: #fff; }
.badge.running { background: var(--blue); color: #fff; }

/* Tabs */
.tabs { display: flex; gap: 0; border-bottom: 1px solid var(--border); margin-bottom: 1.5rem; }
.tab { padding: 0.7rem 1.2rem; cursor: pointer; border-bottom: 2px solid transparent; color: var(--text-dim); font-size: 0.9rem; transition: all 0.15s; }
.tab:hover { color: var(--text); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-content { display: none; }
.tab-content.active { display: block; }

/* Log viewer */
.log-viewer { background: #000; color: #22c55e; font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 0.85rem; padding: 1rem; border-radius: 0.5rem; overflow: auto; max-height: 500px; white-space: pre-wrap; word-break: break-all; }

/* Buttons */
.btn { padding: 0.5rem 1rem; border-radius: 0.4rem; border: none; cursor: pointer; font-size: 0.85rem; font-weight: 600; transition: all 0.15s; }
.btn-primary { background: var(--accent); color: #000; }
.btn-primary:hover { background: #0ea5e9; }
.btn-danger { background: var(--red); color: #fff; }
.btn-danger:hover { background: #dc2626; }
.btn-success { background: var(--green); color: #000; }
.btn-success:hover { background: #16a34a; }
.btn-group { display: flex; gap: 0.5rem; margin-bottom: 1rem; }

/* ROADMAP editor */
.editor-area { width: 100%; min-height: 400px; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 0.5rem; padding: 1rem; font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 0.85rem; resize: vertical; }

/* Generator */
.generator-input { width: 100%; min-height: 120px; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 0.5rem; padding: 1rem; font-size: 0.9rem; resize: vertical; margin-bottom: 1rem; }
select.eco-select { background: var(--surface); color: var(--text); border: 1px solid var(--border); padding: 0.5rem; border-radius: 0.4rem; margin-bottom: 1rem; }

/* Diff viewer */
.diff-line-add { color: var(--green); }
.diff-line-del { color: var(--red); }
.diff-line-info { color: var(--accent); }

/* Toast */
.toast { position: fixed; bottom: 1rem; right: 1rem; background: var(--surface2); color: var(--text); padding: 0.8rem 1.2rem; border-radius: 0.5rem; border: 1px solid var(--border); z-index: 1000; animation: slideIn 0.3s; }
@keyframes slideIn { from { transform: translateY(100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

/* Responsive */
@media (max-width: 768px) {
    .app { flex-direction: column; }
    .sidebar { width: 100%; height: auto; max-height: 200px; }
    .cards { grid-template-columns: repeat(2, 1fr); }
}
</style>
</head>
<body>
<div class="app">
    <nav class="sidebar">
        <div class="sidebar-header">
            <h1><span>⚡</span> agentik</h1>
        </div>
        <ul class="project-list" id="project-list"></ul>
    </nav>

    <main class="main" id="main-content">
        <div id="welcome" style="text-align:center; padding-top:4rem; color:var(--text-dim);">
            <h2>Select a project</h2>
            <p style="margin-top:0.5rem;">Choose a project from the sidebar to view its dashboard.</p>
        </div>

        <div id="project-view" style="display:none;">
            <h2 id="project-title" style="margin-bottom:1rem;"></h2>

            <div class="tabs">
                <div class="tab active" data-tab="overview">Overview</div>
                <div class="tab" data-tab="graph">Graph</div>
                <div class="tab" data-tab="tasks">Tasks</div>
                <div class="tab" data-tab="logs">Logs</div>
                <div class="tab" data-tab="editor">ROADMAP Editor</div>
                <div class="tab" data-tab="generator">Generator</div>
                <div class="tab" data-tab="review">Review</div>
                <div class="tab" data-tab="controls">Controls</div>
            </div>

            <!-- Overview Tab -->
            <div class="tab-content active" id="tab-overview">
                <div class="cards" id="stat-cards"></div>
                <div class="section">
                    <div class="section-title">Cost Over Time</div>
                    <canvas id="cost-chart" height="200"></canvas>
                </div>
            </div>

            <!-- Graph Tab -->
            <div class="tab-content" id="tab-graph">
                <div id="graph-container">
                    <pre class="mermaid" id="mermaid-graph"></pre>
                </div>
            </div>

            <!-- Tasks Tab -->
            <div class="tab-content" id="tab-tasks">
                <table class="task-table">
                    <thead><tr><th>ID</th><th>Title</th><th>Status</th><th>Agent</th><th>Tokens</th><th>Deps</th></tr></thead>
                    <tbody id="task-tbody"></tbody>
                </table>
            </div>

            <!-- Logs Tab -->
            <div class="tab-content" id="tab-logs">
                <div id="log-list"></div>
                <div class="log-viewer" id="log-content" style="display:none;"></div>
            </div>

            <!-- Editor Tab -->
            <div class="tab-content" id="tab-editor">
                <div class="btn-group">
                    <button class="btn btn-primary" onclick="saveRoadmap()">Save & Validate</button>
                    <button class="btn" onclick="loadRoadmapEditor()" style="background:var(--surface2);color:var(--text);">Reload</button>
                </div>
                <textarea class="editor-area" id="roadmap-editor"></textarea>
                <div id="editor-status" style="margin-top:0.5rem;font-size:0.85rem;"></div>
            </div>

            <!-- Generator Tab -->
            <div class="tab-content" id="tab-generator">
                <div class="section-title">Generate ROADMAP from Description</div>
                <p style="color:var(--text-dim); margin-bottom:1rem; font-size:0.9rem;">
                    Describe your project in plain language. The AI architect will generate a complete ROADMAP.json.
                </p>
                <select class="eco-select" id="gen-ecosystem">
                    <option value="python">Python</option>
                    <option value="deno">Deno</option>
                    <option value="node">Node/TypeScript</option>
                    <option value="go">Go</option>
                    <option value="rust">Rust</option>
                </select>
                <textarea class="generator-input" id="gen-description" placeholder="Describe your project..."></textarea>
                <div class="btn-group">
                    <button class="btn btn-primary" onclick="generateRoadmap()">Generate ROADMAP</button>
                </div>
                <div id="gen-result" style="display:none;">
                    <div class="section-title">Generated ROADMAP</div>
                    <textarea class="editor-area" id="gen-output" readonly></textarea>
                    <div class="btn-group" style="margin-top:1rem;">
                        <button class="btn btn-success" onclick="acceptGenerated()">Accept & Save</button>
                        <button class="btn btn-danger" onclick="document.getElementById('gen-result').style.display='none'">Discard</button>
                    </div>
                </div>
            </div>

            <!-- Review Tab -->
            <div class="tab-content" id="tab-review">
                <div class="section-title">Human-in-the-Loop Review</div>
                <div id="review-status" style="color:var(--text-dim); margin-bottom:1rem;"></div>
                <div class="log-viewer" id="diff-viewer" style="display:none;"></div>
                <div class="btn-group" id="review-buttons" style="display:none; margin-top:1rem;">
                    <button class="btn btn-success" onclick="reviewAction('approve')">✔ Approve</button>
                    <button class="btn btn-danger" onclick="reviewAction('reject')">✗ Reject</button>
                </div>
            </div>

            <!-- Controls Tab -->
            <div class="tab-content" id="tab-controls">
                <div class="section-title">Pipeline Controls</div>
                <div class="btn-group">
                    <button class="btn btn-primary" onclick="startPipeline(false)">▶ Run Pipeline (compact)</button>
                    <button class="btn btn-primary" onclick="startPipeline(true)">▶ Run Pipeline (verbose)</button>
                    <button class="btn btn-danger" onclick="stopPipeline()">⏹ Stop</button>
                </div>
                <div class="section-title" style="margin-top:2rem;">Dry Run — Cost Estimate</div>
                <button class="btn" onclick="runDryRun()" style="background:var(--surface2);color:var(--text);">📊 Estimate Cost</button>
                <div id="dryrun-result" style="margin-top:1rem;"></div>
            </div>
        </div>
    </main>
</div>

<script>
let currentProject = null;
let projectData = null;
let ws = null;

// ── Init ──
async function init() {
    const res = await fetch('/api/projects');
    const projects = await res.json();
    const list = document.getElementById('project-list');
    list.innerHTML = projects.map(p => `
        <li class="project-item" onclick="selectProject('${p.name}')">
            <div class="project-name">${p.name}</div>
            <div class="project-meta">${p.status} · ${p.tasks_done}/${p.tasks_total} tasks</div>
        </li>
    `).join('');

    connectWebSocket();
}

function connectWebSocket() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.event === 'pipeline_started' || msg.event === 'pipeline_stopped') {
            if (currentProject) loadProjectData(currentProject);
        }
    };
    ws.onclose = () => setTimeout(connectWebSocket, 3000);
    setInterval(() => { if (ws.readyState === 1) ws.send('ping'); }, 30000);
}

// ── Project selection ──
async function selectProject(name) {
    currentProject = name;
    document.querySelectorAll('.project-item').forEach(el => el.classList.remove('active'));
    event.currentTarget?.classList.add('active');
    document.getElementById('welcome').style.display = 'none';
    document.getElementById('project-view').style.display = 'block';
    await loadProjectData(name);
}

async function loadProjectData(name) {
    const res = await fetch(`/api/projects/${name}`);
    projectData = await res.json();
    renderOverview();
    renderGraph();
    renderTasks();
    loadLogs();
    loadRoadmapEditor();
    loadReviewTab();
}

// ── Overview ──
function renderOverview() {
    const d = projectData;
    document.getElementById('project-title', d.name);
    document.getElementById('project-title').textContent = d.name;

    const pct = d.state.total > 0 ? Math.round(d.state.completed / d.state.total * 100) : 0;
    document.getElementById('stat-cards').innerHTML = `
        <div class="card"><div class="card-label">Progress</div><div class="card-value green">${pct}%</div></div>
        <div class="card"><div class="card-label">Tasks</div><div class="card-value blue">${d.state.completed} / ${d.state.total}</div></div>
        <div class="card"><div class="card-label">Tokens Used</div><div class="card-value">${formatTokens(d.budget.total_tokens)}</div></div>
        <div class="card"><div class="card-label">API Calls</div><div class="card-value">${d.budget.total_calls}</div></div>
        <div class="card"><div class="card-label">Ecosystem</div><div class="card-value" style="font-size:1.1rem;">${d.ecosystem}</div></div>
        <div class="card"><div class="card-label">Review</div><div class="card-value" style="font-size:1rem;">${d.review_enabled ? '✔ Enabled' : 'Off'}</div></div>
    `;

    renderCostChart();
}

function renderCostChart() {
    const canvas = document.getElementById('cost-chart');
    const ctx = canvas.getContext('2d');
    const sessions = projectData.budget.sessions;
    if (!sessions.length) { ctx.clearRect(0,0,canvas.width,canvas.height); return; }

    // Group by date.
    const byDate = {};
    sessions.forEach(s => {
        const d = s.date || 'unknown';
        byDate[d] = (byDate[d] || 0) + (s.tokens || 0);
    });
    const dates = Object.keys(byDate).sort();
    const values = dates.map(d => byDate[d]);
    const maxVal = Math.max(...values, 1);

    canvas.width = canvas.parentElement.offsetWidth;
    canvas.height = 200;
    ctx.clearRect(0,0,canvas.width,canvas.height);

    const padding = { left: 60, right: 20, top: 20, bottom: 30 };
    const w = canvas.width - padding.left - padding.right;
    const h = canvas.height - padding.top - padding.bottom;
    const barW = Math.max(2, w / dates.length - 2);

    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px sans-serif';
    for (let i = 0; i <= 4; i++) {
        const y = padding.top + h - (i/4 * h);
        const val = Math.round(maxVal * i / 4);
        ctx.fillText(formatTokens(val), 2, y + 4);
        ctx.strokeStyle = '#334155';
        ctx.beginPath(); ctx.moveTo(padding.left, y); ctx.lineTo(padding.left + w, y); ctx.stroke();
    }

    dates.forEach((d, i) => {
        const x = padding.left + (i / dates.length) * w;
        const barH = (values[i] / maxVal) * h;
        ctx.fillStyle = '#38bdf8';
        ctx.fillRect(x, padding.top + h - barH, barW, barH);
        if (dates.length <= 15) {
            ctx.fillStyle = '#94a3b8';
            ctx.fillText(d.slice(5), x, canvas.height - 5);
        }
    });
}

// ── Graph ──
function renderGraph() {
    const tasks = projectData.tasks;
    let lines = ['graph TD'];
    tasks.forEach(t => {
        const id = 'T' + String(t.id).padStart(3,'0');
        const label = `${String(t.id).padStart(3,'0')} - ${t.title}`;
        const tokens = t.tokens ? `<br/>${formatTokens(t.tokens)}` : '';
        const agent = t.agent !== 'build' ? `<br/>(${t.agent})` : '';
        lines.push(`    ${id}["${label}${agent}${tokens}"]`);

        const colors = { done: '#22c55e,#16a34a,#fff', ready: '#eab308,#ca8a04,#000', blocked: '#6b7280,#4b5563,#fff', failed: '#ef4444,#dc2626,#fff', running: '#3b82f6,#2563eb,#fff' };
        const c = (colors[t.status] || colors.blocked).split(',');
        lines.push(`    style ${id} fill:${c[0]},stroke:${c[1]},color:${c[2]}`);

        t.deps.forEach(dep => {
            lines.push(`    T${dep.padStart(3,'0')} --> ${id}`);
        });
    });

    const el = document.getElementById('mermaid-graph');
    el.textContent = lines.join('\\n');
    el.removeAttribute('data-processed');
    mermaid.init(undefined, el);
}

// ── Tasks ──
function renderTasks() {
    const tbody = document.getElementById('task-tbody');
    tbody.innerHTML = projectData.tasks.map(t => `
        <tr>
            <td>${String(t.id).padStart(3,'0')}</td>
            <td>${t.title}</td>
            <td><span class="badge ${t.status}">${t.status}</span></td>
            <td>${t.agent}</td>
            <td>${formatTokens(t.tokens)}</td>
            <td>${t.deps.join(', ') || '—'}</td>
        </tr>
    `).join('');
}

// ── Logs ──
async function loadLogs() {
    const res = await fetch(`/api/projects/${currentProject}/logs`);
    const logs = await res.json();
    const container = document.getElementById('log-list');
    if (!logs.length) { container.innerHTML = '<p style="color:var(--text-dim)">No logs yet.</p>'; return; }

    container.innerHTML = logs.map(group => `
        <div style="margin-bottom:1rem;">
            <strong>${group.task_slug}</strong>
            ${group.failure_report ? '<span class="badge failed" style="margin-left:0.5rem;">FAILED</span>' : ''}
            <div style="margin-top:0.3rem;">
                ${group.logs.map(l => `<a href="#" onclick="viewLog('${currentProject}','${group.task_slug}','${l.name}');return false;" style="margin-right:1rem;font-size:0.85rem;">${l.name} (${(l.size/1024).toFixed(1)}KB)</a>`).join('')}
            </div>
            ${group.failure_report ? `<pre style="background:var(--surface);padding:0.5rem;border-radius:0.3rem;font-size:0.8rem;margin-top:0.5rem;">${JSON.stringify(group.failure_report, null, 2)}</pre>` : ''}
        </div>
    `).join('');
}

async function viewLog(project, slug, name) {
    const res = await fetch(`/api/projects/${project}/logs/${slug}/${name}`);
    const data = await res.json();
    const viewer = document.getElementById('log-content');
    viewer.style.display = 'block';
    viewer.textContent = data.content;
}

// ── ROADMAP Editor ──
async function loadRoadmapEditor() {
    try {
        const res = await fetch(`/api/projects/${currentProject}/roadmap`);
        const roadmap = await res.json();
        document.getElementById('roadmap-editor').value = JSON.stringify(roadmap, null, 2);
    } catch(e) {
        document.getElementById('roadmap-editor').value = '// Error loading ROADMAP';
    }
}

async function saveRoadmap() {
    const text = document.getElementById('roadmap-editor').value;
    const status = document.getElementById('editor-status');
    try {
        const parsed = JSON.parse(text);
        const res = await fetch(`/api/projects/${currentProject}/roadmap`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(parsed),
        });
        const result = await res.json();
        status.innerHTML = result.valid
            ? '<span style="color:var(--green)">✔ Saved and validated successfully</span>'
            : '<span style="color:var(--yellow)">⚠ Saved but validation found issues</span>';
        loadProjectData(currentProject);
    } catch(e) {
        status.innerHTML = `<span style="color:var(--red)">✗ Invalid JSON: ${e.message}</span>`;
    }
}

// ── Generator ──
async function generateRoadmap() {
    const desc = document.getElementById('gen-description').value;
    const eco = document.getElementById('gen-ecosystem').value;
    if (!desc.trim()) { toast('Please enter a description'); return; }

    toast('Generating ROADMAP... this may take a minute.');
    try {
        const res = await fetch(`/api/projects/${currentProject}/generate-roadmap`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ description: desc, ecosystem: eco }),
        });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        document.getElementById('gen-output').value = JSON.stringify(data.roadmap, null, 2);
        document.getElementById('gen-result').style.display = 'block';
    } catch(e) {
        toast('Generation failed: ' + e.message);
    }
}

async function acceptGenerated() {
    const text = document.getElementById('gen-output').value;
    document.getElementById('roadmap-editor').value = text;
    await saveRoadmap();
    document.getElementById('gen-result').style.display = 'none';
    // Switch to editor tab.
    switchTab('editor');
    toast('ROADMAP saved!');
}

// ── Review ──
async function loadReviewTab() {
    const status = document.getElementById('review-status');
    if (!projectData.review_enabled) {
        status.textContent = 'Human review is not enabled. Add "review": true to your ROADMAP.json to enable it.';
        document.getElementById('diff-viewer').style.display = 'none';
        document.getElementById('review-buttons').style.display = 'none';
        return;
    }
    status.textContent = 'Review is enabled. Diffs will appear here during pipeline runs.';

    // Load current diff.
    try {
        const res = await fetch(`/api/projects/${currentProject}/diff`);
        const data = await res.json();
        if (data.diff || data.status) {
            const viewer = document.getElementById('diff-viewer');
            viewer.style.display = 'block';
            viewer.innerHTML = colorDiff(data.status + '\\n' + data.diff);
            document.getElementById('review-buttons').style.display = 'flex';
        }
    } catch(e) {}
}

function colorDiff(text) {
    return text.split('\\n').map(line => {
        if (line.startsWith('+') && !line.startsWith('+++')) return `<span class="diff-line-add">${esc(line)}</span>`;
        if (line.startsWith('-') && !line.startsWith('---')) return `<span class="diff-line-del">${esc(line)}</span>`;
        if (line.startsWith('@@')) return `<span class="diff-line-info">${esc(line)}</span>`;
        return esc(line);
    }).join('\\n');
}

async function reviewAction(action) {
    await fetch(`/api/projects/${currentProject}/review/${action}`, { method: 'POST' });
    toast(`Review: ${action}`);
    loadProjectData(currentProject);
}

// ── Controls ──
async function startPipeline(verbose) {
    try {
        await fetch(`/api/projects/${currentProject}/run`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ verbose }),
        });
        toast('Pipeline started');
    } catch(e) {
        toast('Failed to start: ' + e.message);
    }
}

async function stopPipeline() {
    await fetch(`/api/projects/${currentProject}/stop`, { method: 'POST' });
    toast('Pipeline stop requested');
}

async function runDryRun() {
    const res = await fetch(`/api/projects/${currentProject}/dryrun`);
    const data = await res.json();
    document.getElementById('dryrun-result').innerHTML = `
        <div class="card" style="margin-top:1rem;">
            <p><strong>Remaining tasks:</strong> ${data.remaining_tasks} / ${data.total_tasks}</p>
            <p><strong>Est. tokens:</strong> ${formatTokens(data.estimated_tokens)}</p>
            <p><strong>Est. cost:</strong> $${data.estimated_usd.toFixed(4)}</p>
            <p><strong>Est. time:</strong> ${formatDuration(data.estimated_time_sec)}</p>
        </div>
    `;
}

// ── Tabs ──
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('tab')) {
        switchTab(e.target.dataset.tab);
    }
});

function switchTab(name) {
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.toggle('active', c.id === 'tab-' + name));
}

// ── Helpers ──
function formatTokens(n) {
    if (n >= 1e6) return (n/1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n/1e3).toFixed(1) + 'K';
    return String(n);
}

function formatDuration(sec) {
    if (sec < 60) return Math.round(sec) + 's';
    if (sec < 3600) return Math.round(sec/60) + 'm ' + Math.round(sec%60) + 's';
    return Math.floor(sec/3600) + 'h ' + Math.round((sec%3600)/60) + 'm';
}

function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function toast(msg) {
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3000);
}

// ── Boot ──
mermaid.initialize({ startOnLoad: false, theme: 'dark', themeVariables: { primaryColor:'#334155', primaryTextColor:'#e2e8f0', lineColor:'#64748b' }, flowchart: { useMaxWidth:false, htmlLabels:true, curve:'basis' }});
init();
</script>
</body>
</html>
"""
