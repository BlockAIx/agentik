"""agentik.py — Entry point. All logic lives in the runner/ package.

Run with:
    python agentik.py
or, after pip install -e .:
    agentik

CLI flags:
    --dry-run       Walk the dependency graph and estimate cost without running.
    --graph-html    Generate an interactive HTML dependency graph.
    --web           Launch the web UI dashboard.
"""

import sys


def _cli() -> None:
    """Parse CLI flags and delegate to the appropriate mode."""
    args = sys.argv[1:]

    if "--web" in args:
        try:
            from runner.web.app import start_server

            start_server()
        except ImportError as e:
            print(f"Error: {e}")
            sys.exit(1)
        return

    if "--dry-run" in args or "--dryrun" in args:
        from runner.opencode import check_models, select_project

        check_models()
        project_dir = select_project()
        from runner.workspace import ensure_workspace_dirs

        ensure_workspace_dirs(project_dir)
        from runner.dryrun import dry_run

        dry_run(project_dir)
        return

    if "--graph-html" in args:
        from runner.opencode import check_models, select_project

        check_models()
        project_dir = select_project()
        from runner.workspace import ensure_workspace_dirs

        ensure_workspace_dirs(project_dir)
        from runner.graph_html import generate_graph_html

        generate_graph_html(project_dir)
        return

    # Default: interactive pipeline.
    from runner import main

    main()


if __name__ == "__main__":
    _cli()
