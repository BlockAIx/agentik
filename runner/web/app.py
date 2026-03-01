"""app.py — FastAPI web application for agentik runner dashboard."""

import asyncio
import json
import os
import re
import subprocess
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

try:
    import uvicorn
    from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse, Response
except ImportError:
    raise ImportError(
        "Web UI requires fastapi and uvicorn. Install with:\n"
        "  pip install fastapi uvicorn[standard]"
    )

from runner.config import (
    MAX_ATTEMPTS,
    MAX_PARALLEL_AGENTS,
    MONTHLY_LIMIT_TOKENS,
    OPENCODE_CMD,
    PROJECTS_ROOT,
    ROADMAP_FILENAME,
    _console,
)


@asynccontextmanager
async def _lifespan(_app: FastAPI):  # type: ignore[type-arg]
    """Capture the running event loop so background threads can schedule broadcasts."""
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    yield


app = FastAPI(title="agentik", docs_url="/api/docs", lifespan=_lifespan)

# Strip ANSI escape codes from subprocess output before sending to the browser.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")

# WebSocket connections for live updates.
_ws_clients: list[WebSocket] = []
_pipeline_lock = threading.Lock()
_pipeline_running = False
_pipeline_project: str | None = None
_pipeline_thread: threading.Thread | None = None
_pipeline_process: "subprocess.Popen[str] | None" = None
# The main event loop captured at startup — used by background threads to
# safely schedule coroutines via asyncio.run_coroutine_threadsafe.
_main_loop: asyncio.AbstractEventLoop | None = None


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
    """Thread-safe sync wrapper: schedules broadcast on the main event loop."""
    if _main_loop is not None and _main_loop.is_running():
        asyncio.run_coroutine_threadsafe(_broadcast(event, data), _main_loop)


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


@app.post("/api/projects")
async def create_project(request: Request) -> dict:
    """Create a new project directory with a ROADMAP.json and optional git init."""
    body = await request.json()
    name = body.get("name", "").strip()
    if not name or not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise HTTPException(
            400, "Invalid project name (alphanumeric, hyphens, underscores only)"
        )
    project_dir = PROJECTS_ROOT / name
    if project_dir.exists():
        raise HTTPException(409, f"Project '{name}' already exists")

    ecosystem = body.get("ecosystem", "python")
    preamble = body.get("preamble", "")
    git_enabled = body.get("git", False)

    project_dir.mkdir(parents=True, exist_ok=True)

    roadmap = {
        "name": f"{name} v0.1",
        "ecosystem": ecosystem,
        "preamble": preamble,
        "tasks": [],
    }
    if git_enabled:
        roadmap["git"] = {"enabled": True}

    (project_dir / ROADMAP_FILENAME).write_text(
        json.dumps(roadmap, indent=2), encoding="utf-8"
    )

    # Init git repo if requested.
    if git_enabled:
        subprocess.run(
            ["git", "init"],
            cwd=str(project_dir),
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", "main"],
            cwd=str(project_dir),
            capture_output=True,
        )
        (project_dir / ".gitignore").write_text(
            "logs/\n__pycache__/\n*.pyc\n.runner_state.json\n",
            encoding="utf-8",
        )

    return {"created": True, "name": name, "path": str(project_dir)}


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


@app.get("/api/projects/{name}/budget")
def get_project_budget(name: str) -> dict:
    """Get the per-project budget.json content."""
    from runner.state import load_project_budget  # noqa: PLC0415

    project_dir = PROJECTS_ROOT / name
    if not project_dir.exists():
        raise HTTPException(404, f"Project '{name}' not found")
    return load_project_budget(project_dir)


@app.put("/api/projects/{name}/budget")
async def update_project_budget(name: str, request: Request) -> dict:
    """Update the per-project budget.json."""
    from runner.state import save_project_budget  # noqa: PLC0415

    project_dir = PROJECTS_ROOT / name
    if not project_dir.exists():
        raise HTTPException(404, f"Project '{name}' not found")

    body = await request.json()
    save_project_budget(project_dir, body)
    return {"saved": True}


@app.post("/api/projects/{name}/run")
async def run_pipeline(name: str, request: Request) -> dict:
    """Start the pipeline for a project as a subprocess and stream logs over WebSocket."""
    global _pipeline_running, _pipeline_project, _pipeline_thread

    if _pipeline_running:
        raise HTTPException(409, "Pipeline already running")

    project_dir = PROJECTS_ROOT / name
    if not project_dir.exists():
        raise HTTPException(404, f"Project '{name}' not found")

    body: dict = {}
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        pass
    verbose = bool(body.get("verbose", False))

    def _run() -> None:
        global _pipeline_running, _pipeline_project, _pipeline_process
        rc = -1
        try:
            _pipeline_running = True
            _pipeline_project = name
            broadcast_sync("pipeline_started", {"project": name})
            env = {**os.environ, "PYTHONUNBUFFERED": "1"}
            if verbose:
                env["AGENTIK_VERBOSE"] = "1"
            cmd = [
                sys.executable,
                "-m",
                "runner.web._pipeline_worker",
                str(project_dir),
            ]
            with subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            ) as proc:
                _pipeline_process = proc
                assert proc.stdout is not None
                for line in proc.stdout:
                    clean = _ANSI_RE.sub("", line.rstrip())
                    if clean:
                        broadcast_sync("log_line", {"project": name, "line": clean})
                proc.wait()
                rc = proc.returncode
        except Exception as exc:  # noqa: BLE001
            broadcast_sync("log_line", {"project": name, "line": f"[ERROR] {exc}"})
        finally:
            _pipeline_running = False
            _pipeline_project = None
            _pipeline_process = None
            broadcast_sync("pipeline_stopped", {"project": name, "rc": rc})

    _pipeline_thread = threading.Thread(target=_run, daemon=True)
    _pipeline_thread.start()
    return {"started": True}


@app.post("/api/projects/{name}/stop")
def stop_pipeline(name: str) -> dict:
    """Terminate the running pipeline subprocess if one is active."""
    global _pipeline_running, _pipeline_project, _pipeline_process
    _pipeline_running = False
    _pipeline_project = None
    if _pipeline_process is not None:
        _pipeline_process.terminate()
    return {"stopped": True}


@app.get("/api/pipeline/status")
def pipeline_status() -> dict:
    """Return whether a pipeline is currently running."""
    return {"running": _pipeline_running, "project": _pipeline_project}


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


# ── Model management ──────────────────────────────────────────────────────────

_AGENT_NAMES = [
    "build",
    "fix",
    "test",
    "document",
    "explore",
    "plan",
    "architect",
    "milestone",
]


def _load_opencode(project_dir: Path) -> tuple[dict, Path | None]:
    """Load opencode.jsonc from project or workspace root."""
    for candidate in [project_dir / "opencode.jsonc", Path("opencode.jsonc")]:
        if candidate.exists():
            text = candidate.read_text(encoding="utf-8")
            # Strip single-line comments but preserve // inside quoted strings.
            cleaned = re.sub(
                r'"(?:[^"\\]|\\.)*"|//.*$',
                lambda m: m.group() if m.group().startswith('"') else "",
                text,
                flags=re.MULTILINE,
            )
            return json.loads(cleaned), candidate
    return {}, None


@app.get("/api/projects/{name}/models")
def get_models(name: str) -> list[dict]:
    """Get model configuration for each agent in the project."""
    project_dir = PROJECTS_ROOT / name
    if not project_dir.exists():
        raise HTTPException(404, f"Project '{name}' not found")

    config, _ = _load_opencode(project_dir)
    default_model = config.get("model", "")
    agents = config.get("agent", {})

    result = []
    for agent_name in _AGENT_NAMES:
        agent_config = agents.get(agent_name, {})
        result.append(
            {
                "agent": agent_name,
                "model": agent_config.get("model", default_model),
                "max_steps": agent_config.get("max_steps", 3),
            }
        )
    return result


@app.put("/api/projects/{name}/models/{agent}")
async def update_model(name: str, agent: str, request: Request) -> dict:
    """Update the model for a specific agent in the project's opencode.jsonc."""
    if agent not in _AGENT_NAMES:
        raise HTTPException(400, f"Unknown agent: {agent}")

    project_dir = PROJECTS_ROOT / name
    if not project_dir.exists():
        raise HTTPException(404, f"Project '{name}' not found")

    body = await request.json()
    new_model = body.get("model", "")
    if not new_model:
        raise HTTPException(400, "Model name is required")

    config, config_path = _load_opencode(project_dir)
    if config_path is None:
        # Create project-level config.
        config_path = project_dir / "opencode.jsonc"
        config = {"model": new_model, "agent": {}}

    if "agent" not in config:
        config["agent"] = {}
    if agent not in config["agent"]:
        config["agent"][agent] = {}
    config["agent"][agent]["model"] = new_model

    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return {"saved": True}


# ── Models catalog (autocomplete) ─────────────────────────────────────────────

_models_catalog_cache: list[str] | None = None


@app.get("/api/models-catalog")
def get_models_catalog() -> list[str]:
    """Return the full models.dev model list for autocomplete.

    Fetches from https://models.dev/api.json once and caches in memory.
    The API shape is {provider_id: {models: {model_key: {id, name, ...}}}}.
    Returns strings in "provider/model" format, sorted alphabetically.
    Does NOT cache on network failure so the next request retries.
    """
    global _models_catalog_cache
    if _models_catalog_cache is not None:
        return _models_catalog_cache

    import urllib.request  # noqa: PLC0415

    try:
        with urllib.request.urlopen("https://models.dev/api.json", timeout=10) as resp:
            data: dict = json.loads(resp.read().decode("utf-8"))
        ids: list[str] = []
        for provider_id, provider_obj in data.items():
            models_dict = (
                provider_obj.get("models", {}) if isinstance(provider_obj, dict) else {}
            )
            for model_key in models_dict:
                ids.append(f"{provider_id}/{model_key}")
        _models_catalog_cache = sorted(ids)
    except Exception:  # noqa: BLE001
        # Do not cache on failure — allow the next request to retry
        return []
    return _models_catalog_cache


# ── Global budget config ──────────────────────────────────────────────────────

_BUDGET_CONFIG_PATH = Path("budget.json")


@app.get("/api/config/budget")
def get_budget_config() -> dict:
    """Read the global budget.json configuration."""
    if not _BUDGET_CONFIG_PATH.exists():
        raise HTTPException(404, "budget.json not found")
    return json.loads(_BUDGET_CONFIG_PATH.read_text(encoding="utf-8"))


@app.put("/api/config/budget")
async def update_budget_config(request: Request) -> dict:
    """Update the global budget.json configuration.

    Note: changes take effect on next pipeline run (config.py reads at import time).
    """
    body = await request.json()
    _BUDGET_CONFIG_PATH.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return {"saved": True}


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


# Hardcoded MIME map — bypasses Python's mimetypes module which reads from
# the Windows registry and often maps .js to text/plain.
_MIME_MAP: dict[str, str] = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".map": "application/json",
    ".wasm": "application/wasm",
}


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    """Serve the React SPA index.html."""
    return HTMLResponse(_read_index())


@app.get("/assets/{path:path}")
def serve_asset(path: str) -> Response:
    """Serve static assets with explicit MIME types."""
    file_path = (_ASSETS_DIR / path).resolve()
    if not file_path.is_file() or not str(file_path).startswith(
        str(_ASSETS_DIR.resolve())
    ):
        raise HTTPException(status_code=404, detail="Asset not found")
    media_type = _MIME_MAP.get(file_path.suffix.lower(), "application/octet-stream")
    return Response(content=file_path.read_bytes(), media_type=media_type)


# SPA fallback: return index.html for any unmatched GET request (client-side
# routing).
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
