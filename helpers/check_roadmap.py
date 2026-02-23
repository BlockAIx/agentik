"""Validate a project ROADMAP.json against runner conventions.

Keep in sync with AGENTS.md / .github/copilot-instructions.md when
changing field keys, valid agents/ecosystems, or architecture rules.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Configuration -- mirrors AGENTS.md conventions
# ---------------------------------------------------------------------------

# Titles become git branch names; keep slug-friendly and reasonably short.
MAX_TITLE_WORDS: int = 6

VALID_AGENTS: frozenset[str] = frozenset(
    {"build", "fix", "test", "document", "explore", "plan", "architect", "milestone"}
)

VALID_ECOSYSTEMS: frozenset[str] = frozenset({"python", "deno", "node", "go", "rust"})

# Architecture enforcement: tasks whose outputs land in a "protected" namespace
# must not depend on tasks whose outputs land in a "forbidden" namespace.
ARCH_RULES: dict[str, list[str]] = {
    "src/core/": ["src/render/"],
    "src/content/": ["src/render/"],
}

# All recognized task-level field keys.
_ALL_TASK_FIELDS = frozenset(
    {
        "id",
        "title",
        "agent",
        "ecosystem",
        "depends_on",
        "context",
        "outputs",
        "acceptance",
        "version",
        "description",
        "deploy",
    }
)

# Recognised keys inside the top-level "deploy" block.
_DEPLOY_BLOCK_FIELDS = frozenset({"enabled", "script", "env"})

# Recognised keys inside the top-level "git" block.
_GIT_BLOCK_FIELDS = frozenset({"enabled"})


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class Issue(NamedTuple):
    level: str  # "ERROR" | "WARNING"
    task: str  # 3-digit string or "preamble"
    message: str


@dataclass
class Task:
    number: int
    title: str
    raw: dict  # original JSON dict for the task
    outputs: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)
    acceptance: str = ""
    agent: str = ""
    ecosystem: str = ""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _resolve_text(value) -> str:
    """Convert a string or list-of-strings field to a single string."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(s) for s in value)
    return str(value)


def parse_roadmap(data: dict) -> tuple[str, list[Task]]:
    """Return (preamble_text, list_of_tasks) from a parsed ROADMAP JSON dict."""
    preamble = _resolve_text(data.get("preamble", ""))
    tasks: list[Task] = []

    for entry in data.get("tasks", []):
        if not isinstance(entry, dict):
            continue
        task_id = entry.get("id")
        title = entry.get("title", "")
        if task_id is None:
            continue

        t = Task(
            number=int(task_id),
            title=str(title).strip(),
            raw=entry,
        )

        # Extract fields
        outputs = entry.get("outputs", [])
        if isinstance(outputs, str):
            t.outputs = [p.strip() for p in outputs.split(",") if p.strip()]
        elif isinstance(outputs, list):
            t.outputs = [str(o).strip() for o in outputs if str(o).strip()]

        deps = entry.get("depends_on", [])
        if isinstance(deps, list):
            t.depends_on = [int(d) for d in deps if isinstance(d, (int, float))]

        t.acceptance = str(entry.get("acceptance", "")).strip()
        t.agent = str(entry.get("agent", "")).strip()
        t.ecosystem = str(entry.get("ecosystem", "")).strip()

        tasks.append(t)

    return preamble, tasks


# ---------------------------------------------------------------------------
# Individual checks -- each returns a list[Issue]
# ---------------------------------------------------------------------------


def check_preamble(data: dict, _tasks: list[Task]) -> list[Issue]:
    issues: list[Issue] = []
    eco = data.get("ecosystem", "")
    if eco and eco not in VALID_ECOSYSTEMS:
        issues.append(
            Issue(
                "WARNING",
                "preamble",
                f"Unknown ecosystem '{eco}'; known: {sorted(VALID_ECOSYSTEMS)}",
            )
        )
    return issues


def check_deploy_block(data: dict, tasks: list[Task]) -> list[Issue]:
    """Validate the optional top-level ``deploy`` block and per-task ``deploy`` flags."""
    issues: list[Issue] = []
    deploy = data.get("deploy")
    if deploy is None:
        return issues  # no deploy block — perfectly fine
    if not isinstance(deploy, dict):
        issues.append(Issue("ERROR", "preamble", "'deploy' must be an object (dict)"))
        return issues
    for key in deploy:
        if key not in _DEPLOY_BLOCK_FIELDS:
            issues.append(Issue("WARNING", "preamble", f"Unknown deploy field '{key}'"))
    enabled = deploy.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        issues.append(Issue("ERROR", "preamble", "deploy.enabled must be a boolean"))
    env = deploy.get("env")
    if env is not None and not isinstance(env, dict):
        issues.append(Issue("ERROR", "preamble", "deploy.env must be an object (dict)"))
    script = deploy.get("script")
    if script is not None and not isinstance(script, str):
        issues.append(Issue("ERROR", "preamble", "deploy.script must be a string"))
    # Check per-task deploy flags.
    for t in tasks:
        tag = f"{t.number:03d}"
        val = t.raw.get("deploy")
        if val is not None and not isinstance(val, bool):
            issues.append(
                Issue(
                    "ERROR", tag, "Task-level 'deploy' must be a boolean (true/false)"
                )
            )
    return issues


def check_git_block(data: dict, _tasks: list[Task]) -> list[Issue]:
    """Validate the optional top-level ``git`` block."""
    issues: list[Issue] = []
    git = data.get("git")
    if git is None:
        return issues
    if not isinstance(git, dict):
        issues.append(Issue("ERROR", "preamble", "'git' must be an object (dict)"))
        return issues
    for key in git:
        if key not in _GIT_BLOCK_FIELDS:
            issues.append(Issue("WARNING", "preamble", f"Unknown git field '{key}'"))
    enabled = git.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        issues.append(Issue("ERROR", "preamble", "git.enabled must be a boolean"))
    return issues


def check_numbering(_data: dict, tasks: list[Task]) -> list[Issue]:
    issues: list[Issue] = []
    if not tasks:
        issues.append(Issue("ERROR", "000", "No tasks found in file"))
        return issues
    seen: set[int] = set()
    for t in tasks:
        tag = f"{t.number:03d}"
        if t.number in seen:
            issues.append(Issue("ERROR", tag, f"Duplicate task number {tag}"))
        seen.add(t.number)
    nums = sorted(seen)
    for expected in range(nums[0], nums[-1] + 1):
        if expected not in seen:
            issues.append(
                Issue(
                    "ERROR", f"{expected:03d}", f"Gap: task {expected:03d} is missing"
                )
            )
    return issues


def check_fields(_data: dict, tasks: list[Task]) -> list[Issue]:
    issues: list[Issue] = []
    for t in tasks:
        tag = f"{t.number:03d}"
        # Milestone tasks don't require outputs or acceptance.
        if t.agent == "milestone":
            continue
        if not t.outputs:
            issues.append(Issue("ERROR", tag, "Missing required 'outputs' field"))
        if not t.acceptance:
            issues.append(Issue("ERROR", tag, "Missing required 'acceptance' field"))
        # depends_on is required -- must be present as a key even if empty list.
        if "depends_on" not in t.raw:
            issues.append(
                Issue(
                    "ERROR",
                    tag,
                    "Missing required 'depends_on' field "
                    "(use an empty array [] for tasks with no dependencies)",
                )
            )
        if t.agent and t.agent not in VALID_AGENTS:
            issues.append(
                Issue(
                    "WARNING",
                    tag,
                    f"Unknown agent '{t.agent}'; valid: {sorted(VALID_AGENTS)}",
                )
            )
        if t.ecosystem and t.ecosystem not in VALID_ECOSYSTEMS:
            issues.append(
                Issue("WARNING", tag, f"Unknown ecosystem override '{t.ecosystem}'")
            )
        # Warn about unrecognised keys.
        for key in t.raw:
            if key not in _ALL_TASK_FIELDS:
                issues.append(Issue("WARNING", tag, f"Unknown task field '{key}'"))
    return issues


def check_titles(_data: dict, tasks: list[Task]) -> list[Issue]:
    issues: list[Issue] = []
    for t in tasks:
        tag = f"{t.number:03d}"
        word_count = len(t.title.split())
        if word_count > MAX_TITLE_WORDS:
            issues.append(
                Issue(
                    "ERROR",
                    tag,
                    f"Title is {word_count} words (max {MAX_TITLE_WORDS}): '{t.title}'",
                )
            )
        if re.search(r"[^a-zA-Z0-9 \-/+]", t.title):
            issues.append(
                Issue(
                    "WARNING",
                    tag,
                    f"Title contains chars that may not survive branch-name slugification: '{t.title}'",
                )
            )
    return issues


def check_depends_on(_data: dict, tasks: list[Task]) -> list[Issue]:
    issues: list[Issue] = []
    all_nums = {t.number for t in tasks}
    for t in tasks:
        tag = f"{t.number:03d}"
        for ref in t.depends_on:
            if ref not in all_nums:
                issues.append(
                    Issue(
                        "ERROR",
                        tag,
                        f"depends_on {ref:03d} references a non-existent task",
                    )
                )
            elif ref > t.number:
                issues.append(
                    Issue(
                        "ERROR",
                        tag,
                        f"depends_on {ref:03d} is a forward reference (later than {tag})",
                    )
                )
            elif ref == t.number:
                issues.append(Issue("ERROR", tag, "Task depends on itself"))
    return issues


def _task_output_namespaces(task: Task) -> set[str]:
    """Set of all ARCH_RULES-relevant prefixes that appear in task outputs."""
    all_prefixes = set(ARCH_RULES.keys())
    for deps in ARCH_RULES.values():
        all_prefixes.update(deps)
    ns: set[str] = set()
    for out in task.outputs:
        for prefix in all_prefixes:
            if out.startswith(prefix):
                ns.add(prefix)
    return ns


def check_architecture(_data: dict, tasks: list[Task]) -> list[Issue]:
    """Tasks in a protected namespace must not depend on tasks in forbidden namespaces."""
    issues: list[Issue] = []
    task_ns: dict[int, set[str]] = {t.number: _task_output_namespaces(t) for t in tasks}

    for t in tasks:
        tag = f"{t.number:03d}"
        my_ns = task_ns[t.number]
        for protected, forbidden_list in ARCH_RULES.items():
            if protected not in my_ns:
                continue
            for dep_num in t.depends_on:
                dep_ns = task_ns.get(dep_num, set())
                for forbidden in forbidden_list:
                    if forbidden in dep_ns:
                        issues.append(
                            Issue(
                                "ERROR",
                                tag,
                                f"Architecture violation: '{protected}' task {tag} "
                                f"depends on '{forbidden}' task {dep_num:03d}",
                            )
                        )
    return issues


def check_checkpoint_refs(data: dict, tasks: list[Task]) -> list[Issue]:
    """Warn if backtick numbers in 'Target task/point' lines don't exist as tasks."""
    issues: list[Issue] = []
    all_nums = {t.number for t in tasks}
    preamble = _resolve_text(data.get("preamble", ""))
    for m in re.finditer(r"[Tt]arget (?:task|point)[^`\n]*`(\d+)`", preamble):
        ref = int(m.group(1))
        if ref not in all_nums:
            issues.append(
                Issue(
                    "WARNING",
                    "preamble",
                    f"Checkpoint references task {ref:03d} which does not exist",
                )
            )
    return issues


def check_single_root_task(_data: dict, tasks: list[Task]) -> list[Issue]:
    """Exactly one task must have depends_on: [] (the project root / layer 0)."""
    issues: list[Issue] = []
    roots = [t for t in tasks if not t.depends_on]
    if len(roots) == 0 and tasks:
        issues.append(
            Issue(
                "ERROR",
                "global",
                "No root task found — at least one task must have depends_on: []",
            )
        )
    elif len(roots) > 1:
        ids = ", ".join(f"{t.number:03d}" for t in roots)
        issues.append(
            Issue(
                "ERROR",
                "global",
                f"Multiple root tasks (depends_on: []): {ids} — "
                "exactly one task should be the project root (layer 0)",
            )
        )
    return issues


def check_disjoint_parallel_outputs(_data: dict, tasks: list[Task]) -> list[Issue]:
    """Tasks that can run in parallel (same dependency set) must have disjoint outputs."""
    issues: list[Issue] = []
    # Group tasks by their dependency signature (sorted tuple).
    from collections import defaultdict

    dep_groups: dict[tuple[int, ...], list[Task]] = defaultdict(list)
    for t in tasks:
        key = tuple(sorted(t.depends_on))
        dep_groups[key].append(t)

    for _key, group in dep_groups.items():
        if len(group) < 2:
            continue
        # Pair-wise output overlap check within the group.
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                overlap = set(a.outputs) & set(b.outputs)
                if overlap:
                    files = ", ".join(sorted(overlap))
                    issues.append(
                        Issue(
                            "ERROR",
                            f"{a.number:03d}",
                            f"Parallel tasks {a.number:03d} and {b.number:03d} "
                            f"share outputs: {files}",
                        )
                    )
    return issues


# ---------------------------------------------------------------------------
# Check registry (add new checks here -- they run in order)
# ---------------------------------------------------------------------------


CHECKS: list[tuple[str, object]] = [
    ("Preamble ecosystem", check_preamble),
    ("Deploy block", check_deploy_block),
    ("Git block", check_git_block),
    ("Task numbering", check_numbering),
    ("Required fields", check_fields),
    ("Title word limit", check_titles),
    ("depends_on refs", check_depends_on),
    ("Single root task", check_single_root_task),
    ("Disjoint parallel outputs", check_disjoint_parallel_outputs),
    ("Architecture rules", check_architecture),
    ("Checkpoint task refs", check_checkpoint_refs),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_checks(path: Path) -> int:
    """Validate *path* (ROADMAP.json) and print a report; return 0 (clean) or 1 (errors found)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON in {path}: {exc}")
        return 1

    preamble, tasks = parse_roadmap(data)

    nums = sorted(t.number for t in tasks) if tasks else []
    range_str = f"{nums[0]:03d} to {nums[-1]:03d}" if nums else "n/a"

    print(f"Checking : {path}")
    print(f"Tasks    : {len(tasks)}  ({range_str})")
    print()

    all_issues: list[Issue] = []
    for name, fn in CHECKS:
        issues: list[Issue] = fn(data, tasks)  # type: ignore[operator]
        errors_in = [i for i in issues if i.level == "ERROR"]
        warnings_in = [i for i in issues if i.level == "WARNING"]
        if errors_in:
            status, symbol = "FAIL", "FAIL"
        elif warnings_in:
            status, symbol = "WARN", "WARN"
        else:
            status, symbol = "PASS", "ok  "

        print(f"  [{symbol}] {name:<30}  ({status})")
        for issue in issues:
            print(f"        [{issue.level:7s}] task {issue.task}: {issue.message}")
        all_issues.extend(issues)

    errors = sum(1 for i in all_issues if i.level == "ERROR")
    warnings = sum(1 for i in all_issues if i.level == "WARNING")

    print()
    print("-" * 50)
    if errors == 0 and warnings == 0:
        print("[ok  ] All checks passed.")
    elif errors == 0:
        print(f"[WARN] Passed with {warnings} warning(s).")
    else:
        print(f"[FAIL] FAILED -- {errors} error(s), {warnings} warning(s).")
    print("-" * 50)

    return 1 if errors else 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def find_default_roadmap() -> Path | None:
    # helpers/ lives one level below the workspace root, so go up one level.
    base = Path(__file__).parent.parent / "projects"
    if not base.is_dir():
        return None
    return next(iter(sorted(base.glob("*/ROADMAP.json"))), None)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a ROADMAP.json against runner conventions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit 0 = clean/warnings only, 1 = errors found, 2 = file not found.",
    )
    parser.add_argument(
        "roadmap",
        nargs="?",
        help="Path to ROADMAP.json (default: first projects/*/ROADMAP.json found)",
    )
    args = parser.parse_args()

    if args.roadmap:
        path = Path(args.roadmap)
    else:
        path = find_default_roadmap()
        if path is None:
            print("No ROADMAP.json found. Pass a path explicitly.", file=sys.stderr)
            sys.exit(2)

    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(2)

    sys.exit(run_checks(path))


if __name__ == "__main__":
    main()
