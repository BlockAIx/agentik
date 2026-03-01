# Agent Instructions — agentik Runner

You are inside an **autonomous development loop** driven by `runner.py`. Read
this before writing any code or modifying any project.

---

## What this workspace is

`runner.py` processes each task in a project `ROADMAP.json` through this
pipeline:

```
Build → Deps → Test → Coverage → Fix (retry) → Static Checks → Static Fix (retry) → Review → Document → Commit → Notify → Deploy hook
```

**Your job as `build` / `fix`:** implement one task exactly as specified, then
stop. Do not implement future tasks.

---

## Project change requests from the workspace root

**When a user asks to add or change something in a project (`projects/<name>/`)
and the conversation context is at the agentik root level, first ask the
user how they want it handled** using a single-select prompt with two options:

- **Add as ROADMAP task** — append a well-formed task to the project's
  `ROADMAP.json` so it runs through the full pipeline (build → test →
  static checks → docs → commit).
- **Implement directly** — make the change immediately without going through
  the runner pipeline.

Only present the prompt once per request. After the user selects an option,
proceed without asking again.

**If the user chose "Add as ROADMAP task":**

1. Identify (or confirm) the target project under `projects/`.
2. Read the project's `ROADMAP.json` to understand existing tasks, dependencies,
   and the highest current `id`.
3. Append a new well-formed task (correct `id`, `depends_on`, `context`,
   `outputs`, `acceptance`, `description`) to the `tasks` array.
4. Validate the updated ROADMAP by running:
   ```
   python check_roadmap.py projects/<name>/ROADMAP.json
   ```
5. Fix any reported errors, then confirm to the user that the task has been
   added and explain what it will do.

**If the user is already working inside the project directory** (e.g. files
opened are under `projects/<name>/`, or the request is clearly scoped to a
single file in the project), proceed with direct implementation as normal
without prompting.

The prompt exists so that every intentional project change can go through the
runner pipeline (tests → static checks → docs → git) rather than bypassing it,
while still allowing quick direct edits when the user prefers.

---

## Modifying the workspace root

When you change anything that affects how the runner works, keep these in sync
**in the same response**:

| What you changed                                | Also update                                                                                                                |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `runner.py` pipeline phases / behaviour / flags | `README.md` (pipeline + How it works), `AGENTS.md`, affected `prompts/*.md`                                                |
| `prompts/*.md` wording                          | `AGENTS.md` section for that phase                                                                                         |
| `opencode.jsonc` agent definitions              | `README.md` Agents table, `AGENTS.md` Agents table                                                                         |
| Deploy hook / `try_deploy_hook()`               | `README.md` Deploy hook section, `AGENTS.md` Deploy hook section                                    |
| Budget / token tracking                         | `README.md` Budget section                                                                                                 |
| `.runner_state.json` schema                     | `README.md` Project state section                                                                                          |
| ROADMAP.json task format / field names / rules  | `helpers/check_roadmap.py` (update `_ALL_TASK_FIELDS`, `VALID_AGENTS`, `VALID_ECOSYSTEMS`, `ARCH_RULES`, `MAX_TITLE_WORDS`) |
| Any `runner/` module behaviour                  | `tests/` — keep runner unit tests green; add tests for new logic                                                           |

**Rule of thumb:** if `README.md` still accurately describes the system and
`pytest tests/` is green, you're done.

---

## Repository layout

```
agentik/                     <- workspace root repo (runner tooling only)
├── agentik.py
├── budget.json             <- global token limits
├── opencode.jsonc          <- agent definitions (do NOT edit during a task)
├── Dockerfile              <- full-stack Docker image
├── docker-compose.yml      <- recommended way to run
├── .env.example            <- template for API keys
├── prompts/                <- prompt templates (build.md, fix.md, ...)
├── scripts/
│   ├── start.sh            <- quick-start (Linux/macOS)
│   └── start.ps1           <- quick-start (Windows)
├── helpers/                <- workspace-level utilities (importable by runner)
│   └── check_roadmap.py    <- ROADMAP structural validator (run before pipeline)
├── runner/
│   ├── config.py           <- constants, Rich console, prompt loader
│   ├── opencode.py         <- opencode invocation wrappers
│   ├── pipeline.py         <- main pipeline orchestration
│   ├── roadmap.py          <- ROADMAP.json parsing and helpers
│   ├── state.py            <- progress tracking, budget accounting
│   ├── workspace.py        <- ecosystem detection, git operations
│   ├── coverage.py         <- test coverage gating
│   ├── diagnostics.py      <- structured failure reports
│   ├── dryrun.py           <- dry-run cost / time estimation
│   ├── graph_html.py       <- interactive HTML dependency graph
│   ├── notify.py           <- webhook notification support
│   ├── plan.py             <- ROADMAP generation from NL descriptions
│   ├── review.py           <- human-in-the-loop review mode
│   └── rollback.py         <- git rollback on task failure
├── web/                        <- web UI dashboard (separate from runner)
│   ├── app.py              <- FastAPI backend + REST API
│   └── frontend/           <- React + Tailwind + shadcn SPA
├── AGENTS.md
├── requirements.txt        <- runner deps
└── projects/
    └── <project-name>/     <- each project is its own git repo
        ├── ROADMAP.json
        ├── budget.json         <- auto-managed
        ├── .runner_state.json  <- auto-managed
        ├── <source-root>/      <- see table below
        └── tests/
```

| Ecosystem   | Source root       | Notes                                              |
| ----------- | ----------------- | -------------------------------------------------- |
| Python      | `<project-name>/` | Package name = folder name (hyphens → underscores) |
| Deno / Node | `src/`            | Standard TS/JS layout                              |
| Rust        | `src/`            | Mandated by Cargo                                  |
| Go          | _(project root)_  | Go packages at module root                         |

**Critical rules:**

- `requirements.txt` at workspace root is for runner tooling only — project deps
  go in `projects/<name>/requirements.txt`.
- Never touch `.runner_state.json` or `projects/<name>/budget.json`.
- If git is managed (`"git": {"enabled": true}` in ROADMAP), never run
  `git push`, `git merge`, or `git tag` — the runner owns git.
- `helpers/check_roadmap.py` runs automatically at pipeline startup. Fix all
  reported **errors** before starting a run; warnings are informational.

---

## How the pipeline calls you

**Build** — prompt contains: (1) pre-embedded **context files** from the task's
`context:` field, (2) the **task body** verbatim, (3) **project context** — the
ROADMAP preamble (title and `ecosystem:` lines stripped), which carries
architecture notes and design constraints to every task automatically. The build
agent also writes compact docstrings (one sentence + param/return lines, no
prose blocks) and short inline comments on non-obvious logic.

> **Note on `context:`** — build agents have full file-tool access and will
> discover and read dependency files on their own. `context:` pre-embeds file
> content directly in the prompt, which is marginally useful for large or
> non-obvious dependencies but redundant for anything a competent agent would
> naturally read. Missing entries are silently skipped. Prefer rich
> `description:` fields over long `context:` lists.

**Fix** — runner appends full test output and continues the session. Fix only
what's failing; no refactoring.

**Static checks** — after green tests the runner auto-detects and runs the
appropriate static analysis tools for the project's ecosystem (e.g.
`ruff` for Python, `deno check` + `deno lint` for Deno, `npx tsc --noEmit`
for Node/TS, `go vet` for Go, `cargo clippy` for Rust). If issues are found
it continues the session asking you to fix **only** what was reported.

**IDE / editor diagnostic check** — after every file edit (build *and* fix
passes) call the IDE diagnostic tool before declaring work complete:
- **VS Code** — use the `get_errors` tool. It surfaces Pylance type errors,
  ESLint/Tailwind lint warnings, unused-variable diagnostics, and any other
  language-server reports that CLI tools do not catch.
- **Other editors / headless** — run the ecosystem CLI linter directly
  (`ruff check`, `npx eslint`, `deno lint`, etc.).

Fix every reported error. Warnings that the linter suggests be converted to
a canonical form (e.g. Tailwind arbitrary values → shorthand classes) must
also be resolved — leave no stale IDE diagnostics.

For **Node/TS projects** the runner also calls `npx tsc --noEmit`. Before every
build the scaffold step auto-patches `tsconfig.json` to:

- Add `"tests/**/*"` to `include` when a `tests/` directory exists.
- Add the appropriate `compilerOptions.types` entry for detected test frameworks
  (`"jest"` when `@types/jest` / `jest` is in `package.json`, `"vitest/globals"`
  when `@vitest/ui` is present).
- Widen `rootDir` from `"./src"` to `"."` so `tsc` accepts test files that live
  outside `src/`.

You should still write code that passes `tsc --noEmit` from the start — the
patch ensures the tsconfig won't block a compliant codebase.

Write code that passes static checks from the start:

- **Deno/TS** — explicit return types on all exports; no `any`; no `!`
  assertions; never `async` without `await` (use `Promise.resolve(value)`
  instead); `_`-prefix or remove unused params.
- **Python** — no unused imports; type annotations where ruff flags them.
- **Go** — `go vet` clean.
- **Rust** — `cargo clippy -- -D warnings` clean.
- **Dockerfile** — prefer single-stage; multi-stage `COPY --from` only copies
  paths explicitly written in that stage (never implicit dirs like
  `/root/.cache` or `/deno-dir`). See `prompts/build.md` for the canonical Deno
  pattern.

**Document** — runner continues the session asking for a `README.md` update
(summary, directory tree, how to run, how to test). No logic or code changes.

---

## Writing a ROADMAP.json

```
projects/<your-project>/ROADMAP.json
```

```json
{
  "name": "Project Name v0.1",
  "ecosystem": "python",
  "preamble": "Brief description.",
  "git": { "enabled": true },
  "review": true,
  "min_coverage": 80,
  "notify": {
    "url": "https://hooks.slack.com/services/...",
    "events": ["task_complete", "task_failed", "pipeline_done"]
  },
  "deploy": {
    "enabled": true,
    "script": "scripts/deploy.sh",
    "env": { "provider": "fly", "app": "my-app", "region": "fra" }
  },
  "tasks": [
    {
      "id": 1,
      "title": "Short Imperative Title",
      "depends_on": [1, 2],
      "context": ["src/existing_module.py"],
      "outputs": ["src/new_module.py", "tests/test_new_module.py"],
      "acceptance": "all tests in tests/test_new_module.py pass",
      "deploy": true,
      "description": "Task description as a brief to a senior engineer."
    }
  ]
}
```

| Field         | Required | Type             | Example                                             |
| ------------- | -------- | ---------------- | --------------------------------------------------- |
| `id`          | **yes**  | integer          | `1`                                                 |
| `title`       | **yes**  | string           | `"Parser Core"`                                     |
| `agent`       | no       | string           | `"architect"` or `"milestone"` (default: `"build"`) |
| `ecosystem`   | no       | string           | `"deno"` (overrides project default)                |
| `depends_on`  | **yes**  | array of ints    | `[1, 2]` or `[]`                                    |
| `context`     | no       | array of strings | `["src/models.py"]` — pre-embeds files in the prompt; mostly optional since agents can read files on their own |
| `outputs`     | **yes**\* | array of strings | `["src/parser.py", "tests/test_parser.py"]`         |
| `acceptance`  | **yes**\* | string           | `"all tests pass"`                                  |
| `version`     | no       | string           | `"0.2.0"` (milestone only)                          |
| `deploy`      | no       | boolean          | `true` — run deploy hook after this task's commit   |
| `description` | no       | string           | Full task spec (can contain markdown)               |

\* Required for all tasks except `agent: "milestone"` tasks.

Titles become git branch names — ≤ 6 words, no special characters.

### Dependency design rules

1. **Exactly one root task** — only one task may have `depends_on: []`. This is
   the project scaffolding / foundation task and always runs alone (layer 0).
   The validator enforces this (`check_single_root_task`). **The root task must
   fully prepare the project** so every subsequent task can start building
   immediately: create the directory layout, manifest / dependency file
   (e.g. `requirements.txt`, `package.json`, `deno.json`), configuration
   files (linter, formatter, tsconfig, etc.), shared types / interfaces /
   base classes that later tasks import, and the test harness (`conftest.py`,
   test config). All later tasks depend on the outputs of this root task
   (declare them in `depends_on:`); add them to `context:` only if they are
   large or non-obvious and you want them pre-embedded in the prompt.

2. **Every non-root task must declare its dependencies** — never leave
   `depends_on: []` on a task that actually needs files from an earlier task.
   Ask: "which outputs must exist before this task can start?" and list those
   task IDs.

3. **No forward references** — `depends_on` may only reference tasks with a
   lower `id`. The task list is topologically ordered.

4. **No self-references** — a task cannot depend on itself.

5. **Parallel tasks must have disjoint `outputs:`** — tasks that share the same
   dependency set run concurrently. If two parallel tasks write to the same
   file, the build will conflict. The validator enforces this
   (`check_disjoint_parallel_outputs`).

6. **`context:` is optional** — build agents can discover and read dependency
   files on their own using file tools. Only use `context:` for large or
   non-obvious dependencies where you want to guarantee the file content is
   in the prompt at task-start (e.g. a key interface file the agent must
   closely follow). Prefer a detailed `description:` over a long `context:`
   list.

7. **Milestones are sequential** — `agent: "milestone"` tasks always run alone
   and depend on all preceding work they review.

8. **Design layers intentionally** — sketch the dependency graph as layers
   before writing tasks. Layer 0 = foundation, subsequent layers add features
   that build on earlier ones, final layers = integration / milestones.

**Important:** Whenever you modify or create a ROADMAP.json, you **must** validate it by running python check_roadmap.py projects/<your-project>/ROADMAP.json in the terminal and fix any errors reported.

---

## Agents reference

`agent:` in a task controls only the first build pass. The runner picks the
right agent for every other phase automatically. Models are in `opencode.jsonc`.

| Agent       | Writes files  | Role                                                      |
| ----------- | ------------- | --------------------------------------------------------- |
| `build`     | ✅            | Implement module + unit tests + compact docstrings        |
| `fix`       | ✅            | Repair failing tests (continues build session)            |
| `test`      | ✅ tests only | Extend / improve the test suite                           |
| `document`  | ✅ docs only  | README update only, no logic changes                      |
| `explore`   | ❌            | Read-only research spike                                  |
| `plan`      | ❌            | Lightweight planning                                      |
| `architect` | ❌            | Design / ADRs (use via task, not automatic)       |
| `milestone` | ❌            | Review gate + semver tag on develop                  |

`explore` / `plan` / `architect` cannot write files or run commands — use them
for thinking, then follow with a `build` task.

`milestone` invokes a review agent that can **read files and run inspection
commands** (`git log`, `git diff`, `cat`, `grep`, etc.) but cannot edit files or
run destructive commands. When git is managed, the runner tags develop with
semver and pushes to origin. Milestone tasks always run alone (never in
parallel).

---

## Project dependencies

Declare in the project folder, not the workspace root. Pin versions when
reproducibility matters (`pygame==2.6.1`).

| Manifest           | Installer          | Ecosystem         |
| ------------------ | ------------------ | ----------------- |
| `requirements.txt` | `pip install -r`   | Python            |
| `pyproject.toml`   | `pip install -e .` | Python (modern)   |
| `package.json`     | `pnpm install`     | Node / TypeScript |
| `Gemfile`          | `bundle install`   | Ruby              |
| `go.mod`           | `go mod download`  | Go                |
| `Cargo.toml`       | `cargo fetch`      | Rust              |

---

## Budget

```json
{
  "monthly_limit_tokens": 2000000000,
  "per_task_limit_tokens": 2000000,
  "max_attempts_per_task": 4,
  "max_parallel_agents": 3
}
```

Runner aborts (exit 2) if monthly limit is hit. A task is abandoned after
`max_attempts_per_task` failed fix cycles.

### Parallel builds

When `max_parallel_agents > 1`, the runner uses `depends_on:` to build a
dependency graph and schedules independent tasks in parallel. The **build**
phase runs concurrently; test, static checks, and document then run **once per
batch** (not per task). Only commits remain per-task for git attribution. The
first task always runs alone (project setup). Set `max_parallel_agents: 1` to
disable parallelism.

### Agent logs

Every opencode invocation writes a log file to `projects/<name>/logs/<task-slug>/`:

```
logs/<task-slug>/<yyyymmdd_HHMMSS>_<phase>_a<attempt>.log
```

Timestamp-first filenames mean `ls logs/<task-slug>/` is always chronological.

**Log verbosity** is selected once per run (at the "What would you like to do?" prompt):

- **Compact (default)** — agent output silenced; terminal shows `✓/✗ <phase>  +<tokens>` per
  invocation. On failure the last 40 lines of the log are printed inline so errors
  are immediately visible.
- **Verbose** — every agent line streams to the terminal in real time; log file is
  still written as a durable copy.
- **Parallel builds** always capture output (cannot safely interleave concurrent
  agent streams) regardless of the selected mode.

`logs/` is automatically added to `.gitignore` on first run and is never
committed.

### Project AGENTS.md

On the **first run** against a project (or whenever the file is absent),
`ensure_workspace_dirs` calls `generate_project_agents_md` to write an
`AGENTS.md` into the project directory. This file gives opencode agents working
inside the project full context about:

- Project name, ecosystem, preamble (from `ROADMAP.json`)
- Directory layout (ecosystem-specific)
- ROADMAP task JSON format and field list
- Pipeline phases in order
- Ecosystem-specific implementation guidelines (ruff for Python, `deno check` for Deno, etc.)
- Testing and scope rules (outputs-only, no barrel files, parallel safety)

Unlike `logs/`, `AGENTS.md` is **committed** to the project repository so agents
always have it available. Regenerate it at any time from the pipeline mode menu:

```
📝 Generate project AGENTS.md   (first run)
🔄 Regenerate project AGENTS.md (already exists)
```

---

## Git workflow (opt-in — `"git": {"enabled": true}` in ROADMAP)

When a project opts in to runner-managed git, the runner creates branches,
commits, merges, and pushes automatically:

```
main  →  develop  →  feature/<slug>   (per task)
```

Each task is committed on `feature/<slug>`, merged to `develop`, tagged
`task-<NNN>`, then the branch is deleted. You may run `git status` / `git diff`
to inspect state only.

When git is **not** managed (the default), the runner skips all git operations.
You can use your own version control workflow.

### Milestone tags (semver)

`agent: milestone` tasks create a `v<major>.<minor>.<patch>` tag on `develop`
and push to origin. Merging to `main` is manual. Use `version:` in the task body
to set the tag explicitly, or the runner derives one from the task number.

---

## Implementation guidelines

### Deno / TypeScript

- Explicit parameter and return types on all exports.
- No `any` (use `unknown` + narrowing); no `!` assertions (use conditionals).
- Never `async` without `await` — return `Promise.resolve(value)` when interface
  needs a `Promise`.
- Unused vars / params are compile errors — remove or `_`-prefix them.
- Every code path must return (`noImplicitReturns`).

### Python

- Prefer stdlib; add third-party deps only when clearly needed.
- Keep modules renderer-agnostic for full unit-testability.
- Tests in `tests/test_<module>.py`; shared fixtures in `conftest.py`.
- Import with package name: `from tetris.board import Board` — not relative
  imports from tests.
- No `if __name__ == "__main__"` guards in library modules.

### Tests

- At least one test per public function / method (happy path + task-specified
  edge cases).
- Mock only external I/O (filesystem, network, time) — never mock the module
  under test.
- Deterministic: no `random`, `time.sleep`, or unmocked network calls.
- `acceptance:` field is the exact criterion the runner checks.

### IDE / editor diagnostics

After **every** file edit — whether build, fix, or direct change — run the
IDE diagnostic check before considering the work done:

1. **In VS Code:** call the `get_errors` tool. Review every reported item:
   - Errors (`compileError`) **must** be fixed before finishing.
   - Suggestions (e.g. "class X can be written as Y") **must** also be
     applied — they appear as compile errors in the panel.
2. **Outside VS Code / headless:** run the appropriate CLI linter for the
   ecosystem (`ruff check .`, `npx tsc --noEmit && npx eslint .`,
   `deno check && deno lint`, `go vet ./...`, `cargo clippy -- -D warnings`).
3. Re-run the check after applying fixes to confirm zero remaining errors.

Never hand back to the user while `get_errors` (or its CLI equivalent)
still reports unresolved diagnostics in files you edited.

### Scope

- Implement only what the current task specifies.
- **CRITICAL for parallel builds:** Multiple agents may be editing the workspace simultaneously. **NEVER** modify files outside your `outputs:` list or the specific files requested in the task. Do not update shared barrel files (e.g., `index.ts`) or global registries unless explicitly listed in your task's `outputs:`.
- Don't modify completed-task files unless a dependency is genuinely broken.
- Don't add features not listed in `outputs:` or the task body.

---

## Deploy hook

**Deployment is opt-in and provider-agnostic.** Only configure it when the
project ROADMAP explicitly mentions deployment, hosting, or a production
environment. Never scaffold deploy scripts or configs for a library or
local-tool project.

### Configuration

Add a top-level `deploy` block to `ROADMAP.json`:

```json
{
  "deploy": {
    "enabled": true,
    "script": "scripts/deploy.sh",
    "env": {
      "provider": "fly",
      "app": "my-app",
      "region": "fra",
      "health_path": "/health"
    }
  }
}
```

| Field     | Type   | Default                                          | Description                                    |
| --------- | ------ | ------------------------------------------------ | ---------------------------------------------- |
| `enabled` | bool   | `true`                                           | Master switch for the project                  |
| `script`  | string | `scripts/deploy.sh` or `.ps1`                    | Path to deploy script (relative to project)    |
| `env`     | object | `{}`                                             | Key-value pairs injected as `DEPLOY_*` env vars |

`env` fields are uppercased and prefixed: `app` → `DEPLOY_APP`,
`health_path` → `DEPLOY_HEALTH_PATH`, etc.

**Backward compatibility:** if no ROADMAP `deploy` block exists, the runner
falls back to reading a `deploy.json` file at the project root (legacy format).

### Per-task deploy gating

By default, every committed task triggers the deploy hook. To limit deployment
to specific tasks, add `"deploy": true` to those tasks — when **any** task in
the ROADMAP has a `deploy` field, only tasks with `"deploy": true` will trigger
the hook.

### Skipping deployment

The deploy hook is **skipped** when any of these conditions is met:
- `RUNNER_NO_DEPLOY=1` environment variable is set (global suppression).
- `deploy.enabled` is `false` in the ROADMAP (per-project opt-out).
- The task is not marked for deployment (when per-task gating is active).

### Deploy script requirements

- Must be executable and exit non-zero on failure.
- Receives `DEPLOY_*` environment variables from the `env` block.
- The runner does **not** assume any specific provider — scripts can target
  Fly.io, AWS, GCP, Vercel, a bare VPS, or anything else.

The deploy script must exit non-zero on failure so the runner surfaces errors.

---

## Running the runner

```bash
# Local (requires Python 3.12+, opencode on PATH)
python agentik.py              # web UI (default)
python agentik.py --pipeline   # interactive pipeline

# Docker (recommended — everything bundled)
./scripts/start.sh             # Linux/macOS
.\scripts\start.ps1            # Windows
docker compose up              # web UI at http://localhost:8420
docker compose run agentik --pipeline   # interactive pipeline
```

The opencode binary path is configurable via `OPENCODE_CMD` env var (default:
`opencode`). Inside Docker this is set automatically.

After selecting a project, choose a mode:

- **Run pipeline** — work through all uncompleted tasks automatically.
- **Show dependency graph** — display a colour-coded task graph with layers,
  status badges (✓ done / ▶ ready / · blocked), and dependency links.

**Ctrl-C** pauses and saves state; next run resumes from the exact task and
attempt. To start a new project, create `projects/<name>/ROADMAP.json`.
