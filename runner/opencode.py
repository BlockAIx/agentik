"""opencode.py — All opencode invocations and budget guards."""

import datetime
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


class ModelConfigError(Exception):
    """Raised when the agent fails due to a model configuration problem.

    These errors are non-retriable: retrying with the same model config will
    always fail.  The pipeline should stop immediately and surface the error.
    """


import questionary

from runner.config import (
    _LOG_TAIL_LINES,
    _PRICES,
    MONTHLY_LIMIT_TOKENS,
    OPENCODE_CMD,
    PROJECTS_ROOT,
    ROADMAP_FILENAME,
    _console,
    is_verbose,
    rbox,
    render_prompt,
)
from runner.roadmap import (
    _detect_test_command,
    _ecosystem_prompt_blocks,
    get_task_body,
    get_task_context_files,
    get_task_ecosystem,
    get_tasks,
)
from runner.state import (
    _format_duration,
    _format_tokens,
    _load_budget_state,
    _raw_state,
    _save_budget_state,
    _tokens_to_usd,
    get_monthly_calls,
    get_token_stats,
    load_project_budget,
    record_project_spend,
)
from runner.workspace import (
    _pkg_name,
    _project_status,
    get_roadmap_project_context,
    list_projects,
    src_dir,
    tests_dir,
)

# ── Subprocess tee helper ──────────────────────────────────────────────────────
# Matches all ANSI/VT100 escape sequences (CSI, OSC, and standalone ESC codes).
_ANSI_RE = re.compile(
    r"\x1b"
    r"(?:"
    r"\[[0-9;?]*[A-Za-z]"  # CSI sequences: ESC [ ... <letter>
    r"|\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC sequences: ESC ] ... BEL/ST
    r"|[^\[\]]"
    r")"
)


def _strip_ansi(text: str) -> str:
    """Remove all ANSI escape codes from *text*."""
    return _ANSI_RE.sub("", text)


def _run_with_log(cmd: str, log_path: Path, *, echo: bool) -> int:
    """Run *cmd* in a shell, write all output to *log_path*, and optionally echo to stdout.

    Uses ``stdout=PIPE`` + ``stderr=STDOUT`` to unify streams.  In sequential
    mode (``echo=True``) each line is printed in real time so the user still
    sees live progress.  In parallel mode (``echo=False``) output is captured
    silently; the caller is responsible for printing a summary.

    Args:
        cmd:      Shell command to execute.
        log_path: Destination log file (parent dirs created automatically).
        echo:     Stream each output line to stdout as it arrives.

    Returns:
        Process return code.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log_fh:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            log_fh.write(_strip_ansi(line))
            log_fh.flush()
            if echo:
                print(line, end="", flush=True)
        proc.wait()
    return proc.returncode


def _tail_log(log_path: Path) -> None:
    """Print the last ``_LOG_TAIL_LINES`` lines of *log_path* inside a red Rich panel.

    Used in compact mode when an agent exits with a non-zero return code so the
    user can see the error without opening the file manually.
    """
    from rich.panel import Panel  # noqa: PLC0415

    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        shown = lines[-_LOG_TAIL_LINES:] if len(lines) > _LOG_TAIL_LINES else lines
        tail_text = "\n".join(shown)
        _console.print(
            Panel(
                tail_text,
                title=f"[red bold]agent output — last {len(shown)} lines[/]  [dim]{log_path.name}[/]",
                border_style="red",
                expand=True,
            )
        )
    except Exception as exc:  # noqa: BLE001
        _console.print(f"[dim](Could not read log {log_path.name}: {exc})[/]")


# Patterns that indicate the model itself is misconfigured — retrying won't help.
_MODEL_ERROR_PATTERNS = [
    re.compile(r"ProviderModelNotFoundError", re.IGNORECASE),
    re.compile(r"model[_ ]not[_ ]found", re.IGNORECASE),
    re.compile(r"model .+ (is not available|does not exist)", re.IGNORECASE),
    re.compile(r"unknown model", re.IGNORECASE),
    re.compile(r"invalid model", re.IGNORECASE),
    re.compile(r"no such model", re.IGNORECASE),
    re.compile(r"model .+ not supported", re.IGNORECASE),
    re.compile(r"Unauthorized|invalid.api.key|authentication.failed", re.IGNORECASE),
    re.compile(r"PROVIDER_NOT_CONFIGURED", re.IGNORECASE),
]


def _check_model_error(log_path: Path) -> None:
    """Scan the last lines of a failed agent log for model config errors.

    Raises ``ModelConfigError`` when the failure is clearly due to a
    misconfigured model (wrong name, missing provider, auth issues).
    These are non-retriable — the pipeline should stop immediately.
    """
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return

    # Only scan the tail to avoid false positives in large logs.
    tail = "\n".join(text.splitlines()[-80:])
    for pattern in _MODEL_ERROR_PATTERNS:
        match = pattern.search(tail)
        if match:
            # Extract a one-line summary from the matched region.
            line = next(
                (l.strip() for l in tail.splitlines() if pattern.search(l)),
                match.group(),
            )
            raise ModelConfigError(f"Model configuration error (non-retriable): {line}")


# ── Budget guard ───────────────────────────────────────────────────────────────


def check_monthly_budget(project_dir: Path | None = None) -> None:
    """Print a status block and abort (exit 2) if the monthly token limit is exceeded."""
    from datetime import date  # noqa: PLC0415

    from rich.table import Table  # noqa: PLC0415

    # Price estimates are only meaningful for direct-API providers (Anthropic,
    # OpenAI, etc.).  GitHub Copilot is subscription-based so we show tokens only.
    show_price = not _is_copilot_only()

    state = _load_budget_state()
    today = date.today()
    month_key = f"{today.year}-{today.month:02d}"
    stats = get_token_stats()

    if state.get("month") != month_key or "baseline_stats" not in state:
        state = {"month": month_key, "baseline_stats": stats}
        _save_budget_state(state)

    baseline = state.get("baseline_stats", {k: 0 for k in stats})
    spent_stats = {k: max(0, stats[k] - baseline.get(k, 0)) for k in stats}
    spent_tokens = spent_stats["total"]
    spent_usd = _tokens_to_usd(spent_stats) if show_price else 0.0
    remaining_tokens = max(0, MONTHLY_LIMIT_TOKENS - spent_tokens)
    pct_used = (
        min(100.0, spent_tokens / MONTHLY_LIMIT_TOKENS * 100)
        if MONTHLY_LIMIT_TOKENS > 0
        else 0.0
    )

    bar_filled = int(pct_used / 100 * 20)
    bar = "[green]" + "█" * bar_filled + "[/][dim]" + "░" * (20 - bar_filled) + "[/]"

    t = Table(
        box=rbox.ROUNDED,
        show_header=False,
        title="[bold]Run Status[/]",
        title_style="",
        border_style="bright_black",
    )
    t.add_column("Label", style="cyan", no_wrap=True)
    t.add_column("Detail", no_wrap=False)

    _monthly_extra = f" · ~${spent_usd:.4f} est." if show_price else ""
    monthly_calls = get_monthly_calls()
    monthly_info = (
        f"{bar}  [bold]{_format_tokens(spent_tokens)}[/] / {_format_tokens(MONTHLY_LIMIT_TOKENS)} tokens"
        f"  [dim]({_format_tokens(remaining_tokens)} left · {monthly_calls} call(s){_monthly_extra})[/]"
    )
    t.add_row("Monthly", monthly_info)

    if project_dir is not None:
        proj_data = load_project_budget(project_dir)
        proj_tokens = proj_data.get("total_tokens", 0)
        proj_calls = proj_data.get("total_calls", len(proj_data["sessions"]))
        if show_price:
            proj_usd = (
                sum(
                    s["tokens"] * (sum(_PRICES[k] for k in _PRICES) / len(_PRICES))
                    for s in proj_data["sessions"]
                    if "tokens" in s
                )
                / 1_000_000
            )
            _proj_cost = f" · ~${proj_usd:.4f} est."
        else:
            _proj_cost = ""
        proj_info = (
            f"[bold]{project_dir.name}[/]  —  "
            f"[bold]{_format_tokens(proj_tokens)}[/] tokens · {proj_calls} call(s){_proj_cost}"
        )
        t.add_row("Project", proj_info)

        all_tasks = get_tasks(project_dir)
        task_total = len(all_tasks)
        raw_st = _raw_state(project_dir)
        task_done_count = len(raw_st["completed"])
        task_remaining = task_total - task_done_count
        if task_total > 0:
            pct_prog = task_done_count / task_total * 100
            prog_filled = int(pct_prog / 100 * 20)
            prog_bar = (
                "[green]"
                + "█" * prog_filled
                + "[/][dim]"
                + "░" * (20 - prog_filled)
                + "[/]"
            )
            t.add_row(
                "Progress",
                f"{prog_bar}  [bold]{task_done_count}[/] / {task_total} tasks ({pct_prog:.0f}%)",
            )
        else:
            t.add_row("Progress", "[dim]No tasks found in ROADMAP[/]")

        durations = raw_st.get("task_durations", [])
        if task_remaining == 0:
            t.add_row("ETA", "[green]✔ All tasks complete[/]")
        elif durations:
            avg_sec = sum(durations) / len(durations)
            eta_sec = avg_sec * task_remaining
            t.add_row(
                "ETA",
                f"~[bold]{_format_duration(eta_sec)}[/]  "
                f"[dim](avg {_format_duration(avg_sec)}/task · {task_remaining} remaining)[/]",
            )
        else:
            t.add_row(
                "ETA", f"[dim]No data yet — {task_remaining} task(s) remaining[/]"
            )

    _console.print(t)

    if spent_tokens >= MONTHLY_LIMIT_TOKENS:
        _cost_note = f" · ~${spent_usd:.4f} est." if show_price else ""
        _console.print(
            f"\n[red bold]✗ Monthly token budget exhausted[/] "
            f"({_format_tokens(spent_tokens)} / {_format_tokens(MONTHLY_LIMIT_TOKENS)} tokens{_cost_note})."
        )
        sys.exit(2)


# ── Project selection UI ───────────────────────────────────────────────────────


def select_project() -> Path:
    """Interactively prompt the user to select a project with arrow-key navigation."""
    projects = list_projects()
    if not projects:
        _console.print(f"[red]No projects found in {PROJECTS_ROOT}/.[/]")
        _console.print(
            f"Create a subdirectory there with a {ROADMAP_FILENAME} to get started."
        )
        sys.exit(1)

    _BADGE_ICON = {
        "complete": "✔",
        "in progress": "◑",
        "interrupted": "▶",
        "not started": "○",
        "no tasks": "?",
    }
    statuses = [_project_status(p) for p in projects]
    badge_w = max(len(b) for b, _ in statuses)
    name_w = max(len(p.name) for p in projects)

    choices = []
    for proj, (badge, detail) in zip(projects, statuses):
        icon = _BADGE_ICON.get(badge, " ")
        title = f"{badge:<{badge_w}}  {icon}  {proj.name:<{name_w}}   {detail}"
        choices.append(questionary.Choice(title=title, value=proj))

    selected = questionary.select(
        "Select project:",
        choices=choices,
        use_shortcuts=False,
    ).ask()

    if selected is None:
        sys.exit(0)
    return selected


# ── Core opencode invocation ───────────────────────────────────────────────────


def _invoke_opencode(
    prompt: str,
    *,
    agent: str,
    project_dir: Path,
    continue_session: bool,
    task: str | None = None,
    phase: str = "build",
    attempt: int = 0,
    capture: bool = False,
    parallel_batch: list[str] | None = None,
) -> int:
    """Invoke opencode with *prompt* as a temp file; return token delta.

    Args:
        capture: Force-suppress terminal echo and per-invocation prints.
                 Used for parallel builds; the batch spinner in pipeline.py
                 covers the UX while all agents run concurrently.
    """
    verbose = is_verbose() and not capture

    stats_before = get_token_stats()

    # ── Build a human-readable task label ────────────────────────────────
    m = re.match(r"^##\s*(\d+)\s*-\s*(.+)$", (task or "").strip())
    task_display = (
        f"{m.group(1)} · {m.group(2)[:55]}" if m else (task or "unknown")[:60]
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(prompt)
        tmpfile = f.name

    rc = 1  # default so it's defined after the try block
    try:
        dir_path = Path(project_dir).resolve().as_posix()
        tmpfile_posix = Path(tmpfile).resolve().as_posix()
        flags = f'--agent {agent} --dir "{dir_path}"' + (
            " --continue" if continue_session else ""
        )
        cmd = f'{OPENCODE_CMD} run "Execute the task in the attached file." {flags} -f "{tmpfile_posix}"'

        # ── Per-invocation log file (timestamp-first for natural sort order) ─
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        task_slug = re.sub(
            r"[^a-z0-9]+", "-", (task or "unknown").lower().lstrip("#").strip()
        ).strip("-")[:50]
        log_name = f"{timestamp}_{phase}_a{attempt}.log"
        log_path = project_dir / "logs" / task_slug / log_name
        log_rel = f"logs/{task_slug}/{log_name}"

        # ── Pre-run status line ───────────────────────────────────────────
        if verbose:
            # Verbose: show log destination; streaming output follows immediately.
            _console.print(f"[dim]→ log: {log_rel}[/]")
            rc = _run_with_log(cmd, log_path, echo=True)
        elif capture:
            # Parallel capture: output suppressed — batch-level spinner covers UX.
            rc = _run_with_log(cmd, log_path, echo=False)
        else:
            # Compact sequential: animated spinner while the agent runs.
            _console.print(f"  [dim]→ {log_rel}[/]")
            with _console.status(
                f"[dim]{phase:<12}[/] {task_display}",
                spinner="dots",
                spinner_style="cyan",
            ):
                rc = _run_with_log(cmd, log_path, echo=False)
    finally:
        Path(tmpfile).unlink(missing_ok=True)

    # ── Token accounting ──────────────────────────────────────────────────
    stats_after = get_token_stats()
    delta_tokens = max(0, stats_after["total"] - stats_before["total"])
    delta_stats = {k: max(0, stats_after[k] - stats_before[k]) for k in stats_after}
    delta_usd = _tokens_to_usd(delta_stats)

    proj_tokens = 0
    if task is not None:
        proj_tokens = record_project_spend(
            project_dir,
            task,
            phase,
            delta_tokens,
            attempt,
            parallel_batch=parallel_batch,
        )

    show_price = not _is_copilot_only()

    # ── Post-run summary ──────────────────────────────────────────────────
    if verbose:
        # Verbose: print the familiar token line, then an error note if needed.
        if delta_tokens > 0:
            _price_note = f" (~${delta_usd:.4f})" if show_price else ""
            _console.print(
                f"[dim]tokens:[/] [green]{_format_tokens(delta_tokens)}[/] this call{_price_note} · "
                f"[green]{_format_tokens(proj_tokens)}[/] project total · phase: [cyan]{phase}[/]"
            )
        if rc != 0:
            _console.print(
                f"[yellow]⚠ opencode exited with code {rc}[/] (phase: {phase}, log: {log_rel})"
            )
    else:
        # Compact: one summary line, error panel if needed.
        if delta_tokens > 0:
            _price_note = f"  (~${delta_usd:.4f})" if show_price else ""
            token_note = f"  [dim]+{_format_tokens(delta_tokens)}{_price_note}[/]"
        else:
            token_note = ""
        if rc == 0:
            _console.print(f"  [green]✓ {phase}[/]{token_note}")
        else:
            _console.print(f"  [red]✗ {phase}  (exit {rc})[/]  [dim]{log_rel}[/]")
            _tail_log(log_path)

    # ── Detect non-retriable model errors ─────────────────────────────────
    # Always check — some providers exit 0 despite model-not-found errors.
    _check_model_error(log_path)

    return delta_tokens


# ── High-level opencode wrappers ───────────────────────────────────────────────


def run_opencode_build(
    task: str,
    project_dir: Path,
    fix_logs: str | None = None,
    attempt: int = 0,
    force_new_session: bool = False,
    capture: bool = False,
    parallel_batch: list[str] | None = None,
) -> int:
    """Invoke the build/fix agent for *task*; return token delta.

    Args:
        task:              ROADMAP heading.
        project_dir:       Project directory.
        fix_logs:          Previous test output (None = first attempt).
        attempt:           Zero-based attempt index.
        force_new_session: Start fresh even on fix (used after parallel builds).
        capture:           Suppress terminal echo; log to file only (parallel mode).
        parallel_batch:    All task headings in the parallel batch; recorded in
                           the budget session as ``parallel_with``.

    Returns:
        Token delta.
    """
    _src = src_dir(project_dir)
    _tests = tests_dir(project_dir)
    phase = "build" if fix_logs is None else "fix"
    task_spec = get_task_body(task, project_dir)
    task_eco = get_task_ecosystem(task, project_dir)
    _, test_label = _detect_test_command(project_dir, eco=task_eco)
    eco_blocks = _ecosystem_prompt_blocks(
        project_dir, _src, _tests, _pkg_name(project_dir), eco=task_eco
    )

    context_files = get_task_context_files(task, project_dir)
    context_files_block = ""
    if context_files:
        parts = ["\n## Context files (read-only reference)\n"]
        for rel, content in context_files.items():
            parts.append(f"### `{rel}`\n```\n{content}\n```\n")
        context_files_block = "\n".join(parts)

    preamble_text = get_roadmap_project_context(project_dir)
    project_context_block = (
        f"\n## Project context\n{preamble_text}\n" if preamble_text else ""
    )

    # Dockerfile rules — only injected when the project actually has a Dockerfile.
    has_dockerfile = (project_dir / "Dockerfile").exists()
    dockerfile_rules = (
        (
            "\n## Dockerfile rules\n"
            "- Prefer single-stage builds; multi-stage `COPY --from` silently produces empty layers"
            " if the source path does not exist in the builder stage — only copy paths you explicitly created.\n"
            "- Deno pattern: `FROM denoland/deno:x.y.z` → `COPY deno.json + src/` → `RUN deno cache src/main.ts`"
            ' → `COPY public/` → `CMD ["run","--allow-env","--allow-net","--allow-read","src/main.ts"]`.'
            " Add `--allow-read` whenever the app reads files at runtime.\n"
        )
        if has_dockerfile
        else ""
    )

    # Deploy rules — only injected when the project has deployment configured.
    from runner.roadmap import get_deploy_config  # noqa: PLC0415

    deploy_cfg = get_deploy_config(project_dir)
    has_deploy = deploy_cfg.get("enabled", False)
    deploy_rules = (
        (
            "\n## Deploy rules\n"
            "This project has deployment enabled. Deploy scripts are called automatically"
            ' after commits on tasks marked with `"deploy": true`.\n'
            "The deploy script receives environment variables prefixed with `DEPLOY_`"
            " (derived from the ROADMAP deploy block's `env` field).\n"
            "The deploy script must exit non-zero on failure so the runner surfaces errors.\n"
            "If the project exposes a health endpoint, the deploy script should poll it"
            " after deploy and exit non-zero if it never returns 2xx.\n"
        )
        if has_deploy
        else ""
    )

    if fix_logs is None:
        prompt = render_prompt(
            "build",
            TASK=task,
            LANG_LINE=eco_blocks["lang_line"],
            LOCATIONS=eco_blocks["locations"],
            IMPORT_RULES=eco_blocks["import_rules"],
            SRC=str(_src),
            TESTS=str(_tests),
            MANIFEST_TABLE=eco_blocks["manifest_table"],
            TASK_SPEC=task_spec,
            CONTEXT_FILES=context_files_block,
            PROJECT_CONTEXT=project_context_block,
            DOCKERFILE_RULES=dockerfile_rules,
            DEPLOY_RULES=deploy_rules,
        )
    else:
        truncated_logs = fix_logs[-3000:] if len(fix_logs) > 3000 else fix_logs
        prompt = render_prompt(
            "fix",
            TASK=task,
            TEST_LABEL=test_label,
            TRUNCATED_LOGS=truncated_logs,
        )

    effective_agent = "fix" if fix_logs is not None else "build"
    continue_session = (fix_logs is not None) and not force_new_session
    return _invoke_opencode(
        prompt,
        agent=effective_agent,
        project_dir=project_dir,
        continue_session=continue_session,
        task=task,
        phase=phase,
        attempt=attempt,
        capture=capture,
        parallel_batch=parallel_batch,
    )


def run_opencode_document(task: str, project_dir: Path) -> int:
    """Invoke the document agent to finalise docs (continues session); return token delta."""
    prompt = render_prompt("document", TASK=task)
    return _invoke_opencode(
        prompt,
        agent="document",
        project_dir=project_dir,
        continue_session=True,
        task=task,
        phase="document",
    )


def run_opencode_static_fix(task: str, project_dir: Path, check_output: str) -> int:
    """Ask the fix agent to repair static analysis failures (continues session); return token delta."""
    truncated = check_output[-3000:] if len(check_output) > 3000 else check_output
    prompt = render_prompt(
        "static_fix",
        TASK=task,
        TRUNCATED_LOGS=truncated,
    )
    return _invoke_opencode(
        prompt,
        agent="fix",
        project_dir=project_dir,
        continue_session=True,
        task=task,
        phase="static_fix",
    )


def run_opencode_milestone(task: str, version: str, project_dir: Path) -> int:
    """Invoke the milestone agent to review the project before tagging; return token delta.

    Args:
        task:        ROADMAP heading for the milestone task.
        version:     Semver string (e.g. ``"0.2.0"``).
        project_dir: Project directory path.

    Returns:
        Token delta.
    """
    _pkg = _pkg_name(project_dir)
    roadmap = (project_dir / ROADMAP_FILENAME).read_text(encoding="utf-8")
    task_spec = get_task_body(task, project_dir)

    file_listing: list[str] = []
    _SKIP_DIRS = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".venv",
        "dist",
        "build",
    }
    for path in sorted(project_dir.rglob("*")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            file_listing.append(f"  {path.relative_to(project_dir).as_posix()}")
    listing_text = "\n".join(file_listing) if file_listing else "  (empty)"

    prompt = render_prompt(
        "milestone",
        PROJECT_NAME=project_dir.name,
        PKG=_pkg,
        VERSION=version,
        LISTING_TEXT=listing_text,
        ROADMAP=roadmap,
        TASK=task,
        TASK_SPEC=task_spec,
    )
    return _invoke_opencode(
        prompt,
        agent="milestone",
        project_dir=project_dir,
        continue_session=False,
        task=task,
        phase="milestone",
    )


# ── Opencode config helpers ─────────────────────────────────────────────────────


def _strip_jsonc_comments(text: str) -> str:
    """Remove ``//`` line comments from JSONC text (string-aware)."""
    out: list[str] = []
    i = 0
    in_string = False
    while i < len(text):
        c = text[i]
        if in_string:
            if c == "\\":
                out.append(c)
                i += 1
                if i < len(text):
                    out.append(text[i])
            elif c == '"':
                in_string = False
                out.append(c)
            else:
                out.append(c)
        else:
            if c == '"':
                in_string = True
                out.append(c)
            elif c == "/" and i + 1 < len(text) and text[i + 1] == "/":
                while i < len(text) and text[i] != "\n":
                    i += 1
                continue
            else:
                out.append(c)
        i += 1
    return "".join(out)


def _load_opencode_config() -> dict:
    """Parse ``opencode.jsonc`` into a plain dict, tolerating ``//`` comments."""
    raw = Path("opencode.jsonc").read_text(encoding="utf-8")
    return json.loads(_strip_jsonc_comments(raw))


def _is_copilot_only() -> bool:
    """Return True if every configured model uses the ``github-copilot/`` provider.

    Used to suppress USD price estimates for subscription-based providers where
    per-token billing does not apply.
    """
    try:
        cfg = _load_opencode_config()
        models = [cfg.get("model", "")]
        models += [
            v.get("model", "")
            for v in cfg.get("agent", {}).values()
            if isinstance(v, dict)
        ]
        non_empty = [m for m in models if m]
        return bool(non_empty) and all(
            m.startswith("github-copilot/") for m in non_empty
        )
    except Exception:  # noqa: BLE001
        return False
