"""agentik.py — Entry point. All logic lives in the runner/ package.

Run with:
    python agentik.py           Interactive menu (default).
    python agentik.py --web     Launch the web UI dashboard directly.
or, after pip install -e .:
    agentik

CLI flags:
    --web           Launch the web UI dashboard without a menu prompt.
    --pipeline      Run the interactive pipeline directly (no menu).
    --dry-run       Walk the dependency graph and estimate cost without running.
    --graph-html    Generate an interactive HTML dependency graph.
    --host HOST     Web UI host (default: 127.0.0.1).
    --port PORT     Web UI port (default: 8420).
"""

import sys


def _start_web(host: str = "127.0.0.1", port: int = 8420) -> None:
    """Launch the FastAPI web UI server."""
    try:
        from runner.web.app import start_server

        start_server(host=host, port=port)
    except ImportError as e:
        print(f"Error: {e}")
        sys.exit(1)


def _run_pipeline() -> None:
    from runner import main

    main()


def _run_dryrun() -> None:
    from runner.opencode import select_project

    project_dir = select_project()
    from runner.workspace import ensure_workspace_dirs

    ensure_workspace_dirs(project_dir)
    from runner.dryrun import dry_run

    dry_run(project_dir)


def _run_graph_html() -> None:
    from runner.opencode import select_project

    project_dir = select_project()
    from runner.workspace import ensure_workspace_dirs

    ensure_workspace_dirs(project_dir)
    from runner.graph_html import generate_graph_html

    generate_graph_html(project_dir)


def _menu(host: str, port: int) -> None:
    """Show an interactive main menu and dispatch to the selected mode."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import IntPrompt

    console = Console()
    console.print(
        Panel.fit(
            "[bold cyan]agentik[/]  — autonomous development loop",
            border_style="cyan",
        )
    )
    console.print()
    console.print(
        "  [bold]1.[/]  Launch [cyan]web UI[/] dashboard  "
        f"[dim](http://{host}:{port})[/]"
    )
    console.print("  [bold]2.[/]  Run [yellow]interactive pipeline[/]")
    console.print("  [bold]3.[/]  [dim]Dry-run[/] — estimate cost without executing")
    console.print("  [bold]4.[/]  Generate [dim]HTML[/] dependency graph")
    console.print()

    choice = IntPrompt.ask("Select", choices=["1", "2", "3", "4"], default=1)
    console.print()

    if choice == 1:
        _start_web(host=host, port=port)
    elif choice == 2:
        _run_pipeline()
    elif choice == 3:
        _run_dryrun()
    elif choice == 4:
        _run_graph_html()


def _cli() -> None:
    """Parse CLI flags and delegate to the appropriate mode."""
    args = sys.argv[1:]

    if "--pipeline" in args:
        _run_pipeline()
        return

    if "--dry-run" in args or "--dryrun" in args:
        _run_dryrun()
        return

    if "--graph-html" in args:
        _run_graph_html()
        return

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

    if "--web" in args:
        # Explicit flag — skip menu, start web UI directly (used by Docker).
        _start_web(host=host, port=port)
        return

    # Default: show interactive menu.
    _menu(host=host, port=port)


if __name__ == "__main__":
    _cli()
