"""Tests for runner.notify — webhook notifications."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture()
def notify_project(tmp_path: Path) -> Path:
    """Project with notification configured."""
    project = tmp_path / "notify-proj"
    project.mkdir()
    roadmap = {
        "name": "Notify Project",
        "ecosystem": "python",
        "notify": {
            "url": "https://hooks.example.com/webhook",
            "events": ["task_done", "task_failed", "pipeline_done"],
        },
        "tasks": [
            {
                "id": 1,
                "title": "First Task",
                "depends_on": [],
                "outputs": ["src/a.py"],
                "acceptance": "tests pass",
            },
        ],
    }
    (project / "ROADMAP.json").write_text(json.dumps(roadmap), encoding="utf-8")
    return project


class TestGetNotifyConfig:
    def test_returns_config_when_set(self, notify_project: Path) -> None:
        from runner.notify import get_notify_config

        cfg = get_notify_config(notify_project)
        assert cfg is not None
        assert cfg["url"] == "https://hooks.example.com/webhook"
        assert "task_done" in cfg["events"]

    def test_returns_none_when_not_set(self, tmp_project: Path) -> None:
        from runner.notify import get_notify_config

        assert get_notify_config(tmp_project) is None


class TestSendNotification:
    def test_sends_when_event_matches(self, notify_project: Path) -> None:
        from runner.notify import send_notification

        with patch("runner.notify._post_webhook") as mock_post:
            send_notification(
                notify_project,
                "task_done",
                task="## 001 - First Task",
                status="done",
            )
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://hooks.example.com/webhook"
            payload = call_args[0][1]
            assert payload["event"] == "task_done"
            assert payload["task"] == "## 001 - First Task"

    def test_skips_when_event_not_in_list(self, notify_project: Path) -> None:
        from runner.notify import send_notification

        with patch("runner.notify._post_webhook") as mock_post:
            send_notification(notify_project, "some_other_event")
            mock_post.assert_not_called()

    def test_skips_when_no_config(self, tmp_project: Path) -> None:
        from runner.notify import send_notification

        with patch("runner.notify._post_webhook") as mock_post:
            send_notification(tmp_project, "task_done")
            mock_post.assert_not_called()

    def test_does_not_raise_on_webhook_failure(self, notify_project: Path) -> None:
        from runner.notify import send_notification

        with patch("runner.notify._post_webhook", side_effect=Exception("network error")):
            # Should not raise.
            send_notification(notify_project, "task_done")
