"""Tests for runner.diagnostics — structured failure reports."""

import json
from pathlib import Path

import pytest


class TestSaveFailureReport:
    def test_creates_report_file(self, tmp_project: Path) -> None:
        from runner.diagnostics import save_failure_report

        report_path = save_failure_report(
            "## 001 - First Task",
            tmp_project,
            attempts=3,
            last_error="AssertionError: expected 1, got 2",
            tokens_spent=50000,
        )
        assert report_path.exists()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["attempts"] == 3
        assert "AssertionError" in report["last_error"]
        assert report["tokens_spent"] == 50000

    def test_report_in_logs_directory(self, tmp_project: Path) -> None:
        from runner.diagnostics import save_failure_report

        report_path = save_failure_report(
            "## 001 - First Task",
            tmp_project,
            attempts=1,
        )
        assert "logs" in str(report_path)
        assert report_path.name == "failure_report.json"

    def test_extracts_error_from_logs(self, tmp_project: Path) -> None:
        from runner.diagnostics import save_failure_report

        logs = "running tests...\nTraceback:\nValueError: bad input\n"
        report_path = save_failure_report(
            "## 001 - First Task",
            tmp_project,
            attempts=2,
            fix_logs=logs,
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert "ValueError" in report["last_error"]


class TestExtractError:
    def test_extracts_python_error(self) -> None:
        from runner.diagnostics import _extract_error

        logs = "Some output\nTypeError: unsupported operand\nMore stuff"
        result = _extract_error(logs)
        assert result is not None
        assert "TypeError" in result

    def test_extracts_assertion_error(self) -> None:
        from runner.diagnostics import _extract_error

        logs = "FAILED tests/test_foo.py::test_bar\nAssertionError: 1 != 2"
        result = _extract_error(logs)
        assert result is not None
        assert "AssertionError" in result

    def test_returns_none_for_empty(self) -> None:
        from runner.diagnostics import _extract_error

        assert _extract_error(None) is None
        assert _extract_error("") is None

    def test_fallback_to_last_line(self) -> None:
        from runner.diagnostics import _extract_error

        result = _extract_error("no patterns here\njust regular output")
        assert result == "just regular output"


class TestExtractFailingTest:
    def test_extracts_pytest_format(self) -> None:
        from runner.diagnostics import _extract_failing_test

        logs = "FAILED tests/test_module.py::test_function - AssertionError"
        result = _extract_failing_test(logs)
        assert result == "tests/test_module.py::test_function"

    def test_returns_none_for_no_match(self) -> None:
        from runner.diagnostics import _extract_failing_test

        assert _extract_failing_test("all tests passed") is None

    def test_returns_none_for_empty(self) -> None:
        from runner.diagnostics import _extract_failing_test

        assert _extract_failing_test(None) is None
