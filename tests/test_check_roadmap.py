"""Tests for helpers.check_roadmap -- ROADMAP.json structural validator."""

import json
from pathlib import Path

import pytest

from helpers.check_roadmap import (
    check_architecture,
    check_checkpoint_refs,
    check_depends_on,
    check_disjoint_parallel_outputs,
    check_fields,
    check_git_block,
    check_numbering,
    check_preamble,
    check_single_root_task,
    check_titles,
    parse_roadmap,
    run_checks,
)

# -- Helpers -------------------------------------------------------------------


def _roadmap(**overrides) -> dict:
    """Return a minimal valid ROADMAP dict, with optional overrides."""
    base = {
        "name": "Test",
        "ecosystem": "python",
        "preamble": "",
        "tasks": [
            {
                "id": 1,
                "title": "Alpha",
                "depends_on": [],
                "outputs": ["x.py"],
                "acceptance": "ok",
                "description": "Do alpha.",
            }
        ],
    }
    base.update(overrides)
    return base


def _write(path: Path, data: dict) -> Path:
    """Write a ROADMAP.json and return the path."""
    f = path / "ROADMAP.json"
    f.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return f


# -- parse_roadmap -------------------------------------------------------------


class TestParseRoadmap:
    def test_parses_tasks(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "Alpha",
                    "depends_on": [],
                    "outputs": ["x.py"],
                    "acceptance": "ok",
                },
                {
                    "id": 2,
                    "title": "Beta",
                    "depends_on": [1],
                    "outputs": ["y.py"],
                    "acceptance": "ok",
                },
            ]
        )
        _, tasks = parse_roadmap(data)
        assert len(tasks) == 2
        assert tasks[0].number == 1
        assert tasks[0].title == "Alpha"
        assert tasks[1].number == 2
        assert tasks[1].depends_on == [1]

    def test_extracts_outputs(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "depends_on": [],
                    "outputs": ["src/a.py", "src/b.py"],
                    "acceptance": "ok",
                }
            ]
        )
        _, tasks = parse_roadmap(data)
        assert tasks[0].outputs == ["src/a.py", "src/b.py"]

    def test_extracts_agent(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "agent": "architect",
                    "depends_on": [],
                    "outputs": ["x"],
                    "acceptance": "ok",
                }
            ]
        )
        _, tasks = parse_roadmap(data)
        assert tasks[0].agent == "architect"

    def test_extracts_ecosystem(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "ecosystem": "deno",
                    "depends_on": [],
                    "outputs": ["x"],
                    "acceptance": "ok",
                }
            ]
        )
        _, tasks = parse_roadmap(data)
        assert tasks[0].ecosystem == "deno"


# -- check_preamble -----------------------------------------------------------


class TestCheckPreamble:
    def test_valid_ecosystem(self) -> None:
        data = _roadmap()
        _, tasks = parse_roadmap(data)
        issues = check_preamble(data, tasks)
        assert not issues

    def test_missing_ecosystem_ok(self) -> None:
        data = _roadmap()
        del data["ecosystem"]
        _, tasks = parse_roadmap(data)
        issues = check_preamble(data, tasks)
        assert not any(i.level == "ERROR" for i in issues)

    def test_unknown_ecosystem_warns(self) -> None:
        data = _roadmap(ecosystem="java")
        _, tasks = parse_roadmap(data)
        issues = check_preamble(data, tasks)
        assert any(i.level == "WARNING" and "Unknown" in i.message for i in issues)


# -- check_git_block -----------------------------------------------------------


class TestCheckGitBlock:
    def test_no_git_block(self) -> None:
        data = _roadmap()
        _, tasks = parse_roadmap(data)
        assert not check_git_block(data, tasks)

    def test_valid_git_block(self) -> None:
        data = _roadmap(git={"enabled": True})
        _, tasks = parse_roadmap(data)
        assert not check_git_block(data, tasks)

    def test_git_not_dict(self) -> None:
        data = _roadmap(git="yes")
        _, tasks = parse_roadmap(data)
        issues = check_git_block(data, tasks)
        assert any(i.level == "ERROR" and "object" in i.message for i in issues)

    def test_enabled_not_bool(self) -> None:
        data = _roadmap(git={"enabled": "true"})
        _, tasks = parse_roadmap(data)
        issues = check_git_block(data, tasks)
        assert any(i.level == "ERROR" and "boolean" in i.message for i in issues)

    def test_unknown_field_warns(self) -> None:
        data = _roadmap(git={"enabled": True, "auto_push": True})
        _, tasks = parse_roadmap(data)
        issues = check_git_block(data, tasks)
        assert any(i.level == "WARNING" and "auto_push" in i.message for i in issues)


# -- check_numbering -----------------------------------------------------------


class TestCheckNumbering:
    def test_sequential(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "depends_on": [],
                    "outputs": ["x"],
                    "acceptance": "ok",
                },
                {
                    "id": 2,
                    "title": "B",
                    "depends_on": [1],
                    "outputs": ["y"],
                    "acceptance": "ok",
                },
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_numbering(data, tasks)
        assert not issues

    def test_gap_detected(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "depends_on": [],
                    "outputs": ["x"],
                    "acceptance": "ok",
                },
                {
                    "id": 3,
                    "title": "C",
                    "depends_on": [1],
                    "outputs": ["z"],
                    "acceptance": "ok",
                },
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_numbering(data, tasks)
        assert any(i.level == "ERROR" and "002" in i.message for i in issues)

    def test_duplicate_detected(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "depends_on": [],
                    "outputs": ["x"],
                    "acceptance": "ok",
                },
                {
                    "id": 1,
                    "title": "B",
                    "depends_on": [],
                    "outputs": ["y"],
                    "acceptance": "ok",
                },
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_numbering(data, tasks)
        assert any(i.level == "ERROR" and "Duplicate" in i.message for i in issues)

    def test_no_tasks(self) -> None:
        issues = check_numbering({}, [])
        assert any(i.level == "ERROR" and "No tasks" in i.message for i in issues)


# -- check_fields --------------------------------------------------------------


class TestCheckFields:
    def test_all_required_present(self) -> None:
        data = _roadmap()
        _, tasks = parse_roadmap(data)
        issues = check_fields(data, tasks)
        assert not issues

    def test_missing_outputs(self) -> None:
        data = _roadmap(
            tasks=[{"id": 1, "title": "A", "depends_on": [], "acceptance": "ok"}]
        )
        _, tasks = parse_roadmap(data)
        issues = check_fields(data, tasks)
        assert any("outputs" in i.message for i in issues)

    def test_missing_acceptance(self) -> None:
        data = _roadmap(
            tasks=[{"id": 1, "title": "A", "depends_on": [], "outputs": ["x.py"]}]
        )
        _, tasks = parse_roadmap(data)
        issues = check_fields(data, tasks)
        assert any("acceptance" in i.message for i in issues)

    def test_missing_depends_on(self) -> None:
        data = _roadmap(
            tasks=[{"id": 1, "title": "A", "outputs": ["x.py"], "acceptance": "ok"}]
        )
        _, tasks = parse_roadmap(data)
        issues = check_fields(data, tasks)
        assert any("depends_on" in i.message for i in issues)

    def test_invalid_agent_warns(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "agent": "invalid_agent",
                    "depends_on": [],
                    "outputs": ["x"],
                    "acceptance": "ok",
                }
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_fields(data, tasks)
        assert any(i.level == "WARNING" and "agent" in i.message for i in issues)

    def test_milestone_skips_outputs_acceptance(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "agent": "milestone",
                    "depends_on": [],
                    "version": "0.1.0",
                }
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_fields(data, tasks)
        assert not any(i.level == "ERROR" for i in issues)


# -- check_titles --------------------------------------------------------------


class TestCheckTitles:
    def test_within_limit(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "Short Title",
                    "depends_on": [],
                    "outputs": ["x"],
                    "acceptance": "ok",
                }
            ]
        )
        _, tasks = parse_roadmap(data)
        assert not check_titles(data, tasks)

    def test_exceeds_word_limit(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "One Two Three Four Five Six Seven",
                    "depends_on": [],
                    "outputs": ["x"],
                    "acceptance": "ok",
                }
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_titles(data, tasks)
        assert any(i.level == "ERROR" and "words" in i.message for i in issues)


# -- check_depends_on ---------------------------------------------------------


class TestCheckDependsOn:
    def test_valid_references(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "depends_on": [],
                    "outputs": ["x"],
                    "acceptance": "ok",
                },
                {
                    "id": 2,
                    "title": "B",
                    "depends_on": [1],
                    "outputs": ["y"],
                    "acceptance": "ok",
                },
            ]
        )
        _, tasks = parse_roadmap(data)
        assert not check_depends_on(data, tasks)

    def test_nonexistent_reference(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "depends_on": [99],
                    "outputs": ["x"],
                    "acceptance": "ok",
                }
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_depends_on(data, tasks)
        assert any("non-existent" in i.message for i in issues)

    def test_forward_reference(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "depends_on": [2],
                    "outputs": ["x"],
                    "acceptance": "ok",
                },
                {
                    "id": 2,
                    "title": "B",
                    "depends_on": [],
                    "outputs": ["y"],
                    "acceptance": "ok",
                },
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_depends_on(data, tasks)
        assert any("forward reference" in i.message for i in issues)

    def test_self_reference(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "depends_on": [1],
                    "outputs": ["x"],
                    "acceptance": "ok",
                }
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_depends_on(data, tasks)
        assert any("depends on itself" in i.message for i in issues)


# -- check_architecture -------------------------------------------------------


class TestCheckArchitecture:
    def test_valid_deps(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "depends_on": [],
                    "outputs": ["src/core/x.ts"],
                    "acceptance": "ok",
                },
                {
                    "id": 2,
                    "title": "B",
                    "depends_on": [1],
                    "outputs": ["src/core/y.ts"],
                    "acceptance": "ok",
                },
            ]
        )
        _, tasks = parse_roadmap(data)
        assert not check_architecture(data, tasks)

    def test_core_depends_on_render_violation(self) -> None:
        data = _roadmap(
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "depends_on": [],
                    "outputs": ["src/render/view.ts"],
                    "acceptance": "ok",
                },
                {
                    "id": 2,
                    "title": "B",
                    "depends_on": [1],
                    "outputs": ["src/core/model.ts"],
                    "acceptance": "ok",
                },
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_architecture(data, tasks)
        assert any("Architecture violation" in i.message for i in issues)


# -- check_checkpoint_refs ----------------------------------------------------


class TestCheckCheckpointRefs:
    def test_valid_checkpoint(self) -> None:
        data = _roadmap(
            preamble="Target task: `1`\n",
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "depends_on": [],
                    "outputs": ["x"],
                    "acceptance": "ok",
                }
            ],
        )
        _, tasks = parse_roadmap(data)
        assert not check_checkpoint_refs(data, tasks)

    def test_invalid_checkpoint_ref(self) -> None:
        data = _roadmap(
            preamble="Target task: `999`\n",
            tasks=[
                {
                    "id": 1,
                    "title": "A",
                    "depends_on": [],
                    "outputs": ["x"],
                    "acceptance": "ok",
                }
            ],
        )
        _, tasks = parse_roadmap(data)
        issues = check_checkpoint_refs(data, tasks)
        assert any("999" in i.message for i in issues)


# -- check_single_root_task ----------------------------------------------------


class TestCheckSingleRootTask:
    def test_single_root_ok(self) -> None:
        data = _roadmap()
        _, tasks = parse_roadmap(data)
        issues = check_single_root_task(data, tasks)
        assert len(issues) == 0

    def test_multiple_roots_error(self) -> None:
        data = _roadmap(
            tasks=[
                {"id": 1, "title": "Alpha", "depends_on": [], "outputs": ["a.py"]},
                {"id": 2, "title": "Beta", "depends_on": [], "outputs": ["b.py"]},
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_single_root_task(data, tasks)
        assert len(issues) == 1
        assert issues[0].level == "ERROR"
        assert "001" in issues[0].message
        assert "002" in issues[0].message

    def test_no_root_error(self) -> None:
        data = _roadmap(
            tasks=[
                {"id": 1, "title": "Alpha", "depends_on": [2], "outputs": ["a.py"]},
                {"id": 2, "title": "Beta", "depends_on": [1], "outputs": ["b.py"]},
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_single_root_task(data, tasks)
        assert len(issues) == 1
        assert issues[0].level == "ERROR"
        assert "No root task" in issues[0].message

    def test_empty_tasks_no_issue(self) -> None:
        """No tasks at all — other checks catch that, not this one."""
        data = _roadmap(tasks=[])
        _, tasks = parse_roadmap(data)
        issues = check_single_root_task(data, tasks)
        assert len(issues) == 0


# -- check_disjoint_parallel_outputs -------------------------------------------


class TestCheckDisjointParallelOutputs:
    def test_disjoint_ok(self) -> None:
        data = _roadmap(
            tasks=[
                {"id": 1, "title": "Root", "depends_on": [], "outputs": ["a.py"]},
                {"id": 2, "title": "Alpha", "depends_on": [1], "outputs": ["b.py"]},
                {"id": 3, "title": "Beta", "depends_on": [1], "outputs": ["c.py"]},
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_disjoint_parallel_outputs(data, tasks)
        assert len(issues) == 0

    def test_overlapping_outputs_error(self) -> None:
        data = _roadmap(
            tasks=[
                {"id": 1, "title": "Root", "depends_on": [], "outputs": ["a.py"]},
                {
                    "id": 2,
                    "title": "Alpha",
                    "depends_on": [1],
                    "outputs": ["shared.py"],
                },
                {"id": 3, "title": "Beta", "depends_on": [1], "outputs": ["shared.py"]},
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_disjoint_parallel_outputs(data, tasks)
        assert len(issues) == 1
        assert issues[0].level == "ERROR"
        assert "shared.py" in issues[0].message

    def test_same_output_different_deps_ok(self) -> None:
        """Tasks with different dependency sets don't run in parallel — no conflict."""
        data = _roadmap(
            tasks=[
                {"id": 1, "title": "Root", "depends_on": [], "outputs": ["a.py"]},
                {
                    "id": 2,
                    "title": "Alpha",
                    "depends_on": [1],
                    "outputs": ["shared.py"],
                },
                {
                    "id": 3,
                    "title": "Beta",
                    "depends_on": [1, 2],
                    "outputs": ["shared.py"],
                },
            ]
        )
        _, tasks = parse_roadmap(data)
        issues = check_disjoint_parallel_outputs(data, tasks)
        assert len(issues) == 0

    def test_single_task_in_group_ok(self) -> None:
        data = _roadmap()
        _, tasks = parse_roadmap(data)
        issues = check_disjoint_parallel_outputs(data, tasks)
        assert len(issues) == 0


# -- run_checks (integration) -------------------------------------------------


class TestRunChecks:
    def test_clean_roadmap_returns_zero(self, tmp_path: Path) -> None:
        f = _write(tmp_path, _roadmap())
        assert run_checks(f) == 0

    def test_errors_return_one(self, tmp_path: Path) -> None:
        data = _roadmap()
        data["tasks"] = []  # no tasks is an ERROR
        f = _write(tmp_path, data)
        assert run_checks(f) == 1

    def test_invalid_json(self, tmp_path: Path) -> None:
        f = tmp_path / "ROADMAP.json"
        f.write_text("{bad json", encoding="utf-8")
        assert run_checks(f) == 1
