"""Tests for runner.state — state persistence, budget tracking, token formatting."""

import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# ── _parse_tokens ──────────────────────────────────────────────────────────────


class TestParseTokens:
    def test_plain_number(self) -> None:
        from runner.state import _parse_tokens

        assert _parse_tokens("500") == 500.0

    def test_thousands(self) -> None:
        from runner.state import _parse_tokens

        assert _parse_tokens("128.7K") == pytest.approx(128_700.0)

    def test_millions(self) -> None:
        from runner.state import _parse_tokens

        assert _parse_tokens("1.2M") == 1_200_000.0

    def test_whitespace(self) -> None:
        from runner.state import _parse_tokens

        assert _parse_tokens("  42  ") == 42.0


# ── _format_tokens ─────────────────────────────────────────────────────────────


class TestFormatTokens:
    def test_small(self) -> None:
        from runner.state import _format_tokens

        assert _format_tokens(850) == "850"

    def test_thousands(self) -> None:
        from runner.state import _format_tokens

        assert _format_tokens(12500) == "12.5K"

    def test_millions(self) -> None:
        from runner.state import _format_tokens

        assert _format_tokens(3_200_000) == "3.2M"

    def test_exact_thousand(self) -> None:
        from runner.state import _format_tokens

        assert _format_tokens(1000) == "1.0K"


# ── _format_duration ───────────────────────────────────────────────────────────


class TestFormatDuration:
    def test_seconds(self) -> None:
        from runner.state import _format_duration

        assert _format_duration(45) == "45s"

    def test_minutes(self) -> None:
        from runner.state import _format_duration

        assert _format_duration(130) == "2m 10s"

    def test_hours(self) -> None:
        from runner.state import _format_duration

        assert _format_duration(3720) == "1h 2m"

    def test_exact_minute(self) -> None:
        from runner.state import _format_duration

        assert _format_duration(60) == "1m"

    def test_exact_hour(self) -> None:
        from runner.state import _format_duration

        assert _format_duration(3600) == "1h"


# ── _tokens_to_usd ────────────────────────────────────────────────────────────


class TestTokensToUsd:
    def test_zero_tokens(self) -> None:
        from runner.state import _tokens_to_usd

        stats = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
        assert _tokens_to_usd(stats) == 0.0

    def test_known_cost(self) -> None:
        from runner.state import _tokens_to_usd

        # 1M input tokens at $1.25/M = $1.25
        stats = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_write": 0}
        result = _tokens_to_usd(stats)
        assert result == 1.25


# ── Runner state persistence ──────────────────────────────────────────────────


class TestRunnerState:
    def test_save_and_load(self, tmp_path: Path) -> None:
        from runner.state import load_runner_state, save_runner_state

        project = tmp_path / "proj"
        project.mkdir()
        # Create empty state file to start
        (project / ".runner_state.json").write_text("{}", encoding="utf-8")

        save_runner_state(project, "## 001 - Task", attempt=0, fix_logs=None)
        state = load_runner_state(project)

        assert state is not None
        assert state["current_task"] == "## 001 - Task"
        assert state["attempt"] == 0
        assert state["fix_logs"] is None

    def test_load_returns_none_when_no_current(self, tmp_path: Path) -> None:
        from runner.state import load_runner_state

        project = tmp_path / "proj"
        project.mkdir()
        (project / ".runner_state.json").write_text("{}", encoding="utf-8")
        assert load_runner_state(project) is None

    def test_load_no_state_file(self, tmp_path: Path) -> None:
        from runner.state import load_runner_state

        project = tmp_path / "proj"
        project.mkdir()
        assert load_runner_state(project) is None

    def test_fix_logs_truncated_on_save(self, tmp_path: Path) -> None:
        from runner.state import load_runner_state, save_runner_state

        project = tmp_path / "proj"
        project.mkdir()
        (project / ".runner_state.json").write_text("{}", encoding="utf-8")

        long_logs = "x" * 5000
        save_runner_state(project, "## 001 - Task", attempt=1, fix_logs=long_logs)
        state = load_runner_state(project)
        assert state is not None
        assert len(state["fix_logs"]) == 3000


# ── mark_done / task_done ──────────────────────────────────────────────────────


class TestMarkDone:
    def test_marks_task_complete(self, tmp_path: Path) -> None:
        from runner.state import mark_done, save_runner_state, task_done

        project = tmp_path / "proj"
        project.mkdir()
        (project / ".runner_state.json").write_text("{}", encoding="utf-8")

        save_runner_state(project, "## 001 - Task", 0, None)
        assert not task_done("## 001 - Task", project)

        mark_done("## 001 - Task", project)
        assert task_done("## 001 - Task", project)

    def test_clears_in_progress_fields(self, tmp_path: Path) -> None:
        from runner.state import load_runner_state, mark_done, save_runner_state

        project = tmp_path / "proj"
        project.mkdir()
        (project / ".runner_state.json").write_text("{}", encoding="utf-8")

        save_runner_state(project, "## 001 - Task", 2, "some logs")
        mark_done("## 001 - Task", project)

        # After marking done, load_runner_state should return None (no current task)
        assert load_runner_state(project) is None

    def test_multiple_tasks_done(self, tmp_path: Path) -> None:
        from runner.state import mark_done, save_runner_state, task_done

        project = tmp_path / "proj"
        project.mkdir()
        (project / ".runner_state.json").write_text("{}", encoding="utf-8")

        save_runner_state(project, "## 001 - First", 0, None)
        mark_done("## 001 - First", project)

        save_runner_state(project, "## 002 - Second", 0, None)
        mark_done("## 002 - Second", project)

        assert task_done("## 001 - First", project)
        assert task_done("## 002 - Second", project)
        assert not task_done("## 003 - Third", project)


# ── Project budget ─────────────────────────────────────────────────────────────


class TestProjectBudget:
    def test_load_fresh(self, tmp_path: Path) -> None:
        from runner.state import load_project_budget

        project = tmp_path / "proj"
        project.mkdir()
        budget = load_project_budget(project)
        assert budget["project"] == "proj"
        assert budget["total_tokens"] == 0
        assert budget["total_calls"] == 0
        assert budget["sessions"] == []

    def test_record_spend(self, tmp_path: Path) -> None:
        from runner.state import load_project_budget, record_project_spend

        project = tmp_path / "proj"
        project.mkdir()

        total = record_project_spend(
            project, "## 001 - Task", "build", 50_000, attempt=0
        )
        assert total == 50_000

        budget = load_project_budget(project)
        assert budget["total_tokens"] == 50_000
        assert budget["total_calls"] == 1
        assert len(budget["sessions"]) == 1
        assert budget["sessions"][0]["task"] == "## 001 - Task"
        assert budget["sessions"][0]["phase"] == "build"
        assert budget["sessions"][0]["tokens"] == 50_000

    def test_cumulative_spend(self, tmp_path: Path) -> None:
        from runner.state import load_project_budget, record_project_spend

        project = tmp_path / "proj"
        project.mkdir()

        record_project_spend(project, "## 001 - A", "build", 10_000)
        total = record_project_spend(project, "## 002 - B", "build", 20_000)
        assert total == 30_000

        budget = load_project_budget(project)
        assert budget["total_calls"] == 2

    def test_zero_delta_still_records_call(self, tmp_path: Path) -> None:
        from runner.state import load_project_budget, record_project_spend

        project = tmp_path / "proj"
        project.mkdir()

        record_project_spend(project, "## 001 - A", "build", 0)
        budget = load_project_budget(project)
        assert budget["total_tokens"] == 0
        # A call with 0 tokens still counts as an API invocation.
        assert budget["total_calls"] == 1
        assert len(budget["sessions"]) == 1

    def test_parallel_batch_recorded(self, tmp_path: Path) -> None:
        from runner.state import load_project_budget, record_project_spend

        project = tmp_path / "proj"
        project.mkdir()
        batch = ["## 002 - Board Grid", "## 003 - Scoring Engine"]

        record_project_spend(
            project, "## 002 - Board Grid", "build", 10_000, parallel_batch=batch
        )
        record_project_spend(
            project, "## 003 - Scoring Engine", "build", 20_000, parallel_batch=batch
        )

        budget = load_project_budget(project)
        for session in budget["sessions"]:
            assert session["parallel_with"] == batch

    def test_solo_task_has_no_parallel_with(self, tmp_path: Path) -> None:
        from runner.state import load_project_budget, record_project_spend

        project = tmp_path / "proj"
        project.mkdir()

        record_project_spend(project, "## 001 - Solo", "build", 5_000)
        budget = load_project_budget(project)
        assert "parallel_with" not in budget["sessions"][0]

    def test_legacy_budget_without_total_calls(self, tmp_path: Path) -> None:
        """Old budget.json files missing total_calls derive it from session count."""
        from runner.state import load_project_budget

        project = tmp_path / "proj"
        project.mkdir()
        # Simulate old format without total_calls
        old_data = {
            "project": "proj",
            "total_tokens": 100_000,
            "sessions": [
                {
                    "date": "2026-01-01",
                    "task": "## 001 - X",
                    "phase": "build",
                    "tokens": 50_000,
                    "attempt": 0,
                },
                {
                    "date": "2026-01-01",
                    "task": "## 002 - Y",
                    "phase": "build",
                    "tokens": 50_000,
                    "attempt": 0,
                },
            ],
        }
        (project / "budget.json").write_text(json.dumps(old_data), encoding="utf-8")
        budget = load_project_budget(project)
        # Should derive total_calls from number of sessions
        assert budget["total_calls"] == 2


# ── Legacy state compatibility ────────────────────────────────────────────────


class TestLegacyState:
    """Verify old .runner_state.json formats are handled gracefully."""

    def test_bare_string_completed(self, tmp_path: Path) -> None:
        from runner.state import task_done

        project = tmp_path / "proj"
        project.mkdir()
        # Old format: completed was a list of strings, not dicts
        state = {
            "current_task": None,
            "attempt": 0,
            "fix_logs": None,
            "completed": ["## 001 - Old Task"],
        }
        (project / ".runner_state.json").write_text(json.dumps(state), encoding="utf-8")
        assert task_done("## 001 - Old Task", project)

    def test_old_task_key(self, tmp_path: Path) -> None:
        from runner.state import load_runner_state

        project = tmp_path / "proj"
        project.mkdir()
        # Old format used 'task' instead of 'current_task'
        state = {"task": "## 001 - Legacy", "attempt": 1, "fix_logs": "err"}
        (project / ".runner_state.json").write_text(json.dumps(state), encoding="utf-8")
        loaded = load_runner_state(project)
        assert loaded is not None
        assert loaded["current_task"] == "## 001 - Legacy"
