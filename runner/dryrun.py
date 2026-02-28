"""dryrun.py — Dry-run mode: estimate cost/time without running the pipeline."""

from pathlib import Path

from runner.config import _PRICES, MAX_ATTEMPTS, MAX_PARALLEL_AGENTS, _console
from runner.roadmap import (
    get_task_layers,
    get_tasks,
    is_milestone_task,
    parse_task_graph,
)
from runner.state import _format_tokens, _raw_state, _completed_tasks, _format_duration


# Rough token estimates per phase (based on typical runs).
_ESTIMATED_TOKENS_PER_PHASE = {
    "build": 150_000,
    "test": 5_000,
    "fix": 80_000,
    "static_check": 5_000,
    "static_fix": 40_000,
    "document": 30_000,
    "milestone": 50_000,
}

# Average seconds per task from historical data (fallback).
_DEFAULT_SECONDS_PER_TASK = 180


def estimate_task_tokens(task: str, project_dir: Path) -> int:
    """Estimate token usage for a single task based on description length."""
    from runner.roadmap import _load_roadmap  # noqa: PLC0415

    roadmap = _load_roadmap(project_dir)
    for t in roadmap.get("tasks", []):
        heading = f"## {t['id']:03d} - {t['title']}"
        if heading == task:
            desc_len = len(str(t.get("description", "")))
            # Longer descriptions → more build tokens.
            build_multiplier = max(1.0, desc_len / 500)
            base = int(_ESTIMATED_TOKENS_PER_PHASE["build"] * build_multiplier)
            # Add test/static/document overhead.
            overhead = (
                _ESTIMATED_TOKENS_PER_PHASE["test"]
                + _ESTIMATED_TOKENS_PER_PHASE["document"]
                + _ESTIMATED_TOKENS_PER_PHASE["static_check"]
            )
            # Milestones are cheaper.
            if t.get("agent") == "milestone":
                return _ESTIMATED_TOKENS_PER_PHASE["milestone"]
            return base + overhead

    return _ESTIMATED_TOKENS_PER_PHASE["build"] + _ESTIMATED_TOKENS_PER_PHASE["document"]


def _tokens_to_usd(tokens: int) -> float:
    """Estimate USD cost from token count using a blended rate."""
    # Approximate input/output split: 70% input, 30% output.
    input_tokens = int(tokens * 0.7)
    output_tokens = int(tokens * 0.3)
    cost = (
        input_tokens * _PRICES["input"]
        + output_tokens * _PRICES["output"]
    ) / 1_000_000
    return round(cost, 4)


def dry_run(project_dir: Path) -> dict:
    """Walk the dependency graph and estimate cost/time for remaining tasks.

    Returns:
        Summary dict with task breakdown, totals, and estimated cost.
    """
    from rich.table import Table  # noqa: PLC0415
    from runner.config import rbox  # noqa: PLC0415

    all_tasks = get_tasks(project_dir)
    graph = parse_task_graph(project_dir)
    state = _raw_state(project_dir)
    done_set = _completed_tasks(state)
    durations = state.get("task_durations", [])

    # Compute average seconds per task.
    avg_sec = (
        sum(durations) / len(durations)
        if durations
        else _DEFAULT_SECONDS_PER_TASK
    )

    remaining = [t for t in all_tasks if t not in done_set]
    layers = get_task_layers(all_tasks, graph, project_dir)

    task_estimates: list[dict] = []
    total_tokens = 0

    for task in remaining:
        est_tokens = estimate_task_tokens(task, project_dir)
        est_usd = _tokens_to_usd(est_tokens)
        is_ms = is_milestone_task(task, project_dir)
        task_estimates.append({
            "task": task.lstrip("# ").strip(),
            "tokens": est_tokens,
            "usd": est_usd,
            "type": "milestone" if is_ms else "build",
        })
        total_tokens += est_tokens

    total_usd = _tokens_to_usd(total_tokens)

    # Estimate time: count layers (with parallelism) for remaining tasks.
    remaining_set = set(remaining)
    remaining_layers = 0
    tasks_in_remaining_layers = 0
    for layer in layers:
        layer_remaining = [t for t in layer if t in remaining_set]
        if layer_remaining:
            remaining_layers += 1
            # With parallelism, a layer takes ceil(tasks / parallel_agents) rounds.
            if MAX_PARALLEL_AGENTS > 1:
                rounds = -(-len(layer_remaining) // MAX_PARALLEL_AGENTS)
            else:
                rounds = len(layer_remaining)
            tasks_in_remaining_layers += rounds

    est_time_sec = tasks_in_remaining_layers * avg_sec

    # Print summary.
    _console.print()
    _console.rule("[bold]Dry Run — Cost & Time Estimate[/]", style="blue")
    _console.print()

    t = Table(box=rbox.ROUNDED, border_style="bright_black", title="[bold]Task Breakdown[/]", title_style="")
    t.add_column("Task", style="dim", no_wrap=False)
    t.add_column("Type", style="cyan", no_wrap=True)
    t.add_column("Est. Tokens", justify="right")
    t.add_column("Est. Cost", justify="right")

    for est in task_estimates:
        t.add_row(
            est["task"],
            est["type"],
            _format_tokens(est["tokens"]),
            f"${est['usd']:.4f}",
        )

    _console.print(t)

    _console.print()
    _console.print("[bold]Summary:[/]")
    _console.print(f"  Tasks remaining:    [bold]{len(remaining)}[/] / {len(all_tasks)}")
    _console.print(f"  Completed:          [green]{len(done_set)}[/]")
    _console.print(f"  Est. total tokens:  [bold]{_format_tokens(total_tokens)}[/]")
    _console.print(f"  Est. total cost:    [bold]${total_usd:.4f}[/]")
    _console.print(f"  Est. time:          [bold]{_format_duration(est_time_sec)}[/]")
    _console.print(f"  Max parallel agents: {MAX_PARALLEL_AGENTS}")
    _console.print(f"  Max attempts/task:   {MAX_ATTEMPTS}")
    _console.print()

    return {
        "remaining_tasks": len(remaining),
        "total_tasks": len(all_tasks),
        "completed_tasks": len(done_set),
        "estimated_tokens": total_tokens,
        "estimated_usd": total_usd,
        "estimated_time_sec": est_time_sec,
        "task_breakdown": task_estimates,
    }
