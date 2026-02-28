"""Tests for runner.review — human-in-the-loop review mode."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def review_project(tmp_path: Path) -> Path:
    """Project with review enabled."""
    project = tmp_path / "review-proj"
    project.mkdir()
    roadmap = {
        "name": "Review Project",
        "ecosystem": "python",
        "review": True,
        "tasks": [
            {
                "id": 1,
                "title": "First Task",
                "depends_on": [],
                "outputs": ["src/a.py"],
                "acceptance": "tests pass",
            },
            {
                "id": 2,
                "title": "Second Task",
                "depends_on": [1],
                "outputs": ["src/b.py"],
                "acceptance": "tests pass",
                "review": False,
            },
        ],
    }
    (project / "ROADMAP.json").write_text(json.dumps(roadmap), encoding="utf-8")
    return project


class TestIsReviewEnabled:
    def test_project_level_review_enabled(self, review_project: Path) -> None:
        from runner.review import is_review_enabled

        assert is_review_enabled(None, review_project) is True

    def test_project_level_review_disabled(self, tmp_project: Path) -> None:
        from runner.review import is_review_enabled

        assert is_review_enabled(None, tmp_project) is False

    def test_task_level_override_disables(self, review_project: Path) -> None:
        from runner.review import is_review_enabled

        # Task 2 has review: false, overriding project-level true.
        assert is_review_enabled("## 002 - Second Task", review_project) is False

    def test_task_inherits_project_setting(self, review_project: Path) -> None:
        from runner.review import is_review_enabled

        # Task 1 has no review field → inherits project-level true.
        assert is_review_enabled("## 001 - First Task", review_project) is True

    def test_unknown_task_inherits_project_setting(self, review_project: Path) -> None:
        from runner.review import is_review_enabled

        assert is_review_enabled("## 999 - Nonexistent", review_project) is True


class TestDiscardChanges:
    def test_discard_runs_git_commands(self, review_project: Path) -> None:
        from runner.review import discard_changes

        with patch("runner.review.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            discard_changes(review_project)
            assert mock_run.call_count >= 2  # At least checkout + clean.
