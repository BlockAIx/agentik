"""Tests for runner.dryrun — dry-run cost/time estimation."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestEstimateTaskTokens:
    def test_returns_positive_estimate(self, tmp_project: Path) -> None:
        from runner.dryrun import estimate_task_tokens

        tokens = estimate_task_tokens("## 001 - First Task", tmp_project)
        assert tokens > 0

    def test_milestone_cheaper_than_build(self, tmp_path: Path) -> None:
        from runner.dryrun import estimate_task_tokens

        project = tmp_path / "ms-proj"
        project.mkdir()
        roadmap = {
            "name": "MS Project",
            "ecosystem": "python",
            "tasks": [
                {
                    "id": 1,
                    "title": "Build Task",
                    "depends_on": [],
                    "outputs": ["src/a.py"],
                    "acceptance": "tests pass",
                    "description": "A very detailed long description " * 20,
                },
                {
                    "id": 2,
                    "title": "Milestone Review",
                    "depends_on": [1],
                    "agent": "milestone",
                    "version": "0.1.0",
                },
            ],
        }
        (project / "ROADMAP.json").write_text(json.dumps(roadmap), encoding="utf-8")

        build_tokens = estimate_task_tokens("## 001 - Build Task", project)
        ms_tokens = estimate_task_tokens("## 002 - Milestone Review", project)
        assert ms_tokens < build_tokens


class TestTokensToUsd:
    def test_returns_float(self) -> None:
        from runner.dryrun import _tokens_to_usd

        cost = _tokens_to_usd(100_000)
        assert isinstance(cost, float)
        assert cost > 0

    def test_zero_tokens(self) -> None:
        from runner.dryrun import _tokens_to_usd

        assert _tokens_to_usd(0) == 0.0


class TestDryRun:
    def test_returns_summary_dict(self, tmp_project: Path) -> None:
        from runner.dryrun import dry_run

        result = dry_run(tmp_project)
        assert "remaining_tasks" in result
        assert "total_tasks" in result
        assert "estimated_tokens" in result
        assert "estimated_usd" in result
        assert result["total_tasks"] == 4
        assert result["remaining_tasks"] == 4
        assert result["estimated_tokens"] > 0

    def test_completed_tasks_excluded(self, tmp_project: Path) -> None:
        from runner.dryrun import dry_run
        from runner.state import _write_state

        # Mark task 1 as done.
        _write_state(tmp_project, {"completed": ["## 001 - First Task"]})
        result = dry_run(tmp_project)
        assert result["remaining_tasks"] == 3
        assert result["completed_tasks"] == 1
