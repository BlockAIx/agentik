"""Tests for runner.roadmap -- ROADMAP.json parsing, graph resolution."""

import json
from pathlib import Path

import pytest

# -- helpers -------------------------------------------------------------------


def _write_roadmap(project: Path, data: dict) -> None:
    (project / "ROADMAP.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _minimal_roadmap(**overrides) -> dict:
    base = {
        "name": "P",
        "ecosystem": "python",
        "preamble": "",
        "tasks": [
            {
                "id": 1,
                "title": "Only Task",
                "depends_on": [],
                "outputs": ["x.py"],
                "acceptance": "ok",
                "description": "Do something.",
            }
        ],
    }
    base.update(overrides)
    return base


# -- get_tasks -----------------------------------------------------------------


class TestGetTasks:
    def test_extracts_all_task_headings(self, tmp_project: Path) -> None:
        from runner.roadmap import get_tasks

        tasks = get_tasks(tmp_project)
        assert len(tasks) == 4
        assert tasks[0] == "## 001 - First Task"
        assert tasks[3] == "## 004 - Integration Task"

    def test_single_task(self, tmp_path: Path) -> None:
        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap())
        from runner.roadmap import get_tasks

        tasks = get_tasks(project)
        assert len(tasks) == 1
        assert tasks[0] == "## 001 - Only Task"

    def test_empty_roadmap(self, tmp_path: Path) -> None:
        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, {"name": "Empty", "ecosystem": "python", "tasks": []})
        from runner.roadmap import get_tasks

        assert get_tasks(project) == []


# -- get_task_body -------------------------------------------------------------


class TestGetTaskBody:
    def test_returns_body_with_metadata(self, tmp_project: Path) -> None:
        from runner.roadmap import get_task_body

        body = get_task_body("## 001 - First Task", tmp_project)
        assert "depends_on: none" in body
        assert "Implement module one" in body

    def test_body_does_not_include_other_tasks(self, tmp_project: Path) -> None:
        from runner.roadmap import get_task_body

        body = get_task_body("## 001 - First Task", tmp_project)
        assert "Second Task" not in body

    def test_nonexistent_task_returns_empty(self, tmp_project: Path) -> None:
        from runner.roadmap import get_task_body

        body = get_task_body("## 999 - Does Not Exist", tmp_project)
        assert body == ""


# -- get_task_ecosystem --------------------------------------------------------


class TestGetTaskEcosystem:
    def test_uses_project_ecosystem_by_default(self, tmp_project: Path) -> None:
        from runner.roadmap import get_task_ecosystem

        assert get_task_ecosystem("## 001 - First Task", tmp_project) == "python"

    def test_task_level_override(self, tmp_path: Path) -> None:
        from runner.roadmap import get_task_ecosystem

        project = tmp_path / "proj"
        project.mkdir()
        data = _minimal_roadmap()
        data["tasks"][0]["ecosystem"] = "deno"
        _write_roadmap(project, data)
        assert get_task_ecosystem("## 001 - Only Task", project) == "deno"

    def test_custom_ecosystem_accepted(self, tmp_path: Path) -> None:
        from runner.roadmap import get_task_ecosystem

        project = tmp_path / "proj"
        project.mkdir()
        data = _minimal_roadmap()
        data["tasks"][0]["ecosystem"] = "custom"
        _write_roadmap(project, data)
        result = get_task_ecosystem("## 001 - Only Task", project)
        assert result == "custom"


# -- is_git_managed ------------------------------------------------------------


class TestIsGitManaged:
    def test_enabled_true(self, tmp_path: Path) -> None:
        from runner.roadmap import is_git_managed

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap(git={"enabled": True}))
        assert is_git_managed(project) is True

    def test_enabled_false(self, tmp_path: Path) -> None:
        from runner.roadmap import is_git_managed

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap(git={"enabled": False}))
        assert is_git_managed(project) is False

    def test_no_git_block(self, tmp_path: Path) -> None:
        from runner.roadmap import is_git_managed

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap())
        assert is_git_managed(project) is False

    def test_git_block_empty(self, tmp_path: Path) -> None:
        from runner.roadmap import is_git_managed

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap(git={}))
        assert is_git_managed(project) is False


# -- get_task_context_files ----------------------------------------------------


class TestGetTaskContextFiles:
    def test_loads_existing_files(self, tmp_path: Path) -> None:
        from runner.roadmap import get_task_context_files

        project = tmp_path / "proj"
        project.mkdir()
        (project / "src").mkdir()
        (project / "src" / "mod.py").write_text("# module", encoding="utf-8")
        data = _minimal_roadmap()
        data["tasks"][0]["context"] = ["src/mod.py"]
        _write_roadmap(project, data)
        result = get_task_context_files("## 001 - Only Task", project)
        assert "src/mod.py" in result
        assert result["src/mod.py"] == "# module"

    def test_skips_missing_files(self, tmp_path: Path) -> None:
        from runner.roadmap import get_task_context_files

        project = tmp_path / "proj"
        project.mkdir()
        data = _minimal_roadmap()
        data["tasks"][0]["context"] = ["missing/file.py"]
        _write_roadmap(project, data)
        result = get_task_context_files("## 001 - Only Task", project)
        assert result == {}

    def test_no_context_field(self, tmp_path: Path) -> None:
        from runner.roadmap import get_task_context_files

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap())
        assert get_task_context_files("## 001 - Only Task", project) == {}

    def test_multiple_files(self, tmp_path: Path) -> None:
        from runner.roadmap import get_task_context_files

        project = tmp_path / "proj"
        project.mkdir()
        (project / "a.py").write_text("A", encoding="utf-8")
        (project / "b.py").write_text("B", encoding="utf-8")
        data = _minimal_roadmap()
        data["tasks"][0]["context"] = ["a.py", "b.py"]
        _write_roadmap(project, data)
        result = get_task_context_files("## 001 - Only Task", project)
        assert len(result) == 2
        assert result["a.py"] == "A"
        assert result["b.py"] == "B"


# -- _task_number --------------------------------------------------------------


class TestTaskNumber:
    def test_valid_heading(self) -> None:
        from runner.roadmap import _task_number

        assert _task_number("## 001 - First Task") == 1
        assert _task_number("## 042 - Something") == 42
        assert _task_number("## 120 - Last") == 120

    def test_invalid_heading(self) -> None:
        from runner.roadmap import _task_number

        assert _task_number("# Not a task") == -1
        assert _task_number("## No Number") == -1


# -- get_task_agent ------------------------------------------------------------


class TestGetTaskAgent:
    def test_default_is_build(self, tmp_path: Path) -> None:
        from runner.roadmap import get_task_agent

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap())
        assert get_task_agent("## 001 - Only Task", project) == "build"

    def test_explicit_agent(self, tmp_path: Path) -> None:
        from runner.roadmap import get_task_agent

        project = tmp_path / "proj"
        project.mkdir()
        data = _minimal_roadmap()
        data["tasks"][0]["agent"] = "milestone"
        _write_roadmap(project, data)
        assert get_task_agent("## 001 - Only Task", project) == "milestone"


# -- get_task_version ----------------------------------------------------------


class TestGetTaskVersion:
    def test_returns_version(self, tmp_path: Path) -> None:
        from runner.roadmap import get_task_version

        project = tmp_path / "proj"
        project.mkdir()
        data = _minimal_roadmap()
        data["tasks"][0]["version"] = "0.2.0"
        _write_roadmap(project, data)
        assert get_task_version("## 001 - Only Task", project) == "0.2.0"

    def test_returns_none_when_absent(self, tmp_path: Path) -> None:
        from runner.roadmap import get_task_version

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap())
        assert get_task_version("## 001 - Only Task", project) is None


# -- is_milestone_task ---------------------------------------------------------


class TestIsMilestoneTask:
    def test_detects_milestone(self, tmp_path: Path) -> None:
        from runner.roadmap import is_milestone_task

        project = tmp_path / "proj"
        project.mkdir()
        data = _minimal_roadmap()
        data["tasks"][0]["agent"] = "milestone"
        data["tasks"][0]["version"] = "0.1.0"
        _write_roadmap(project, data)
        assert is_milestone_task("## 001 - Only Task", project) is True

    def test_build_is_not_milestone(self, tmp_project: Path) -> None:
        from runner.roadmap import is_milestone_task

        assert is_milestone_task("## 001 - First Task", tmp_project) is False


# -- get_task_outputs ----------------------------------------------------------


class TestGetTaskOutputs:
    def test_parses_list(self, tmp_path: Path) -> None:
        from runner.roadmap import get_task_outputs

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap())
        result = get_task_outputs("## 001 - Only Task", project)
        assert result == ["x.py"]

    def test_multiple_outputs(self, tmp_project: Path) -> None:
        from runner.roadmap import get_task_outputs

        result = get_task_outputs("## 001 - First Task", tmp_project)
        assert result == ["src/mod.py", "tests/test_mod.py"]

    def test_no_outputs(self, tmp_path: Path) -> None:
        from runner.roadmap import get_task_outputs

        project = tmp_path / "proj"
        project.mkdir()
        data = _minimal_roadmap()
        del data["tasks"][0]["outputs"]
        _write_roadmap(project, data)
        assert get_task_outputs("## 001 - Only Task", project) == []


# -- parse_task_graph ----------------------------------------------------------


class TestParseTaskGraph:
    def test_builds_correct_graph(self, tmp_project: Path) -> None:
        from runner.roadmap import parse_task_graph

        graph = parse_task_graph(tmp_project)
        assert len(graph) == 4
        assert graph["## 001 - First Task"] == []
        assert graph["## 002 - Second Task"] == ["## 001 - First Task"]
        assert graph["## 003 - Third Task"] == ["## 001 - First Task"]
        deps_004 = graph["## 004 - Integration Task"]
        assert len(deps_004) == 2
        assert "## 002 - Second Task" in deps_004
        assert "## 003 - Third Task" in deps_004

    def test_depends_on_none(self, tmp_path: Path) -> None:
        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap())
        from runner.roadmap import parse_task_graph

        graph = parse_task_graph(project)
        assert graph["## 001 - Only Task"] == []


# -- get_ready_tasks -----------------------------------------------------------


class TestGetReadyTasks:
    def test_initial_state_returns_root_tasks(self, tmp_project: Path) -> None:
        from runner.roadmap import get_ready_tasks, get_tasks, parse_task_graph

        all_tasks = get_tasks(tmp_project)
        graph = parse_task_graph(tmp_project)
        ready = get_ready_tasks(all_tasks, graph, done=set(), project_dir=tmp_project)
        assert ready == ["## 001 - First Task"]

    def test_after_root_done_parallel_tasks_ready(self, tmp_project: Path) -> None:
        from runner.roadmap import get_ready_tasks, get_tasks, parse_task_graph

        all_tasks = get_tasks(tmp_project)
        graph = parse_task_graph(tmp_project)
        done = {"## 001 - First Task"}
        ready = get_ready_tasks(all_tasks, graph, done, project_dir=tmp_project)
        assert len(ready) == 2
        assert "## 002 - Second Task" in ready
        assert "## 003 - Third Task" in ready

    def test_integration_task_not_ready_until_all_deps_done(
        self, tmp_project: Path
    ) -> None:
        from runner.roadmap import get_ready_tasks, get_tasks, parse_task_graph

        all_tasks = get_tasks(tmp_project)
        graph = parse_task_graph(tmp_project)
        done = {"## 001 - First Task", "## 002 - Second Task"}
        ready = get_ready_tasks(all_tasks, graph, done, project_dir=tmp_project)
        assert "## 004 - Integration Task" not in ready
        assert "## 003 - Third Task" in ready

    def test_all_done_returns_empty(self, tmp_project: Path) -> None:
        from runner.roadmap import get_ready_tasks, get_tasks, parse_task_graph

        all_tasks = get_tasks(tmp_project)
        graph = parse_task_graph(tmp_project)
        done = set(all_tasks)
        assert get_ready_tasks(all_tasks, graph, done, project_dir=tmp_project) == []

    def test_preserves_roadmap_order(self, tmp_project: Path) -> None:
        from runner.roadmap import get_ready_tasks, get_tasks, parse_task_graph

        all_tasks = get_tasks(tmp_project)
        graph = parse_task_graph(tmp_project)
        done = {"## 001 - First Task"}
        ready = get_ready_tasks(all_tasks, graph, done, project_dir=tmp_project)
        assert ready.index("## 002 - Second Task") < ready.index("## 003 - Third Task")


# -- print_dependency_graph ----------------------------------------------------


class TestPrintDependencyGraph:
    @staticmethod
    def _strip_ansi(text: str) -> str:
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def test_prints_all_tasks(
        self, tmp_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from runner.roadmap import print_dependency_graph

        print_dependency_graph(tmp_project)
        out = self._strip_ansi(capsys.readouterr().out)
        assert "001" in out
        assert "004" in out
        assert "Layer 0" in out

    def test_shows_done_status(
        self, tmp_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from runner.roadmap import print_dependency_graph
        from runner.state import mark_done

        mark_done("## 001 - First Task", tmp_project)
        print_dependency_graph(tmp_project)
        out = self._strip_ansi(capsys.readouterr().out)
        assert "1 done" in out


# -- get_deploy_config ---------------------------------------------------------


class TestGetDeployConfig:
    def test_returns_roadmap_deploy_block(self, tmp_path: Path) -> None:
        from runner.roadmap import get_deploy_config

        project = tmp_path / "proj"
        project.mkdir()
        roadmap = _minimal_roadmap(
            deploy={
                "enabled": True,
                "script": "scripts/deploy.sh",
                "env": {"app": "myapp"},
            }
        )
        _write_roadmap(project, roadmap)
        cfg = get_deploy_config(project)
        assert cfg["enabled"] is True
        assert cfg["script"] == "scripts/deploy.sh"
        assert cfg["env"] == {"app": "myapp"}

    def test_falls_back_to_deploy_json(self, tmp_path: Path) -> None:
        from runner.roadmap import get_deploy_config

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap())  # no deploy block
        (project / "deploy.json").write_text(
            json.dumps({"provider": "fly", "app": "x"}), encoding="utf-8"
        )
        cfg = get_deploy_config(project)
        assert cfg["enabled"] is True
        assert cfg["env"] == {"provider": "fly", "app": "x"}

    def test_legacy_deploy_false(self, tmp_path: Path) -> None:
        from runner.roadmap import get_deploy_config

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap())
        (project / "deploy.json").write_text(
            json.dumps({"deploy": False, "app": "x"}), encoding="utf-8"
        )
        cfg = get_deploy_config(project)
        assert cfg["enabled"] is False

    def test_no_deploy_config(self, tmp_path: Path) -> None:
        from runner.roadmap import get_deploy_config

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap())
        cfg = get_deploy_config(project)
        assert cfg["enabled"] is False


# -- is_deploy_task ------------------------------------------------------------


class TestIsDeployTask:
    def test_deploy_true(self, tmp_path: Path) -> None:
        from runner.roadmap import is_deploy_task

        project = tmp_path / "proj"
        project.mkdir()
        roadmap = _minimal_roadmap()
        roadmap["tasks"][0]["deploy"] = True
        _write_roadmap(project, roadmap)
        assert is_deploy_task("## 001 - Only Task", project) is True

    def test_deploy_absent(self, tmp_path: Path) -> None:
        from runner.roadmap import is_deploy_task

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap())
        assert is_deploy_task("## 001 - Only Task", project) is False

    def test_unknown_task(self, tmp_path: Path) -> None:
        from runner.roadmap import is_deploy_task

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _minimal_roadmap())
        assert is_deploy_task("## 999 - Ghost", project) is False
