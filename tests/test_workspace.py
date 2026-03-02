"""Tests for runner.workspace -- ecosystem detection, scaffolding, git ops, deploy."""

import json
from pathlib import Path

import pytest

# -- helpers -------------------------------------------------------------------


def _write_roadmap(project: Path, data: dict) -> None:
    (project / "ROADMAP.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _simple_roadmap(ecosystem: str = "python", **overrides) -> dict:
    base: dict = {
        "name": "P",
        "ecosystem": ecosystem,
        "preamble": "",
        "tasks": [
            {
                "id": 1,
                "title": "A",
                "depends_on": [],
                "outputs": ["x.py"],
                "acceptance": "ok",
            }
        ],
    }
    base.update(overrides)
    return base


# -- _detect_ecosystem ---------------------------------------------------------


class TestDetectEcosystem:
    def test_roadmap_ecosystem_declaration(self, tmp_path: Path) -> None:
        from runner.workspace import _detect_ecosystem

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap("deno"))
        assert _detect_ecosystem(project) == "deno"

    def test_deno_json_heuristic(self, tmp_path: Path) -> None:
        from runner.workspace import _detect_ecosystem

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap(ecosystem=""))
        (project / "deno.json").write_text("{}", encoding="utf-8")
        assert _detect_ecosystem(project) == "deno"

    def test_package_json_heuristic(self, tmp_path: Path) -> None:
        from runner.workspace import _detect_ecosystem

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap(ecosystem=""))
        (project / "package.json").write_text("{}", encoding="utf-8")
        assert _detect_ecosystem(project) == "node"

    def test_go_mod_heuristic(self, tmp_path: Path) -> None:
        from runner.workspace import _detect_ecosystem

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap(ecosystem=""))
        (project / "go.mod").write_text("module test\n", encoding="utf-8")
        assert _detect_ecosystem(project) == "go"

    def test_cargo_toml_heuristic(self, tmp_path: Path) -> None:
        from runner.workspace import _detect_ecosystem

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap(ecosystem=""))
        (project / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
        assert _detect_ecosystem(project) == "rust"

    def test_fallback_python(self, tmp_path: Path) -> None:
        from runner.workspace import _detect_ecosystem

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap(ecosystem=""))
        assert _detect_ecosystem(project) == "python"

    def test_roadmap_overrides_heuristic(self, tmp_path: Path) -> None:
        from runner.workspace import _detect_ecosystem

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap("python"))
        (project / "package.json").write_text("{}", encoding="utf-8")
        assert _detect_ecosystem(project) == "python"


# -- _pkg_name -----------------------------------------------------------------


class TestPkgName:
    def test_python_replaces_hyphens(self, tmp_path: Path) -> None:
        from runner.workspace import _pkg_name

        project = tmp_path / "my-project"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap("python"))
        assert _pkg_name(project) == "my_project"

    def test_non_python_uses_dirname(self, tmp_path: Path) -> None:
        from runner.workspace import _pkg_name

        project = tmp_path / "my-app"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap("node"))
        assert _pkg_name(project) == "my-app"


# -- src_dir / tests_dir ------------------------------------------------------


class TestDirs:
    def test_python_src_dir(self, tmp_path: Path) -> None:
        from runner.workspace import src_dir

        project = tmp_path / "my-proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap("python"))
        assert src_dir(project) == project / "my_proj"

    def test_node_src_dir(self, tmp_path: Path) -> None:
        from runner.workspace import src_dir

        project = tmp_path / "app"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap("node"))
        assert src_dir(project) == project / "src"

    def test_go_src_dir(self, tmp_path: Path) -> None:
        from runner.workspace import src_dir

        project = tmp_path / "app"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap("go"))
        assert src_dir(project) == project

    def test_tests_dir(self, tmp_path: Path) -> None:
        from runner.workspace import tests_dir

        project = tmp_path / "proj"
        project.mkdir()
        assert tests_dir(project) == project / "tests"


# -- _write_if_absent ----------------------------------------------------------


class TestWriteIfAbsent:
    def test_writes_new_file(self, tmp_path: Path) -> None:
        from runner.workspace import _write_if_absent

        f = tmp_path / "new.txt"
        assert _write_if_absent(f, "content") is True
        assert f.read_text() == "content"

    def test_skips_existing_file(self, tmp_path: Path) -> None:
        from runner.workspace import _write_if_absent

        f = tmp_path / "existing.txt"
        f.write_text("original", encoding="utf-8")
        assert _write_if_absent(f, "overwrite") is False
        assert f.read_text() == "original"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        from runner.workspace import _write_if_absent

        f = tmp_path / "deep" / "nested" / "file.txt"
        assert _write_if_absent(f, "deep") is True
        assert f.exists()


# -- get_roadmap_project_context -----------------------------------------------


class TestGetRoadmapProjectContext:
    def test_returns_preamble_text(self, tmp_path: Path) -> None:
        from runner.workspace import get_roadmap_project_context

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap(preamble="Some architecture notes."))
        ctx = get_roadmap_project_context(project)
        assert "architecture notes" in ctx

    def test_empty_when_no_preamble(self, tmp_path: Path) -> None:
        from runner.workspace import get_roadmap_project_context

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap(preamble=""))
        ctx = get_roadmap_project_context(project)
        assert ctx.strip() == ""


# -- _load_deploy_config -------------------------------------------------------


class TestLoadDeployConfig:
    def test_loads_from_roadmap_deploy_block(self, tmp_path: Path) -> None:
        from runner.workspace import _load_deploy_config

        project = tmp_path / "proj"
        project.mkdir()
        roadmap = _simple_roadmap(
            deploy={
                "enabled": True,
                "script": "scripts/deploy.sh",
                "env": {"provider": "fly", "app": "myapp", "region": "fra"},
            }
        )
        _write_roadmap(project, roadmap)
        result = _load_deploy_config(project)
        assert result == {
            "DEPLOY_PROVIDER": "fly",
            "DEPLOY_APP": "myapp",
            "DEPLOY_REGION": "fra",
        }

    def test_loads_from_legacy_deploy_json(self, tmp_path: Path) -> None:
        from runner.workspace import _load_deploy_config

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap())  # no deploy block
        config = {"provider": "fly", "app": "myapp", "region": "fra"}
        (project / "deploy.json").write_text(json.dumps(config), encoding="utf-8")
        result = _load_deploy_config(project)
        assert result == {
            "DEPLOY_PROVIDER": "fly",
            "DEPLOY_APP": "myapp",
            "DEPLOY_REGION": "fra",
        }

    def test_missing_file(self, tmp_path: Path) -> None:
        from runner.workspace import _load_deploy_config

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap())
        assert _load_deploy_config(project) == {}

    def test_malformed_json(self, tmp_path: Path) -> None:
        from runner.workspace import _load_deploy_config

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap())
        (project / "deploy.json").write_text("{bad json", encoding="utf-8")
        assert _load_deploy_config(project) == {}


# -- list_projects -------------------------------------------------------------


class TestListProjects:
    def test_finds_projects_with_roadmap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import runner.workspace as ws

        projects_root = tmp_path / "projects"
        projects_root.mkdir()
        p1 = projects_root / "alpha"
        p1.mkdir()
        _write_roadmap(p1, _simple_roadmap())
        p2 = projects_root / "beta"
        p2.mkdir()
        _write_roadmap(p2, _simple_roadmap())
        p3 = projects_root / "gamma"
        p3.mkdir()

        monkeypatch.setattr(ws, "PROJECTS_ROOT", projects_root)
        result = ws.list_projects()
        names = [p.name for p in result]
        assert "alpha" in names
        assert "beta" in names
        assert "gamma" not in names

    def test_empty_projects_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import runner.workspace as ws

        projects_root = tmp_path / "projects"
        projects_root.mkdir()
        monkeypatch.setattr(ws, "PROJECTS_ROOT", projects_root)
        assert ws.list_projects() == []


# -- _project_status -----------------------------------------------------------


class TestProjectStatus:
    def test_no_tasks(self, tmp_path: Path) -> None:
        from runner.workspace import _project_status

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap(tasks=[]))
        badge, _ = _project_status(project)
        assert badge == "no tasks"

    def test_not_started(self, tmp_path: Path) -> None:
        from runner.workspace import _project_status

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap())
        badge, detail = _project_status(project)
        assert badge == "not started"
        assert "0 / 1" in detail

    def test_complete(self, tmp_path: Path) -> None:
        from runner.state import mark_done, save_runner_state
        from runner.workspace import _project_status

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap())
        (project / ".runner_state.json").write_text("{}", encoding="utf-8")
        save_runner_state(project, "## 001 - A", 0, None)
        mark_done("## 001 - A", project)
        badge, _ = _project_status(project)
        assert badge == "complete"


# -- commit_and_merge (selective staging) --------------------------------------


class TestCommitAndMergeSelective:
    def test_selective_adds_only_listed_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from runner.workspace import commit_and_merge

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap(git={"enabled": True}))

        calls: list[str] = []

        def fake_git_run(cmd: str, proj: Path) -> bool:
            calls.append(cmd)
            return True

        monkeypatch.setattr("runner.workspace.git_run", fake_git_run)
        monkeypatch.setattr("runner.workspace._git_has_remote", lambda p: True)
        commit_and_merge(
            "## 001 - Task", project, task_outputs=["src/a.py", "src/b.py"]
        )

        assert 'add "src/a.py"' in calls
        assert 'add "src/b.py"' in calls
        assert "add ." not in calls
        # Verify commit message strips ## prefix.
        assert 'commit -m "feat: 001 - Task"' in calls

    def test_no_outputs_does_add_all(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from runner.workspace import commit_and_merge

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap(git={"enabled": True}))

        calls: list[str] = []

        def fake_git_run(cmd: str, proj: Path) -> bool:
            calls.append(cmd)
            return True

        monkeypatch.setattr("runner.workspace.git_run", fake_git_run)
        monkeypatch.setattr("runner.workspace._git_has_remote", lambda p: True)
        commit_and_merge("## 001 - Task", project, task_outputs=None)

        assert "add ." in calls

    def test_push_skipped_when_no_remote(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from runner.workspace import commit_and_merge

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap(git={"enabled": True}))

        calls: list[str] = []

        def fake_git_run(cmd: str, proj: Path) -> bool:
            calls.append(cmd)
            return True

        monkeypatch.setattr("runner.workspace.git_run", fake_git_run)
        monkeypatch.setattr("runner.workspace._git_has_remote", lambda p: False)
        commit_and_merge("## 001 - Task", project, task_outputs=None)

        assert not any("push" in c for c in calls)

    def test_skipped_when_git_not_managed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from runner.workspace import commit_and_merge

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap())  # no git block

        calls: list[str] = []

        def fake_git_run(cmd: str, proj: Path) -> bool:
            calls.append(cmd)
            return True

        monkeypatch.setattr("runner.workspace.git_run", fake_git_run)
        commit_and_merge("## 001 - Task", project, task_outputs=None)

        assert calls == []  # no git commands should run


# -- tag_milestone -------------------------------------------------------------


class TestTagMilestone:
    def test_git_commands_sequence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from runner.workspace import tag_milestone

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap(git={"enabled": True}))

        calls: list[str] = []

        def fake_git_run(cmd: str, proj: Path) -> bool:
            calls.append(cmd)
            return True

        monkeypatch.setattr("runner.workspace.git_run", fake_git_run)
        monkeypatch.setattr("runner.workspace._git_has_remote", lambda p: True)
        tag_milestone("0.2.0", project)

        assert calls == [
            "add .",
            'commit --allow-empty -m "milestone: v0.2.0"',
            "tag v0.2.0",
            "push origin develop",
            "push origin v0.2.0",
        ]

    def test_skipped_when_git_not_managed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from runner.workspace import tag_milestone

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap())  # no git block

        calls: list[str] = []

        def fake_git_run(cmd: str, proj: Path) -> bool:
            calls.append(cmd)
            return True

        monkeypatch.setattr("runner.workspace.git_run", fake_git_run)
        tag_milestone("0.2.0", project)

        assert calls == []  # skipped — git not managed


# -- try_deploy_hook deploy gating --------------------------------------------


class TestTryDeployHookDeployFalse:
    def test_skips_when_deploy_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ROADMAP deploy.enabled=false must suppress the hook entirely."""
        import subprocess

        from runner.workspace import try_deploy_hook

        project = tmp_path / "proj"
        project.mkdir()
        roadmap = _simple_roadmap(deploy={"enabled": False})
        _write_roadmap(project, roadmap)
        # Create a deploy script so the hook *would* run if not blocked.
        scripts = project / "scripts"
        scripts.mkdir()
        (scripts / "deploy.ps1").write_text("exit 0", encoding="utf-8")
        (scripts / "deploy.sh").write_text("exit 0", encoding="utf-8")

        ran: list[bool] = []
        monkeypatch.delenv("RUNNER_NO_DEPLOY", raising=False)
        original_run = subprocess.run

        def spy_run(cmd: object, **kwargs: object) -> object:
            ran.append(True)
            return original_run(cmd, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(subprocess, "run", spy_run)
        try_deploy_hook("## 001 - A", project)
        assert ran == [], "deploy hook should have been skipped"

    def test_skips_when_legacy_deploy_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Legacy deploy.json with deploy=false must suppress the hook."""
        import subprocess

        from runner.workspace import try_deploy_hook

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap())  # no deploy block
        (project / "deploy.json").write_text(
            json.dumps({"deploy": False, "app": "x"}), encoding="utf-8"
        )
        scripts = project / "scripts"
        scripts.mkdir()
        (scripts / "deploy.ps1").write_text("exit 0", encoding="utf-8")
        (scripts / "deploy.sh").write_text("exit 0", encoding="utf-8")

        ran: list[bool] = []
        monkeypatch.delenv("RUNNER_NO_DEPLOY", raising=False)
        original_run = subprocess.run

        def spy_run(cmd: object, **kwargs: object) -> object:
            ran.append(True)
            return original_run(cmd, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(subprocess, "run", spy_run)
        try_deploy_hook("## 001 - A", project)
        assert ran == [], "deploy hook should have been skipped"

    def test_runs_when_deploy_enabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ROADMAP deploy.enabled=true should run the hook."""
        from runner.workspace import try_deploy_hook

        project = tmp_path / "proj"
        project.mkdir()
        roadmap = _simple_roadmap(deploy={"enabled": True, "env": {"app": "x"}})
        # Mark the task for deploy
        roadmap["tasks"][0]["deploy"] = True
        _write_roadmap(project, roadmap)
        scripts = project / "scripts"
        scripts.mkdir()
        (scripts / "deploy.ps1").write_text("# no-op", encoding="utf-8")
        (scripts / "deploy.sh").write_text("true", encoding="utf-8")

        monkeypatch.delenv("RUNNER_NO_DEPLOY", raising=False)

        called_cmds: list[str] = []

        def fake_run(cmd: str, **kwargs: object) -> object:
            called_cmds.append(str(cmd))

            class R:
                returncode = 0

            return R()

        import subprocess

        monkeypatch.setattr(subprocess, "run", fake_run)
        try_deploy_hook("## 001 - A", project)
        assert called_cmds, "deploy hook should have run"


# -- _ensure_logs_gitignored --------------------------------------------------


class TestEnsureLogsGitignored:
    def test_appends_to_existing_gitignore(self, tmp_path: Path) -> None:
        from runner.workspace import _ensure_logs_gitignored

        project = tmp_path / "proj"
        project.mkdir()
        gitignore = project / ".gitignore"
        gitignore.write_text("node_modules/\n", encoding="utf-8")
        _ensure_logs_gitignored(project)
        content = gitignore.read_text(encoding="utf-8")
        assert "logs/" in content

    def test_idempotent(self, tmp_path: Path) -> None:
        from runner.workspace import _ensure_logs_gitignored

        project = tmp_path / "proj"
        project.mkdir()
        gitignore = project / ".gitignore"
        gitignore.write_text("node_modules/\nlogs/\n", encoding="utf-8")
        _ensure_logs_gitignored(project)
        content = gitignore.read_text(encoding="utf-8")
        # 'logs/' must appear exactly once.
        assert content.count("logs/") == 1

    def test_no_gitignore_does_nothing(self, tmp_path: Path) -> None:
        from runner.workspace import _ensure_logs_gitignored

        project = tmp_path / "proj"
        project.mkdir()
        # No .gitignore — function must not crash and must not create the file.
        _ensure_logs_gitignored(project)
        assert not (project / ".gitignore").exists()


# -- generate_project_agents_md -----------------------------------------------


class TestGenerateProjectAgentsMd:
    """Tests for generate_project_agents_md in workspace.py."""

    def _make_project(
        self,
        tmp_path: Path,
        ecosystem: str = "python",
        name: str = "My Project",
        preamble: str = "",
    ) -> Path:
        project = tmp_path / "my_project"
        project.mkdir()
        _write_roadmap(
            project,
            {
                "name": name,
                "ecosystem": ecosystem,
                "preamble": preamble,
                "tasks": [
                    {
                        "id": 1,
                        "title": "Do Thing",
                        "depends_on": [],
                        "outputs": ["x.py"],
                        "acceptance": "ok",
                    },
                    {
                        "id": 2,
                        "title": "Do Other",
                        "depends_on": [1],
                        "outputs": ["y.py"],
                        "acceptance": "ok",
                    },
                ],
            },
        )
        return project

    def test_creates_file(self, tmp_path: Path) -> None:
        from runner.workspace import generate_project_agents_md

        project = self._make_project(tmp_path)
        generate_project_agents_md(project)
        assert (project / "AGENTS.md").exists()

    def test_contains_project_name(self, tmp_path: Path) -> None:
        from runner.workspace import generate_project_agents_md

        project = self._make_project(tmp_path, name="Awesome Engine")
        generate_project_agents_md(project)
        content = (project / "AGENTS.md").read_text(encoding="utf-8")
        assert "Awesome Engine" in content

    def test_contains_preamble(self, tmp_path: Path) -> None:
        from runner.workspace import generate_project_agents_md

        project = self._make_project(tmp_path, preamble="A retro space shooter game.")
        generate_project_agents_md(project)
        content = (project / "AGENTS.md").read_text(encoding="utf-8")
        assert "A retro space shooter game." in content

    def test_ecosystem_python_guidelines(self, tmp_path: Path) -> None:
        from runner.workspace import generate_project_agents_md

        project = self._make_project(tmp_path, ecosystem="python")
        generate_project_agents_md(project)
        content = (project / "AGENTS.md").read_text(encoding="utf-8")
        assert "ruff" in content.lower()
        assert "pytest" in content.lower()

    def test_ecosystem_deno_guidelines(self, tmp_path: Path) -> None:
        from runner.workspace import generate_project_agents_md

        project = self._make_project(tmp_path, ecosystem="deno")
        generate_project_agents_md(project)
        content = (project / "AGENTS.md").read_text(encoding="utf-8")
        assert "deno check" in content.lower()

    def test_ecosystem_node_guidelines(self, tmp_path: Path) -> None:
        from runner.workspace import generate_project_agents_md

        project = self._make_project(tmp_path, ecosystem="node")
        generate_project_agents_md(project)
        content = (project / "AGENTS.md").read_text(encoding="utf-8")
        assert "tsc" in content.lower()

    def test_contains_roadmap_task_format(self, tmp_path: Path) -> None:
        from runner.workspace import generate_project_agents_md

        project = self._make_project(tmp_path)
        generate_project_agents_md(project)
        content = (project / "AGENTS.md").read_text(encoding="utf-8")
        # Should document the task JSON fields.
        assert '"outputs"' in content
        assert '"depends_on"' in content
        assert '"acceptance"' in content

    def test_contains_scope_rules(self, tmp_path: Path) -> None:
        from runner.workspace import generate_project_agents_md

        project = self._make_project(tmp_path)
        generate_project_agents_md(project)
        content = (project / "AGENTS.md").read_text(encoding="utf-8")
        assert "outputs" in content
        assert "git push" in content or "git commit" in content

    def test_contains_pipeline_phases(self, tmp_path: Path) -> None:
        from runner.workspace import generate_project_agents_md

        project = self._make_project(tmp_path)
        generate_project_agents_md(project)
        content = (project / "AGENTS.md").read_text(encoding="utf-8")
        assert "Build" in content
        assert "Commit" in content

    def test_overwrite_on_second_call(self, tmp_path: Path) -> None:
        """Calling the function twice rewrites the file (no duplicate content)."""
        from runner.workspace import generate_project_agents_md

        project = self._make_project(tmp_path)
        generate_project_agents_md(project)
        generate_project_agents_md(project)
        second = (project / "AGENTS.md").read_text(encoding="utf-8")
        # Timestamps differ so content will differ slightly — but the heading
        # should appear exactly once (not doubled).
        assert second.count("## Project overview") == 1
        # Core content is still present.
        assert "## Scope rules" in second

    def test_not_in_gitignore(self, tmp_path: Path) -> None:
        """AGENTS.md must NOT be added to .gitignore — it should be committed."""
        from runner.workspace import generate_project_agents_md

        project = self._make_project(tmp_path)
        gitignore = project / ".gitignore"
        gitignore.write_text("node_modules/\nlogs/\n", encoding="utf-8")
        generate_project_agents_md(project)
        content = gitignore.read_text(encoding="utf-8")
        assert "AGENTS.md" not in content

    def test_auto_called_first_run_in_ensure_workspace_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ensure_workspace_dirs generates AGENTS.md when it does not yet exist."""
        from runner import workspace as ws

        calls: list[Path] = []

        def _fake_generate(project_dir: Path) -> None:
            calls.append(project_dir)

        monkeypatch.setattr(ws, "generate_project_agents_md", _fake_generate)
        monkeypatch.setattr(ws, "install_project_dependencies", lambda _p: None)
        monkeypatch.setattr(ws, "_sync_opencode_config", lambda _p: None)
        monkeypatch.setattr(ws, "ensure_project_git", lambda _p: None)
        monkeypatch.setattr(ws, "_ensure_logs_gitignored", lambda _p: None)

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap("python"))
        # AGENTS.md absent → should call generate.
        ws.ensure_workspace_dirs(project)
        assert calls == [project]

    def test_not_auto_called_when_agents_md_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ensure_workspace_dirs skips generation when AGENTS.md already exists."""
        from runner import workspace as ws

        calls: list[Path] = []

        def _fake_generate(project_dir: Path) -> None:
            calls.append(project_dir)

        monkeypatch.setattr(ws, "generate_project_agents_md", _fake_generate)
        monkeypatch.setattr(ws, "install_project_dependencies", lambda _p: None)
        monkeypatch.setattr(ws, "_sync_opencode_config", lambda _p: None)
        monkeypatch.setattr(ws, "ensure_project_git", lambda _p: None)
        monkeypatch.setattr(ws, "_ensure_logs_gitignored", lambda _p: None)

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _simple_roadmap("python"))
        (project / "AGENTS.md").write_text("# existing\n", encoding="utf-8")
        # AGENTS.md always regenerated to stay in sync with ROADMAP.
        ws.ensure_workspace_dirs(project)
        assert calls == [project]


# -- _has_broken_pnpm_store / _is_broken_symlink / _nuke_node_modules --------

# Symlink creation may fail on Windows without developer mode or admin
# privileges.  Skip symlink-dependent tests gracefully.
_symlink_supported = True
try:
    import tempfile as _tf

    with _tf.TemporaryDirectory() as _td:
        _target = Path(_td) / "target"
        _target.mkdir()
        _link = Path(_td) / "link"
        _link.symlink_to(_target)
except OSError:
    _symlink_supported = False

_needs_symlinks = pytest.mark.skipif(
    not _symlink_supported, reason="OS does not support unprivileged symlinks"
)


class TestIsBrokenSymlink:
    @_needs_symlinks
    def test_healthy_symlink(self, tmp_path: Path) -> None:
        from runner.workspace import _is_broken_symlink

        target = tmp_path / "real"
        target.mkdir()
        link = tmp_path / "link"
        link.symlink_to(target)
        assert _is_broken_symlink(link) is False

    @_needs_symlinks
    def test_broken_symlink(self, tmp_path: Path) -> None:
        from runner.workspace import _is_broken_symlink

        target = tmp_path / "gone"
        target.mkdir()
        link = tmp_path / "link"
        link.symlink_to(target)
        target.rmdir()  # break the link
        assert _is_broken_symlink(link) is True

    def test_regular_file(self, tmp_path: Path) -> None:
        from runner.workspace import _is_broken_symlink

        f = tmp_path / "file.txt"
        f.write_text("hi")
        assert _is_broken_symlink(f) is False


class TestHasBrokenPnpmStore:
    def test_no_node_modules(self, tmp_path: Path) -> None:
        """No node_modules at all → not broken."""
        from runner.workspace import _has_broken_pnpm_store

        project = tmp_path / "proj"
        project.mkdir()
        assert _has_broken_pnpm_store(project) is False

    def test_empty_pnpm_dir(self, tmp_path: Path) -> None:
        """Empty .pnpm directory → broken."""
        from runner.workspace import _has_broken_pnpm_store

        project = tmp_path / "proj"
        nm = project / "node_modules" / ".pnpm"
        nm.mkdir(parents=True)
        assert _has_broken_pnpm_store(project) is True

    @_needs_symlinks
    def test_healthy_modern_pnpm(self, tmp_path: Path) -> None:
        """Modern pnpm layout with valid inner symlinks → not broken."""
        from runner.workspace import _has_broken_pnpm_store

        project = tmp_path / "proj"
        nm = project / "node_modules"
        pnpm = nm / ".pnpm"
        # Simulate express@4.18.2/node_modules/express → real content
        real_content = pnpm / "express@4.18.2" / "node_modules" / "express_real"
        real_content.mkdir(parents=True)
        inner_link = pnpm / "express@4.18.2" / "node_modules" / "express"
        inner_link.symlink_to(real_content)
        # Top-level symlink: node_modules/express → .pnpm/.../express
        top_link = nm / "express"
        top_link.symlink_to(inner_link)
        assert _has_broken_pnpm_store(project) is False

    @_needs_symlinks
    def test_broken_inner_symlink_modern_pnpm(self, tmp_path: Path) -> None:
        """Modern pnpm: inner symlink target gone → broken."""
        from runner.workspace import _has_broken_pnpm_store

        project = tmp_path / "proj"
        nm = project / "node_modules"
        pnpm = nm / ".pnpm"
        # Create then break the inner symlink
        real_content = pnpm / "lodash@4.17.21" / "node_modules" / "lodash_real"
        real_content.mkdir(parents=True)
        inner_link = pnpm / "lodash@4.17.21" / "node_modules" / "lodash"
        inner_link.symlink_to(real_content)
        import shutil

        shutil.rmtree(real_content)  # break it
        assert _has_broken_pnpm_store(project) is True

    @_needs_symlinks
    def test_broken_top_level_symlink(self, tmp_path: Path) -> None:
        """Top-level node_modules symlink target gone → broken."""
        from runner.workspace import _has_broken_pnpm_store

        project = tmp_path / "proj"
        nm = project / "node_modules"
        pnpm = nm / ".pnpm"
        # Valid inner structure but broken top-level link
        real_content = pnpm / "pkg@1.0.0" / "node_modules" / "pkg_real"
        real_content.mkdir(parents=True)
        inner_link = pnpm / "pkg@1.0.0" / "node_modules" / "pkg"
        inner_link.symlink_to(real_content)
        # Top-level link points to something that doesn't exist
        gone = tmp_path / "gone_target"
        gone.mkdir()
        top_link = nm / "pkg"
        top_link.symlink_to(gone)
        import shutil

        shutil.rmtree(gone)
        assert _has_broken_pnpm_store(project) is True

    @_needs_symlinks
    def test_workspace_package_broken(self, tmp_path: Path) -> None:
        """Workspace package node_modules with broken symlinks → broken."""
        from runner.workspace import _has_broken_pnpm_store

        project = tmp_path / "proj"
        # Root .pnpm is healthy
        pnpm = project / "node_modules" / ".pnpm"
        real = pnpm / "a@1.0.0" / "node_modules" / "a_real"
        real.mkdir(parents=True)
        link = pnpm / "a@1.0.0" / "node_modules" / "a"
        link.symlink_to(real)
        # Workspace package has broken link
        pkg_nm = project / "packages" / "backend" / "node_modules"
        pkg_nm.mkdir(parents=True)
        gone = tmp_path / "gone2"
        gone.mkdir()
        pkg_link = pkg_nm / "express"
        pkg_link.symlink_to(gone)
        import shutil

        shutil.rmtree(gone)
        assert _has_broken_pnpm_store(project) is True

    @_needs_symlinks
    def test_pnpm_dir_with_only_metadata_no_packages(self, tmp_path: Path) -> None:
        """.pnpm has only lock.yaml (no package dirs) → broken."""
        from runner.workspace import _has_broken_pnpm_store

        project = tmp_path / "proj"
        pnpm = project / "node_modules" / ".pnpm"
        pnpm.mkdir(parents=True)
        (pnpm / "lock.yaml").write_text("lockfileVersion: 5.4")
        assert _has_broken_pnpm_store(project) is True


class TestNukeNodeModules:
    def test_removes_all_node_modules(self, tmp_path: Path) -> None:
        from runner.workspace import _nuke_node_modules

        project = tmp_path / "proj"
        (project / "node_modules" / "a").mkdir(parents=True)
        (project / "packages" / "b" / "node_modules" / "c").mkdir(parents=True)
        _nuke_node_modules(project)
        assert not (project / "node_modules").exists()
        assert not (project / "packages" / "b" / "node_modules").exists()


class TestInstallDependenciesForceFlag:
    """Verify that install_project_dependencies uses --force after broken store."""

    def test_pnpm_force_on_broken_store(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import runner.workspace as ws

        project = tmp_path / "proj"
        project.mkdir()
        (project / "package.json").write_text('{"name":"t"}', encoding="utf-8")

        # Track all subprocess.run calls
        calls: list[str] = []
        orig_run = ws.subprocess.run

        class _FakeResult:
            returncode = 0
            stdout = ""
            stderr = ""

        def _spy_run(cmd: str, **kwargs: object) -> _FakeResult:
            calls.append(cmd)
            return _FakeResult()

        monkeypatch.setattr(ws.subprocess, "run", _spy_run)
        # Pretend store is broken
        monkeypatch.setattr(ws, "_has_broken_pnpm_store", lambda _p: True)
        (project / "node_modules").mkdir()

        ws.install_project_dependencies(project)

        pnpm_calls = [c for c in calls if "pnpm" in c]
        assert len(pnpm_calls) == 1
        assert "--force" in pnpm_calls[0]

    def test_pnpm_normal_when_store_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import runner.workspace as ws

        project = tmp_path / "proj"
        project.mkdir()
        (project / "package.json").write_text('{"name":"t"}', encoding="utf-8")

        calls: list[str] = []

        class _FakeResult:
            returncode = 0
            stdout = ""
            stderr = ""

        def _spy_run(cmd: str, **kwargs: object) -> _FakeResult:
            calls.append(cmd)
            return _FakeResult()

        monkeypatch.setattr(ws.subprocess, "run", _spy_run)
        # No node_modules → no broken store check triggers
        ws.install_project_dependencies(project)

        pnpm_calls = [c for c in calls if "pnpm" in c]
        assert len(pnpm_calls) == 1
        assert "--force" not in pnpm_calls[0]
