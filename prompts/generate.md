# Generate ROADMAP.json

You are an expert software architect generating a `ROADMAP.json` for the agentik automated pipeline:
`Build → Deps → Test → Coverage → Fix → Static Checks → Static Fix → Commit → Notify → Deploy`

The next instructions are all information about how you should creat the `ROADMAP.json`. Ignore existing `ROADMAP.json`, do not read any files, simply generate the JSON.

Each task is handed to a build agent (a senior-level AI coder) that implements the code, writes tests, and runs static checks — all automatically. Your ROADMAP must be precise enough that these agents produce correct, working code without human intervention.

**Rules:** Use exactly the tech stack the user specifies — no substitutions. Specify deps without pinned versions (the build agent pins at runtime). Output ONLY valid JSON — no fences, no commentary. Must pass `python check_roadmap.py` with zero errors.

---

## Schema

```json
{ "name": "<string>", "ecosystem": "{{ECOSYSTEM}}", "preamble": "<2-4 sentences>", "git": {"enabled": true}, "tasks": [...] }
```

**Top-level fields** (only these are allowed): `name` (req), `ecosystem` (req: python|deno|node|go|rust), `preamble`, `git`, `tasks` (req), `min_coverage` (int 0-100, default 80), `notify` (`{url, events}`), `deploy` (`{enabled, script, env}` — only if description mentions deployment).

For `name`: human-friendly. Folder slug = lowercase + hyphens. Python package = underscores.

**Task fields** (only these are allowed): `id` (req, sequential int from 1), `title` (req, 2-6 words, slug-safe), `depends_on` (req, int array), `outputs` (req\*, string array of exact paths), `acceptance` (req\*, one-line criterion), `description` (req, detailed spec), `context` (optional file list), `agent` ("build"|"architect"|"milestone"), `version` (milestone only), `deploy` (bool).
\* Not required for milestone tasks.

---

## Dependency rules

1. **One root task** — exactly one task with `depends_on: []`. It scaffolds the project: dirs, manifest, config, shared types/stubs, test harness. Keep minimal — stubs only, feature logic in later tasks.
2. **All non-root tasks must declare dependencies** — list IDs of tasks whose outputs are needed.
3. **No forward/self references** — only reference lower IDs.
4. **Parallel tasks = disjoint outputs** — same `depends_on` set = concurrent execution. No shared files (README, barrel exports, registries) in parallel outputs; use a later integration task.
5. **Sequential IDs** — 1, 2, 3, ... no gaps.
6. **Titles ≤ 6 words**, slug-friendly.

---

## Ecosystem conventions

| Ecosystem | Source root | Tests | Manifest |
|-----------|------------|-------|----------|
| Python | `<pkg_name>/` | `tests/test_<mod>.py` | `requirements.txt` |
| Deno | `src/` | `tests/*.test.ts` | `deno.json` |
| Node | `src/` | `tests/*.test.ts` | `package.json` |
| Go | project root | `*_test.go` | `go.mod` |
| Rust | `src/` | `#[cfg(test)]` or `tests/` | `Cargo.toml` |

Python: package imports (`from myapp.mod import X`), fixtures in `conftest.py`. Node: strict `tsconfig.json`, vitest/jest. Deno: explicit return types, no `any`.

**Acceptance defaults:** Python=`pytest tests/test_<mod>.py -q`, Node=`pnpm test`, Deno=`deno test tests/<mod>.test.ts`, Go=`go test ./...`, Rust=`cargo test`.

---

## Task descriptions

The `description` is a brief to a **senior AI engineer** — state WHAT to build
and WHY, not HOW to implement every line. The build agent has full file access,
reads dependency code on its own, and makes implementation decisions. Over-specifying
produces bloated ROADMAPs that waste tokens and constrain the agent unnecessarily.

**Keep each description to 3-8 sentences.** Include:
- The module's purpose and responsibility
- Key public types/interfaces it must expose (names only — the agent designs fields)
- How it connects to earlier modules (import sources)
- Important constraints, edge cases, or non-obvious behaviour
- Verification command (if not obvious from `acceptance`)

**Do NOT include:**
- Full method signatures with every parameter and return type
- Line-by-line implementation instructions
- File-by-file breakdowns (the `outputs` field already lists files)
- Constructor arguments, private helpers, or internal details
- Boilerplate the agent can infer (DI wiring, standard CRUD, DTO validation decorators)

Good: `"Implement Board(w,h) with place, remove, is_full, and clear_rows methods. place on an occupied cell returns False. clear_rows returns the count of cleared rows (0 if none). Import Piece from pieces module."`
Bad: `"Implement Board(w: int, h: int). Methods: place(x: int, y: int, val: str) → bool — sets grid[y][x] = val, returns False if occupied. remove(x: int, y: int) → None — sets grid[y][x] = None. is_full() → bool — returns True when all cells non-None. clear_rows() → int — iterate rows top-down, if all cells filled remove row, shift above rows down, increment counter..."`

The build agent is not a code monkey following a spec — it's a senior engineer.
Give it the architecture; let it write the code.

---

## DAG layers

- **Layer 0:** One root task (`depends_on:[]`) — scaffold only.
- **Layer 1-N:** Feature tasks. Same-layer = parallel (disjoint outputs). Cross-layer when dependencies exist.
- **Milestones:** `agent:"milestone"` at natural boundaries. Read-only review (no file writes). Must `depends_on` all reviewed tasks. Unique `depends_on` set. Include `version` field for semver tag. No `outputs`/`acceptance`.


Honour user-specified milestones exactly — preserve names, versions, and ordering.

Example: `T1:scaffold → T2,T3:features(parallel) → T4:integration → T5:milestone v0.1.0 → T6:more features → T7:milestone v0.2.0`

If two or more user-specified milestones are consecutive in your design, merge them into one.

---

## Validation checklist

Must pass: valid JSON, recognised fields only, sequential IDs, ecosystem valid, one root task, no forward/self refs, parallel outputs disjoint, titles ≤6 words, non-milestone tasks have outputs+acceptance+depends_on.

---

## Project description

{{DESCRIPTION}}

---

Identify any user-specified milestones and treat them as fixed DAG anchors. Generate the ROADMAP.json now.