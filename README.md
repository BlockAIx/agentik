![agentik](assets/intro.png)

# agentik

An autonomous development pipeline that drives
[opencode](https://opencode.ai) through a full **build → test → fix → document
→ commit** pipeline for every task defined in a project ROADMAP.

Write a structured `ROADMAP.json`, run `python agentik.py`, and let AI agents
implement your project task by task — with git history, cost tracking, parallel
builds, and resume support built in.

## Features

- **Zero-touch pipeline** — build, test, fix, lint, document, and commit in one
  loop, fully automated
- **Parallel builds** — independent tasks run concurrently (dependency-aware
  scheduling)
- **Multi-ecosystem** — auto-detects Python, Deno, Node/TS, Go, Rust; any
  ecosystem works with manual config
- **Budget tracking** — monthly token limits, per-project cost logs, estimated
  USD spend
- **Resume on Ctrl-C** — saves state after every phase; pick up exactly where
  you left off
- **Milestone gates** — semver tagging and merge-to-main via `agent: milestone`
  tasks
- **Deploy hooks** — provider-agnostic deployment via ROADMAP `deploy` block
- **Agent logs** — every opencode call logged with timestamp, phase, and attempt
  number
- **Git managed (opt-in)** — automatic branching, commits, merges, and tags
  when enabled

## Quickstart

### Prerequisites

- **Python 3.12+**
- [opencode](https://opencode.ai) installed and on PATH
- An LLM provider configured in `opencode.jsonc` (e.g. GitHub Copilot,
  Anthropic, OpenAI)

### Install

```bash
git clone https://github.com/BlockAIx/agentik.git
cd agentik
pip install -r requirements.txt
```

### Create a project

Create a folder under `projects/` with a `ROADMAP.json`. You can write it by
hand or **ask any AI model** to generate it for you — the workspace-level
[AGENTS.md](AGENTS.md) contains the full ROADMAP schema, task field reference,
and ecosystem conventions, so a model working from the repository root has all
the context it needs.

Example prompt for a new project:

> Create a new project `projects/my-api/ROADMAP.json` for a Python REST API
> with three modules: models, routes, and auth. Follow the ROADMAP format in
> AGENTS.md. Include proper depends_on ordering, outputs, and acceptance
> criteria. Then validate it with
> `python check_roadmap.py projects/my-api/ROADMAP.json`.

To add tasks to an existing project:

> Read `projects/my-api/ROADMAP.json` and add tasks 4–6 for WebSocket support:
> a connection manager, event handlers, and integration tests. Continue the
> existing id sequence and set depends_on correctly. Validate with
> `python check_roadmap.py projects/my-api/ROADMAP.json`.

You can also start from a minimal hand-written file:

```
projects/
  my-project/
    ROADMAP.json
```

```json
{
  "name": "My Project v0.1",
  "ecosystem": "python",
  "preamble": "",
  "tasks": [
    {
      "id": 1,
      "title": "Core Module",
      "depends_on": [],
      "outputs": ["my_project/core.py", "tests/test_core.py"],
      "acceptance": "all tests in tests/test_core.py pass",
      "description": "Implement `greet(name: str) -> str` returning `\"Hello, <name>!\"`.\nTests: normal input, empty string, non-ASCII."
    }
  ]
}
```

See [ROADMAP_EXAMPLE.md](ROADMAP_EXAMPLE.md) for the full syntax reference.

### Run

```bash
python agentik.py
```

An arrow-key project selector appears, then pick a mode:

- **Run pipeline** — work through every uncompleted task
- **Run pipeline (verbose)** — same, but stream full agent output
- **Show dependency graph** — colour-coded task graph with status badges
- **Generate project AGENTS.md** — create or regenerate per-project agent instructions

Press **Ctrl-C** at any time to save state and resume later.

## How it works

For each task agentik executes:

| # | Phase   | What happens                                                           |
|---|---------|------------------------------------------------------------------------|
| 1 | Build   | opencode agent implements the module + unit tests                      |
| 2 | Deps    | Installs any new dependencies the agent declared                       |
| 3 | Test    | Runs ecosystem test suite (pytest / deno test / cargo test / etc.)     |
| 4 | Fix     | If tests fail → fix agent patches code (same session, up to N retries) |
| 5 | Static  | Lint & type checks (ruff / deno check+lint / tsc / go vet / clippy)    |
| 6 | Stfix   | If static checks fail → fix agent resolves them (up to 2 retries)      |
| 7 | Doc     | Document agent updates README                                          |
| 8 | Commit  | `git add → commit → merge to develop` (when git is managed)           |
| 9 | Deploy  | Runs deploy script if configured in ROADMAP (optional)                 |

## Project structure

```
agentik/
├── agentik.py               # entry point
├── runner/                  # pipeline engine
│   ├── config.py            #   constants, Rich console, prompt loader
│   ├── opencode.py          #   opencode invocation wrappers
│   ├── pipeline.py          #   main pipeline orchestration
│   ├── roadmap.py           #   ROADMAP.json parsing and helpers
│   ├── state.py             #   progress tracking, budget accounting
│   └── workspace.py         #   ecosystem detection, git operations
├── helpers/
│   └── check_roadmap.py     # ROADMAP structural validator
├── tests/                   # unit tests
├── prompts/                 # prompt templates (Mustache-style)
│   ├── build.md
│   ├── fix.md
│   ├── static_fix.md
│   ├── document.md
│   └── milestone.md
├── AGENTS.md                # agent instructions for this workspace
├── LICENSE                  # MIT license
├── budget.json              # global limits and token price table
├── check_roadmap.py         # convenience shim for helpers/check_roadmap.py
├── opencode.jsonc           # agent definitions (models, permissions)
├── requirements.txt         # dependencies
├── ROADMAP_EXAMPLE.md       # full ROADMAP syntax reference
└── projects/
    └── <project-name>/
        ├── ROADMAP.json         # task list (you write this)
        ├── budget.json          # per-project cost log (auto-managed)
        ├── .runner_state.json   # progress + resume state (auto-managed)
        ├── AGENTS.md            # auto-generated agent instructions
        ├── <source>/            # implementation (created by agents)
        └── tests/               # unit tests (created by agents)
```

Each project under `projects/` is its own directory. When git is managed
(`"git": {"enabled": true}` in ROADMAP), each project gets its own git
repository with automatic branching and commits.

## ROADMAP.json reference

### Task fields

| Field         | Required           | Type             | Description                            |
| ------------- | ------------------ | ---------------- | -------------------------------------- |
| `id`          | **yes**            | integer          | Unique task ID                         |
| `title`       | **yes**            | string           | Short imperative title (≤ 6 words)     |
| `depends_on`  | **yes**            | array of ints    | Task IDs this depends on (or `[]`)     |
| `outputs`     | **yes**\*          | array of strings | Expected output files                  |
| `acceptance`  | **yes**\*          | string           | Human-readable done criterion          |
| `description` | no                 | string           | Full task spec (can contain markdown)  |
| `agent`       | no                 | string           | Override agent (default: `"build"`)    |
| `ecosystem`   | no                 | string           | Override ecosystem for this task       |
| `context`     | no                 | array of strings | Files pre-injected into the build prompt |
| `version`     | no                 | string           | Semver tag (milestone tasks only)      |
| `deploy`      | no                 | boolean          | Run deploy hook after this task        |

\* Required for all tasks except `agent: "milestone"` tasks.

### Preamble

Everything outside the `tasks` array — `name`, `ecosystem`, and `preamble` — is
project-level config. The `preamble` string is injected into every build prompt
as project context, so architecture notes defined once guide every task.

### Validation

```bash
python check_roadmap.py projects/<name>/ROADMAP.json
```

Checks numbering, required fields, dependency references, single root task
(exactly one `depends_on: []`), disjoint parallel outputs, title length,
architecture rules, and unknown fields.

## Agents

![agentik](assets/agents.png)

Defined in `opencode.jsonc`. agentik selects the right agent per phase;
`agent:` in the ROADMAP only controls the first-pass build.

| Agent       | Writes files | Role                                                |
| ----------- | ------------ | --------------------------------------------------- |
| `build`     | yes          | Implement module + unit tests                       |
| `fix`       | yes          | Repair failing tests (continues build session)      |
| `test`      | tests only   | Extend / improve the test suite                     |
| `document`  | docs only    | README update, no logic changes                     |
| `explore`   | no           | Read-only research spike                            |
| `plan`      | no           | Lightweight planning                                |
| `architect` | no           | Design / ADRs (use via task, not automatic)          |
| `milestone` | no           | Review gate + semver tag on develop                  |

## Budget and cost tracking

Configure in `budget.json`:

```json
{
  "monthly_limit_tokens": 2000000000,
  "per_task_limit_tokens": 2000000,
  "max_attempts_per_task": 4,
  "max_parallel_agents": 3,
  "token_prices_usd_per_million": {
    "input": 1.25,
    "output": 5.00,
    "cache_read": 0.31,
    "cache_write": 1.25
  }
}
```

- **Monthly limit** — agentik aborts (exit 2) when exceeded
- **Per-task limit** — reserved for future enforcement
- **Max attempts** — fix retries before abandoning a task
- **Token prices** — used to estimate USD cost in the status table

Every run displays a status table with token usage, estimated cost, progress
bar, and ETA.

## Parallel builds

When `max_parallel_agents > 1`, independent tasks (no dependency edges between
them) run concurrently. The build phase is parallel; test, static, and document
phases run once per batch.

**Important:** parallel tasks must not have overlapping `outputs:` or modify
shared files. The validator enforces disjoint outputs for tasks that share the
same dependency set. Only one task may have `depends_on: []` (the project
foundation, layer 0).

## Git workflow (opt-in)

Git management is **off by default**. Enable it per project:

```json
{ "git": { "enabled": true } }
```

When enabled:

```
main  ←  develop  ←  feature/<slug>  (per task)
```

Each task is committed on `feature/<slug>`, merged to `develop`, and tagged
`task-<NNN>`. Milestone tasks tag `develop` with a semver tag.

When git is **not** managed, agentik skips all git operations. You can use
your own version control workflow.

## Deploy hook (optional)

Deployment is **opt-in and provider-agnostic**. Add a top-level `deploy` block
to your `ROADMAP.json`:

```json
{
  "deploy": {
    "enabled": true,
    "script": "scripts/deploy.sh",
    "env": { "provider": "fly", "app": "my-app", "region": "fra" }
  }
}
```

- `enabled` — master switch (default `true`)
- `script` — path to deploy script relative to project (default `scripts/deploy.sh` or `.ps1`)
- `env` — key-value pairs injected as `DEPLOY_*` environment variables

**Per-task gating:** add `"deploy": true` to specific tasks. When any task has
a `deploy` field, only those marked `true` trigger the hook.

**Suppress deployment:**
- `RUNNER_NO_DEPLOY=1` — global suppression
- `deploy.enabled: false` in the ROADMAP — per-project opt-out

**Backward compatibility:** if no ROADMAP `deploy` block exists, agentik
falls back to reading a `deploy.json` file at the project root.

## Agent logs

Every opencode invocation is logged to `projects/<name>/logs/<task-slug>/`:

```
logs/<task-slug>/<yyyymmdd_HHMMSS>_<phase>_a<attempt>.log
```

In **compact mode** (default), only status lines appear in the terminal. On
failure, the last 40 log lines are shown inline. In **verbose mode**, all agent
output streams in real time. Logs are gitignored automatically.

## State and resume

Progress is stored in `projects/<name>/.runner_state.json` and committed to the
project repo. Adding new tasks to a ROADMAP works seamlessly — completed tasks
are skipped, new ones are picked up automatically.

## Supported ecosystems

agentik auto-detects these ecosystems from manifest files. Any ecosystem
works — set `"ecosystem": "<name>"` in your ROADMAP and agentik will use
it as-is (unknown values produce a warning, not an error).

| Ecosystem | Manifest           | Test runner       | Static checks              |
| --------- | ------------------ | ----------------- | -------------------------- |
| Python    | `requirements.txt` | `pytest`          | `ruff`                     |
| Deno      | `deno.json`        | `deno test`       | `deno check` + `deno lint` |
| Node      | `package.json`     | `vitest` / `jest` | `tsc --noEmit`             |
| Go        | `go.mod`           | `go test`         | `go vet`                   |
| Rust      | `Cargo.toml`       | `cargo test`      | `cargo clippy`             |

## Contributing

Contributions are welcome. Please:

1. Fork the repo and create a feature branch
2. Keep `pytest tests/` green
3. Update `AGENTS.md` and `README.md` if you change agentik behaviour
4. Submit a pull request

## License

[MIT](LICENSE)
