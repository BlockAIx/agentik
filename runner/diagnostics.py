"""diagnostics.py — Structured failure reports for task failures."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from runner.config import _console


def save_failure_report(
    task: str,
    project_dir: Path,
    *,
    attempts: int,
    last_error: str | None = None,
    failing_test: str | None = None,
    tokens_spent: int = 0,
    fix_logs: str | None = None,
) -> Path:
    """Save a structured JSON failure report and return its path.

    The report is saved at ``projects/<name>/logs/<task-slug>/failure_report.json``.
    """
    report = {
        "task": task.lstrip("# ").strip(),
        "project": project_dir.name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attempts": attempts,
        "last_error": last_error or _extract_error(fix_logs),
        "failing_test": failing_test or _extract_failing_test(fix_logs),
        "tokens_spent": tokens_spent,
    }

    # Save to logs directory.
    slug = re.sub(r"[^a-z0-9]+", "-", task.lower().lstrip("#").strip()).strip("-")[:50]
    report_dir = project_dir / "logs" / slug
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "failure_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Pretty-print the report.
    _console.print("\n[red bold]── Failure Report ──[/]")
    _console.print(f"  [bold]Task:[/]         {report['task']}")
    _console.print(f"  [bold]Attempts:[/]     {report['attempts']}")
    _console.print(f"  [bold]Last error:[/]   {report['last_error'] or 'unknown'}")
    _console.print(f"  [bold]Failing test:[/] {report['failing_test'] or 'unknown'}")
    _console.print(f"  [bold]Tokens spent:[/] {report['tokens_spent']}")
    _console.print(f"  [bold]Report saved:[/] {report_path.relative_to(project_dir)}")

    return report_path


def _extract_error(fix_logs: str | None) -> str | None:
    """Try to extract the most relevant error message from test output."""
    if not fix_logs:
        return None

    # Look for common Python error patterns.
    patterns = [
        # Python tracebacks: last line is usually the error.
        r"((?:TypeError|ValueError|AttributeError|ImportError|KeyError|NameError|"
        r"RuntimeError|AssertionError|ModuleNotFoundError|FileNotFoundError|"
        r"IndexError|ZeroDivisionError|StopIteration|RecursionError|"
        r"PermissionError|NotImplementedError|SyntaxError|IndentationError)"
        r":.+?)(?:\n|$)",
        # Node/Deno errors.
        r"((?:Error|TypeError|ReferenceError|SyntaxError):.+?)(?:\n|$)",
        # Generic FAILED line.
        r"(FAILED .+?)(?:\n|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, fix_logs)
        if match:
            return match.group(1).strip()[:500]

    # Fallback: last non-empty line.
    lines = [line.strip() for line in fix_logs.splitlines() if line.strip()]
    if lines:
        return lines[-1][:500]
    return None


def _extract_failing_test(fix_logs: str | None) -> str | None:
    """Try to extract the name of the failing test from output."""
    if not fix_logs:
        return None

    # pytest pattern: FAILED tests/test_foo.py::test_bar
    match = re.search(r"FAILED\s+(\S+::\S+)", fix_logs)
    if match:
        return match.group(1)

    # pytest short: tests/test_foo.py::test_bar FAILED
    match2 = re.search(r"(\S+::\S+)\s+FAILED", fix_logs)
    if match2:
        return match2.group(1)

    # Deno test: test <name> ... FAILED
    match3 = re.search(r"test\s+(.+?)\s+\.\.\.\s+FAILED", fix_logs)
    if match3:
        return match3.group(1)

    return None
