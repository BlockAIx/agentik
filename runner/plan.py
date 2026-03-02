"""plan.py — ROADMAP.json generation from natural language descriptions."""

import datetime
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import questionary

from runner.config import (
    OPENCODE_CMD,
    PROJECTS_ROOT,
    ROADMAP_FILENAME,
    _console,
    render_prompt,
)

# Default timeout for architect agent (seconds).  Override with
# ROADMAP_GEN_TIMEOUT env var.  10 minutes is generous enough for most
# models while still providing a safety net.
_ARCHITECT_TIMEOUT: int = int(os.environ.get("ROADMAP_GEN_TIMEOUT", "600"))

# ANSI escape sequence pattern (matches CSI, OSC, and standalone ESC codes).
_ANSI_RE = re.compile(
    r"\x1b"
    r"(?:"
    r"\[[0-9;?]*[A-Za-z]"
    r"|\][^\x07\x1b]*(?:\x07|\x1b\\)"
    r"|[^\[\]]"
    r")"
)


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from *text*."""
    return _ANSI_RE.sub("", text)


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

    # Scaffold project dirs, budget, git, opencode config, and AGENTS.md.
    from runner.workspace import ensure_workspace_dirs  # noqa: PLC0415

    ensure_workspace_dirs(project_dir)

    _console.print(f"\n[green bold]✔ Saved:[/] {roadmap_path}")
    return roadmap_path


def _call_architect(
    description: str, project_name: str, ecosystem: str = "python"
) -> str | None:
    """Invoke the architect agent to generate ROADMAP JSON from a description.

    Uses ``Popen`` with streaming output capture so the user sees a live
    progress spinner, and partial output is preserved if the process times
    out.  Retries once with a doubled timeout on the first timeout.
    """
    prompt = render_prompt("generate", DESCRIPTION=description, ECOSYSTEM=ecosystem)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(prompt)
        tmpfile = f.name

    timeout = _ARCHITECT_TIMEOUT
    project_dir = PROJECTS_ROOT / project_name

    for attempt in range(1, 3):  # max 2 attempts
        result = _run_architect_once(tmpfile, timeout, project_dir, attempt)
        if result is not None:
            Path(tmpfile).unlink(missing_ok=True)
            return result

        # On first timeout, retry with a longer budget.
        if attempt == 1 and _last_architect_timed_out:
            _console.print(
                f"[yellow]⟳ Retrying with extended timeout ({timeout * 2}s)...[/]"
            )
            timeout *= 2
        else:
            break

    Path(tmpfile).unlink(missing_ok=True)
    return None


# Sentinel set by _run_architect_once so _call_architect knows whether to retry.
_last_architect_timed_out: bool = False


def _run_architect_once(
    tmpfile: str, timeout: int, project_dir: Path | None = None, attempt: int = 1
) -> str | None:
    """Run the opencode architect subprocess once, streaming output and enforcing *timeout*.

    Captured output is written (ANSI-stripped) to
    ``<project_dir>/logs/roadmap-generate/<timestamp>_generate_a<attempt>.log``.

    Returns extracted JSON on success, or ``None`` on failure.
    Sets the module-level ``_last_architect_timed_out`` flag.
    """
    global _last_architect_timed_out  # noqa: PLW0603
    _last_architect_timed_out = False

    tmpfile_posix = Path(tmpfile).resolve().as_posix()
    dir_flag = ""
    if project_dir is not None and project_dir.exists():
        dir_flag = f' --dir "{project_dir.resolve().as_posix()}"'
    cmd = (
        f'{OPENCODE_CMD} run "You must output ONLY a raw JSON object. '
        f"Do NOT read files, do NOT use tools, do NOT plan or delegate. "
        f"All information is in the attached file. "
        f'Generate the complete ROADMAP.json directly in your response." '
        f'--agent architect{dir_flag} -f "{tmpfile_posix}"'
    )

    collected: list[str] = []
    proc: subprocess.Popen[str] | None = None

    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdout is not None

        # Read output in a background thread so we can enforce a timeout on
        # the main thread while still streaming lines to the console.
        def _reader() -> None:
            assert proc is not None and proc.stdout is not None
            for line in proc.stdout:
                collected.append(line)
                # Stream every line to the console in real time.
                print(line, end="", flush=True)

        reader_thread = threading.Thread(target=_reader, daemon=True)
        reader_thread.start()

        start = time.monotonic()
        while proc.poll() is None:
            elapsed = int(time.monotonic() - start)
            if elapsed >= timeout:
                _last_architect_timed_out = True
                proc.kill()
                break
            time.sleep(0.25)

        # Give the reader thread a moment to flush remaining output.
        reader_thread.join(timeout=3)

        # Write captured output to a log file in the project logs directory.
        log_path = _write_generate_log(collected, project_dir, attempt)
        if log_path is not None:
            log_rel = log_path.relative_to(project_dir) if project_dir else log_path
            _console.print(f"  [dim]→ {log_rel}[/]")

        if _last_architect_timed_out:
            elapsed = int(time.monotonic() - start)
            _console.print(
                f"[red]Architect agent timed out after {elapsed}s "
                f"({len(collected)} lines captured).[/]"
            )
            # Try to salvage partial output.
            partial = "".join(collected).strip()
            if partial:
                _console.print(
                    f"[dim]Partial output ({len(partial)} chars) — attempting JSON extraction…[/]"
                )
                result = _extract_json(partial)
                if result is not None:
                    _console.print(
                        "[green]✔ Extracted valid JSON from partial output.[/]"
                    )
                    return result
                _console.print(
                    "[dim]Could not extract valid JSON from partial output.[/]"
                )
                # Show first/last part for debugging.
                preview = partial[:300] + ("\n…" if len(partial) > 300 else "")
                _console.print(f"[dim]Output preview:[/]\n{preview}")
            return None

        # Process finished normally.
        output = "".join(collected).strip()
        if proc.returncode != 0:
            _console.print(
                f"[red]Architect agent exited with code {proc.returncode}.[/]"
            )
            if output:
                _console.print(f"[dim]{output[:800]}[/]")
            return None

        if not output:
            _console.print("[red]No output from architect agent.[/]")
            return None

        return _extract_json(output)

    except FileNotFoundError:
        _console.print(
            f"[red]opencode binary not found: {OPENCODE_CMD!r}[/]\n"
            "[dim]Set OPENCODE_CMD env var or ensure opencode is on PATH.[/]"
        )
        return None
    except Exception as exc:
        _console.print(f"[red]Error calling architect: {exc}[/]")
        return None
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()


def _write_generate_log(
    collected: list[str], project_dir: Path | None, attempt: int
) -> Path | None:
    """Write ANSI-stripped captured output to the project's logs directory.

    Log path: ``<project_dir>/logs/roadmap-generate/<YYYYMMDD_HHMMSS>_generate_a<N>.log``

    Returns the log path on success, or ``None`` if no project dir or write fails.
    """
    if project_dir is None or not collected:
        return None
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = project_dir / "logs" / "roadmap-generate"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{timestamp}_generate_a{attempt}.log"
        with log_path.open("w", encoding="utf-8", errors="replace") as fh:
            for line in collected:
                fh.write(_strip_ansi(line))
        return log_path
    except Exception as exc:  # noqa: BLE001
        _console.print(f"[dim](Could not write generate log: {exc})[/]")
        return None


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
