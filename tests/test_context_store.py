"""Tests for runner.context_store — inter-task knowledge transfer."""

import json
from pathlib import Path

import pytest


def _write_roadmap(project: Path, data: dict) -> None:
    (project / "ROADMAP.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _roadmap_with_deps() -> dict:
    return {
        "name": "P",
        "ecosystem": "python",
        "preamble": "",
        "tasks": [
            {
                "id": 1,
                "title": "Foundation",
                "depends_on": [],
                "outputs": ["src/a.py"],
                "acceptance": "ok",
            },
            {
                "id": 2,
                "title": "Feature A",
                "depends_on": [1],
                "outputs": ["src/b.py"],
                "acceptance": "ok",
            },
            {
                "id": 3,
                "title": "Feature B",
                "depends_on": [1, 2],
                "outputs": ["src/c.py"],
                "acceptance": "ok",
            },
        ],
    }


class TestSaveAndLoadNotes:
    def test_round_trip(self, tmp_path: Path) -> None:
        from runner.context_store import load_task_notes, save_task_notes

        project = tmp_path / "proj"
        project.mkdir()
        save_task_notes("## 001 - Foundation", project, "Use pattern X for config.")
        notes = load_task_notes("## 001 - Foundation", project)
        assert notes == "Use pattern X for config."

    def test_missing_returns_none(self, tmp_path: Path) -> None:
        from runner.context_store import load_task_notes

        project = tmp_path / "proj"
        project.mkdir()
        assert load_task_notes("## 999 - Missing", project) is None

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        from runner.context_store import load_task_notes, save_task_notes

        project = tmp_path / "proj"
        project.mkdir()
        save_task_notes("## 001 - T", project, "  note with spaces  \n\n")
        assert load_task_notes("## 001 - T", project) == "note with spaces"


class TestCollectDependencyNotes:
    def test_collects_from_deps(self, tmp_path: Path) -> None:
        from runner.context_store import collect_dependency_notes, save_task_notes

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _roadmap_with_deps())

        save_task_notes("## 001 - Foundation", project, "Config uses YAML.")
        save_task_notes("## 002 - Feature A", project, "Module B depends on A.init().")

        result = collect_dependency_notes("## 003 - Feature B", project)
        assert "Config uses YAML" in result
        assert "Module B depends on A.init()" in result
        assert "Notes from dependency tasks" in result

    def test_empty_when_no_deps_have_notes(self, tmp_path: Path) -> None:
        from runner.context_store import collect_dependency_notes

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _roadmap_with_deps())

        result = collect_dependency_notes("## 002 - Feature A", project)
        assert result == ""

    def test_empty_for_root_task(self, tmp_path: Path) -> None:
        from runner.context_store import collect_dependency_notes

        project = tmp_path / "proj"
        project.mkdir()
        _write_roadmap(project, _roadmap_with_deps())

        result = collect_dependency_notes("## 001 - Foundation", project)
        assert result == ""
