"""notify.py — Webhook/notification support for pipeline events."""

import json
import urllib.request
import urllib.error
from pathlib import Path

from runner.config import _console
from runner.roadmap import _load_roadmap


def get_notify_config(project_dir: Path) -> dict | None:
    """Return the ``notify`` config block from ROADMAP.json, or None if not configured.

    Expected format in ROADMAP.json::

        "notify": {
            "url": "https://hooks.slack.com/...",
            "events": ["task_complete", "task_failed", "pipeline_done"]
        }
    """
    roadmap = _load_roadmap(project_dir)
    notify = roadmap.get("notify")
    if isinstance(notify, dict) and notify.get("url"):
        return notify
    return None


def send_notification(
    project_dir: Path,
    event: str,
    *,
    task: str | None = None,
    status: str = "ok",
    details: dict | None = None,
) -> None:
    """Send a webhook POST notification if configured.

    Args:
        project_dir: Project directory.
        event:       Event type (e.g. ``task_complete``, ``task_failed``, ``pipeline_done``).
        task:        ROADMAP heading (optional).
        status:      Status string (``ok``, ``failed``, ``skipped``).
        details:     Extra key-value pairs to include in the payload.
    """
    config = get_notify_config(project_dir)
    if config is None:
        return

    url = config["url"]
    events_filter = config.get("events", [])

    # If an events filter is specified, only send for matching events.
    if events_filter and event not in events_filter:
        return

    payload = {
        "event": event,
        "project": project_dir.name,
        "status": status,
    }
    if task:
        payload["task"] = task
    if details:
        payload.update(details)

    # Add cost info if available.
    try:
        from runner.state import load_project_budget  # noqa: PLC0415

        budget = load_project_budget(project_dir)
        payload["total_tokens"] = budget.get("total_tokens", 0)
    except Exception:  # noqa: BLE001
        pass

    try:
        _post_webhook(url, payload)
    except Exception:  # noqa: BLE001
        # Never let notification failures break the pipeline.
        pass


def _post_webhook(url: str, payload: dict) -> None:
    """Send a JSON POST request to *url* with *payload*. Fail silently."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status < 300:
                _console.print(f"[dim][notify] Webhook sent: {payload.get('event')}[/]")
            else:
                _console.print(
                    f"[yellow][notify] Webhook returned {resp.status}[/]"
                )
    except (urllib.error.URLError, OSError) as exc:
        _console.print(f"[yellow][notify] Webhook failed: {exc}[/]")
    except Exception as exc:  # noqa: BLE001
        _console.print(f"[yellow][notify] Webhook error: {exc}[/]")
