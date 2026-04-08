"""tracing.py — Lightweight per-task pipeline tracing."""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Span:
    """A single phase execution record."""

    phase: str
    started_at: float
    ended_at: float = 0.0
    ok: bool = True
    detail: str = ""

    def duration_s(self) -> float:
        return self.ended_at - self.started_at if self.ended_at else 0.0

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_s": round(self.duration_s(), 3),
            "ok": self.ok,
            "detail": self.detail,
        }


@dataclass
class TaskTrace:
    """Collects spans for one task's pipeline run."""

    task: str
    spans: list[Span] = field(default_factory=list)
    attempts: int = 0
    _current: Span | None = field(default=None, repr=False)

    def begin(self, phase: str) -> None:
        span = Span(phase=phase, started_at=time.time())
        self._current = span
        self.spans.append(span)

    def end(self, ok: bool = True, detail: str = "") -> None:
        if self._current is not None:
            self._current.ended_at = time.time()
            self._current.ok = ok
            self._current.detail = detail
            self._current = None

    def total_duration_s(self) -> float:
        return sum(s.duration_s() for s in self.spans)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "attempts": self.attempts,
            "total_duration_s": round(self.total_duration_s(), 3),
            "spans": [s.to_dict() for s in self.spans],
        }


# ── Per-project trace store ────────────────────────────────────────────────────

_TRACE_FILE = "traces.json"

# In-memory traces for the current run, keyed by task heading.
_traces: dict[str, TaskTrace] = {}


def get_trace(task: str) -> TaskTrace:
    """Return (or create) the trace for *task*."""
    if task not in _traces:
        _traces[task] = TaskTrace(task=task)
    return _traces[task]


def save_traces(project_dir: Path) -> Path:
    """Persist all collected traces to ``<project>/logs/traces.json``."""
    logs_dir = project_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    out_path = logs_dir / _TRACE_FILE

    existing: list[dict] = []
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = []

    existing.extend(t.to_dict() for t in _traces.values())
    out_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return out_path


def load_traces(project_dir: Path) -> list[dict]:
    """Load previously saved traces from disk."""
    trace_path = project_dir / "logs" / _TRACE_FILE
    if not trace_path.exists():
        return []
    try:
        return json.loads(trace_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def reset() -> None:
    """Clear in-memory traces (mainly for tests)."""
    _traces.clear()
