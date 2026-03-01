"""plan.py — ROADMAP.json generation from natural language descriptions."""

import json
import subprocess
import tempfile
from pathlib import Path

import questionary

from runner.config import (
    OPENCODE_CMD,
    PROJECTS_ROOT,
    ROADMAP_FILENAME,
    _console,
    render_prompt,
)


def generate_roadmap_interactive(project_name: str | None = None) -> Path | None:
    """Interactive ROADMAP generation: get description, call architect, validate, approve.

    Returns:
        Path to the created ROADMAP.json, or None if cancelled.
    """
    _console.print("\n[bold]ROADMAP Generator[/]")
    _console.print(
        "[dim]Describe your project in plain language and the AI will generate a ROADMAP.[/]\n"
    )

    # Get project name.
    if not project_name:
        project_name = questionary.text(
            "Project name (lowercase, no spaces):",
            validate=lambda x: len(x.strip()) > 0,
        ).ask()
        if not project_name:
            return None
    project_name = project_name.strip().lower().replace(" ", "-")

    # Get description.
    description = questionary.text(
        "Describe your project (be detailed — what it does, tech stack, features):",
    ).ask()
    if not description:
        return None

    # Get ecosystem.
    ecosystem = questionary.select(
        "Ecosystem:",
        choices=["python", "deno", "node", "go", "rust"],
        default="python",
    ).ask()
    if not ecosystem:
        return None

    full_description = (
        f"Project: {project_name}\nEcosystem: {ecosystem}\n\n{description}"
    )

    _console.print("\n[dim]Generating ROADMAP with AI architect...[/]")

    # Call opencode architect agent.
    roadmap_json = _call_architect(full_description, project_name, ecosystem)

    if roadmap_json is None:
        _console.print("[red]Failed to generate ROADMAP.[/]")
        return None

    # Validate the generated JSON.
    try:
        roadmap = json.loads(roadmap_json)
    except json.JSONDecodeError as e:
        _console.print(f"[red]Generated invalid JSON: {e}[/]")
        _console.print(f"[dim]Raw output:[/]\n{roadmap_json[:2000]}")
        return None

    # Ensure ecosystem is set.
    roadmap.setdefault("ecosystem", ecosystem)
    roadmap.setdefault("git", {"enabled": True})

    # Pretty-print for review.
    formatted = json.dumps(roadmap, indent=2)
    _console.print("\n[bold]Generated ROADMAP:[/]\n")
    _console.print(formatted)

    # Ask for approval.
    action = questionary.select(
        "\nWhat would you like to do?",
        choices=[
            questionary.Choice(title="✔ Accept and save", value="accept"),
            questionary.Choice(title="✎ Edit description and regenerate", value="edit"),
            questionary.Choice(title="✗ Cancel", value="cancel"),
        ],
    ).ask()

    if action == "cancel" or action is None:
        return None

    if action == "edit":
        return generate_roadmap_interactive(project_name)

    # Save to project directory.
    project_dir = PROJECTS_ROOT / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    roadmap_path = project_dir / ROADMAP_FILENAME
    roadmap_path.write_text(formatted, encoding="utf-8")

    # Validate with check_roadmap.
    _console.print("\n[dim]Validating generated ROADMAP...[/]")
    from helpers.check_roadmap import run_checks  # noqa: PLC0415

    rc = run_checks(roadmap_path)
    if rc != 0:
        _console.print(
            "[yellow]⚠ ROADMAP has validation warnings/errors. You may need to fix them.[/]"
        )
    else:
        _console.print("[green]✔ ROADMAP validation passed.[/]")

    _console.print(f"\n[green bold]✔ Saved:[/] {roadmap_path}")
    return roadmap_path


def _call_architect(
    description: str, project_name: str, ecosystem: str = "python"
) -> str | None:
    """Invoke the architect agent to generate ROADMAP JSON from a description."""
    prompt = render_prompt("generate", DESCRIPTION=description, ECOSYSTEM=ecosystem)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(prompt)
        tmpfile = f.name

    try:
        # Use opencode in non-interactive mode.
        tmpfile_posix = Path(tmpfile).resolve().as_posix()
        cmd = (
            f'{OPENCODE_CMD} run "Generate the ROADMAP.json as specified in the attached file. '
            f'Output ONLY the JSON, no markdown fences." '
            f'--agent architect -f "{tmpfile_posix}"'
        )

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

        output = result.stdout.strip()
        if not output:
            _console.print("[red]No output from architect agent.[/]")
            if result.stderr:
                _console.print(f"[dim]{result.stderr[:500]}[/]")
            return None

        # Extract JSON from the output (skip any non-JSON preamble).
        return _extract_json(output)

    except subprocess.TimeoutExpired:
        _console.print("[red]Architect agent timed out.[/]")
        return None
    except Exception as exc:
        _console.print(f"[red]Error calling architect: {exc}[/]")
        return None
    finally:
        Path(tmpfile).unlink(missing_ok=True)


def _extract_json(text: str) -> str | None:
    """Extract the first valid JSON object from text, handling markdown fences."""
    import re  # noqa: PLC0415

    # Remove markdown code fences.
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)

    # Try to find a JSON object.
    # Look for the first { and last }.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    return text if text.startswith("{") else None
