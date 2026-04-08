"""context_store.py — Shared context store for inter-task knowledge transfer.

Each completed task can leave notes (architecture decisions, patterns, gotchas)
that are automatically injected into the prompts of dependent tasks.

Storage: ``projects/<name>/.task_notes/<task_slug>.md``
"""

import re
from pathlib import Path

_NOTES_DIR = ".task_notes"
_MAX_NOTES_PER_DEP = 2000  # chars per dependency note


def _slug(task: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", task.lower().lstrip("#").strip()).strip("-")[:50]


def _notes_dir(project_dir: Path) -> Path:
    return project_dir / _NOTES_DIR


def save_task_notes(task: str, project_dir: Path, notes: str) -> None:
    """Persist notes left by *task* for downstream dependents."""
    d = _notes_dir(project_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{_slug(task)}.md").write_text(notes.strip(), encoding="utf-8")


def load_task_notes(task: str, project_dir: Path) -> str | None:
    """Return the notes for *task*, or None if no notes exist."""
    path = _notes_dir(project_dir) / f"{_slug(task)}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def collect_dependency_notes(task: str, project_dir: Path) -> str:
    """Gather notes from all direct dependencies of *task*.

    Returns a markdown block ready for prompt injection, or empty string.
    """
    from runner.roadmap import parse_task_graph  # noqa: PLC0415

    graph = parse_task_graph(project_dir)
    deps = graph.get(task, [])
    if not deps:
        return ""

    parts: list[str] = []
    for dep in deps:
        notes = load_task_notes(dep, project_dir)
        if notes:
            truncated = notes[:_MAX_NOTES_PER_DEP]
            parts.append(f"### From {dep}\n{truncated}")

    if not parts:
        return ""

    return "\n## Notes from dependency tasks\n\n" + "\n\n".join(parts) + "\n"
