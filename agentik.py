"""agentik.py — Entry point. All logic lives in the runner/ package.

Run with:
    python agentik.py           Launch the web UI dashboard (default).
    python agentik.py --web     Same as above (explicit).
or, after pip install -e .:
    agentik

CLI flags:
    --web           Launch the web UI dashboard (default when no flags given).
    --pipeline      Run the interactive pipeline (was the old default).
    --dry-run       Walk the dependency graph and estimate cost without running.
    --graph-html    Generate an interactive HTML dependency graph.
    --host HOST     Web UI host (default: 127.0.0.1).
    --port PORT     Web UI port (default: 8420).
"""

import sys


def _cli() -> None:
    """Parse CLI flags and delegate to the appropriate mode."""
    args = sys.argv[1:]

    if "--pipeline" in args:
        from runner import main

        main()
        return

    if "--dry-run" in args or "--dryrun" in args:
        from runner.opencode import select_project

        project_dir = select_project()
        from runner.workspace import ensure_workspace_dirs

        ensure_workspace_dirs(project_dir)
        from runner.dryrun import dry_run

        dry_run(project_dir)
        return

    if "--graph-html" in args:
        from runner.opencode import select_project

        project_dir = select_project()
        from runner.workspace import ensure_workspace_dirs

        ensure_workspace_dirs(project_dir)
        from runner.graph_html import generate_graph_html

        generate_graph_html(project_dir)
        return

    # Default: web UI dashboard (standalone).
    host = "127.0.0.1"
    port = 8420
    if "--host" in args:
        idx = args.index("--host")
        if idx + 1 < len(args):
            host = args[idx + 1]
    if "--port" in args:
        idx = args.index("--port")
        if idx + 1 < len(args):
            port = int(args[idx + 1])

    try:
        from runner.web.app import start_server

        start_server(host=host, port=port)
    except ImportError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    _cli()
