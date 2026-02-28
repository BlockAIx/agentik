"""rollback.py — Git rollback on task failure: reset feature branch and mark task failed."""

import subprocess
from pathlib import Path

from runner.config import _console


def rollback_feature_branch(task: str, project_dir: Path) -> bool:
    """Hard-reset the feature branch to the last clean state on failure.

    Returns True if rollback succeeded, False if git is not available or not managed.
    """
    from runner.roadmap import is_git_managed  # noqa: PLC0415

    if not is_git_managed(project_dir):
        _console.print("[dim][rollback] Git not managed — skipping rollback.[/]")
        return False

    _console.print("[yellow][rollback] Rolling back failed task changes...[/]")

    # Reset all changes on the current feature branch.
    result = subprocess.run(
        f'git -C "{project_dir}" reset --hard HEAD',
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        _console.print(f"[red][rollback] git reset --hard failed: {result.stderr}[/]")
        return False

    # Clean untracked files.
    subprocess.run(
        f'git -C "{project_dir}" clean -fd',
        shell=True,
        capture_output=True,
    )

    # Switch back to develop.
    subprocess.run(
        f'git -C "{project_dir}" checkout develop',
        shell=True,
        capture_output=True,
    )

    # Delete the failed feature branch.
    from runner.config import slugify  # noqa: PLC0415

    branch = f"feature/{slugify(task)}"
    subprocess.run(
        f'git -C "{project_dir}" branch -D {branch}',
        shell=True,
        capture_output=True,
    )
    _console.print(f"[yellow][rollback] Rolled back to develop, deleted {branch}.[/]")
    return True


def mark_task_failed(task: str, project_dir: Path, error_info: dict | None = None) -> None:
    """Mark a task as failed in runner state (not done) so next run can retry or skip."""
    from runner.state import _raw_state, _write_state  # noqa: PLC0415

    state = _raw_state(project_dir)
    state["current_task"] = None
    state["attempt"] = 0
    state["fix_logs"] = None
    state["task_started_at"] = None

    # Add to a separate 'failed' list.
    failed = state.get("failed", [])
    entry = {"task": task}
    if error_info:
        entry.update(error_info)
    failed.append(entry)
    state["failed"] = failed
    _write_state(project_dir, state)
