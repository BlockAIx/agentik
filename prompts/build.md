# Task: {{TASK}}

{{LANG_LINE}}

## Output locations

{{LOCATIONS}}

{{IMPORT_RULES}}

## Requirements

- Implementation goes in `{{SRC}}/`; tests go in `{{TESTS}}/`.
- Tests must cover all public behaviour, edge cases, and error paths.
- No speculative features — implement only what this task specifies.
- Do not use deprecated APIs or language features — the linter enforces
  `@typescript-eslint/no-deprecated` and will fail on any usage flagged as
  `@deprecated`.
- Docstrings / JSDoc on every public module, class, and function:
  - **One sentence** — what it does, nothing more.
  - List each parameter and return value on its own line (name + brief
    type/purpose).
  - No `Example:`, `Note:`, or `Raises:` sections.
- Inline comments only on genuinely non-obvious lines; skip anything
  self-explanatory.

## Post-edit checklist

After writing or modifying any file, run the IDE diagnostic check:
- **VS Code** — call the `get_errors` tool and fix every reported error or
  lint suggestion before finishing.
- **Headless / other editor** — run the ecosystem CLI linter
  (`ruff check .`, `npx tsc --noEmit`, `deno check && deno lint`,
  `go vet ./...`, `cargo clippy -- -D warnings`) and resolve all output.

Only proceed to the dependency checklist once the diagnostic check is clean.

## Dependency checklist

For every third-party import you used, confirm it is declared in the manifest.

{{MANIFEST_TABLE}}

Stdlib / built-ins don't need declaring. Create the manifest if it doesn't exist
yet.

{{DOCKERFILE_RULES}}{{DEPLOY_RULES}}{{PROJECT_CONTEXT}}

## Task specification

{{TASK}}

{{TASK_SPEC}} {{CONTEXT_FILES}}
