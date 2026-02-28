"""review.py — Human-in-the-loop review mode: pause after build, show diff, ask approval."""

import subprocess
from pathlib import Path

import questionary

from runner.config import _console
from runner.roadmap import _load_roadmap


def is_review_enabled(task: str | None, project_dir: Path) -> bool:
    """Return True if human review is required for this task.

    Checks task-level ``"review": true`` first, then project-level ``"review": true``.
    """
    roadmap = _load_roadmap(project_dir)

    # Project-wide flag.
    project_review = roadmap.get("review", False) is True

    if task is None:
        return project_review

    # Task-level override.
    for t in roadmap.get("tasks", []):
        heading = f"## {t['id']:03d} - {t['title']}"
        if heading == task:
            task_review = t.get("review")
            if task_review is not None:
                return task_review is True
            break

    return project_review


def show_diff_and_ask(project_dir: Path) -> str:
    """Show the current git diff (or file changes) and ask user to approve/reject/edit.

    Returns:
        ``'approve'``, ``'reject'``, or ``'edit'``.
    """
    _console.print("\n[bold yellow]── Human Review ──[/]")

    # Try git diff first (works for git-managed projects).
    diff = _get_git_diff(project_dir)
    if diff:
        _console.print("[dim]Changes since last commit:[/]\n")
        _print_coloured_diff(diff)
    else:
        _console.print("[dim]No git diff available (project may not use git).[/]")
        _show_recent_changes(project_dir)

    # Ask user.
    choice = questionary.select(
        "Review decision:",
        choices=[
            questionary.Choice(title="✔ Approve — continue to commit", value="approve"),
            questionary.Choice(
                title="✗ Reject  — discard changes and retry", value="reject"
            ),
            questionary.Choice(
                title="✎ Edit    — open a shell to make manual edits, then re-review",
                value="edit",
            ),
        ],
        use_shortcuts=False,
    ).ask()

    if choice is None:
        return "reject"

    if choice == "edit":
        _console.print(
            "[yellow]Opening a shell in the project directory. Type 'exit' when done.[/]"
        )
        _console.print(f"[dim]  cd {project_dir}[/]")
        import platform  # noqa: PLC0415

        shell = "powershell" if platform.system() == "Windows" else "bash"
        subprocess.run(shell, cwd=str(project_dir))
        # Re-show diff and re-ask after editing.
        return show_diff_and_ask(project_dir)

    return choice


def _get_git_diff(project_dir: Path) -> str:
    """Return colourless git diff output, or empty string if git unavailable."""
    result = subprocess.run(
        f'git -C "{project_dir}" diff --stat',
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stat = result.stdout.strip()

    result2 = subprocess.run(
        f'git -C "{project_dir}" diff',
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    full_diff = result2.stdout.strip()

    # Also include untracked files.
    result3 = subprocess.run(
        f'git -C "{project_dir}" status --short',
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    status = result3.stdout.strip()

    parts = []
    if stat:
        parts.append(f"[Diff stat]\n{stat}")
    if status:
        parts.append(f"\n[Status]\n{status}")
    if full_diff:
        # Truncate very large diffs.
        if len(full_diff) > 8000:
            full_diff = (
                full_diff[:8000] + "\n... (truncated, full diff available via git)"
            )
        parts.append(f"\n[Full diff]\n{full_diff}")
    return "\n".join(parts)


def _print_coloured_diff(diff: str) -> None:
    """Print diff lines with basic +/- colouring."""
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            _console.print(f"[green]{line}[/]")
        elif line.startswith("-") and not line.startswith("---"):
            _console.print(f"[red]{line}[/]")
        elif line.startswith("@@"):
            _console.print(f"[cyan]{line}[/]")
        else:
            _console.print(f"[dim]{line}[/]")


def _show_recent_changes(project_dir: Path) -> None:
    """Fallback: list recently modified files when git is not available."""
    import time  # noqa: PLC0415

    _console.print("[dim]Recently modified files:[/]")
    now = time.time()
    recent: list[tuple[float, Path]] = []
    skip_dirs = {"__pycache__", ".git", "node_modules", ".pytest_cache", "logs"}
    for p in project_dir.rglob("*"):
        if any(part in skip_dirs for part in p.parts):
            continue
        if p.is_file():
            mtime = p.stat().st_mtime
            if now - mtime < 600:  # Modified in the last 10 minutes.
                recent.append((mtime, p))
    recent.sort(key=lambda x: x[0], reverse=True)
    for _, p in recent[:20]:
        _console.print(f"  [dim]{p.relative_to(project_dir)}[/]")
    if not recent:
        _console.print("  [dim](no recent changes detected)[/]")


def discard_changes(project_dir: Path) -> None:
    """Revert all uncommitted changes (git reset --hard + clean)."""
    result = subprocess.run(
        f'git -C "{project_dir}" rev-parse --git-dir',
        shell=True,
        capture_output=True,
    )
    if result.returncode == 0:
        subprocess.run(
            f'git -C "{project_dir}" checkout -- .',
            shell=True,
            capture_output=True,
        )
        subprocess.run(
            f'git -C "{project_dir}" clean -fd',
            shell=True,
            capture_output=True,
        )
        _console.print("[yellow]Changes discarded (git reset).[/]")
    else:
        _console.print("[yellow]Cannot auto-discard: project is not a git repo.[/]")
