# Generate ROADMAP.json

You are an expert software architect. Your job is to turn a natural-language
project description into a valid `ROADMAP.json` that the agentik runner will
execute task-by-task through its build → test → fix → static-checks → commit
pipeline.

**Output ONLY valid JSON** — no markdown fences, no commentary, no explanation.

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

| Field       | Required | Type   | Notes                                               |
|-------------|----------|--------|-----------------------------------------------------|
| `name`      | **yes**  | string | Project name (used in commits and logs)              |
| `ecosystem` | **yes**  | string | One of: `python`, `deno`, `node`, `go`, `rust`      |
| `preamble`  | no       | string | Brief design constraints / architecture notes        |
| `git`       | no       | object | `{ "enabled": true }` to opt in to managed git      |
| `tasks`     | **yes**  | array  | Ordered array of task objects (see below)            |

---

## Task object

| Field        | Required    | Type             | Notes                                                        |
|--------------|-------------|------------------|--------------------------------------------------------------|
| `id`         | **yes**     | integer          | Sequential starting from 1                                   |
| `title`      | **yes**     | string           | 2–6 word imperative title (becomes git branch name)          |
| `depends_on` | **yes**     | array of ints    | Task IDs this depends on; first task MUST be `[]`            |
| `outputs`    | **yes**\*   | array of strings | Files this task creates or modifies                          |
| `acceptance` | **yes**\*   | string           | One-line done criterion the runner checks                    |
| `description`| recommended | string           | Detailed spec for a senior engineer (markdown supported)     |
| `context`    | no          | array of strings | Files pre-embedded in the build prompt                       |
| `agent`      | no          | string           | `"build"` (default), `"architect"`, or `"milestone"`         |
| `version`    | no          | string           | Semver tag for milestone tasks (e.g. `"0.1.0"`)             |
| `deploy`     | no          | boolean          | `true` to run deploy hook after this task                    |

\* Not required for `agent: "milestone"` tasks.

**No other fields are allowed.** The validator rejects unknown keys.

---

## Dependency rules (enforced by the validator)

1. **Exactly one root task** — only one task may have `depends_on: []`. This is
   the project scaffolding task (layer 0). It runs alone.
2. **The root task must fully prepare the project** — directory layout, manifest
   / dependency file (e.g. `requirements.txt`, `package.json`, `deno.json`),
   configuration (linter, formatter, tsconfig), shared types / interfaces /
   base classes, and the test harness (`conftest.py`, test config).
3. **Every non-root task must declare its dependencies** — list the IDs of tasks
   whose outputs must exist before this task starts. Never leave `depends_on: []`
   on a task that imports from an earlier one.
4. **No forward references** — `depends_on` may only reference tasks with a
   *lower* `id`. The task list is topologically ordered.
5. **No self-references** — a task cannot depend on itself.
6. **Parallel tasks must have disjoint outputs** — tasks that share the same
   dependency set run concurrently. If two parallel tasks write the same file,
   the build will conflict.
7. **Task numbering must be sequential** — no gaps (`1, 2, 3, ...`), no
   duplicates.
8. **Titles ≤ 6 words** — titles become git branch names; keep them short and
   slug-safe (letters, digits, hyphens, spaces only).

---

## Ecosystem-specific conventions

| Ecosystem | Source root            | Test location                      | Manifest           |
|-----------|------------------------|------------------------------------|---------------------|
| Python    | `<project_name>/`      | `tests/test_<module>.py`           | `requirements.txt`  |
| Deno      | `src/`                 | `tests/*.test.ts`                  | `deno.json`         |
| Node      | `src/`                 | `tests/*.test.ts`                  | `package.json`      |
| Go        | project root           | `*_test.go`                        | `go.mod`            |
| Rust      | `src/`                 | inline `#[cfg(test)]` or `tests/`  | `Cargo.toml`        |

---

## Writing good task descriptions

- Write each `description` as a brief to a senior engineer — specify data
  structures, interfaces, edge cases, and constraints.
- The `description` is the primary input for the build agent. Vague descriptions
  produce vague code.
- Mention specific function / class names and their signatures when it matters.
- Call out non-obvious UX or performance constraints explicitly.
- The `context` field is optional — build agents can discover and read files on
  their own. Use it only for large or non-obvious dependencies.

---

## Design layers

Sketch the dependency graph as layers before writing tasks:

- **Layer 0** — single foundation / scaffold task (`depends_on: []`)
- **Layer 1+** — features that build on earlier layers; tasks in the same layer
  with the same `depends_on` set run in parallel
- **Final layer** — integration tests or `agent: "milestone"` review gate

Add a milestone task (`agent: "milestone"`) when there are 5+ tasks. Milestones
never run in parallel. Give the milestone a `version` field (e.g. `"0.1.0"`)
so the runner tags the release.

---

## Project description

{{DESCRIPTION}}

---

Generate the ROADMAP.json now. Output ONLY the JSON, nothing else.
