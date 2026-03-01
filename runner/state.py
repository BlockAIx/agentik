"""state.py — Runner state persistence, per-project budget tracking, and token stats."""

import json
import re
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from runner.config import (
    _BUDGET_STATE_FILE,
    _PRICES,
)

# ── Token / cost ───────────────────────────────────────────────────────────────


def _parse_tokens(value: str) -> float:
    """Parse opencode stats token strings (e.g. ``'128.7K'``, ``'1.2M'``) into a raw count."""
    v = value.strip()
    if v.endswith("M"):
        return float(v[:-1]) * 1_000_000
    if v.endswith("K"):
        return float(v[:-1]) * 1_000
    return float(v)


def get_token_stats() -> dict:
    """Return cumulative token counts from ``opencode stats``.

    Returns:
        Dict with keys ``input``, ``output``, ``cache_read``, ``cache_write``, ``total``.
    """
    from runner.config import OPENCODE_CMD  # noqa: PLC0415

    result = subprocess.run(
        f"{OPENCODE_CMD} stats",
        shell=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    out = result.stdout

    def _find(label: str) -> int:
        m = re.search(rf"{re.escape(label)}\s+([\d.]+[KM]?)\b", out)
        return int(_parse_tokens(m.group(1))) if m else 0

    stats = {
        "input": _find("Input"),
        "output": _find("Output"),
        "cache_read": _find("Cache Read"),
        "cache_write": _find("Cache Write"),
    }
    stats["total"] = (
        stats["input"] + stats["output"] + stats["cache_read"] + stats["cache_write"]
    )
    return stats


def _tokens_to_usd(stats: dict) -> float:
    """Estimate USD cost from a token-stats dict using the price table."""
    return round(
        (
            stats["input"] * _PRICES["input"]
            + stats["output"] * _PRICES["output"]
            + stats["cache_read"] * _PRICES["cache_read"]
            + stats["cache_write"] * _PRICES["cache_write"]
        )
        / 1_000_000,
        6,
    )


def _format_tokens(n: int) -> str:
    """Format a raw token count as a compact string (e.g. ``12.5K``, ``3.2M``)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _format_duration(seconds: float) -> str:
    """Format *seconds* as a compact string (e.g. ``2m 10s``, ``1h 2m``)."""
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        m, sec = divmod(s, 60)
        return f"{m}m {sec}s" if sec else f"{m}m"
    h, rem = divmod(s, 3600)
    m = rem // 60
    return f"{h}h {m}m" if m else f"{h}h"


# ── Monthly budget baseline ───────────────────────────────────────────────────


def _load_budget_state() -> dict:
    """Load the persisted monthly budget baseline from disk."""
    if _BUDGET_STATE_FILE.exists():
        return json.loads(_BUDGET_STATE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_budget_state(state: dict) -> None:
    """Persist the monthly budget baseline to disk."""
    _BUDGET_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _month_key() -> str:
    """Return a ``YYYY-MM`` key for the current month."""
    today = date.today()
    return f"{today.year}-{today.month:02d}"


def _increment_monthly_calls() -> None:
    """Bump the monthly call counter by one, resetting on a new month."""
    state = _load_budget_state()
    key = _month_key()
    if state.get("month") != key:
        state["monthly_calls"] = 1
    else:
        state["monthly_calls"] = state.get("monthly_calls", 0) + 1
    _save_budget_state(state)


def get_monthly_calls() -> int:
    """Return the number of API calls made this calendar month."""
    state = _load_budget_state()
    key = _month_key()
    if state.get("month") != key:
        return 0
    return state.get("monthly_calls", 0)


# ── Per-project budget ─────────────────────────────────────────────────────────


def project_budget_path(project_dir: Path) -> Path:
    """Return the path to ``projects/<name>/budget.json``."""
    return project_dir / "budget.json"


def load_project_budget(project_dir: Path) -> dict:
    """Load (or initialise) the per-project budget tracking file.

    Returns:
        Dict with keys ``project``, ``total_tokens``, ``total_calls``, ``sessions``.
    """
    path = project_budget_path(project_dir)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        # Back-compat: old files before total_calls was added.
        data.setdefault("total_calls", len(data.get("sessions", [])))
        return data
    return {
        "project": project_dir.name,
        "total_tokens": 0,
        "total_calls": 0,
        "sessions": [],
    }


def save_project_budget(project_dir: Path, data: dict) -> None:
    """Write the per-project budget data back to disk."""
    project_budget_path(project_dir).write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )


def record_project_spend(
    project_dir: Path,
    task: str,
    phase: str,
    delta_tokens: int,
    attempt: int = 0,
    parallel_batch: list[str] | None = None,
) -> int:
    """Record an API call and add *delta_tokens* to the project total.

    Every invocation appends a session record (even when *delta_tokens* is zero)
    so that the call count stays accurate.

    Args:
        project_dir:    Project directory path.
        task:           ROADMAP heading string.
        phase:          ``'build'``, ``'fix'``, ``'document'``, etc.
        delta_tokens:   Tokens consumed by this invocation.
        attempt:        Zero-based attempt index.
        parallel_batch: All task headings in the parallel batch (including this
                        one).  Stored as ``parallel_with`` in the session record
                        when provided so the budget log shows which tasks ran
                        together.

    Returns:
        Updated project total_tokens.
    """
    data = load_project_budget(project_dir)
    # Back-compat: old files may have total_usd instead of total_tokens.
    data.setdefault("total_tokens", 0)
    data.setdefault("total_calls", 0)
    data["total_tokens"] = data["total_tokens"] + max(0, delta_tokens)
    data["total_calls"] = data["total_calls"] + 1
    session: dict = {
        "date": date.today().isoformat(),
        "task": task,
        "phase": phase,
        "tokens": max(0, delta_tokens),
        "attempt": attempt,
    }
    if parallel_batch and len(parallel_batch) > 1:
        session["parallel_with"] = parallel_batch
    data["sessions"].append(session)
    save_project_budget(project_dir, data)
    # Increment the monthly call counter in the global budget state.
    _increment_monthly_calls()
    return data["total_tokens"]


# ── Runner state helpers ───────────────────────────────────────────────────────


def runner_state_path(project_dir: Path) -> Path:
    """Return the path to ``projects/<name>/.runner_state.json``."""
    return project_dir / ".runner_state.json"


def _raw_state(project_dir: Path) -> dict:
    """Load the raw state dict from disk, or return defaults if absent."""
    path = runner_state_path(project_dir)
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    # Back-compat: old format used 'task' key instead of 'current_task'.
    current = data.get("current_task") or data.get("task")
    return {
        "current_task": current,
        "attempt": data.get("attempt", 0),
        "fix_logs": data.get("fix_logs"),
        "completed": data.get("completed", []),
        # ISO-8601 UTC timestamp of when the current task first started.
        # Set on attempt 0; cleared when the task is marked done.
        "task_started_at": data.get("task_started_at"),
        # Per-task elapsed seconds for completed tasks; used to compute ETA.
        "task_durations": data.get("task_durations", []),
        # Tasks that failed after max attempts (populated by rollback module).
        "failed": data.get("failed", []),
    }


def _write_state(project_dir: Path, state: dict) -> None:
    """Write *state* to the project's ``.runner_state.json``."""
    runner_state_path(project_dir).write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )


def save_runner_state(
    project_dir: Path, task: str, attempt: int, fix_logs: str | None
) -> None:
    """Persist the in-progress task, attempt index, and fix logs for crash recovery.

    Args:
        project_dir: Project directory path.
        task:        Current ROADMAP heading.
        attempt:     Zero-based attempt index.
        fix_logs:    Pytest output from last failure, or None.
    """
    state = _raw_state(project_dir)  # preserve completed list
    state["current_task"] = task
    state["attempt"] = attempt
    state["fix_logs"] = (
        fix_logs[-3000:] if fix_logs and len(fix_logs) > 3000 else fix_logs
    )
    # Stamp the start time on the very first attempt so we can measure duration.
    if attempt == 0 and not state.get("task_started_at"):
        state["task_started_at"] = datetime.now(timezone.utc).isoformat()
    _write_state(project_dir, state)


def load_runner_state(project_dir: Path) -> dict | None:
    """Return the in-progress task state, or None if no task is interrupted."""
    state = _raw_state(project_dir)
    if state["current_task"] is not None:
        return state
    return None


def _completed_tasks(state: dict) -> set[str]:
    """Return the set of completed task headings from *state* (handles legacy formats)."""
    result: set[str] = set()
    for entry in state.get("completed", []):
        if isinstance(entry, dict):
            result.add(entry["task"])
        elif isinstance(entry, str):
            result.add(entry)
    return result


def task_done(task: str, project_dir: Path) -> bool:
    """Return True if *task* is in the project's completed list."""
    return task in _completed_tasks(_raw_state(project_dir))


def mark_done(task: str, project_dir: Path) -> None:
    """Add *task* to the completed list, record duration, and clear in-progress fields."""
    state = _raw_state(project_dir)
    if task not in _completed_tasks(state):
        state["completed"].append({"task": task, "attempts": state["attempt"] + 1})
    # Compute elapsed wall-clock seconds and store for ETA estimation.
    started_at = state.get("task_started_at")
    if started_at:
        try:
            elapsed = (
                datetime.now(timezone.utc) - datetime.fromisoformat(started_at)
            ).total_seconds()
            state["task_durations"].append(round(elapsed, 1))
        except (ValueError, TypeError):
            pass
    state["current_task"] = None
    state["attempt"] = 0
    state["fix_logs"] = None
    state["task_started_at"] = None
    _write_state(project_dir, state)
