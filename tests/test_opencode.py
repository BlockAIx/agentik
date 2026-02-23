"""Tests for runner.opencode — JSONC parsing, model check helpers, milestone agent."""

import json
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from runner.opencode import _strip_jsonc_comments


# ── _strip_jsonc_comments ──────────────────────────────────────────────────────


class TestStripJsoncComments:
    def test_removes_line_comments(self) -> None:
        text = '{\n  "key": "value" // this is a comment\n}'
        result = _strip_jsonc_comments(text)
        parsed = json.loads(result)
        assert parsed == {"key": "value"}

    def test_preserves_urls_in_strings(self) -> None:
        text = '{\n  "url": "https://example.com/path"\n}'
        result = _strip_jsonc_comments(text)
        parsed = json.loads(result)
        assert parsed["url"] == "https://example.com/path"

    def test_handles_escaped_quotes(self) -> None:
        text = '{\n  "escaped": "has \\"quotes\\""\n}'
        result = _strip_jsonc_comments(text)
        parsed = json.loads(result)
        assert "quotes" in parsed["escaped"]

    def test_comment_at_start_of_line(self) -> None:
        text = '// top comment\n{\n  "key": 1\n}'
        result = _strip_jsonc_comments(text)
        parsed = json.loads(result)
        assert parsed == {"key": 1}

    def test_multiple_comments(self) -> None:
        text = textwrap.dedent("""\
            {
              // first comment
              "a": 1,
              // second comment
              "b": 2
            }
        """)
        result = _strip_jsonc_comments(text)
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": 2}

    def test_no_comments(self) -> None:
        text = '{"key": "value"}'
        assert _strip_jsonc_comments(text) == text

    def test_empty_string(self) -> None:
        assert _strip_jsonc_comments("") == ""

    def test_url_inside_string_not_stripped(self) -> None:
        """Double-slash inside a JSON string value must not be treated as a comment."""
        text = '{"model": "anthropic/claude-sonnet-4-20250514"}'
        result = _strip_jsonc_comments(text)
        parsed = json.loads(result)
        assert parsed["model"] == "anthropic/claude-sonnet-4-20250514"


# ── run_opencode_milestone ─────────────────────────────────────────────────────


class TestRunOpencodeMilestone:
    """Verify run_opencode_milestone builds the prompt and invokes the agent."""

    def test_builds_prompt_and_invokes(self, tmp_path: Path) -> None:
        from runner.opencode import run_opencode_milestone

        # Minimal project structure
        import json as _json
        roadmap = {
            "name": "Demo v0.1",
            "ecosystem": "python",
            "preamble": "",
            "tasks": [
                {"id": 1, "title": "Release", "agent": "milestone", "version": "0.1.0", "depends_on": []}
            ],
        }
        (tmp_path / "ROADMAP.json").write_text(_json.dumps(roadmap), encoding="utf-8")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hi')", encoding="utf-8")

        with patch("runner.opencode._invoke_opencode", return_value=500) as mock_invoke:
            result = run_opencode_milestone("## 001 - Release", "0.1.0", tmp_path)

        assert result == 500
        mock_invoke.assert_called_once()
        call_kwargs = mock_invoke.call_args
        assert call_kwargs.kwargs["agent"] == "milestone"
        assert call_kwargs.kwargs["phase"] == "milestone"
        # Prompt should contain version and project name
        prompt_arg = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("prompt", "")
        assert "0.1.0" in prompt_arg
        assert tmp_path.name in prompt_arg

    def test_skips_git_and_pycache(self, tmp_path: Path) -> None:
        from runner.opencode import run_opencode_milestone

        import json as _json
        roadmap = {
            "name": "Demo",
            "ecosystem": "python",
            "preamble": "",
            "tasks": [
                {"id": 1, "title": "Release", "agent": "milestone", "version": "0.1.0", "depends_on": []}
            ],
        }
        (tmp_path / "ROADMAP.json").write_text(_json.dumps(roadmap), encoding="utf-8")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("x", encoding="utf-8")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "mod.pyc").write_text("x", encoding="utf-8")
        (tmp_path / "real.py").write_text("x", encoding="utf-8")

        with patch("runner.opencode._invoke_opencode", return_value=0) as mock_invoke:
            run_opencode_milestone("## 001 - Release", "0.1.0", tmp_path)

        prompt = mock_invoke.call_args.args[0]
        assert ".git" not in prompt
        assert "__pycache__" not in prompt
        assert "real.py" in prompt


# ── _run_with_log ───────────────────────────────────────────────────────────────


class TestRunWithLog:
    def test_writes_output_to_log(self, tmp_path: Path) -> None:
        from runner.opencode import _run_with_log
        import sys

        log = tmp_path / "out.log"
        cmd = f'{sys.executable} -c "print(\'hello log\')"'
        rc = _run_with_log(cmd, log, echo=False)

        assert rc == 0
        assert log.exists()
        assert "hello log" in log.read_text(encoding="utf-8")

    def test_echo_false_suppresses_stdout(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from runner.opencode import _run_with_log
        import sys

        log = tmp_path / "out.log"
        cmd = f'{sys.executable} -c "print(\'should not appear\')"'
        _run_with_log(cmd, log, echo=False)

        captured = capsys.readouterr()
        assert "should not appear" not in captured.out

    def test_echo_true_streams_to_stdout(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from runner.opencode import _run_with_log
        import sys

        log = tmp_path / "out.log"
        cmd = f'{sys.executable} -c "print(\'streamed output\')"'
        _run_with_log(cmd, log, echo=True)

        captured = capsys.readouterr()
        assert "streamed output" in captured.out

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        from runner.opencode import _run_with_log
        import sys

        log = tmp_path / "deep" / "nested" / "out.log"
        cmd = f'{sys.executable} -c "print(\'nested dirs\')"'
        _run_with_log(cmd, log, echo=False)

        assert log.exists()

    def test_nonzero_exit_code_returned(self, tmp_path: Path) -> None:
        from runner.opencode import _run_with_log
        import sys

        log = tmp_path / "err.log"
        cmd = f'{sys.executable} -c "import sys; sys.exit(42)"'
        rc = _run_with_log(cmd, log, echo=False)

        assert rc == 42


# ── _tail_log ──────────────────────────────────────────────────────────────────────


class TestTailLog:
    def test_prints_last_n_lines(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from runner.opencode import _tail_log

        log = tmp_path / "test.log"
        lines = [f"line {i}" for i in range(100)]
        log.write_text("\n".join(lines), encoding="utf-8")

        _tail_log(log)
        out = capsys.readouterr().out
        # Last line should be present
        assert "line 99" in out
        # Very early lines should not be present (only last 40)
        assert "line 0" not in out

    def test_fewer_lines_than_tail(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from runner.opencode import _tail_log

        log = tmp_path / "short.log"
        log.write_text("only a few\nlines here\n", encoding="utf-8")
        _tail_log(log)  # must not raise
        out = capsys.readouterr().out
        assert "only a few" in out

    def test_missing_file_does_not_raise(self, tmp_path: Path) -> None:
        from runner.opencode import _tail_log

        _tail_log(tmp_path / "nonexistent.log")  # must not raise


# ── _invoke_opencode: echo mode and log filename format ──────────────────────────


class TestInvokeOpencodeLogBehavior:
    """Verify echo mode selection and log-file naming in _invoke_opencode."""

    def _make_project(self, tmp_path: Path) -> Path:
        import json as _j
        project = tmp_path / "proj"
        project.mkdir()
        roadmap = {
            "name": "P", "ecosystem": "python", "preamble": "",
            "tasks": [{"id": 1, "title": "T", "depends_on": []}],
        }
        (project / "ROADMAP.json").write_text(_j.dumps(roadmap), encoding="utf-8")
        return project

    def _patch_invoke(self, monkeypatch: pytest.MonkeyPatch, rc: int = 0) -> "list[dict]":
        """Patch _run_with_log, get_token_stats, record_project_spend; return call-info list."""
        import runner.opencode as oc
        calls: list[dict] = []

        def fake_run(cmd: str, log_path: Path, *, echo: bool) -> int:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("fake\nlog\noutput", encoding="utf-8")
            calls.append({"log_path": log_path, "echo": echo})
            return rc

        monkeypatch.setattr(oc, "_run_with_log", fake_run)
        monkeypatch.setattr(oc, "get_token_stats", lambda: {"total": 0, "input": 0, "output": 0, "cache_read": 0, "cache_write": 0})
        monkeypatch.setattr(oc, "record_project_spend", lambda *a, **kw: 0)
        return calls

    def test_compact_mode_echo_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import runner.config as cfg
        import runner.opencode as oc
        monkeypatch.setattr(cfg, "_verbose", False)
        calls = self._patch_invoke(monkeypatch)
        project = self._make_project(tmp_path)

        oc._invoke_opencode("prompt", agent="build", project_dir=project,
                            continue_session=False, task="## 001 - Test", phase="build")
        assert calls[0]["echo"] is False

    def test_verbose_mode_echo_true(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import runner.config as cfg
        import runner.opencode as oc
        monkeypatch.setattr(cfg, "_verbose", True)
        calls = self._patch_invoke(monkeypatch)
        project = self._make_project(tmp_path)

        oc._invoke_opencode("prompt", agent="build", project_dir=project,
                            continue_session=False, task="## 001 - Test", phase="build")
        assert calls[0]["echo"] is True

    def test_capture_overrides_verbose(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """capture=True must force echo=False even when verbose mode is on."""
        import runner.config as cfg
        import runner.opencode as oc
        monkeypatch.setattr(cfg, "_verbose", True)
        calls = self._patch_invoke(monkeypatch)
        project = self._make_project(tmp_path)

        oc._invoke_opencode("prompt", agent="build", project_dir=project,
                            continue_session=False, task="## 001 - Test", phase="build",
                            capture=True)
        assert calls[0]["echo"] is False

    def test_log_filename_timestamp_first(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Log filename must start with a YYYYMMDD_HHMMSS timestamp."""
        import re as _re
        import runner.config as cfg
        import runner.opencode as oc
        monkeypatch.setattr(cfg, "_verbose", False)
        calls = self._patch_invoke(monkeypatch)
        project = self._make_project(tmp_path)

        oc._invoke_opencode("prompt", agent="build", project_dir=project,
                            continue_session=False, task="## 001 - Test", phase="build")
        log_name = calls[0]["log_path"].name
        assert _re.match(r"^\d{8}_\d{6}_", log_name), f"unexpected log name: {log_name}"

    def test_compact_failure_calls_tail_log(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_tail_log must be called when rc != 0 in compact mode."""
        import runner.config as cfg
        import runner.opencode as oc
        monkeypatch.setattr(cfg, "_verbose", False)
        self._patch_invoke(monkeypatch, rc=1)
        project = self._make_project(tmp_path)

        tailed: list[Path] = []
        monkeypatch.setattr(oc, "_tail_log", lambda p: tailed.append(p))

        oc._invoke_opencode("prompt", agent="build", project_dir=project,
                            continue_session=False, task="## 001 - Test", phase="build")
        assert len(tailed) == 1

    def test_verbose_failure_no_tail(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_tail_log must NOT be called in verbose mode (output already streamed)."""
        import runner.config as cfg
        import runner.opencode as oc
        monkeypatch.setattr(cfg, "_verbose", True)
        self._patch_invoke(monkeypatch, rc=1)
        project = self._make_project(tmp_path)

        tailed: list[Path] = []
        monkeypatch.setattr(oc, "_tail_log", lambda p: tailed.append(p))

        oc._invoke_opencode("prompt", agent="build", project_dir=project,
                            continue_session=False, task="## 001 - Test", phase="build")
        assert tailed == []
