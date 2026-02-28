"""Tests for runner.coverage — test coverage gating."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def coverage_project(tmp_path: Path) -> Path:
    """Project with min_coverage configured."""
    project = tmp_path / "cov-proj"
    project.mkdir()
    roadmap = {
        "name": "Coverage Project",
        "ecosystem": "python",
        "min_coverage": 80,
        "tasks": [
            {
                "id": 1,
                "title": "First Task",
                "depends_on": [],
                "outputs": ["src/a.py"],
                "acceptance": "tests pass",
            },
        ],
    }
    (project / "ROADMAP.json").write_text(json.dumps(roadmap), encoding="utf-8")
    (project / "cov_proj").mkdir()
    (project / "tests").mkdir()
    return project


class TestGetMinCoverage:
    def test_returns_threshold(self, coverage_project: Path) -> None:
        from runner.coverage import get_min_coverage

        assert get_min_coverage(coverage_project) == 80

    def test_returns_none_when_not_set(self, tmp_project: Path) -> None:
        from runner.coverage import get_min_coverage

        assert get_min_coverage(tmp_project) is None


class TestParseCoverageTotal:
    def test_parses_standard_total(self) -> None:
        from runner.coverage import _parse_coverage_total

        output = (
            "Name              Stmts   Miss  Cover\n"
            "-------------------------------------\n"
            "my_module.py         50     10    80%\n"
            "TOTAL                50     10    80%\n"
        )
        assert _parse_coverage_total(output) == 80.0

    def test_parses_high_coverage(self) -> None:
        from runner.coverage import _parse_coverage_total

        output = "TOTAL                100      2    98%\n"
        assert _parse_coverage_total(output) == 98.0

    def test_returns_none_for_no_coverage(self) -> None:
        from runner.coverage import _parse_coverage_total

        assert _parse_coverage_total("all tests passed\n") is None


class TestCheckCoverageGate:
    def test_passes_when_above_threshold(self, coverage_project: Path) -> None:
        from runner.coverage import check_coverage_gate

        ok, msg = check_coverage_gate(coverage_project, 90.0)
        assert ok is True
        assert "90%" in msg

    def test_passes_when_equal_to_threshold(self, coverage_project: Path) -> None:
        from runner.coverage import check_coverage_gate

        ok, _ = check_coverage_gate(coverage_project, 80.0)
        assert ok is True

    def test_fails_when_below_threshold(self, coverage_project: Path) -> None:
        from runner.coverage import check_coverage_gate

        ok, msg = check_coverage_gate(coverage_project, 50.0)
        assert ok is False
        assert "below" in msg.lower()

    def test_passes_when_no_threshold(self, tmp_project: Path) -> None:
        from runner.coverage import check_coverage_gate

        ok, _ = check_coverage_gate(tmp_project, 50.0)
        assert ok is True

    def test_passes_when_coverage_none(self, coverage_project: Path) -> None:
        from runner.coverage import check_coverage_gate

        ok, msg = check_coverage_gate(coverage_project, None)
        assert ok is True
        assert "not available" in msg.lower()
