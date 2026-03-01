# ROADMAP.json — Reference & Example

> Create `projects/<name>/ROADMAP.json`. The runner reads each task and drives
> agents through **build → test → fix → static → commit** automatically.
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
| `agent`       | no       | string           | `"build"` (default), `"milestone"`, `"architect"`  |
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

A complete ROADMAP showing parallel tasks, milestone, git, deployment, and an
AI opponent with realistic move animation:

```json
{
  "name": "BlockDrop",
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
      "title": "Pygame Renderer",
      "depends_on": [5],
      "context": ["blockdrop/game.py"],
      "outputs": ["blockdrop/renderer.py", "blockdrop/__main__.py"],
      "acceptance": "python -m blockdrop launches without errors",
      "description": "Visual display using pygame. Reads Game state only — no logic.\n\n**Important UX constraint:** do **not** render a ghost/drop-preview piece. No shadow, no landing guide, no translucent outline showing where the active piece will land. The board should show only the locked cells and the active falling piece."
    },
    {
      "id": 7,
      "title": "Alpha Milestone",
      "agent": "milestone",
      "depends_on": [6],
      "version": "0.1.0",
      "deploy": true,
      "description": "All core logic delivered. Tag v0.1.0 and deploy."
    },
    {
      "id": 8,
      "title": "AI Opponent Race",
      "depends_on": [7],
      "context": [
        "blockdrop/game.py",
        "blockdrop/board.py",
        "blockdrop/pieces.py",
        "blockdrop/controller.py",
        "blockdrop/renderer.py",
        "blockdrop/__main__.py"
      ],
      "outputs": [
        "blockdrop/ai.py",
        "blockdrop/renderer.py",
        "blockdrop/__main__.py"
      ],
      "acceptance": "python -m blockdrop launches a split-screen showing two boards side by side: player on the left (keyboard-controlled), AI on the right (auto-playing), both racing to top score",
      "description": "Add an AI opponent that plays a second parallel game visible alongside the player's game.\n\n### What to build\n\n**`blockdrop/ai.py` — `AIPlayer` class (pure logic, no pygame)**\n- Implements a classic Tetris heuristic AI using a weighted evaluation of candidate placements.\n- For each possible (column, rotation) placement of the current piece, simulate dropping it and score the resulting board using these heuristics (weighted sum):\n  - **Aggregate height** (sum of column heights) — penalise high stacks.\n  - **Complete lines** — reward clears.\n  - **Holes** (empty cells with a filled cell above them) — penalise heavily.\n  - **Bumpiness** (sum of absolute height differences between adjacent columns) — penalise uneven surfaces.\n- Default weights: height=-0.51, lines=+0.76, holes=-0.36, bumpiness=-0.18 (classic values).\n- `AIPlayer.choose_action(game: Game) -> None` computes the best `(target_col, num_rotations)` and stores the resulting move sequence as an internal action queue (a `deque` of callables or `(\"rotate\"|\"left\"|\"right\")` tokens). Call this once when a new piece spawns.\n- `AIPlayer.step(game: Game) -> bool` pops and executes the **next single action** from the queue (one rotation or one column shift). Returns `True` while moves remain, `False` when the queue is empty (piece is now in position and falls naturally with gravity — **no hard-drop**). The main loop calls `step()` on a fixed timer so moves are visible one at a time.\n\n**Realistic AI speed — critical constraint:**\nThe AI must **not** teleport pieces instantly. It executes one move per `AI_MOVE_INTERVAL` (≈ 120 ms). The piece then falls with normal gravity, exactly like the player's piece. This makes the AI look human-paced and gives the player a fair chance to watch and react.\n- `AI_MOVE_INTERVAL = 120` ms (constant in `__main__.py`, tunable).\n- Implement with a dedicated `ai_move_timer` accumulated in the game loop: fire `ai_player.step(ai_game)` only when `ai_move_timer >= AI_MOVE_INTERVAL`, then reset the timer.\n- Never call `step()` more than once per timer tick.\n- Never hard-drop or loop until placed — the piece must visibly slide and rotate one step at a time before gravity takes over.\n\n**`blockdrop/renderer.py` — extend `Renderer`**\n- `render(surface, game, offset_x=0)` — add an `offset_x` parameter (pixels) so the board can be drawn anywhere horizontally. All existing draw calls shift by `offset_x`.\n- Add a `label` parameter to `render` (string, default `\"\"`) displayed centred above the board.\n- **No ghost/drop-preview piece** — same constraint as task 6; do not add one here either.\n- No other changes to existing rendering logic.\n\n**`blockdrop/__main__.py` — split-screen main loop**\n- Create two `Game` instances: `player_game` and `ai_game`, each with a fresh independent `_random_piece` generator.\n- Create one `AIPlayer` instance. On every new piece spawn for `ai_game`, call `ai_player.choose_action(ai_game)` to queue the move sequence.\n- Window width = `2 * board_width * cell_size + gap` (gap = 20 px between boards). Window title: `\"BlockDrop — Player vs AI\"`.\n- Player board drawn at `offset_x = 0`, AI board drawn at `offset_x = board_width * cell_size + gap`.\n- A thin vertical separator line is drawn between the boards.\n- Each board shows its label (`\"PLAYER\"` / `\"AI\"`) and stats (score, level, lines).\n- AI move timer: accumulate `dt` each frame; when `ai_move_timer >= AI_MOVE_INTERVAL` call `ai_player.step(ai_game)` once and reset the timer.\n- When both games are over, display `\"PLAYER WINS!\"` or `\"AI WINS!\"` (or `\"DRAW\"`) centred on the full window based on score comparison.\n- When only the player's game is over, keep rendering the AI side live.\n- Keyboard controls unchanged (arrow keys control player only)."
    }
  ]
}
```

**Parallel tasks:** task 1 runs alone (root). Tasks 2 and 3 both depend on 1
and run in parallel. Then 4, 5, 6, 7 (milestone, sequential), 8.

**Dependency graph:**

```
Layer 0:  [1] Piece Definitions
Layer 1:  [2] Board Grid  ·  [3] Scoring Engine     ← parallel
Layer 2:  [4] Piece Controller
Layer 3:  [5] Game Orchestrator
Layer 4:  [6] Pygame Renderer
Layer 5:  [7] Alpha Milestone                        ← tags v0.1.0, deploys
Layer 6:  [8] AI Opponent Race
```

**Design notes:**

- **No ghost piece** — the renderer must never draw a drop-preview shadow.
  This is a deliberate UX choice for a cleaner visual; specify it explicitly
  so build agents don't add one "helpfully".
- **Realistic AI pacing** — the AI executes one move every `AI_MOVE_INTERVAL`
  (≈ 120 ms) and lets the piece fall with normal gravity afterward. Never
  use a hard-drop or an instant teleport. Specifying the timer variable name
  and interval in the description pins the implementation and prevents the
  agent from choosing a trivially fast loop.
