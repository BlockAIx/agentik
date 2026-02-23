"""Shared fixtures for runner unit tests."""

import json
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal project directory with a ROADMAP.json and required structure."""
    project = tmp_path / "test-project"
    project.mkdir()
    roadmap = {
        "name": "Test Project v0.1",
        "ecosystem": "python",
        "preamble": "A test project.",
        "tasks": [
            {
                "id": 1,
                "title": "First Task",
                "depends_on": [],
                "outputs": ["src/mod.py", "tests/test_mod.py"],
                "acceptance": "all tests pass",
                "description": "Implement module one.",
            },
            {
                "id": 2,
                "title": "Second Task",
                "depends_on": [1],
                "outputs": ["src/other.py", "tests/test_other.py"],
                "acceptance": "all tests pass",
                "description": "Implement module two.",
            },
            {
                "id": 3,
                "title": "Third Task",
                "depends_on": [1],
                "outputs": ["src/util.py", "tests/test_util.py"],
                "acceptance": "all tests pass",
                "description": "Implement utilities.",
            },
            {
                "id": 4,
                "title": "Integration Task",
                "depends_on": [2, 3],
                "outputs": ["src/app.py", "tests/test_app.py"],
                "acceptance": "all tests pass",
                "description": "Integrate everything.",
            },
        ],
    }
    (project / "ROADMAP.json").write_text(
        json.dumps(roadmap, indent=2), encoding="utf-8"
    )
    (project / "test_project").mkdir()
    (project / "tests").mkdir()
    return project


@pytest.fixture()
def budget_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Write a budget.json to tmp_path and monkeypatch cwd so config.py finds it."""
    budget = {
        "monthly_limit_tokens": 100_000,
        "per_task_limit_tokens": 50_000,
        "max_attempts_per_task": 3,
        "max_parallel_agents": 2,
        "token_prices_usd_per_million": {
            "input": 3.0,
            "output": 15.0,
            "cache_read": 0.30,
            "cache_write": 3.75,
        },
    }
    path = tmp_path / "budget.json"
    path.write_text(json.dumps(budget), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return path
