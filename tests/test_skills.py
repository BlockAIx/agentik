"""Tests for runner.skills — skill discovery, loading, and prompt injection."""

import json
from pathlib import Path

import pytest


@pytest.fixture()
def skills_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary skills directory and patch the module to use it."""
    sd = tmp_path / "skills"
    sd.mkdir()
    import runner.skills as mod

    monkeypatch.setattr(mod, "_SKILLS_DIR", sd)
    return sd


@pytest.fixture()
def two_skills(skills_dir: Path) -> Path:
    """Set up two skills: alpha and beta."""
    alpha = skills_dir / "alpha"
    alpha.mkdir()
    (alpha / "SKILL.md").write_text("# Alpha\nDo alpha things.", encoding="utf-8")
    (alpha / "skill.json").write_text(
        json.dumps({"name": "Alpha Skill", "description": "Alpha desc", "agents": ["build"]}),
        encoding="utf-8",
    )

    beta = skills_dir / "beta"
    beta.mkdir()
    (beta / "SKILL.md").write_text("# Beta\nDo beta things.", encoding="utf-8")
    # No skill.json — should fall back to defaults.
    return skills_dir


class TestListSkills:
    def test_empty_dir(self, skills_dir: Path) -> None:
        from runner.skills import list_skills

        assert list_skills() == []

    def test_discovers_skills(self, two_skills: Path) -> None:
        from runner.skills import list_skills

        result = list_skills()
        slugs = [s["slug"] for s in result]
        assert "alpha" in slugs
        assert "beta" in slugs

    def test_metadata_from_json(self, two_skills: Path) -> None:
        from runner.skills import list_skills

        alpha = next(s for s in list_skills() if s["slug"] == "alpha")
        assert alpha["name"] == "Alpha Skill"
        assert alpha["description"] == "Alpha desc"
        assert alpha["agents"] == ["build"]

    def test_metadata_fallback(self, two_skills: Path) -> None:
        from runner.skills import list_skills

        beta = next(s for s in list_skills() if s["slug"] == "beta")
        assert beta["name"] == "beta"
        assert beta["description"] == ""
        assert beta["agents"] == ["build", "architect"]

    def test_ignores_dir_without_skill_md(self, skills_dir: Path) -> None:
        from runner.skills import list_skills

        (skills_dir / "empty").mkdir()
        assert list_skills() == []


class TestGetSkillContent:
    def test_reads_content(self, two_skills: Path) -> None:
        from runner.skills import get_skill_content

        content = get_skill_content("alpha")
        assert content is not None
        assert "Do alpha things" in content

    def test_missing_skill(self, skills_dir: Path) -> None:
        from runner.skills import get_skill_content

        assert get_skill_content("nonexistent") is None


class TestAgentSkills:
    def test_get_and_save(self, two_skills: Path, tmp_path: Path) -> None:
        from runner.skills import get_agent_skills, save_agent_skills

        project = tmp_path / "proj"
        project.mkdir()

        # Initially empty.
        assert get_agent_skills("build", project) == []

        # Save and reload.
        save_agent_skills("build", project, ["alpha", "beta"])
        assert get_agent_skills("build", project) == ["alpha", "beta"]

        # Verify the file was written.
        config = json.loads((project / "opencode.jsonc").read_text(encoding="utf-8"))
        assert config["agent"]["build"]["skills"] == ["alpha", "beta"]

    def test_preserves_existing_config(self, two_skills: Path, tmp_path: Path) -> None:
        from runner.skills import get_agent_skills, save_agent_skills

        project = tmp_path / "proj"
        project.mkdir()
        (project / "opencode.jsonc").write_text(
            json.dumps({"agent": {"build": {"model": "test-model"}}}),
            encoding="utf-8",
        )

        save_agent_skills("build", project, ["alpha"])
        config = json.loads((project / "opencode.jsonc").read_text(encoding="utf-8"))
        assert config["agent"]["build"]["model"] == "test-model"
        assert config["agent"]["build"]["skills"] == ["alpha"]


class TestCollectSkillBlocks:
    def test_returns_empty_when_no_skills(self, two_skills: Path, tmp_path: Path) -> None:
        from runner.skills import collect_skill_blocks

        project = tmp_path / "proj"
        project.mkdir()
        assert collect_skill_blocks("build", project) == ""

    def test_collects_assigned_skills(self, two_skills: Path, tmp_path: Path) -> None:
        from runner.skills import collect_skill_blocks, save_agent_skills

        project = tmp_path / "proj"
        project.mkdir()
        save_agent_skills("build", project, ["alpha"])

        block = collect_skill_blocks("build", project)
        assert "## Skills" in block
        assert "Do alpha things" in block
        assert "beta" not in block.lower() or "Do beta things" not in block

    def test_multiple_skills(self, two_skills: Path, tmp_path: Path) -> None:
        from runner.skills import collect_skill_blocks, save_agent_skills

        project = tmp_path / "proj"
        project.mkdir()
        save_agent_skills("build", project, ["alpha", "beta"])

        block = collect_skill_blocks("build", project)
        assert "Do alpha things" in block
        assert "Do beta things" in block

    def test_rewrites_skill_paths(self, skills_dir: Path, tmp_path: Path) -> None:
        """Self-referencing paths like skills/<slug>/ are rewritten to absolute."""
        from runner.skills import collect_skill_blocks, save_agent_skills

        gamma = skills_dir / "gamma"
        gamma.mkdir()
        (gamma / "SKILL.md").write_text(
            "Run `python3 skills/gamma/scripts/search.py`", encoding="utf-8"
        )
        project = tmp_path / "proj"
        project.mkdir()
        save_agent_skills("build", project, ["gamma"])

        block = collect_skill_blocks("build", project)
        resolved = str(gamma.resolve())
        assert resolved in block
        assert "skills/gamma/" not in block
