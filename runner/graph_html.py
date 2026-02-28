"""graph_html.py — Generate an interactive HTML dependency graph using Mermaid.js."""

import json
import re
import webbrowser
from pathlib import Path

from runner.config import _console
from runner.roadmap import (
    get_task_agent,
    get_task_layers,
    get_tasks,
    parse_task_graph,
)
from runner.state import (
    _completed_tasks,
    _format_tokens,
    _raw_state,
    load_project_budget,
)


def generate_graph_html(project_dir: Path, open_browser: bool = True) -> Path:
    """Generate an interactive HTML dependency graph and optionally open it.

    Returns:
        Path to the generated HTML file.
    """
    all_tasks = get_tasks(project_dir)
    graph = parse_task_graph(project_dir)
    state = _raw_state(project_dir)
    done_set = _completed_tasks(state)
    layers = get_task_layers(all_tasks, graph, project_dir)

    # Collect per-task token spend from budget.
    budget = load_project_budget(project_dir)
    task_tokens: dict[str, int] = {}
    for session in budget.get("sessions", []):
        task_name = session.get("task", "")
        task_tokens[task_name] = task_tokens.get(task_name, 0) + session.get("tokens", 0)

    # Build Mermaid graph definition.
    mermaid_lines = ["graph TD"]
    node_ids: dict[str, str] = {}

    for task in all_tasks:
        # Create node ID.
        m = re.match(r"^## (\d{3}) - (.+)$", task)
        if m:
            node_id = f"T{m.group(1)}"
            label = f"{m.group(1)} - {m.group(2)}"
        else:
            node_id = re.sub(r"[^a-zA-Z0-9]", "", task)[:20]
            label = task.lstrip("# ").strip()
        node_ids[task] = node_id

        # Status styling.
        tokens = task_tokens.get(task, 0)
        token_str = f"<br/>{_format_tokens(tokens)} tokens" if tokens else ""
        agent = get_task_agent(task, project_dir)
        agent_str = f"<br/>({agent})" if agent != "build" else ""

        if task in done_set:
            mermaid_lines.append(f'    {node_id}["{label}{agent_str}{token_str}"]')
            mermaid_lines.append(f"    style {node_id} fill:#22c55e,stroke:#16a34a,color:#fff")
        else:
            # Check if ready.
            deps = graph.get(task, [])
            all_deps_done = all(d in done_set for d in deps)
            if all_deps_done:
                mermaid_lines.append(f'    {node_id}["{label}{agent_str}{token_str}"]')
                mermaid_lines.append(f"    style {node_id} fill:#eab308,stroke:#ca8a04,color:#000")
            else:
                mermaid_lines.append(f'    {node_id}["{label}{agent_str}{token_str}"]')
                mermaid_lines.append(f"    style {node_id} fill:#6b7280,stroke:#4b5563,color:#fff")

    # Add edges.
    for task in all_tasks:
        deps = graph.get(task, [])
        for dep in deps:
            if dep in node_ids and task in node_ids:
                mermaid_lines.append(f"    {node_ids[dep]} --> {node_ids[task]}")

    mermaid_def = "\n".join(mermaid_lines)

    # Build the overall project stats.
    total_tokens = budget.get("total_tokens", 0)
    total_calls = budget.get("total_calls", 0)
    done_count = len(done_set)
    total_count = len(all_tasks)

    # Collect per-task log paths.
    log_dir = project_dir / "logs"
    log_links: dict[str, list[str]] = {}
    if log_dir.exists():
        for task_log_dir in sorted(log_dir.iterdir()):
            if task_log_dir.is_dir():
                logs = sorted(task_log_dir.glob("*.log"))
                if logs:
                    log_links[task_log_dir.name] = [
                        l.relative_to(project_dir).as_posix() for l in logs
                    ]

    log_links_json = json.dumps(log_links)

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{project_dir.name} — Dependency Graph</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background: #0f172a;
        color: #e2e8f0;
        min-height: 100vh;
    }}
    .header {{
        background: #1e293b;
        padding: 1.5rem 2rem;
        border-bottom: 1px solid #334155;
    }}
    .header h1 {{
        font-size: 1.5rem;
        margin-bottom: 0.5rem;
    }}
    .stats {{
        display: flex;
        gap: 2rem;
        flex-wrap: wrap;
    }}
    .stat {{
        background: #334155;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        font-size: 0.9rem;
    }}
    .stat .value {{ font-weight: bold; color: #38bdf8; }}
    .legend {{
        display: flex;
        gap: 1rem;
        margin-top: 1rem;
        flex-wrap: wrap;
    }}
    .legend-item {{
        display: flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.85rem;
    }}
    .legend-dot {{
        width: 14px;
        height: 14px;
        border-radius: 3px;
    }}
    .graph-container {{
        padding: 2rem;
        display: flex;
        justify-content: center;
        overflow: auto;
    }}
    .mermaid {{
        max-width: 100%;
    }}
    .mermaid svg {{
        max-width: none !important;
    }}
    .footer {{
        text-align: center;
        padding: 1rem;
        color: #64748b;
        font-size: 0.8rem;
    }}
</style>
</head>
<body>
<div class="header">
    <h1>📊 {project_dir.name}</h1>
    <div class="stats">
        <div class="stat">Tasks: <span class="value">{done_count} / {total_count}</span></div>
        <div class="stat">Tokens: <span class="value">{_format_tokens(total_tokens)}</span></div>
        <div class="stat">API Calls: <span class="value">{total_calls}</span></div>
        <div class="stat">Layers: <span class="value">{len(layers)}</span></div>
    </div>
    <div class="legend">
        <div class="legend-item"><div class="legend-dot" style="background:#22c55e"></div> Done</div>
        <div class="legend-item"><div class="legend-dot" style="background:#eab308"></div> Ready</div>
        <div class="legend-item"><div class="legend-dot" style="background:#6b7280"></div> Blocked</div>
        <div class="legend-item"><div class="legend-dot" style="background:#ef4444"></div> Failed</div>
        <div class="legend-item"><div class="legend-dot" style="background:#3b82f6"></div> Running</div>
    </div>
</div>
<div class="graph-container">
    <pre class="mermaid">
{mermaid_def}
    </pre>
</div>
<div class="footer">
    Generated by agentik runner &bull; {project_dir.name}
</div>
<script>
    mermaid.initialize({{
        startOnLoad: true,
        theme: 'dark',
        themeVariables: {{
            primaryColor: '#334155',
            primaryTextColor: '#e2e8f0',
            lineColor: '#64748b',
        }},
        flowchart: {{
            useMaxWidth: false,
            htmlLabels: true,
            curve: 'basis',
        }},
    }});
</script>
</body>
</html>
"""

    output_path = project_dir / "dependency_graph.html"
    output_path.write_text(html, encoding="utf-8")
    _console.print(f"[green]✔ Graph saved:[/] {output_path}")

    if open_browser:
        webbrowser.open(output_path.as_uri())

    return output_path
