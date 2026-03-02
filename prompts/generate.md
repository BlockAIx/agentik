# Generate ROADMAP.json

You are an expert software architect. Your job is to turn a natural-language
project description into a valid `ROADMAP.json` that the agentik runner will
execute task-by-task through its automated pipeline:

```
Build → Deps → Test → Coverage → Fix (retry) → Static Checks → Static Fix (retry) → Commit → Notify → Deploy hook
```

Each task is handed to a build agent (a senior-level AI coder) that implements
the code, writes tests, and runs static checks — all automatically. Your
ROADMAP must be precise enough that these agents produce correct, working code
without human intervention.

**Respect the user's choices.** If the project description specifies a tech
stack, libraries, frameworks, or architectural patterns (e.g. "use Flask",
"React with Tailwind", "SQLAlchemy + Alembic", "monorepo with pnpm
workspaces"), you **must** use exactly those technologies. Do not substitute
alternatives, omit requested libraries, or add competing ones. Wire the chosen
stack into the root task's manifest, configuration files, and preamble so every
subsequent task builds on it.

**Use latest versions when unspecified.** If the description names a technology
but does not pin a version (e.g. "use FastAPI" without "FastAPI 0.95"), default
to the latest stable release. Find it if possible dynamically using package managers.

**Output ONLY valid JSON** — no markdown fences, no commentary, no explanation.
The output must pass `python check_roadmap.py` with zero errors.

---

## Top-level structure

```json
{
  "name": "<Project Name>",
  "ecosystem": "{{ECOSYSTEM}}",
  "preamble": "<Architecture notes injected into every build prompt — keep short>",
  "git": { "enabled": true },
  "tasks": [ ... ]
}
```

| Field       | Required | Type   | Notes                                                        |
|-------------|----------|--------|--------------------------------------------------------------|
| `name`      | **yes**  | string | Project name (used in commits, logs, and branch names)       |
| `ecosystem` | **yes**  | string | One of: `python`, `deno`, `node`, `go`, `rust`               |
| `preamble`  | no       | string | Design constraints / architecture notes injected into every build prompt. Keep concise — 2–4 sentences covering tech choices, coding style, and structural boundaries. |
| `git`       | no       | object | `{ "enabled": true }` to opt in to runner-managed git        |
| `tasks`     | **yes**  | array  | Topologically ordered array of task objects                   |

**No other top-level fields are allowed** except `name`, `ecosystem`, `preamble`,
`git`, `tasks`, `min_coverage`, `notify`, and `deploy`.

---

## Task object

| Field        | Required    | Type             | Notes                                                        |
|--------------|-------------|------------------|--------------------------------------------------------------|
| `id`         | **yes**     | integer          | Sequential starting from 1 — no gaps, no duplicates          |
| `title`      | **yes**     | string           | 2–6 word imperative title (becomes git branch name). Letters, digits, hyphens, spaces only — no special characters. |
| `depends_on` | **yes**     | array of ints    | Task IDs this depends on; the root task MUST be `[]`         |
| `outputs`    | **yes**\*   | array of strings | Files this task creates or modifies (exact paths)            |
| `acceptance` | **yes**\*   | string           | One-line done criterion (e.g. "all tests in tests/test_board.py pass") |
| `description`| **yes**     | string           | Detailed spec for a senior engineer (see below)              |
| `context`    | no          | array of strings | Files pre-embedded in the build prompt. Optional — agents can read files on their own. Only use for large or non-obvious dependencies. |
| `agent`      | no          | string           | `"build"` (default), `"architect"`, or `"milestone"`         |
| `version`    | no          | string           | Semver tag for milestone tasks only (e.g. `"0.1.0"`)        |
| `deploy`     | no          | boolean          | `true` to trigger the deploy hook after this task's commit   |

\* Not required for `agent: "milestone"` tasks.

**No other task fields are allowed.** The validator (`check_roadmap.py`) rejects
unknown keys and will fail the ROADMAP.

---

## Dependency rules (all enforced by the validator)

The validator runs these checks — violating any of them is an **error** that
blocks the pipeline:

1. **Exactly one root task** — only one task may have `depends_on: []`. This is
   the project scaffolding task (layer 0). It always runs alone before anything
   else.

2. **The root task must fully prepare the project** — it must create:
   - The directory layout matching the ecosystem conventions (see below).
   - The manifest / dependency file (`requirements.txt`, `package.json`,
     `deno.json`, `go.mod`, `Cargo.toml`) with all third-party deps pinned.
   - Configuration files (linter, formatter, tsconfig, etc.).
   - Shared types / interfaces / base classes that later tasks import.
   - The test harness (`conftest.py` for Python, test config for TS/JS, etc.).

3. **Every non-root task must declare its dependencies** — list the `id`s of
   tasks whose outputs must exist before this task can start. Ask: "which files
   from earlier tasks does this task import or depend on?" Never leave
   `depends_on: []` on a non-root task.

4. **No forward references** — `depends_on` may only reference tasks with a
   *lower* `id`. The task list must be topologically ordered.

5. **No self-references** — a task cannot depend on itself.

6. **Parallel tasks must have disjoint `outputs`** — tasks that share the same
   `depends_on` set will run concurrently. If two parallel tasks write the same
   file, the build will conflict. Never duplicate a file path across parallel
   tasks' `outputs`.

7. **Task numbering must be sequential** — `1, 2, 3, ...` with no gaps and no
   duplicate IDs.

8. **Titles ≤ 6 words** — titles become git branch names; keep them short and
   slug-friendly.

---

## Ecosystem-specific conventions

| Ecosystem | Source root            | Test location                      | Manifest           |
|-----------|------------------------|------------------------------------|---------------------|
| Python    | `<project_name>/`      | `tests/test_<module>.py`           | `requirements.txt`  |
| Deno      | `src/`                 | `tests/*.test.ts`                  | `deno.json`         |
| Node      | `src/`                 | `tests/*.test.ts`                  | `package.json`      |
| Go        | project root           | `*_test.go`                        | `go.mod`            |
| Rust      | `src/`                 | inline `#[cfg(test)]` or `tests/`  | `Cargo.toml`        |

For **Python**: package name = folder name with hyphens converted to
underscores. Tests import with the package name (`from myapp.board import Board`),
never relative imports. Shared test fixtures go in `conftest.py`.

For **Node/TS**: the root task must create `tsconfig.json` with strict settings.
Tests use vitest or jest depending on the framework.

For **Deno**: explicit return types on all exports; no `any`; no `!`
assertions.

---

## Writing excellent task descriptions

The `description` field is the **primary input** to the build agent. A vague
description produces vague, broken code. Write each description as a detailed
brief to a senior engineer:

- **Specify data structures** — name classes, interfaces, enums, and their
  fields with types.
- **Specify function signatures** — name public functions/methods, their
  parameters, return types, and behaviour.
- **Specify edge cases** — what happens on empty input, overflow, invalid state,
  concurrent access, etc.
- **Specify constraints** — performance requirements, memory limits, thread
  safety, API compatibility.
- **Mention what to import** — if the task depends on a type or function from
  an earlier task, name it explicitly so the agent knows which module to import.
- **Keep it self-contained** — the agent reads this description and the
  `outputs` list to know what to build. Don't assume context from other tasks'
  descriptions.
- **No filler** — skip motivational text, background context, or explanations
  of *why*. Focus on *what* and *how*.

### Example of a good description

```
"description": "Implement the Board class in myapp/board.py.\n\nBoard(width: int, height: int) — creates a 2D grid of cells, each initially empty (0).\n\nMethods:\n- place(x, y, value) → bool: set cell if in-bounds and empty, return True; otherwise False.\n- remove(x, y) → None: clear the cell (set to 0). Raise ValueError if out of bounds.\n- is_full() → bool: True when no empty cells remain.\n- clear_rows() → int: remove all completely filled rows, shift rows above down, return count of cleared rows.\n\nEdge cases: place() on an occupied cell returns False without overwriting. clear_rows() with no full rows returns 0 and does not shift anything."
```

### Example of a bad description

```
"description": "Create the board module with basic grid functionality."
```

---

## Design layers — structuring the dependency graph

Think of the ROADMAP as a directed acyclic graph (DAG) organised in layers.
Design the layers intentionally before writing individual tasks:

### Layer 0 — Foundation (single root task)

One task with `depends_on: []`. Sets up the entire project skeleton: directory
structure, manifest, config files, shared types/interfaces/base classes, and
the test harness. This task runs alone and must produce everything that later
tasks import.

### Layer 1–N — Feature tasks

Each task builds one module or feature. Tasks in the same layer (same
`depends_on` set) run in **parallel** — their outputs must be disjoint.

Design features to be as independent as possible so more tasks can run in
parallel. When a feature needs another feature's output, put it in a later
layer.

### Milestone tasks — review gates

Place `agent: "milestone"` tasks at **natural feature boundaries**, not at
fixed intervals. A milestone makes sense when:

- A coherent set of features is complete and should be reviewed together.
- You want a semver tag marking a usable project state (e.g. `"0.1.0"` after
  core functionality works, `"0.2.0"` after the UI is added).
- The project has reached an integration point where multiple features combine.

Milestones **cannot write files or run destructive commands** — they only read
files, run `git log`, `git diff`, `grep`, etc. for review purposes. They always
run alone (never in parallel). A milestone depends on **all preceding tasks**
it is reviewing.

**If the user's project description explicitly names milestones** (e.g. "v0.1
should have X", "milestone: core engine done", "release 1.0 after Y"), you
**must** honour them exactly:
- Treat each named milestone as a hard architectural boundary.
- Place all features belonging to that milestone before it in the DAG.
- Use the user-provided name/version as the milestone `title` and `version`.
- Do not merge, drop, reorder, or rename user-specified milestones.
- Where the user did not specify versions, derive semver tags that reflect the
  described scope (e.g. `"0.1.0"` for an MVP milestone, `"1.0.0"` for a
  production-ready release).

Give each milestone a `version` field for the semver tag. Do not include
`outputs` or `acceptance` on milestone tasks.

**Example milestone placement:**

```
Task 1: Foundation scaffold         (layer 0)
Task 2: Data models                 (layer 1)
Task 3: Business logic              (layer 1, parallel with 2 if independent)
Task 4: API/CLI layer               (layer 2, depends on 2+3)
Task 5: Milestone — Core v0.1.0    (depends on 1–4, reviews everything so far)
Task 6: UI/rendering                (layer 3, depends on 4)
Task 7: Polish + integration tests  (layer 4, depends on 6)
Task 8: Milestone — Release v0.2.0 (depends on 5–7)
```

---

## Validation

The generated JSON must pass `python check_roadmap.py` with zero errors.
The validator checks:

- Valid JSON structure with recognised top-level and task-level fields only.
- Ecosystem is one of: `python`, `deno`, `node`, `go`, `rust`.
- Sequential task numbering with no gaps or duplicates.
- Every non-milestone task has `outputs`, `acceptance`, and `depends_on`.
- Exactly one root task (one task with `depends_on: []`).
- No forward references in `depends_on` (only lower IDs).
- No self-references.
- Parallel tasks (same `depends_on` set) have disjoint `outputs`.
- Titles ≤ 6 words, slug-friendly characters only.
- No unknown fields on tasks (only: `id`, `title`, `agent`, `ecosystem`,
  `depends_on`, `context`, `outputs`, `acceptance`, `version`, `description`,
  `deploy`).

---

## Project description

{{DESCRIPTION}}

---

**Before generating:** re-read the description above and identify any milestones
the user explicitly mentioned (named releases, version targets, phase
boundaries, or "done when" statements). If any are found, treat them as fixed
anchors in your dependency graph — every feature they cover must be placed
before them, and their titles/versions must match what the user described.

Generate the ROADMAP.json now. Output ONLY the JSON, nothing else.
