"""runner — Autonomous multi-project development loop.

Pipeline per task: Build → Deps → Test → Fix (retry) → Static → Static Fix (retry) → Document → Commit → Deploy.
"""

from runner.pipeline import main

__all__ = ["main"]
