"""Tests for runner.rollback — git rollback on failure."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestRollbackFeatureBranch:
    def test_skips_when_git_not_managed(self, tmp_project: Path) -> None:
        from runner.rollback import rollback_feature_branch

        result = rollback_feature_branch("## 001 - First Task", tmp_project)
        assert result is False

    def test_runs_git_commands_when_managed(self, tmp_project: Path) -> None:
        from runner.rollback import rollback_feature_branch

        # Add git config to ROADMAP.
        roadmap = json.loads((tmp_project / "ROADMAP.json").read_text(encoding="utf-8"))
        roadmap["git"] = {"enabled": True}
        (tmp_project / "ROADMAP.json").write_text(json.dumps(roadmap), encoding="utf-8")

        with patch("runner.rollback.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = rollback_feature_branch("## 001 - First Task", tmp_project)
            assert result is True
            # Should call: reset --hard, clean -fd, checkout develop, branch -D.
            assert mock_run.call_count == 4

    def test_returns_false_on_reset_failure(self, tmp_project: Path) -> None:
        from runner.rollback import rollback_feature_branch

        roadmap = json.loads((tmp_project / "ROADMAP.json").read_text(encoding="utf-8"))
        roadmap["git"] = {"enabled": True}
        (tmp_project / "ROADMAP.json").write_text(json.dumps(roadmap), encoding="utf-8")

        with patch("runner.rollback.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="error")
            result = rollback_feature_branch("## 001 - First Task", tmp_project)
            assert result is False


class TestMarkTaskFailed:
    def test_adds_to_failed_list(self, tmp_project: Path) -> None:
        from runner.rollback import mark_task_failed
        from runner.state import _raw_state

        mark_task_failed("## 001 - First Task", tmp_project, {"reason": "tests failed"})
        state = _raw_state(tmp_project)
        assert len(state.get("failed", [])) == 1
        assert state["failed"][0]["task"] == "## 001 - First Task"
        assert state["failed"][0]["reason"] == "tests failed"

    def test_appends_multiple_failures(self, tmp_project: Path) -> None:
        from runner.rollback import mark_task_failed
        from runner.state import _raw_state

        mark_task_failed("## 001 - First Task", tmp_project)
        mark_task_failed("## 002 - Second Task", tmp_project)
        state = _raw_state(tmp_project)
        assert len(state.get("failed", [])) == 2
