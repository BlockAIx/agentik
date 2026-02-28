"""Tests for runner.plan — ROADMAP generation from natural language."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestExtractJson:
    def test_extracts_plain_json(self) -> None:
        from runner.plan import _extract_json

        raw = '{"name": "test", "tasks": []}'
        result = _extract_json(raw)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["name"] == "test"

    def test_extracts_from_markdown_fences(self) -> None:
        from runner.plan import _extract_json

        raw = 'Here is the ROADMAP:\n```json\n{"name": "test"}\n```\nDone!'
        result = _extract_json(raw)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["name"] == "test"

    def test_returns_none_for_no_json(self) -> None:
        from runner.plan import _extract_json

        result = _extract_json("no json here at all")
        assert result is None

    def test_handles_nested_objects(self) -> None:
        from runner.plan import _extract_json

        raw = '{"name": "proj", "git": {"enabled": true}, "tasks": [{"id": 1}]}'
        result = _extract_json(raw)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["git"]["enabled"] is True


class TestCallArchitect:
    def test_returns_none_on_timeout(self) -> None:
        from runner.plan import _call_architect
        import subprocess

        with patch("runner.plan.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 120)):
            result = _call_architect("Test project", "test-proj")
            assert result is None

    def test_returns_none_on_empty_output(self) -> None:
        from runner.plan import _call_architect
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("runner.plan.subprocess.run", return_value=mock_result):
            result = _call_architect("Test project", "test-proj")
            assert result is None
