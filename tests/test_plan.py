"""Tests for runner.plan — ROADMAP generation from natural language."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch


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


class TestRunArchitectOnce:
    """Tests for the streaming _run_architect_once helper."""

    def test_returns_json_on_success(self) -> None:
        """Successful subprocess produces valid JSON."""
        from runner.plan import _run_architect_once

        json_out = '{"name": "proj", "tasks": []}\n'

        mock_proc = MagicMock()
        mock_proc.stdout = iter([json_out])
        # poll() is called repeatedly: None while running, then 0 once done,
        # and again in the finally clause — use a callable that switches.
        _calls = iter([None, 0, 0, 0, 0, 0])
        mock_proc.poll = MagicMock(side_effect=lambda: next(_calls, 0))
        mock_proc.returncode = 0
        mock_proc.kill = MagicMock()

        with patch("runner.plan.subprocess.Popen", return_value=mock_proc):
            result = _run_architect_once("/tmp/fake.md", 300)

        assert result is not None
        parsed = json.loads(result)
        assert parsed["name"] == "proj"

    def test_returns_none_on_not_found(self) -> None:
        """FileNotFoundError (missing opencode) returns None."""
        from runner.plan import _run_architect_once

        with patch(
            "runner.plan.subprocess.Popen", side_effect=FileNotFoundError("opencode")
        ):
            result = _run_architect_once("/tmp/fake.md", 300)
            assert result is None


class TestCallArchitect:
    def test_returns_none_when_run_architect_fails(self) -> None:
        from runner.plan import _call_architect

        with patch("runner.plan._run_architect_once", return_value=None):
            import runner.plan as plan_mod

            plan_mod._last_architect_timed_out = False
            result = _call_architect("Test project", "test-proj")
            assert result is None

    def test_returns_json_on_success(self) -> None:
        from runner.plan import _call_architect

        good_json = '{"name": "test", "tasks": []}'
        with patch("runner.plan._run_architect_once", return_value=good_json):
            result = _call_architect("Test project", "test-proj")
            assert result == good_json

    def test_retries_on_timeout(self) -> None:
        """When the first attempt times out, _call_architect retries with doubled timeout."""
        import runner.plan as plan_mod
        from runner.plan import _call_architect

        call_count = 0
        good_json = '{"name": "test", "tasks": []}'

        def fake_run(
            tmpfile: str,
            timeout: int,
            project_dir: Path | None = None,
            attempt: int = 1,
        ) -> str | None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                plan_mod._last_architect_timed_out = True
                return None
            plan_mod._last_architect_timed_out = False
            return good_json

        with patch("runner.plan._run_architect_once", side_effect=fake_run):
            result = _call_architect("Test project", "test-proj")
            assert result == good_json
            assert call_count == 2


class TestWriteGenerateLog:
    """Tests for _write_generate_log and _strip_ansi."""

    def test_strip_ansi_removes_escapes(self) -> None:
        from runner.plan import _strip_ansi

        assert _strip_ansi("\x1b[31mred\x1b[0m") == "red"
        assert _strip_ansi("plain") == "plain"

    def test_writes_log_file(self, tmp_path: Path) -> None:
        from runner.plan import _write_generate_log

        lines = ["line one\n", "\x1b[32mcolored\x1b[0m line two\n"]
        log_path = _write_generate_log(lines, tmp_path, attempt=1)
        assert log_path is not None
        assert log_path.exists()
        assert "roadmap-generate" in str(log_path)
        content = log_path.read_text(encoding="utf-8")
        assert "line one" in content
        assert "colored line two" in content
        # ANSI codes must be stripped.
        assert "\x1b" not in content

    def test_returns_none_when_no_project_dir(self) -> None:
        from runner.plan import _write_generate_log

        assert _write_generate_log(["data\n"], None, 1) is None

    def test_returns_none_when_no_lines(self, tmp_path: Path) -> None:
        from runner.plan import _write_generate_log

        assert _write_generate_log([], tmp_path, 1) is None
