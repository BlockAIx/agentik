"""workspace.py — Ecosystem detection, scaffolding, dependency install, and git ops."""

import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

from runner.config import PROJECTS_ROOT, ROADMAP_FILENAME, _console, slugify
from runner.state import (
    _completed_tasks,
    _raw_state,
    save_project_budget,
)

# ── Ecosystem detection ────────────────────────────────────────────────────────


def get_roadmap_ecosystem(project_dir: Path) -> str | None:
    """Parse the ``ecosystem`` field from ROADMAP.json, or return None."""
    roadmap = project_dir / ROADMAP_FILENAME
    if not roadmap.exists():
        return None
    try:
        data = json.loads(roadmap.read_text(encoding="utf-8"))
        value = data.get("ecosystem", "").strip().lower()
        if value:
            return value
    except (json.JSONDecodeError, OSError):
        pass
    return None


def get_roadmap_project_context(project_dir: Path) -> str:
    """Return the ROADMAP preamble text for prompt injection."""
    roadmap = project_dir / ROADMAP_FILENAME
    if not roadmap.exists():
        return ""
    try:
        data = json.loads(roadmap.read_text(encoding="utf-8"))
        preamble = data.get("preamble", "")
        if isinstance(preamble, list):
            return "\n".join(preamble).strip()
        return str(preamble).strip()
    except (json.JSONDecodeError, OSError):
        return ""


def _detect_ecosystem(project_dir: Path) -> str:
    """Return the primary ecosystem for *project_dir* (ROADMAP field → heuristic → ``'python'``)."""
    declared = get_roadmap_ecosystem(project_dir)
    if declared is not None:
        return declared
    if (project_dir / "deno.json").exists() or (project_dir / "deno.jsonc").exists():
        return "deno"
    if (project_dir / "package.json").exists():
        return "node"
    if (project_dir / "go.mod").exists():
        return "go"
    if (project_dir / "Cargo.toml").exists():
        return "rust"
    return "python"


def _pkg_name(project_dir: Path) -> str:
    """Return the implementation package / source directory name."""
    eco = _detect_ecosystem(project_dir)
    if eco == "python":
        return project_dir.name.replace("-", "_")
    return project_dir.name


def src_dir(project_dir: Path) -> Path:
    """Return the implementation source root for a project."""
    eco = _detect_ecosystem(project_dir)
    if eco == "python":
        return project_dir / _pkg_name(project_dir)
    if eco in {"deno", "node", "rust"}:
        return project_dir / "src"
    # Go: source lives at the project root itself.
    return project_dir


def tests_dir(project_dir: Path) -> Path:
    """Return ``projects/<name>/tests/``."""
    return project_dir / "tests"


# ── Ecosystem scaffold templates ───────────────────────────────────────────────


def _write_if_absent(path: Path, content: str) -> bool:
    """Write *content* to *path* only if the file does not exist; return True if written."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def scaffold_ecosystem_configs(project_dir: Path, eco: str) -> None:
    """Create ecosystem-specific config and boilerplate files (idempotent)."""
    written: list[str] = []
    pkg = _pkg_name(project_dir)
    _src = src_dir(project_dir)

    # Ensure the source root for this ecosystem exists.
    if eco != "go":  # Go source lives at project root — already exists
        _src.mkdir(parents=True, exist_ok=True)

    if eco == "python":
        conftest = project_dir / "conftest.py"
        if _write_if_absent(
            conftest,
            """\
import sys
from pathlib import Path

# Make the project root importable so pytest finds the package without
# needing an editable install.  This mirrors the standard pytest convention.
sys.path.insert(0, str(Path(__file__).parent))
""",
        ):
            written.append("conftest.py")

    elif eco == "deno":
        if _write_if_absent(
            project_dir / "deno.json",
            """\
{
  "compilerOptions": {
    "strict": true
  },
  "imports": {}
}
""",
        ):
            written.append("deno.json")

    elif eco == "node":
        if _write_if_absent(
            project_dir / "tsconfig.json",
            """\
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules"]
}
""",
        ):
            written.append("tsconfig.json")

        # Write a stub package.json only when none exists at all.
        if _write_if_absent(
            project_dir / "package.json",
            f"""\
{{
  "name": "{pkg}",
  "version": "0.1.0",
  "type": "module"
}}
""",
        ):
            written.append("package.json (stub)")

    if eco in ("node", "deno"):
        _patch_tsconfig_for_tests(project_dir)

    elif eco == "go":
        if _write_if_absent(
            project_dir / "go.mod",
            f"""\
module github.com/local/{pkg}

go 1.22
""",
        ):
            written.append("go.mod")

    elif eco == "rust":
        if _write_if_absent(
            project_dir / "Cargo.toml",
            f"""\
[package]
name = "{pkg}"
version = "0.1.0"
edition = "2021"

[dependencies]

[dev-dependencies]
""",
        ):
            written.append("Cargo.toml")

    if written:
        _console.print(f"[dim][[scaffold]][/] {eco}: {', '.join(written)}")


# ── tsconfig test-framework patching ──────────────────────────────────────────

# Map from npm package name → TypeScript ``compilerOptions.types`` entry.
# Ordered so that the first matching entry wins when multiple frameworks are
# present in the same project.
_TEST_FRAMEWORK_TYPES: list[tuple[str, str]] = [
    ("@types/jest", "jest"),
    ("jest", "jest"),
    ("@vitest/ui", "vitest/globals"),
]


def _patch_tsconfig_for_tests(project_dir: Path) -> None:
    """Ensure ``tsconfig.json`` has test-framework types, ``tests/**/*`` include, and wide rootDir."""
    tsconfig_path = project_dir / "tsconfig.json"
    pkg_path = project_dir / "package.json"
    if not tsconfig_path.exists() or not pkg_path.exists():
        return

    try:
        pkg: dict = json.loads(pkg_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return

    all_deps: dict[str, str] = {
        **pkg.get("dependencies", {}),
        **pkg.get("devDependencies", {}),
    }

    # Collect which type entries are needed for this project's test stack.
    needed_types: list[str] = []
    for pkg_name, type_entry in _TEST_FRAMEWORK_TYPES:
        if pkg_name in all_deps and type_entry not in needed_types:
            needed_types.append(type_entry)

    has_tests_dir = (project_dir / "tests").exists()
    if not needed_types and not has_tests_dir:
        return  # Nothing to patch.

    # Parse tsconfig — strip ``//`` comments first for robustness.
    try:
        raw = tsconfig_path.read_text(encoding="utf-8")
        cleaned = re.sub(r"//[^\n]*", "", raw)
        cfg: dict = json.loads(cleaned)
    except Exception:  # noqa: BLE001
        return

    changed = False
    opts: dict = cfg.setdefault("compilerOptions", {})

    # ── 1. Merge test types ────────────────────────────────────────────────
    if needed_types:
        existing_types: list[str] = opts.get("types", [])
        for t in needed_types:
            if t not in existing_types:
                existing_types.append(t)
                changed = True
        opts["types"] = existing_types

    # ── 2. Include tests directory ─────────────────────────────────────────
    if has_tests_dir:
        includes: list[str] = cfg.get("include", [])
        if "tests/**/*" not in includes:
            includes.append("tests/**/*")
            cfg["include"] = includes
            changed = True

    # ── 3. Widen rootDir so it covers included test files ──────────────────
    if "tests/**/*" in cfg.get("include", []):
        if opts.get("rootDir") in ("./src", "src"):
            opts["rootDir"] = "."
            changed = True

    if changed:
        tsconfig_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        _console.print(
            "[dim][[scaffold]][/] tsconfig.json patched for tests"
            + (f" — types: {needed_types}" if needed_types else "")
        )


# ── Dependency installation ────────────────────────────────────────────────────

# Ordered list of (manifest filename, shell command template, display label).
# All matching manifests are installed — a full-stack project may have several.
# Placeholders expanded at call time:
#   {manifest} — absolute POSIX path to the manifest file
#   {dir}      — absolute POSIX path to the project directory
#   {python}   — current Python interpreter (sys.executable)
_DEP_INSTALLERS: list[tuple[str, str, str]] = [
    (
        "requirements.txt",
        "{python} -m pip install --prefer-binary -r {manifest}",
        "pip",
    ),
    ("pyproject.toml", "{python} -m pip install --prefer-binary -e {dir}", "pip"),
    ("package.json", "pnpm install", "pnpm"),
    ("Gemfile", "bundle install", "bundle"),
    ("go.mod", "go mod download", "go"),
    ("Cargo.toml", "cargo fetch", "cargo"),
]


def install_project_dependencies(project_dir: Path) -> None:
    """Install all dependencies declared by the project's manifest files."""
    python = Path(sys.executable).resolve().as_posix()
    proj_dir_posix = project_dir.resolve().as_posix()
    found_any = False

    for manifest_name, cmd_template, label in _DEP_INSTALLERS:
        manifest = project_dir / manifest_name
        if not manifest.exists():
            continue
        found_any = True
        manifest_posix = manifest.resolve().as_posix()
        cmd = cmd_template.format(
            manifest=manifest_posix, dir=proj_dir_posix, python=python
        )
        _console.print(f"[dim][[deps]][/] {manifest_name} → [cyan]{label}[/] ...")
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=str(project_dir)
        )
        if result.returncode != 0:
            # Show a concise error: extract the last non-blank error line.
            err_lines = [ln.strip() for ln in result.stderr.splitlines() if ln.strip()]
            err_summary = err_lines[-1] if err_lines else "unknown error"
            _console.print(
                f"[yellow]⚠ dependency install failed ({manifest_name}):[/] {err_summary}"
            )
            _console.print(f"[dim]  full output in terminal scrollback[/]")
        else:
            _console.print(f"[dim][deps][/] {manifest_name} installed.")

    if not found_any:
        _console.print(
            f"[dim][deps] No dependency manifest found in {project_dir.name} — skipping.[/]"
        )


# ── opencode config sync ───────────────────────────────────────────────────────


def _sync_opencode_config(project_dir: Path) -> None:
    """Copy workspace ``opencode.jsonc`` into *project_dir* for agent sandboxing."""
    src = Path("opencode.jsonc")
    dst = project_dir / "opencode.jsonc"
    if src.exists():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


# ── Git helpers ────────────────────────────────────────────────────────────────

# Standard gitignore written into every new project repo.
# Covers common artefacts across Python, Node/Deno, Go, and Rust ecosystems.
_PROJECT_GITIGNORE = """\
# Python
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
coverage/
*.egg-info/

# Node / Deno
node_modules/
.deno/
*.tsbuildinfo

# Go
vendor/

# Build artefacts
dist/
build/
target/

# Environment / secrets — never commit
.env
.env.*
!.env.example

# Runner-managed: copied from workspace opencode.jsonc at each startup.
opencode.jsonc

# Runner agent logs (per-invocation; auto-generated)
logs/
"""


def git_run(cmd: str, project_dir: Path) -> bool:
    """Run ``git -C <project_dir> <cmd>`` silently; return True on exit code 0."""
    return (
        subprocess.run(
            f'git -C "{project_dir}" {cmd}',
            shell=True,
            capture_output=True,
        ).returncode
        == 0
    )


def _git_has_remote(project_dir: Path) -> bool:
    """Return True if the repo has an 'origin' remote configured."""
    result = subprocess.run(
        f'git -C "{project_dir}" remote get-url origin',
        shell=True,
        capture_output=True,
    )
    return result.returncode == 0


def _git_push_if_remote(ref: str, project_dir: Path) -> None:
    """Push *ref* to origin if a remote is configured; skip silently otherwise."""
    if _git_has_remote(project_dir):
        git_run(f"push origin {ref}", project_dir)


def ensure_project_git(project_dir: Path) -> None:
    """Bootstrap a standalone git repo with ``main`` and ``develop`` branches.

    No-op if ``.git/`` already exists or the project does not opt in to
    runner-managed git (``git.enabled`` in ROADMAP.json).
    """
    from runner.roadmap import is_git_managed  # noqa: PLC0415

    if not is_git_managed(project_dir):
        return

    git_dir = project_dir / ".git"
    if git_dir.exists():
        return

    _console.print(
        f"[dim][[git]][/] Initialising project repo in [cyan]{project_dir}[/] ..."
    )

    gitignore = project_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(_PROJECT_GITIGNORE, encoding="utf-8")

    git_run("init", project_dir)
    git_run("add .", project_dir)
    git_run('commit -m "chore: initial project scaffold"', project_dir)
    git_run("branch -M main", project_dir)
    git_run("checkout -b develop", project_dir)
    _console.print(
        f"[dim][git][/] Repo initialised — branches: [cyan]main[/], [cyan]develop[/]"
    )


def _clean_task_label(task: str) -> str:
    """Strip the ``## `` markdown prefix from a task heading for display."""
    return task.lstrip("# ").strip()


def ensure_feature_branch(task: str, project_dir: Path) -> str | None:
    """Create or switch to the ``feature/<slug>`` branch for *task*.

    Returns the branch name, or None if git is not managed.
    """
    from runner.roadmap import is_git_managed  # noqa: PLC0415

    if not is_git_managed(project_dir):
        return None
    branch = f"feature/{slugify(task)}"
    if not git_run(f"checkout -b {branch}", project_dir):
        git_run(f"checkout {branch}", project_dir)
    _console.print(f"[dim][git] On branch [cyan]{branch}[/cyan][/]")
    return branch


def commit_and_merge(
    task: str, project_dir: Path, task_outputs: list[str] | None = None
) -> None:
    """Stage, commit on feature branch, merge into develop, delete branch, and push.

    No-op if the project does not opt in to runner-managed git.
    """
    from runner.roadmap import is_git_managed  # noqa: PLC0415

    if not is_git_managed(project_dir):
        return
    branch = f"feature/{slugify(task)}"
    label = _clean_task_label(task)
    # Always include runner state so the completed-task record is part of the commit.
    if (project_dir / ".runner_state.json").exists():
        git_run('add ".runner_state.json"', project_dir)
    if task_outputs:
        for out in task_outputs:
            git_run(f'add "{out}"', project_dir)
    else:
        git_run("add .", project_dir)
    git_run(f'commit -m "feat: {label}"', project_dir)
    git_run("checkout develop", project_dir)
    git_run(f"merge --no-ff {branch}", project_dir)
    git_run(f"branch -d {branch}", project_dir)
    _git_push_if_remote("develop", project_dir)
    _console.print(
        f"[dim][git] Committed [cyan]{label}[/cyan] → develop (branch {branch} merged & deleted)[/]"
    )


def tag_milestone(version: str, project_dir: Path) -> None:
    """Tag ``v<version>`` on develop and push.

    No-op if the project does not opt in to runner-managed git.
    """
    from runner.roadmap import is_git_managed  # noqa: PLC0415

    if not is_git_managed(project_dir):
        _console.print(
            f"[bold magenta]Milestone:[/] v{version} [dim](git not managed — skipping tag)[/]"
        )
        return
    _console.print(f"[bold magenta]Milestone:[/] tagging [cyan]v{version}[/]")
    git_run("add .", project_dir)
    git_run(f'commit --allow-empty -m "milestone: v{version}"', project_dir)
    git_run(f"tag v{version}", project_dir)
    _git_push_if_remote("develop", project_dir)
    _git_push_if_remote(f"v{version}", project_dir)
    _console.print(f"[green bold]✔ Tagged v{version} on develop[/]")


# ── Deploy hook ────────────────────────────────────────────────────────────────


def _load_deploy_config(project_dir: Path) -> dict[str, str]:
    """Build ``DEPLOY_*`` env vars from the ROADMAP deploy block or ``deploy.json`` fallback."""
    from runner.roadmap import get_deploy_config  # noqa: PLC0415

    cfg = get_deploy_config(project_dir)
    env_block = cfg.get("env", {})
    if not isinstance(env_block, dict):
        return {}
    return {f"DEPLOY_{k.upper()}": str(v) for k, v in env_block.items()}


def try_deploy_hook(task: str | None, project_dir: Path) -> None:
    """Run the deploy script if the task is marked for deployment.

    Deploy runs when ALL of these are true:
    - ``RUNNER_NO_DEPLOY`` env var is not set.
    - The project has deployment enabled (ROADMAP ``deploy.enabled`` or
      legacy ``deploy.json`` without ``"deploy": false``).
    - The *task* has ``"deploy": true`` in the ROADMAP — **or** *task* is
      ``None`` (backward-compat: deploy on every commit when no per-task
      control is used and a deploy script is found).

    The deploy script path is resolved from (in order):
    1. ``deploy.script`` in the ROADMAP deploy block.
    2. ``scripts/deploy.ps1`` (Windows) or ``scripts/deploy.sh`` (Linux/macOS).
    """
    if os.environ.get("RUNNER_NO_DEPLOY"):
        return

    from runner.roadmap import get_deploy_config, is_deploy_task  # noqa: PLC0415

    cfg = get_deploy_config(project_dir)
    if not cfg.get("enabled", False):
        return

    # Per-task gating: skip unless the task is marked for deploy.
    if task is not None and not is_deploy_task(task, project_dir):
        return

    # Resolve script path.
    explicit_script = cfg.get("script")
    if explicit_script:
        script = (project_dir / explicit_script).resolve()
        if not script.exists():
            _console.print(
                f"[yellow]⚠ deploy.script '{explicit_script}' not found — skipping deploy.[/]"
            )
            return
    else:
        candidates = (
            ["scripts/deploy.ps1", "scripts/deploy.sh"]
            if platform.system() == "Windows"
            else ["scripts/deploy.sh"]
        )
        script = None
        for candidate in candidates:
            p = (project_dir / candidate).resolve()
            if p.exists():
                script = p
                break
        if script is None:
            return

    deploy_env = {**os.environ, **_load_deploy_config(project_dir)}

    cmd = (
        f'powershell -ExecutionPolicy Bypass -File "{script}"'
        if platform.system() == "Windows"
        else f'bash "{script}"'
    )
    _console.print(
        f"[dim][deploy] running {script.relative_to(project_dir.resolve())}...[/]"
    )
    result = subprocess.run(cmd, shell=True, cwd=str(project_dir), env=deploy_env)
    if result.returncode == 0:
        _console.print("[green bold]✈ Deploy completed.[/]")
    else:
        _console.print(
            f"[yellow]⚠ Deploy script exited with code {result.returncode} — check output above.[/]"
        )


# ── Workspace initialisation ───────────────────────────────────────────────────


def ensure_workspace_dirs(project_dir: Path) -> None:
    """Create source/test dirs, budget file, sync config, and init git for *project_dir*."""
    eco = _detect_ecosystem(project_dir)
    scaffold_ecosystem_configs(project_dir, eco)
    if eco == "python":
        init = src_dir(project_dir) / "__init__.py"
        if not init.exists():
            init.touch()
    tst = tests_dir(project_dir)
    tst.mkdir(parents=True, exist_ok=True)
    budget_path = project_dir / "budget.json"
    if not budget_path.exists():
        save_project_budget(
            project_dir,
            {
                "project": project_dir.name,
                "total_tokens": 0,
                "total_calls": 0,
                "sessions": [],
            },
        )
    _sync_opencode_config(project_dir)
    ensure_project_git(project_dir)
    _ensure_logs_gitignored(project_dir)
    if not (project_dir / "AGENTS.md").exists():
        generate_project_agents_md(project_dir)


def _ensure_logs_gitignored(project_dir: Path) -> None:
    """Append ``logs/`` to the project .gitignore if it is not already listed."""
    gitignore = project_dir / ".gitignore"
    entry = "logs/"
    if gitignore.exists():
        text = gitignore.read_text(encoding="utf-8")
        # Check whether the entry (as its own non-commented line) is already present.
        if any(line.strip() == entry for line in text.splitlines()):
            return
        gitignore.write_text(
            text.rstrip("\n")
            + f"\n\n# Runner agent logs (per-invocation; auto-generated)\n{entry}\n",
            encoding="utf-8",
        )


# ── Project-level AGENTS.md ────────────────────────────────────────────────────

_ECO_LAYOUT: dict[str, str] = {
    "python": """\
```
<project>/
├── <pkg>/          ← implementation package (import as `from <pkg>.module import …`)
│   └── *.py
├── tests/
│   └── test_*.py
├── ROADMAP.json
└── requirements.txt / pyproject.toml
```""",
    "node": """\
```
<project>/
├── src/            ← all implementation TypeScript
│   └── *.ts
├── tests/
│   └── *.test.ts
├── ROADMAP.json
├── package.json
└── tsconfig.json
```""",
    "deno": """\
```
<project>/
├── src/            ← all implementation TypeScript
│   └── *.ts
├── tests/
│   └── *.test.ts
├── ROADMAP.json
└── deno.json
```""",
    "go": """\
```
<project>/
├── *.go            ← implementation at module root
├── *_test.go       ← tests alongside source
├── ROADMAP.json
└── go.mod
```""",
    "rust": """\
```
<project>/
├── src/
│   └── *.rs
├── tests/
│   └── *.rs
├── ROADMAP.json
└── Cargo.toml
```""",
}

_ECO_GUIDELINES: dict[str, str] = {
    "python": """\
- Prefer stdlib; add third-party deps only when clearly needed.
- Keep modules renderer-agnostic for full unit-testability.
- Tests in `tests/test_<module>.py`; shared fixtures in `conftest.py`.
- Import with the package name (`from <pkg>.module import Foo`) — **never** use
  relative imports from test files.
- No `if __name__ == "__main__"` guards in library modules.
- No unused imports (`ruff` enforces this).
- Add type annotations where `ruff` flags them.
- `ruff check` and `ruff format` must pass before considering a task complete.""",
    "node": """\
- Explicit parameter and return types on **all** exports.
- No `any` — use `unknown` + type narrowing instead.
- No non-null assertions (`!`) — use conditionals.
- Never mark a function `async` unless it actually `await`s something; use
  `Promise.resolve(value)` when the interface signature requires a `Promise`.
- Unused vars / params are compile errors — remove them or prefix with `_`.
- Every code path must return a value (`noImplicitReturns`).
- `pnpm lint` (ESLint) and `pnpm typecheck` (tsc --noEmit) must pass.""",
    "deno": """\
- Explicit parameter and return types on **all** exports.
- No `any` — use `unknown` + type narrowing instead.
- No non-null assertions (`!`) — use conditionals.
- Never mark a function `async` unless it actually `await`s something.
- Unused vars / params are compile errors — remove or `_`-prefix them.
- Every code path must return (`noImplicitReturns`).
- `deno check` and `deno lint` must pass before considering a task complete.""",
    "go": """\
- All exported identifiers need Go doc comments.
- Prefer table-driven tests with `t.Run`.
- `go vet ./…` must pass.
- Avoid `init()` side effects in library packages.""",
    "rust": """\
- All public items need doc comments.
- Prefer `Result`/`Option` over `unwrap()` / `expect()` in library code.
- `cargo clippy -- -D warnings` must pass.
- No `unsafe` blocks unless the task explicitly requires FFI.""",
}

_STATIC_CHECK: dict[str, str] = {
    "python": "`ruff check` + `ruff format --check`",
    "node": "`pnpm lint` (ESLint) + `npx tsc --noEmit`",
    "deno": "`deno check` + `deno lint`",
    "go": "`go vet ./…`",
    "rust": "`cargo clippy -- -D warnings`",
}

_TEST_CMD: dict[str, str] = {
    "python": "`pytest`",
    "node": "`pnpm test`",
    "deno": "`deno test`",
    "go": "`go test ./…`",
    "rust": "`cargo test`",
}


def generate_project_agents_md(project_dir: Path) -> None:
    """Generate (or overwrite) ``AGENTS.md`` in *project_dir*.

    Produces a project-specific agents instruction file derived from the project
    ROADMAP.json (name, ecosystem, preamble, task list) and the workspace
    implementation guidelines.  Written in a format that opencode agents working
    **inside** the project directory can use as authoritative context without
    needing access to the workspace-level AGENTS.md.
    """
    import datetime as _dt  # noqa: PLC0415

    roadmap_path = project_dir / ROADMAP_FILENAME
    roadmap: dict = {}
    if roadmap_path.exists():
        try:
            roadmap = json.loads(roadmap_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    project_name = roadmap.get("name") or project_dir.name
    eco = _detect_ecosystem(project_dir)
    preamble = roadmap.get("preamble", "")
    if isinstance(preamble, list):
        preamble = "\n".join(preamble)
    preamble = preamble.strip()

    pkg = _pkg_name(project_dir)
    _src = src_dir(project_dir)
    src_rel = _src.relative_to(project_dir).as_posix() if _src != project_dir else "."

    layout = (
        _ECO_LAYOUT.get(eco, f"`src/` — implementation\n`tests/` — tests")
        .replace("<pkg>", pkg)
        .replace("<project>", project_dir.name)
    )
    guidelines = _ECO_GUIDELINES.get(
        eco, "- Follow standard conventions for the ecosystem."
    )
    static_check = _STATIC_CHECK.get(eco, "run the project linter")
    test_cmd = _TEST_CMD.get(eco, "run the project test suite")

    # ── Task summary ──────────────────────────────────────────────────────
    tasks: list[dict] = roadmap.get("tasks", [])
    total_tasks = len(tasks)
    done_tasks = len(_completed_tasks(_raw_state(project_dir)))
    task_summary = (
        f"{done_tasks} / {total_tasks} tasks complete"
        if total_tasks
        else "No tasks defined yet"
    )

    # ── Build the document ────────────────────────────────────────────────
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    out_lines: list[str] = [
        f"<!-- auto-generated by runner on {ts} — regenerate via runner menu -->\n",
        f"# {project_name} — Agent Instructions\n",
        "This file is read automatically by opencode agents working inside this\n"
        "project directory. It describes the layout, conventions, and task rules.\n"
        "**Do not edit by hand** — regenerate via the runner menu when the ROADMAP changes.\n",
        "---\n",
        "## Project overview\n",
        f"| Field      | Value |\n"
        f"|------------|-------|\n"
        f"| Name       | {project_name} |\n"
        f"| Ecosystem  | {eco} |\n"
        f"| Source     | `{src_rel}/` |\n"
        f"| Tests      | `tests/` |\n"
        f"| Progress   | {task_summary} |\n",
    ]

    if preamble:
        out_lines += [
            "\n### Description\n",
            preamble + "\n",
        ]

    out_lines += [
        "\n---\n",
        "## Repository layout\n",
        layout + "\n",
        "\n---\n",
        "## ROADMAP and tasks\n",
        f"All tasks are defined in `ROADMAP.json` at the project root.\n"
        f"The runner passes the current task's full spec to the agent as a prompt.\n",
        "\nEach task has this shape:\n",
        "```json\n"
        "{\n"
        '  "id": 3,\n'
        '  "title": "Short Title",\n'
        '  "depends_on": [1, 2],\n'
        '  "context": ["src/existing_module.ts"],\n'
        '  "outputs": ["src/new_module.ts", "tests/new_module.test.ts"],\n'
        '  "acceptance": "all tests in tests/new_module.test.ts pass",\n'
        '  "description": "Detailed implementation spec…"\n'
        "}\n"
        "```\n",
        "\n**The root task** (task 1, `depends_on: []`) must fully prepare the project:\n"
        "directory layout, manifest / dependency file, config files (linter, formatter,\n"
        "tsconfig), shared types / interfaces / base classes, and the test harness.\n"
        "All later tasks depend on the root's outputs and start building immediately.\n",
        "\n**Implement exactly what `outputs:` and `description:` require — nothing more.**\n",
        "\n---\n",
        "## Pipeline phases\n",
        "The runner drives the agent through these phases for each task:\n",
        "```\n"
        f"Build    → implement module + unit tests ({src_rel}/ and tests/)\n"
        f"Test     → {test_cmd}\n"
        "Fix      → repair failing tests (same session, full test output provided)\n"
        f"Static   → {static_check}\n"
        "Stfix    → repair static analysis issues\n"
        "Document → update README only (no logic changes)\n"
        "Commit   → runner handles git (feature/<slug> → develop)\n"
        "```\n",
        "\n---\n",
        "## Implementation guidelines\n",
        guidelines + "\n",
        "\n---\n",
        "## Testing rules\n",
        "- At least one test per public function / method (happy path + task-specified edge cases).\n"
        "- Mock only external I/O (filesystem, network, time) — never mock the module under test.\n"
        "- Deterministic: no unbounded `random`, `time.sleep`, or unmocked network calls.\n"
        "- The `acceptance:` field in the task is the exact criterion used to pass the task.\n",
        "\n---\n",
        "## Scope rules\n",
        "- Implement **only** what the current task specifies.\n"
        "- **Do NOT** modify files outside the task's `outputs:` list unless the description\n"
        "  explicitly requires it.\n"
        "- **Do NOT** update shared barrel / index files unless they appear in `outputs:`.\n"
        "- **CRITICAL for parallel builds:** multiple agents may edit the workspace\n"
        "  simultaneously. Never touch files not in your own `outputs:`.\n"
        "- Do not modify already-completed task files unless a dependency is genuinely broken.\n"
        "- Do not run `git push`, `git merge`, `git tag`, or `git commit` — the runner owns git.\n"
        "- Do not add features not listed in `outputs:` or the task body.\n",
    ]

    out = "\n".join(out_lines)
    agents_path = project_dir / "AGENTS.md"
    agents_path.write_text(out, encoding="utf-8")
    _console.print(
        f"[green]✔ AGENTS.md[/] generated → [dim]{agents_path.relative_to(project_dir.parent)}[/]"
    )


# ── Project listing / status ───────────────────────────────────────────────────


def list_projects() -> list[Path]:
    """Return sorted project directories under PROJECTS_ROOT that contain a ROADMAP.json."""
    if not PROJECTS_ROOT.exists():
        return []
    return sorted(
        p
        for p in PROJECTS_ROOT.iterdir()
        if p.is_dir() and (p / ROADMAP_FILENAME).exists()
    )


def _project_status(proj: Path) -> tuple[str, str]:
    """Return ``(badge, detail)`` describing the project's completion status."""
    # Import here to avoid a circular dep: roadmap imports workspace.
    from runner.roadmap import get_tasks  # noqa: PLC0415

    all_tasks = get_tasks(proj)
    total = len(all_tasks)
    state = _raw_state(proj)
    done_set = _completed_tasks(state)
    done = len(done_set)
    interrupted = state.get("current_task") is not None

    if total == 0:
        return "no tasks", "ROADMAP has no tasks yet"
    if done == total:
        return "complete", f"{done} / {total} tasks"
    if interrupted:
        current = state["current_task"]
        try:
            idx = all_tasks.index(current) + 1
            interrupted_label = f"interrupted at task {idx}"
        except ValueError:
            interrupted_label = "interrupted"
        return "interrupted", f"{done} / {total} tasks · {interrupted_label}"
    if done == 0:
        return "not started", f"0 / {total} tasks"
    remaining = total - done
    return "in progress", f"{done} / {total} tasks · {remaining} remaining"
