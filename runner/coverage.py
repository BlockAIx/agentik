"""coverage.py — Test coverage gating: run tests with coverage and enforce thresholds."""

import re
import subprocess
from pathlib import Path

from runner.roadmap import _load_roadmap
from runner.workspace import _detect_ecosystem


def get_min_coverage(project_dir: Path) -> int | None:
    """Return the ``min_coverage`` threshold from ROADMAP.json, or None if not set."""
    roadmap = _load_roadmap(project_dir)
    return roadmap.get("min_coverage")


def run_tests_with_coverage(project_dir: Path) -> tuple[bool, str, float | None]:
    """Run tests with coverage collection and return ``(passed, output, coverage_pct)``.

    If coverage tools aren't available or the ecosystem doesn't support it,
    ``coverage_pct`` is None.
    """
    eco = _detect_ecosystem(project_dir)

    if eco == "python":
        return _run_python_coverage(project_dir)
    # Future: add node/deno/go/rust coverage support.
    return _run_generic_tests(project_dir)


def _run_python_coverage(project_dir: Path) -> tuple[bool, str, float | None]:
    """Run pytest with --cov and parse the coverage percentage."""
    pkg_name = project_dir.name.replace("-", "_")
    cmd = f"pytest --cov={pkg_name} --cov-report=term-missing --tb=short"

    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(project_dir),
    )
    output = (result.stdout or "") + (result.stderr or "")
    passed = result.returncode == 0

    # Parse coverage percentage from pytest-cov output.
    # Looks for lines like: TOTAL    ...   85%
    coverage_pct = _parse_coverage_total(output)

    return passed, output, coverage_pct


def _parse_coverage_total(output: str) -> float | None:
    """Extract total coverage % from pytest-cov output."""
    # Match "TOTAL" line: TOTAL    123    12    90%
    match = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%", output, re.MULTILINE)
    if match:
        return float(match.group(1))
    # Also try: <filename>  <stmts>  <miss>  <cover>%
    # Last percentage on a line containing TOTAL.
    match2 = re.search(r"TOTAL.*?(\d+)%", output)
    if match2:
        return float(match2.group(1))
    return None


def _run_generic_tests(project_dir: Path) -> tuple[bool, str, float | None]:
    """Fallback: run tests without coverage for unsupported ecosystems."""
    from runner.roadmap import run_tests  # noqa: PLC0415
    passed, output = run_tests(project_dir)
    return passed, output, None


def check_coverage_gate(
    project_dir: Path, coverage_pct: float | None
) -> tuple[bool, str]:
    """Check if coverage meets the minimum threshold.

    Returns:
        ``(passed, message)`` — passed is True if threshold met or not configured.
    """
    threshold = get_min_coverage(project_dir)
    if threshold is None:
        return True, ""

    if coverage_pct is None:
        return True, "Coverage measurement not available for this ecosystem."

    if coverage_pct >= threshold:
        return True, f"Coverage {coverage_pct:.0f}% >= {threshold}% threshold"

    return False, (
        f"Coverage {coverage_pct:.0f}% is below the {threshold}% threshold. "
        f"Add more meaningful tests to increase coverage."
    )
