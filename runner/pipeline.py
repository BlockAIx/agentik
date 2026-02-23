"""pipeline.py — Task pipeline orchestration and main entry point."""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from runner.config import (
    MAX_ATTEMPTS,
    MAX_PARALLEL_AGENTS,
    ROADMAP_FILENAME,
    _console,
    set_verbose,
)
from runner.opencode import (
    check_models,
    check_monthly_budget,
    run_opencode_build,
    run_opencode_document,
    run_opencode_milestone,
    run_opencode_static_fix,
    select_project,
)
from runner.roadmap import (
    get_ready_tasks,
    get_task_body,
    get_task_ecosystem,
    get_task_outputs,
    get_task_version,
    get_tasks,
    is_milestone_task,
    parse_task_graph,
    run_static_checks,
    run_tests,
)
from runner.state import (
    _format_tokens,
    load_project_budget,
    load_runner_state,
    mark_done,
    save_runner_state,
    task_done,
)
from runner.workspace import (
    commit_and_merge,
    ensure_workspace_dirs,
    generate_project_agents_md,
    install_project_dependencies,
    scaffold_ecosystem_configs,
    tag_milestone,
    try_deploy_hook,
)

# ── Attempt pipeline ───────────────────────────────────────────────────────────


def run_attempt(
    task: str, attempt: int, fix_logs: str | None, project_dir: Path
) -> tuple[bool, str | None]:
    """Run one build → test cycle for *task*.

    Args:
        task:        ROADMAP heading.
        attempt:     Zero-based attempt index.
        fix_logs:    Previous test output, or None on first attempt.
        project_dir: Project directory path.

    Returns:
        ``(True, None)`` on success; ``(False, test_output)`` on failure.
    """
    phase_label = "Build" if fix_logs is None else "Fix"
    _console.print(
        f"\n[bold][1/5] {phase_label}[/]  [dim](attempt {attempt + 1}/{MAX_ATTEMPTS})[/]"
    )

    # On the first attempt, scaffold any ecosystem config files this task needs.
    if fix_logs is None:
        task_eco = get_task_ecosystem(task, project_dir)
        scaffold_ecosystem_configs(project_dir, task_eco)

    run_opencode_build(task, project_dir, fix_logs=fix_logs, attempt=attempt)

    _console.print("[dim][deps] Syncing project dependencies...[/]")
    install_project_dependencies(project_dir)

    # Re-run scaffold after build — the agent may have created config files
    # (e.g. vite.config.ts) that need patching (host/port binding, tsconfig
    # test types).  scaffold_ecosystem_configs is idempotent.
    task_eco = get_task_ecosystem(task, project_dir)
    scaffold_ecosystem_configs(project_dir, task_eco)

    _console.print("\n[bold][2/5] Test[/]")
    passed, output = run_tests(project_dir)
    return passed, (None if passed else output)


_STATIC_FIX_MAX_ATTEMPTS = 2


def finalise_task(
    task: str, project_dir: Path, task_outputs: list[str] | None = None
) -> None:
    """Static-check, document, commit, merge, and tag a successfully tested task."""
    _console.print("\n[bold][3/5] Static checks[/]")
    for _attempt in range(_STATIC_FIX_MAX_ATTEMPTS):
        ok, check_output = run_static_checks(project_dir)
        if ok:
            _console.print("[green]Static checks passed.[/]")
            break
        _console.print(
            f"[yellow]Static analysis issues found (attempt {_attempt + 1}/{_STATIC_FIX_MAX_ATTEMPTS}).[/]"
        )
        run_opencode_static_fix(task, project_dir, check_output)
    else:
        _console.print(
            "[yellow]⚠ Static analysis still failing after max attempts — proceeding.[/]"
        )

    _console.print("\n[bold][4/5] Document[/]")
    run_opencode_document(task, project_dir)

    _console.print("\n[bold][5/5] Commit & merge[/]")
    mark_done(task, project_dir)
    commit_and_merge(task, project_dir, task_outputs=task_outputs)
    try_deploy_hook(task, project_dir)
    _console.print(f"\n[green bold]✔ Completed:[/] {task}")


def _validate_roadmap(project_dir: Path) -> None:
    """Run ``helpers/check_roadmap`` and abort (exit 1) on structural errors."""
    from helpers.check_roadmap import run_checks  # noqa: PLC0415

    _console.print()
    _console.rule("[bold]ROADMAP Validation[/]", style="dim")
    rc = run_checks(project_dir / ROADMAP_FILENAME)
    if rc != 0:
        _console.print(
            "\n[red bold]ROADMAP has structural errors. "
            "Fix them before running the pipeline.[/]"
        )
        sys.exit(1)
    _console.print()


def process_task(
    task: str,
    project_dir: Path,
    resume_attempt: int = 0,
    resume_fix_logs: str | None = None,
) -> None:
    """Drive a single ROADMAP task through build → test → fix → finalise.

    Args:
        task:              ROADMAP heading.
        project_dir:       Project directory path.
        resume_attempt:    Attempt to start from (non-zero on resume).
        resume_fix_logs:   Saved fix logs from last failure, or None.
    """
    _console.print()
    resume_note = (
        f"[dim] — resuming from attempt {resume_attempt + 1}[/]"
        if resume_attempt > 0
        else ""
    )
    _console.rule(f"[bold cyan]{task}[/]{resume_note}", style="cyan")

    check_monthly_budget(project_dir=project_dir)

    from runner.workspace import ensure_feature_branch  # noqa: PLC0415

    ensure_feature_branch(task, project_dir)

    fix_logs: str | None = resume_fix_logs

    for attempt in range(resume_attempt, MAX_ATTEMPTS):
        save_runner_state(project_dir, task, attempt, fix_logs)

        passed, fix_logs = run_attempt(task, attempt, fix_logs, project_dir)

        if passed:
            finalise_task(task, project_dir)
            return

        _console.print(f"  [yellow]Tests failed on attempt {attempt + 1}.[/]")
        if attempt == MAX_ATTEMPTS - 1:
            _console.print("[red]Max attempts reached. Stopping.[/]")
            sys.exit(1)


# ── Milestone pipeline ─────────────────────────────────────────────────────────


def process_milestone(task: str, project_dir: Path) -> None:
    """Process an ``agent: milestone`` task — review, merge to main, and tag.

    Milestone tasks are barrier points: they never run in parallel.  The
    milestone agent reviews the project state (read-only), then the runner
    merges develop into main and creates a semver tag.
    """
    _console.print()
    _console.rule(f"[bold magenta]{task}[/]  [dim](milestone)[/]", style="magenta")

    version = get_task_version(task, project_dir)
    if not version:
        # Derive a fallback version from the task number.
        import re  # noqa: PLC0415

        m = re.match(r"^## (\d{3}) - ", task)
        version = f"0.0.{int(m.group(1))}" if m else "0.0.0"

    check_monthly_budget(project_dir=project_dir)
    _console.print(f"\n[bold][1/2] Milestone review[/]  [dim](v{version})[/]")
    run_opencode_milestone(task, version, project_dir)

    _console.print(f"\n[bold][2/2] Tag & merge[/]")
    tag_milestone(version, project_dir)
    mark_done(task, project_dir)
    _console.print(f"\n[green bold]✔ Milestone:[/] {task} → v{version}")


# ── Parallel batch pipeline ───────────────────────────────────────────────────


def process_parallel_batch(batch: list[str], project_dir: Path) -> None:
    """Build *batch* tasks in parallel, then test/static/document once and commit per-task."""
    from runner.workspace import ensure_feature_branch  # noqa: PLC0415

    _console.print()
    _console.rule("[bold magenta]Parallel Build Batch[/]", style="magenta")
    _console.print(f"[dim]Building {len(batch)} independent tasks in parallel[/]")
    for t in batch:
        _console.print(f"  [dim]→ {t}[/]")

    check_monthly_budget(project_dir=project_dir)

    # Pre-scaffold ecosystem configs for all tasks in the batch.
    for task in batch:
        eco = get_task_ecosystem(task, project_dir)
        scaffold_ecosystem_configs(project_dir, eco)

    # ── 1/4 Build (parallel) ──────────────────────────────────────────────
    _console.print(f"\n[bold][1/4] Build[/]  [dim](parallel, {len(batch)} agents)[/]")

    def _build_one(task: str) -> str:
        run_opencode_build(
            task,
            project_dir,
            fix_logs=None,
            attempt=0,
            capture=True,
            parallel_batch=batch,
        )
        return task

    spinner_label = f"[dim]{'build':<12}[/] {len(batch)} tasks in parallel"
    with _console.status(spinner_label, spinner="dots", spinner_style="cyan"):
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            futures = {executor.submit(_build_one, t): t for t in batch}
            results: list[tuple[str, Exception | None]] = []
            for future in as_completed(futures):
                task = futures[future]
                try:
                    future.result()
                    results.append((task, None))
                except Exception as exc:
                    results.append((task, exc))
    for task, exc in results:
        if exc is None:
            _console.print(f"  [green]✓ Built:[/] {task}")
        else:
            _console.print(f"  [red]✗ Build failed:[/] {task}: {exc}")
    for task, exc in results:
        if exc is not None:
            raise exc
    _console.print(f"[dim]  All agent output in: {project_dir.name}/logs/[/]")

    # Sync dependencies once after all builds.
    _console.print("[dim][deps] Syncing project dependencies...[/]")
    install_project_dependencies(project_dir)

    # ── 2/4 Test (once for the whole batch) ───────────────────────────────
    _console.print("\n[bold][2/4] Test[/]  [dim](batch)[/]")
    passed, output = run_tests(project_dir)

    if not passed:
        # Fix loop — use first task as context; the agent sees all code + test output.
        fix_logs: str | None = output
        for attempt in range(1, MAX_ATTEMPTS):
            _console.print(
                f"\n[bold][2/4] Fix[/]  [dim](attempt {attempt + 1}/{MAX_ATTEMPTS})[/]"
            )
            save_runner_state(project_dir, batch[0], attempt, fix_logs)
            run_opencode_build(
                batch[0],
                project_dir,
                fix_logs=fix_logs,
                attempt=attempt,
                force_new_session=True,
            )
            install_project_dependencies(project_dir)

            _console.print("\n[bold][2/4] Re-test[/]")
            passed, output = run_tests(project_dir)
            if passed:
                break
            fix_logs = output
        else:
            _console.print("[red]Max fix attempts reached for batch. Stopping.[/]")
            sys.exit(1)

    # ── 3/4 Static checks (once for the whole batch) ─────────────────────
    _console.print("\n[bold][3/4] Static checks[/]  [dim](batch)[/]")
    for _attempt in range(_STATIC_FIX_MAX_ATTEMPTS):
        ok, check_output = run_static_checks(project_dir)
        if ok:
            _console.print("[green]Static checks passed.[/]")
            break
        _console.print(
            f"[yellow]Static analysis issues found (attempt {_attempt + 1}/{_STATIC_FIX_MAX_ATTEMPTS}).[/]"
        )
        run_opencode_static_fix(batch[0], project_dir, check_output)
    else:
        _console.print(
            "[yellow]⚠ Static analysis still failing after max attempts — proceeding.[/]"
        )

    # ── 4/4 Document (once) + Commit (per-task for git attribution) ──────
    _console.print("\n[bold][4/4] Document & commit[/]  [dim](batch)[/]")
    run_opencode_document(batch[0], project_dir)

    for idx, task in enumerate(batch):
        is_last = idx == len(batch) - 1
        ensure_feature_branch(task, project_dir)

        outputs = get_task_outputs(task, project_dir)
        # Last task uses `git add .` to catch any files not in any outputs list.
        selective = outputs if outputs and not is_last else None

        mark_done(task, project_dir)
        commit_and_merge(task, project_dir, task_outputs=selective)
        try_deploy_hook(task, project_dir)
        _console.print(f"  [green]✔ Committed:[/] {task}")


# ── Entry point ────────────────────────────────────────────────────────────────


def main() -> None:
    """Select a project and mode (build or graph), then run accordingly."""
    import questionary  # noqa: PLC0415

    check_models()

    project_dir = select_project()
    _console.print(
        f"\n[bold]Project:[/] [cyan]{project_dir.name}[/]  [dim]({project_dir})[/]"
    )

    proj_data = load_project_budget(project_dir)
    proj_tokens = proj_data.get("total_tokens", 0)
    proj_calls = proj_data.get("total_calls", len(proj_data["sessions"]))
    if proj_calls > 0:
        _console.print(
            f"  [dim]Accumulated usage: {_format_tokens(proj_tokens)} tokens over {proj_calls} call(s)[/]"
        )

    ensure_workspace_dirs(project_dir)
    _validate_roadmap(project_dir)

    # ── Mode selection ─────────────────────────────────────────────────────
    mode = questionary.select(
        "What would you like to do?",
        choices=[
            questionary.Choice(
                title="▶  Run pipeline          (compact logs — errors shown inline)",
                value="build:compact",
            ),
            questionary.Choice(
                title="▶  Run pipeline (verbose) (stream full agent output)",
                value="build:verbose",
            ),
            questionary.Choice(title="🔍 Show dependency graph", value="graph"),
            questionary.Choice(
                title=(
                    "🔄 Regenerate project AGENTS.md"
                    if (project_dir / "AGENTS.md").exists()
                    else "📝 Generate project AGENTS.md"
                ),
                value="agents",
            ),
        ],
        use_shortcuts=False,
    ).ask()

    if mode is None:
        sys.exit(0)

    if mode == "graph":
        from runner.roadmap import print_dependency_graph  # noqa: PLC0415

        print_dependency_graph(project_dir)
        return

    if mode == "agents":
        generate_project_agents_md(project_dir)
        return

    # Derive verbose flag from the selected mode.
    verbose = mode == "build:verbose"
    set_verbose(verbose)
    if verbose:
        _console.print("[dim]Log mode: verbose (full agent output)[/]")
    else:
        _console.print(
            "[dim]Log mode: compact (errors shown inline — full output in logs/)[/]"
        )

    # ── Build mode ─────────────────────────────────────────────────────────
    all_tasks = get_tasks(project_dir)
    graph = parse_task_graph(project_dir)
    first_task = all_tasks[0] if all_tasks else None

    # Print completed tasks.
    for task in all_tasks:
        if task_done(task, project_dir):
            _console.print(f"[dim]✓ Skipping (done):[/] {task}")

    # Handle resume — process the interrupted task sequentially, then continue
    # with graph-based scheduling.
    saved = load_runner_state(project_dir)
    if saved and saved["current_task"]:
        resume_task = saved["current_task"]
        if not task_done(resume_task, project_dir):
            _console.print(
                f"[yellow]▶ Resuming[/] '{resume_task}' from attempt {saved['attempt'] + 1}"
            )
            process_task(
                resume_task,
                project_dir,
                resume_attempt=saved["attempt"],
                resume_fix_logs=saved.get("fix_logs"),
            )

    # ── Graph-based scheduling loop ────────────────────────────────────────
    while True:
        done_set = {t for t in all_tasks if task_done(t, project_dir)}
        ready = get_ready_tasks(all_tasks, graph, done_set, project_dir)

        if not ready:
            break

        # Milestone tasks are barriers — process alone, never in parallel.
        if is_milestone_task(ready[0], project_dir):
            process_milestone(ready[0], project_dir)
            continue

        # The first task (project setup) always runs alone.
        if first_task and first_task in ready:
            process_task(first_task, project_dir)
            continue

        # Filter out any milestone tasks from parallel batches (they wait).
        buildable = [t for t in ready if not is_milestone_task(t, project_dir)]
        if not buildable:
            # Only milestones left but their deps aren't met yet — should not
            # happen with a valid graph, but guard against it.
            break

        # Single task or parallelism disabled → sequential.
        if len(buildable) == 1 or MAX_PARALLEL_AGENTS <= 1:
            process_task(buildable[0], project_dir)
            continue

        # Multiple independent tasks → parallel build.
        batch = buildable[:MAX_PARALLEL_AGENTS]
        process_parallel_batch(batch, project_dir)
