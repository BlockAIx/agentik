"""roadmap.py -- ROADMAP.json parsing, and prompt-block helpers."""

import json
import re
import subprocess
from pathlib import Path

from runner.config import ROADMAP_FILENAME, _console
from runner.workspace import _detect_ecosystem

# -- JSON ROADMAP loading -----------------------------------------------------


def _load_roadmap(project_dir: Path) -> dict:
    """Load and return the parsed ROADMAP.json."""
    with open(project_dir / ROADMAP_FILENAME, encoding="utf-8") as f:
        return json.load(f)


def _task_heading(task_data: dict) -> str:
    """Return canonical `## NNN - Title` heading string from a task dict."""
    return f"## {task_data['id']:03d} - {task_data['title']}"


def _find_task(roadmap: dict, heading: str) -> dict | None:
    """Find a task dict matching the `## NNN - Title` heading."""
    for t in roadmap.get("tasks", []):
        if _task_heading(t) == heading:
            return t
    return None


def _resolve_text(value) -> str:
    """Convert a description/preamble field (string or list of strings) to a single string."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(value)
    return str(value)


# -- ROADMAP parsing -----------------------------------------------------------


def get_tasks(project_dir: Path) -> list[str]:
    """Return all `## NNN - Title` task headings from ROADMAP.json."""
    roadmap = _load_roadmap(project_dir)
    return [_task_heading(t) for t in roadmap.get("tasks", [])]


def get_task_body(task: str, project_dir: Path) -> str:
    """Return the full task specification text (metadata + description).

    Reconstructs metadata lines in the same format the LLM agents expect,
    followed by the description text.
    """
    roadmap = _load_roadmap(project_dir)
    t = _find_task(roadmap, task)
    if not t:
        return ""

    lines: list[str] = []

    agent = t.get("agent", "")
    if agent and agent != "build":
        lines.append(f"agent: {agent}")

    eco = t.get("ecosystem", "")
    if eco:
        lines.append(f"ecosystem: {eco}")

    deps = t.get("depends_on", [])
    if deps:
        lines.append(f"depends_on: {', '.join(f'{d:03d}' for d in deps)}")
    else:
        lines.append("depends_on: none")

    ctx = t.get("context", [])
    if ctx:
        if isinstance(ctx, list):
            lines.append(f"context: {', '.join(ctx)}")
        else:
            lines.append(f"context: {ctx}")

    outputs = t.get("outputs", [])
    if outputs:
        if isinstance(outputs, list):
            lines.append(f"outputs: {', '.join(outputs)}")
        else:
            lines.append(f"outputs: {outputs}")

    acceptance = t.get("acceptance", "")
    if acceptance:
        lines.append(f"acceptance: {acceptance}")

    version = t.get("version", "")
    if version:
        lines.append(f"version: {version}")

    if t.get("deploy") is True:
        lines.append("deploy: true")

    desc = _resolve_text(t.get("description"))
    if desc:
        lines.append("")
        lines.append(desc)

    return "\n".join(lines)


def get_task_ecosystem(task: str, project_dir: Path) -> str:
    """Return the ecosystem for a task (task-level override or project default)."""
    roadmap = _load_roadmap(project_dir)
    t = _find_task(roadmap, task)
    if t:
        eco = t.get("ecosystem", "")
        if eco:
            return eco
    return _detect_ecosystem(project_dir)


def get_task_context_files(task: str, project_dir: Path) -> dict[str, str]:
    """Parse the `context` field and return `{relative_path: content}` for each file."""
    roadmap = _load_roadmap(project_dir)
    t = _find_task(roadmap, task)
    if not t:
        return {}

    ctx = t.get("context", [])
    if isinstance(ctx, str):
        ctx = [p.strip() for p in ctx.split(",") if p.strip()]

    result: dict[str, str] = {}
    for rel in ctx:
        full = project_dir / rel
        if full.exists():
            result[rel] = full.read_text(encoding="utf-8")
    return result


# -- Task field accessors ------------------------------------------------------


def get_task_agent(task: str, project_dir: Path) -> str:
    """Return the `agent` value from a task, defaulting to `'build'`."""
    roadmap = _load_roadmap(project_dir)
    t = _find_task(roadmap, task)
    if t:
        return t.get("agent", "build") or "build"
    return "build"


def get_task_version(task: str, project_dir: Path) -> str | None:
    """Return the `version` value from a task, or None if absent."""
    roadmap = _load_roadmap(project_dir)
    t = _find_task(roadmap, task)
    if t:
        v = t.get("version", "")
        return v if v else None
    return None


def is_milestone_task(task: str, project_dir: Path) -> bool:
    """Return True if *task* uses `agent: milestone`."""
    return get_task_agent(task, project_dir) == "milestone"


def is_deploy_task(task: str, project_dir: Path) -> bool:
    """Return True if *task* has `"deploy": true`."""
    roadmap = _load_roadmap(project_dir)
    t = _find_task(roadmap, task)
    if t:
        return t.get("deploy", False) is True
    return False


def is_git_managed(project_dir: Path) -> bool:
    """Return True if the project opts in to runner-managed git (``git.enabled``)."""
    roadmap = _load_roadmap(project_dir)
    git_block = roadmap.get("git")
    if isinstance(git_block, dict):
        return git_block.get("enabled", False) is True
    return False


def get_deploy_config(project_dir: Path) -> dict:
    """Return the project-level deploy config from ROADMAP.json.

    Returns a dict with keys: ``enabled``, ``script``, ``env``.
    Falls back to ``deploy.json`` for backward compatibility.
    """
    roadmap = _load_roadmap(project_dir)
    deploy = roadmap.get("deploy")
    if isinstance(deploy, dict):
        return {
            "enabled": deploy.get("enabled", True),
            "script": deploy.get("script"),
            "env": deploy.get("env", {}),
        }
    # Backward compat: check for deploy.json at project root.
    cfg_path = project_dir / "deploy.json"
    if cfg_path.exists():
        try:
            raw = json.loads(cfg_path.read_text(encoding="utf-8"))
            if raw.get("deploy") is False:
                return {"enabled": False, "script": None, "env": {}}
            env = {k: v for k, v in raw.items() if k != "deploy"}
            return {"enabled": True, "script": None, "env": env}
        except Exception:  # noqa: BLE001
            pass
    return {"enabled": False, "script": None, "env": {}}


def _task_number(heading: str) -> int:
    """Extract the 3-digit task number from a '## NNN - Title' heading."""
    m = re.match(r"^## (\d{3}) - ", heading)
    return int(m.group(1)) if m else -1


def get_task_outputs(task: str, project_dir: Path) -> list[str]:
    """Return the list of output file paths for a task."""
    roadmap = _load_roadmap(project_dir)
    t = _find_task(roadmap, task)
    if not t:
        return []
    outputs = t.get("outputs", [])
    if isinstance(outputs, str):
        return [p.strip() for p in outputs.split(",") if p.strip()]
    return list(outputs)


def parse_task_graph(project_dir: Path) -> dict[str, list[str]]:
    """Build `{task_heading: [dependency_headings]}` from `depends_on` fields."""
    roadmap = _load_roadmap(project_dir)
    tasks = roadmap.get("tasks", [])
    num_to_heading = {t["id"]: _task_heading(t) for t in tasks}

    graph: dict[str, list[str]] = {}
    for t in tasks:
        heading = _task_heading(t)
        dep_nums = t.get("depends_on", [])
        graph[heading] = [num_to_heading[n] for n in dep_nums if n in num_to_heading]
    return graph


def get_task_layers(
    all_tasks: list[str],
    graph: dict[str, list[str]],
    project_dir: Path,
) -> list[list[str]]:
    """Group tasks into topological layers. Milestones are placed in their own individual layers."""
    layers: list[list[str]] = []
    remaining = list(all_tasks)
    placed: set[str] = set()
    while remaining:
        candidates = [
            t for t in remaining if all(d in placed for d in graph.get(t, []))
        ]
        if not candidates:
            # Fallback for cycles or disconnected graphs
            candidates = list(remaining)

        milestones = [t for t in candidates if is_milestone_task(t, project_dir)]
        non_milestones = [
            t for t in candidates if not is_milestone_task(t, project_dir)
        ]

        if milestones:
            layer = [milestones[0]]
        else:
            layer = non_milestones

        layers.append(layer)
        placed.update(layer)
        remaining = [t for t in remaining if t not in placed]

    return layers


def get_ready_tasks(
    all_tasks: list[str],
    graph: dict[str, list[str]],
    done: set[str],
    project_dir: Path,
) -> list[str]:
    """Return undone tasks from the lowest incomplete layer whose dependencies are satisfied."""
    layers = get_task_layers(all_tasks, graph, project_dir)
    for layer in layers:
        undone = [t for t in layer if t not in done]
        if undone:
            # Return tasks in this layer that have all dependencies met
            return [t for t in undone if all(d in done for d in graph.get(t, []))]
    return []


def print_dependency_graph(project_dir: Path) -> None:
    """Print a colour-coded dependency graph for the project's ROADMAP tasks."""
    from runner.state import task_done  # noqa: PLC0415

    tasks = get_tasks(project_dir)
    graph = parse_task_graph(project_dir)
    done_set = {t for t in tasks if task_done(t, project_dir)}
    ready = get_ready_tasks(tasks, graph, done_set, project_dir)

    layers = get_task_layers(tasks, graph, project_dir)

    total = len(tasks)
    done_count = len(done_set)
    ready_count = len(ready)
    blocked_count = total - done_count - ready_count

    _console.print()
    _console.rule(
        f"[bold]Dependency Graph -- {project_dir.name}[/]  [dim]({total} tasks)[/]",
        style="blue",
    )
    _console.print(
        f"  [green]+ {done_count} done[/]  "
        f"[yellow]> {ready_count} ready[/]  "
        f"[dim]. {blocked_count} blocked[/]"
    )

    for depth, layer in enumerate(layers):
        _console.print(f"\n[blue bold]Layer {depth}[/]")
        for task in layer:
            deps = graph.get(task, [])
            dep_nums = (
                ", ".join(f"{_task_number(d):03d}" for d in deps) if deps else "--"
            )

            agent = get_task_agent(task, project_dir)

            if task in done_set:
                style = "green"
                icon = "+"
            elif task in ready:
                style = "yellow"
                icon = ">"
            else:
                style = "dim"
                icon = "."

            agent_badge = f" [magenta]({agent})[/]" if agent != "build" else ""
            label = task.removeprefix("## ")
            _console.print(
                f"  [{style}]{icon} {label}[/]{agent_badge}  [dim]<- {dep_nums}[/]"
            )

    _console.print()


# -- Test / static-check helpers -----------------------------------------------


def _detect_test_command(project_dir: Path, eco: str | None = None) -> tuple[str, str]:
    """Return `(shell_command, display_label)` for the ecosystem's test runner."""
    if eco is None:
        eco = _detect_ecosystem(project_dir)
    if eco == "deno":
        return "deno test --allow-all", "deno test"
    if eco == "node":
        try:
            pkg = json.loads((project_dir / "package.json").read_text(encoding="utf-8"))
            if "test" in pkg.get("scripts", {}):
                return "pnpm test", "pnpm test"
        except (json.JSONDecodeError, OSError):
            pass
    if eco == "go":
        return "go test ./...", "go test"
    if eco == "rust":
        return "cargo test", "cargo test"
    return "pytest", "pytest"


def _ecosystem_prompt_blocks(
    project_dir: Path,
    src: Path,
    tests: Path,
    pkg: str,
    eco: str | None = None,
) -> dict[str, str]:
    """Return prompt snippet strings keyed by block name for the given ecosystem."""
    if eco is None:
        eco = _detect_ecosystem(project_dir)
    _, test_label = _detect_test_command(project_dir, eco=eco)

    if eco == "deno":
        return {
            "lang_line": "Implement the following task with clean, production-quality **TypeScript for Deno**.",
            "locations": (
                f"- Implementation: `{src}/`\n"
                f"- Unit tests:     `{tests}/` (use `Deno.test` + `@std/assert`, one file per module)"
            ),
            "import_rules": (
                "## Deno conventions\n"
                "- Use `deno.json` `imports` map for all third-party specifiers.\n"
                "- Prefer `jsr:` specifiers; fall back to `npm:` when a JSR package is unavailable.\n"
                "- Do **not** use bare `npm install` -- declare deps in `deno.json` only.\n"
                "- Test files live in `tests/` and must be named `*.test.ts`.\n"
                "- Run with: `deno test --allow-all`"
            ),
            "test_runner": test_label,
            "manifest_table": (
                "| Ecosystem   | Manifest file | How to add                                  |\n"
                "|-------------|---------------|---------------------------------------------|\n"
                '| Deno/TypeScript | `deno.json`  | add under `"imports"`: `"pkg": "npm:pkg@^x"` |'
            ),
        }
    if eco == "node":
        return {
            "lang_line": "Implement the following task with clean, production-quality **TypeScript (Node.js)**.",
            "locations": (
                f"- Implementation: `{src}/`\n"
                f"- Unit tests:     `{tests}/` (`{test_label}`-compatible, one file per module)"
            ),
            "import_rules": (
                "## TypeScript conventions\n"
                "- Use ES module style imports.\n"
                "- Keep `tsconfig.json` strict.\n"
                f"- Run tests with: `{test_label}`"
            ),
            "test_runner": test_label,
            "manifest_table": (
                "| Ecosystem  | Manifest file  | How to add                         |\n"
                "|------------|----------------|------------------------------------|\n"
                "| Node/TS    | `package.json` | `pnpm add <pkg>`                   |"
            ),
        }
    # Python (default)
    return {
        "lang_line": "Implement the following task with clean, production-quality **Python** code.",
        "locations": (
            f"- Implementation: `{src}/`   (Python package, add modules here)\n"
            f"- Unit tests:     `{tests}/` (pytest-compatible, one file per module)"
        ),
        "import_rules": (
            f"## Python package name\n"
            f"The importable package name is **`{pkg}`**.\n"
            f"- All test imports must use fully-qualified names: `from {pkg}.module import X`\n"
            "- Do **not** use bare module imports or `sys.path` manipulation.\n"
            "- The conftest.py at the project root ensures pytest adds the project directory\n"
            "  to `sys.path` automatically; no path hacks are needed in test files."
        ),
        "test_runner": test_label,
        "manifest_table": (
            "| Ecosystem  | Manifest file      | How to add                                |\n"
            "|------------|--------------------|-------------------------------------------|\n"
            "| Python     | `requirements.txt` | one package per line, e.g. `httpx>=0.27` |\n"
            "| Python     | `pyproject.toml`   | under `[project] dependencies`           |"
        ),
    }


# -- Test / static-check runners -----------------------------------------------


def _detect_active_test_suites(project_dir: Path) -> list[tuple[str, str]]:
    """Return all test runner `(command, label)` pairs that have test files present."""
    suites: list[tuple[str, str]] = []
    tests_path = project_dir / "tests"

    # Python
    py_tests = list(tests_path.glob("test_*.py")) if tests_path.exists() else []
    if not py_tests:
        py_tests = list(project_dir.rglob("test_*.py"))
    if py_tests:
        suites.append(("pytest", "pytest"))

    # Deno
    ts_test_files = list(tests_path.glob("*.test.ts")) if tests_path.exists() else []
    has_deno = (project_dir / "deno.json").exists() or (
        project_dir / "deno.jsonc"
    ).exists()
    if ts_test_files and has_deno:
        suites.append(("deno test --allow-all", "deno test"))

    # Node
    if (project_dir / "package.json").exists():
        try:
            pkg = json.loads((project_dir / "package.json").read_text(encoding="utf-8"))
            if "test" in pkg.get("scripts", {}):
                suites.append(("pnpm test", "pnpm test"))
        except (json.JSONDecodeError, OSError):
            pass

    # Go
    if (project_dir / "go.mod").exists():
        go_tests = list(project_dir.rglob("*_test.go"))
        if go_tests:
            suites.append(("go test ./...", "go test"))

    # Rust
    if (project_dir / "Cargo.toml").exists():
        suites.append(("cargo test", "cargo test"))

    if not suites:
        suites.append(_detect_test_command(project_dir))

    return suites


def _detect_static_check_commands(project_dir: Path) -> list[tuple[str, str]]:
    """Return static analysis `(command, label)` pairs for detected ecosystems."""
    cmds: list[tuple[str, str]] = []

    has_deno = (project_dir / "deno.json").exists() or (
        project_dir / "deno.jsonc"
    ).exists()
    if has_deno:
        cmds.append(("deno check src/**/*.ts tests/**/*.ts", "deno check"))
        cmds.append(("deno lint", "deno lint"))
        return cmds

    if (project_dir / "package.json").exists() and (
        project_dir / "tsconfig.json"
    ).exists():
        cmds.append(("npx tsc --noEmit", "tsc"))

    if (project_dir / "go.mod").exists():
        cmds.append(("go vet ./...", "go vet"))

    if (project_dir / "Cargo.toml").exists():
        cmds.append(("cargo clippy -- -D warnings", "cargo clippy"))

    py_files = list(project_dir.rglob("*.py"))
    if py_files:
        ruff = subprocess.run("ruff --version", shell=True, capture_output=True)
        if ruff.returncode == 0:
            cmds.append(("ruff check .", "ruff"))

    return cmds


def run_tests(project_dir: Path) -> tuple[bool, str]:
    """Run all detected test suites and return `(all_passed, combined_output)`."""
    suites = _detect_active_test_suites(project_dir)
    all_passed = True
    combined_output: list[str] = []

    for cmd, label in suites:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(project_dir),
        )
        output = (result.stdout or "") + (result.stderr or "")
        _console.rule(f"[dim]{label} output[/]", style="bright_black")
        _console.print(output[-2000:].rstrip())
        _console.rule(style="bright_black")
        combined_output.append(f"--- {label} ---\n{output}")
        if result.returncode != 0:
            all_passed = False

    return all_passed, "\n".join(combined_output)


def run_static_checks(project_dir: Path) -> tuple[bool, str]:
    """Run all static analysis tools and return `(all_passed, combined_output)`."""
    cmds = _detect_static_check_commands(project_dir)
    if not cmds:
        return True, ""

    all_passed = True
    combined: list[str] = []

    for cmd, label in cmds:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(project_dir),
        )
        output = (result.stdout or "") + (result.stderr or "")
        _console.rule(f"[dim]{label} output[/]", style="bright_black")
        _console.print(output[-2000:].rstrip())
        _console.rule(style="bright_black")
        combined.append(f"--- {label} ---\n{output}")
        if result.returncode != 0:
            all_passed = False

    return all_passed, "\n".join(combined)
