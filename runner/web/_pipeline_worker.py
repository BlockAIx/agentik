"""Subprocess worker: runs run_pipeline_headless for web UI live log streaming.

Invoked as:
    python -m runner.web._pipeline_worker <project_dir>

Environment:
    AGENTIK_VERBOSE=1   Enable verbose (full agent output) mode.
"""

import os
import sys
from pathlib import Path


def main() -> None:
    """Entry point: parse args and run the pipeline headlessly."""
    if len(sys.argv) != 2:
        print(
            "Usage: python -m runner.web._pipeline_worker <project_dir>",
            file=sys.stderr,
        )
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    if not project_dir.is_dir():
        print(f"Project directory not found: {project_dir}", file=sys.stderr)
        sys.exit(1)

    verbose = os.environ.get("AGENTIK_VERBOSE", "0") == "1"

    from runner.pipeline import run_pipeline_headless  # noqa: PLC0415

    try:
        run_pipeline_headless(project_dir, verbose=verbose)
    except SystemExit as exc:
        sys.exit(exc.code)
    except Exception as exc:  # noqa: BLE001
        print(f"\n[ERROR] Pipeline crashed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
