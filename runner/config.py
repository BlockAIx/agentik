"""config.py — Global constants, Rich console, and prompt-template loader."""

import json
import os
import re
import sys
from pathlib import Path

from rich import (
    box as rbox,  # noqa: F401  re-exported; imported via `from runner.config import rbox`
)
from rich.console import Console

# ── Windows UTF-8 console ──────────────────────────────────────────────────────
# Reconfigure Python's own stdout/stderr to UTF-8 so non-Rich prints work.
# We deliberately do NOT call `chcp 65001` — the old Windows console (conhost)
# has a well-known bug where CP65001 makes some characters invisible in the
# terminal (they are still present in the clipboard). Modern Windows Terminal
# handles UTF-8 natively without any code-page switch.
if sys.platform == "win32":
    if not os.environ.get("PYTHONIOENCODING"):
        os.environ["PYTHONIOENCODING"] = "utf-8"
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass

# force_terminal=True ensures Rich always emits proper ANSI sequences on
# Windows, preventing the "jumbled output until you click" bug caused by
# prompt_toolkit (questionary) leaving the terminal in raw mode.
# legacy_windows=False prevents Rich from using the Win32 console API (which
# encodes via cp1252 and fails on box-drawing / emoji characters); modern
# Windows Terminal handles ANSI sequences natively.
_console = Console(force_terminal=True, legacy_windows=False)

# ── Budget constants ───────────────────────────────────────────────────────────

with open("budget.json", encoding="utf-8") as _f:
    _budget = json.load(_f)

MAX_ATTEMPTS: int = _budget["max_attempts_per_task"]
MAX_PARALLEL_AGENTS: int = _budget.get("max_parallel_agents", 1)
MONTHLY_LIMIT_TOKENS: int = _budget["monthly_limit_tokens"]
_PRICES: dict = _budget["token_prices_usd_per_million"]

# ── opencode binary ────────────────────────────────────────────────────────────

# Path or name of the opencode binary.  Override with OPENCODE_CMD env var
# (e.g. inside Docker where it lives at a non-standard location).
OPENCODE_CMD: str = os.environ.get("OPENCODE_CMD", "opencode")

# ── Paths ──────────────────────────────────────────────────────────────────────

# Output root — every project lives in its own subdirectory here.
PROJECTS_ROOT = Path("projects")

# The filename used for project roadmaps (JSON format).
ROADMAP_FILENAME = "ROADMAP.json"

# Global monthly-baseline state lives at the workspace root.
_BUDGET_STATE_FILE = Path(".budget_state.json")

# Prompt templates: one .md file per pipeline phase.
# __file__ is runner/config.py → parent is runner/ → parent is workspace root.
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# ── Prompt rendering ───────────────────────────────────────────────────────────


def render_prompt(name: str, **kwargs: str) -> str:
    """Load ``prompts/<name>.md`` and replace ``{{KEY}}`` placeholders with *kwargs*.

    Args:
        name:    Template file stem (e.g. ``"build"``).
        **kwargs: Placeholder values.

    Returns:
        Rendered prompt string.
    """
    template_path = PROMPTS_DIR / f"{name}.md"
    if not template_path.exists():
        raise FileNotFoundError(
            f"Prompt template not found: {template_path}\n"
            f"Expected one of: {sorted(p.stem for p in PROMPTS_DIR.glob('*.md'))}"
        )
    text = template_path.read_text(encoding="utf-8")
    for key, value in kwargs.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


# ── Utilities ──────────────────────────────────────────────────────────────────


def slugify(task: str) -> str:
    """Convert a ``## NNN - Title`` heading to a lowercase safe slug for branch names."""
    return re.sub(r"[^a-z0-9]+", "-", task.lower().lstrip("#").strip()).strip("-")


# ── Verbosity mode ─────────────────────────────────────────────────────────────

# Default is compact: agent output is captured silently; errors are shown inline.
# Set to True to stream every agent line to the terminal in real time.
_verbose: bool = False


def set_verbose(v: bool) -> None:
    """Switch the global log verbosity mode.  True = stream; False = compact (default)."""
    global _verbose
    _verbose = v


def is_verbose() -> bool:
    """Return True when verbose (full-stream) mode is active."""
    return _verbose


# Number of log tail lines shown inline when an agent exits with a non-zero code
# in compact mode.
_LOG_TAIL_LINES: int = 40
