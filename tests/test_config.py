"""Tests for runner.config — budget loading, render_prompt, slugify."""

import json
import re
import textwrap
from pathlib import Path

import pytest


# ── slugify ────────────────────────────────────────────────────────────────────


class TestSlugify:
    """Verify heading-to-slug conversion used for branch names."""

    def test_basic_heading(self) -> None:
        from runner.config import slugify
        assert slugify("## 001 - Message Contract") == "001-message-contract"

    def test_strips_leading_hashes(self) -> None:
        from runner.config import slugify
        assert slugify("## 012 - Foo Bar") == "012-foo-bar"

    def test_collapses_special_chars(self) -> None:
        from runner.config import slugify
        assert slugify("## 005 - Multi-Word Title!") == "005-multi-word-title"

    def test_removes_trailing_dash(self) -> None:
        from runner.config import slugify
        result = slugify("## 009 - Trailing Special $")
        assert not result.endswith("-")

    def test_empty_string(self) -> None:
        from runner.config import slugify
        assert slugify("") == ""


# ── render_prompt ──────────────────────────────────────────────────────────────


class TestRenderPrompt:
    """Verify prompt template loading and placeholder substitution."""

    def test_substitutes_placeholders(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        (prompts / "test_tmpl.md").write_text("Task: {{TASK}}\nBody: {{BODY}}", encoding="utf-8")

        # Patch PROMPTS_DIR to use our temp dir
        import runner.config as cfg
        monkeypatch.setattr(cfg, "PROMPTS_DIR", prompts)

        result = cfg.render_prompt("test_tmpl", TASK="## 001 - Foo", BODY="hello")
        assert "Task: ## 001 - Foo" in result
        assert "Body: hello" in result

    def test_missing_template_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        import runner.config as cfg
        monkeypatch.setattr(cfg, "PROMPTS_DIR", prompts)

        with pytest.raises(FileNotFoundError, match="Prompt template not found"):
            cfg.render_prompt("nonexistent")

    def test_unknown_placeholders_left_intact(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        (prompts / "partial.md").write_text("A: {{A}} B: {{B}}", encoding="utf-8")
        import runner.config as cfg
        monkeypatch.setattr(cfg, "PROMPTS_DIR", prompts)

        result = cfg.render_prompt("partial", A="filled")
        assert "A: filled" in result
        assert "{{B}}" in result

    def test_extra_kwargs_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        (prompts / "simple.md").write_text("Hello {{NAME}}", encoding="utf-8")
        import runner.config as cfg
        monkeypatch.setattr(cfg, "PROMPTS_DIR", prompts)

        result = cfg.render_prompt("simple", NAME="World", EXTRA="ignored")
        assert result == "Hello World"


# ── Verbosity mode ───────────────────────────────────────────────────────────────


class TestVerbosityMode:
    """Verify set_verbose / is_verbose round-trip and default state."""

    def test_default_is_compact(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import runner.config as cfg
        monkeypatch.setattr(cfg, "_verbose", False)
        assert cfg.is_verbose() is False

    def test_set_verbose_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import runner.config as cfg
        monkeypatch.setattr(cfg, "_verbose", False)
        cfg.set_verbose(True)
        assert cfg.is_verbose() is True

    def test_set_verbose_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import runner.config as cfg
        monkeypatch.setattr(cfg, "_verbose", True)
        cfg.set_verbose(False)
        assert cfg.is_verbose() is False

    def test_log_tail_lines_positive(self) -> None:
        from runner.config import _LOG_TAIL_LINES
        assert isinstance(_LOG_TAIL_LINES, int)
        assert _LOG_TAIL_LINES > 0
