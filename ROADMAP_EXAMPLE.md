# ROADMAP.json — Reference & Example

> Create `projects/<name>/ROADMAP.json`. The runner reads each task and drives
> agents through **build → test → fix → static → document → commit** automatically.
> Write descriptions as if briefing a senior engineer.

---

## Schema

```json
{
  "name": "Project Name v0.1",
  "ecosystem": "python",
  "preamble": "Architecture notes injected into every build prompt.",
  "git": { "enabled": true },
  "deploy": {
    "enabled": true,
    "script": "scripts/deploy.sh",
    "env": { "app": "my-app", "region": "fra" }
  },
  "tasks": [ ... ]
}
```

### Top-level fields

| Field       | Required | Description                                                        |
| ----------- | -------- | ------------------------------------------------------------------ |
| `name`      | **yes**  | Project name (used in commits and logs)                            |
| `ecosystem` | no       | Default ecosystem — auto-detected from manifests if omitted        |
| `preamble`  | no       | Architecture notes injected into every build prompt (keep it short)|
| `git`       | no       | `{ "enabled": true }` to opt in to runner-managed git             |
| `deploy`    | no       | Deploy hook config (see AGENTS.md)                                 |
| `tasks`     | **yes**  | Array of task objects                                              |

### Task fields

| Field         | Required | Type             | Description                                                  |
| ------------- | -------- | ---------------- | ------------------------------------------------------------ |
| `id`          | **yes**  | integer          | Unique task number (1–999)                                   |
| `title`       | **yes**  | string           | Short imperative title (≤ 6 words, becomes branch name)      |
| `depends_on`  | **yes**  | array of ints    | IDs this depends on; `[]` for independent tasks              |
| `agent`       | no       | string           | `"build"` (default), `"milestone"`, `"plan"`, `"architect"`  |
| `ecosystem`   | no       | string           | Override project default for this task                       |
| `context`     | no       | array of strings | Existing files pre-injected into the build prompt            |
| `outputs`     | **yes**\* | array of strings | Files this task creates or modifies                          |
| `acceptance`  | **yes**\* | string           | Done criterion checked by the runner                         |
| `version`     | no       | string           | Semver tag for milestone tasks (e.g. `"0.1.0"`)              |
| `deploy`      | no       | boolean          | Run deploy hook after this task                              |
| `description` | no       | string           | Full task spec (markdown supported)                          |

\* Required for all tasks except `agent: "milestone"` tasks.

---

## Key concepts

### Dependency design rules (enforced by validator)

1. **Exactly one root task** — only task 1 may have `depends_on: []`. It
   runs alone as layer 0 (project scaffolding). The validator errors if
   multiple tasks have empty dependencies. **This root task must fully
   prepare the project** for all subsequent work: directory layout, manifest
   / dependency file, configuration (linter, formatter, tsconfig), shared
   types / interfaces / base classes, and the test harness. Every later task
   builds on top of — and `context:`-references — the root's outputs.

2. **Every non-root task declares its dependencies** — list the IDs of all
   tasks whose outputs must exist before this task can start. Ask: "which
   files does my task import or read?" and trace them back to their producing
   task.

3. **No forward references** — `depends_on` may only contain IDs lower than
   the task's own `id`. Tasks are listed in topological order.

4. **Parallel tasks have disjoint outputs** — tasks sharing the same
   dependency set run concurrently. If two parallel tasks write the same
   file, the build will conflict. The validator checks this.

5. **Use `context:`** to inject files from dependency outputs so the build
   agent can read them.

6. **Design layers first** — sketch the dependency graph as layers before
   writing tasks:
   - Layer 0 = single foundation task
   - Layer 1+ = features building on earlier layers
   - Final layers = integration, milestones, UI

### Other concepts

**Parallel builds** — tasks with no dependency edges between them run
concurrently. Parallel tasks must have **disjoint `outputs:`**. The first task
always runs alone.

**Milestones** — `"agent": "milestone"` creates a review gate. When git is
managed, the runner tags `develop` with `v<version>` and pushes. Milestones
never run in parallel.

**Deploy hooks** — when a task has `"deploy": true` and the project has a
`deploy` block, the runner executes the deploy script after commit.

**Git (opt-in)** — set `"git": {"enabled": true}` for automatic
`feature/<slug>` branching, merge to develop, and tagging. Without it the
runner skips all git operations.

**Validation** — run `python check_roadmap.py projects/<name>/ROADMAP.json`
to check structure before starting the pipeline.

---

## Full example — block-stacking game (Python)

A complete ROADMAP showing parallel tasks, milestone, git, and deployment:

```json
{
  "name": "BlockDrop v0.1",
  "ecosystem": "python",
  "preamble": "A Tetris-like block-stacking game.\n\n### Layers\n- **blockdrop/** — pure logic (no rendering, fully testable)\n- **tests/** — unit tests (no pygame)\n\n### Rules\n- No side-effects at import time.\n- All game state passed explicitly.",
  "git": { "enabled": true },
  "deploy": {
    "enabled": true,
    "script": "scripts/deploy.sh",
    "env": { "app": "blockdrop", "region": "fra" }
  },
  "tasks": [
    {
      "id": 1,
      "title": "Piece Definitions",
      "depends_on": [],
      "outputs": ["blockdrop/pieces.py", "tests/test_pieces.py"],
      "acceptance": "all tests in tests/test_pieces.py pass",
      "description": "Define the 7 standard piece shapes and their rotations as pure data.\n\nTests: all shapes construct, 4× rotate returns original, O-piece invariant."
    },
    {
      "id": 2,
      "title": "Board Grid",
      "depends_on": [1],
      "context": ["blockdrop/pieces.py"],
      "outputs": ["blockdrop/board.py", "tests/test_board.py"],
      "acceptance": "all tests in tests/test_board.py pass",
      "description": "Game grid with placement, collision detection, and line clearing."
    },
    {
      "id": 3,
      "title": "Scoring Engine",
      "depends_on": [1],
      "outputs": ["blockdrop/scoring.py", "tests/test_scoring.py"],
      "acceptance": "all tests in tests/test_scoring.py pass",
      "description": "Pure scoring: points per lines cleared, level progression, combo multiplier.\n\nNo board or piece imports — numbers only."
    },
    {
      "id": 4,
      "title": "Piece Controller",
      "depends_on": [1, 2],
      "context": ["blockdrop/pieces.py", "blockdrop/board.py"],
      "outputs": ["blockdrop/controller.py", "tests/test_controller.py"],
      "acceptance": "all tests in tests/test_controller.py pass",
      "description": "Active piece management: move, rotate, gravity tick, lock to board."
    },
    {
      "id": 5,
      "title": "Game Orchestrator",
      "depends_on": [2, 3, 4],
      "context": ["blockdrop/board.py", "blockdrop/scoring.py", "blockdrop/controller.py"],
      "outputs": ["blockdrop/game.py", "tests/test_game.py"],
      "acceptance": "all tests in tests/test_game.py pass",
      "description": "Top-level Game class wiring board + controller + scoring.\n\nExposes tick(), move(), rotate(), and read-only state for renderers."
    },
    {
      "id": 6,
      "title": "Alpha Milestone",
      "agent": "milestone",
      "depends_on": [5],
      "version": "0.1.0",
      "deploy": true,
      "description": "All core logic delivered. Tag v0.1.0 and deploy."
    },
    {
      "id": 7,
      "title": "Pygame Renderer",
      "depends_on": [5],
      "context": ["blockdrop/game.py"],
      "outputs": ["blockdrop/renderer.py", "blockdrop/__main__.py"],
      "acceptance": "python -m blockdrop launches without errors",
      "description": "Visual display using pygame. Reads Game state only — no logic."
    }
  ]
}
```

**Parallel tasks:** 1 (Pieces) has `depends_on: []` and runs alone as the first
task. Tasks 2 (Board Grid) and 3 (Scoring Engine) both depend on 1 and run in
parallel, then 4, then 5, then 6 (milestone, sequential), then 7.

**Dependency graph:**

```
Layer 0:  [1] Piece Definitions
Layer 1:  [2] Board Grid  ·  [3] Scoring Engine     ← parallel
Layer 2:  [4] Piece Controller
Layer 3:  [5] Game Orchestrator
Layer 4:  [6] Alpha Milestone                        ← tags v0.1.0, deploys
Layer 5:  [7] Pygame Renderer
```
