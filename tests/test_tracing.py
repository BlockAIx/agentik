"""Tests for runner.tracing — lightweight pipeline tracing."""

import json
from pathlib import Path

from runner.tracing import TaskTrace, get_trace, load_traces, reset, save_traces


class TestSpanAndTrace:
    def test_span_duration(self) -> None:
        trace = TaskTrace(task="## 001 - Test")
        trace.begin("build")
        # Manually tweak timestamps for determinism.
        trace.spans[0].started_at = 100.0
        trace.end(ok=True)
        trace.spans[0].ended_at = 105.5
        assert trace.spans[0].duration_s() == 5.5

    def test_trace_to_dict(self) -> None:
        trace = TaskTrace(task="## 001 - Test", attempts=2)
        trace.begin("build")
        trace.spans[0].started_at = 0.0
        trace.spans[0].ended_at = 1.0
        trace.end(ok=True)

        d = trace.to_dict()
        assert d["task"] == "## 001 - Test"
        assert d["attempts"] == 2
        assert len(d["spans"]) == 1
        assert d["spans"][0]["phase"] == "build"
        assert d["spans"][0]["ok"] is True

    def test_multiple_spans(self) -> None:
        trace = TaskTrace(task="## 002 - Multi")
        trace.begin("build")
        trace.spans[-1].started_at = 0.0
        trace.end()
        trace.spans[-1].ended_at = 2.0
        trace.begin("test")
        trace.spans[-1].started_at = 2.0
        trace.end(ok=False, detail="tests failed")
        trace.spans[-1].ended_at = 3.0

        assert len(trace.spans) == 2
        assert trace.total_duration_s() == 3.0
        assert trace.spans[1].ok is False


class TestStoreOperations:
    def setup_method(self) -> None:
        reset()

    def test_get_trace_creates_new(self) -> None:
        t = get_trace("## 001 - Task")
        assert t.task == "## 001 - Task"
        assert get_trace("## 001 - Task") is t

    def test_save_and_load_traces(self, tmp_path: Path) -> None:
        project = tmp_path / "proj"
        project.mkdir()

        t = get_trace("## 001 - Task")
        t.attempts = 1
        t.begin("build")
        t.spans[-1].started_at = 0.0
        t.spans[-1].ended_at = 1.0
        t.end()

        path = save_traces(project)
        assert path.exists()

        loaded = load_traces(project)
        assert len(loaded) == 1
        assert loaded[0]["task"] == "## 001 - Task"

    def test_load_empty(self, tmp_path: Path) -> None:
        assert load_traces(tmp_path) == []

    def test_save_appends(self, tmp_path: Path) -> None:
        project = tmp_path / "proj"
        project.mkdir()

        t1 = get_trace("## 001 - First")
        t1.begin("build")
        t1.spans[-1].started_at = 0.0
        t1.spans[-1].ended_at = 1.0
        t1.end()
        save_traces(project)

        reset()
        t2 = get_trace("## 002 - Second")
        t2.begin("build")
        t2.spans[-1].started_at = 1.0
        t2.spans[-1].ended_at = 2.0
        t2.end()
        save_traces(project)

        loaded = load_traces(project)
        assert len(loaded) == 2

    def test_reset_clears(self) -> None:
        get_trace("## 001 - Task")
        reset()
        # New call should create a fresh trace.
        t = get_trace("## 001 - Task")
        assert len(t.spans) == 0
