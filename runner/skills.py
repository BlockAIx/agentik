"""skills.py — Skill discovery, loading, and prompt injection."""

import json
from pathlib import Path

from runner.config import _console

# Workspace-level skills directory.
_SKILLS_DIR = Path(__file__).parent.parent / "skills"


def _skill_dirs() -> list[Path]:
    """Return all valid skill directories (must contain SKILL.md)."""
    if not _SKILLS_DIR.is_dir():
        return []
    return sorted(
        d for d in _SKILLS_DIR.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
    )


def list_skills() -> list[dict]:
    """Return metadata dicts for every installed skill."""
    result: list[dict] = []
    for d in _skill_dirs():
        meta = _load_meta(d)
        result.append(meta)
    return result


def _load_meta(skill_dir: Path) -> dict:
    """Load skill.json metadata, falling back to sensible defaults."""
    meta_path = skill_dir / "skill.json"
    meta: dict = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    slug = skill_dir.name
    return {
        "slug": slug,
        "name": meta.get("name", slug),
        "description": meta.get("description", ""),
        "agents": meta.get("agents", ["build", "architect"]),
    }


def get_skill_content(slug: str) -> str | None:
    """Read the SKILL.md content for a given skill slug."""
    skill_path = _SKILLS_DIR / slug / "SKILL.md"
    if not skill_path.exists():
        return None
    return skill_path.read_text(encoding="utf-8")


def get_agent_skills(agent: str, project_dir: Path) -> list[str]:
    """Return the skill slugs assigned to *agent* in the project config."""
    config = _load_opencode_config(project_dir)
    agents = config.get("agent", {})
    agent_cfg = agents.get(agent, {})
    skills = agent_cfg.get("skills", [])
    if isinstance(skills, str):
        return [skills]
    return list(skills)


def collect_skill_blocks(agent: str, project_dir: Path) -> str:
    """Build the prompt block with all skill content for *agent*.

    Returns a markdown section ready for template injection, or empty string.
    """
    slugs = get_agent_skills(agent, project_dir)
    if not slugs:
        return ""

    parts: list[str] = []
    for slug in slugs:
        content = get_skill_content(slug)
        if content:
            skill_dir = (_SKILLS_DIR / slug).resolve()
            # Rewrite self-referencing paths so agents in project dirs can
            # find runtime files (scripts, data) shipped with the skill.
            content = content.replace(f"skills/{slug}/", str(skill_dir) + "/")
            preamble = f"> **Skill directory:** `{skill_dir}`\n\n"
            parts.append(
                f"### Skill: {slug}\n\n{preamble}{content.strip()}"
            )
        else:
            _console.print(f"[yellow]⚠ Skill '{slug}' not found — skipping[/]")

    if not parts:
        return ""

    return "\n## Skills\n\n" + "\n\n---\n\n".join(parts) + "\n"


def save_agent_skills(
    agent: str, project_dir: Path, skill_slugs: list[str]
) -> None:
    """Persist the skill list for *agent* in the project's opencode.jsonc."""
    import re as _re  # noqa: PLC0415

    config_path = project_dir / "opencode.jsonc"

    config: dict = {}
    if config_path.exists():
        text = config_path.read_text(encoding="utf-8")
        cleaned = _re.sub(
            r'"(?:[^"\\]|\\.)*"|//.*$',
            lambda m: m.group() if m.group().startswith('"') else "",
            text,
            flags=_re.MULTILINE,
        )
        try:
            config = json.loads(cleaned)
        except json.JSONDecodeError:
            config = {}

    if "agent" not in config:
        config["agent"] = {}
    if agent not in config["agent"]:
        config["agent"][agent] = {}
    config["agent"][agent]["skills"] = skill_slugs

    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def _load_opencode_config(project_dir: Path) -> dict:
    """Load opencode.jsonc from project or workspace root (comments stripped)."""
    import re as _re  # noqa: PLC0415

    for candidate in [project_dir / "opencode.jsonc", Path("opencode.jsonc")]:
        if candidate.exists():
            text = candidate.read_text(encoding="utf-8")
            cleaned = _re.sub(
                r'"(?:[^"\\]|\\.)*"|//.*$',
                lambda m: m.group() if m.group().startswith('"') else "",
                text,
                flags=_re.MULTILINE,
            )
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue
    return {}
