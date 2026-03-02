# Task: {{TASK}}

{{LANG_LINE}}

## Outputs: {{LOCATIONS}}

{{IMPORT_RULES}}

## Rules

- Code in `{{SRC}}/`, tests in `{{TESTS}}/`. Cover all public behaviour, edge cases, error paths.
- Only what this task specifies — no speculative features. No deprecated APIs.
- Docstrings on public module/class/function: one sentence + param/return lines. No `Example:`/`Note:`/`Raises:`.
- Inline comments only on non-obvious logic.
- Maintain `.gitignore` — add entries for any new generated artefacts, caches, or secrets.

## Post-edit check

Run `get_errors` (VS Code) or ecosystem CLI linter and fix all errors/suggestions before proceeding.

## Deps

Confirm every third-party import is in the manifest:

{{MANIFEST_TABLE}}

Create manifest if missing. Stdlib needs no entry.

{{DOCKERFILE_RULES}}{{DEPLOY_RULES}}{{PROJECT_CONTEXT}}

## Spec

{{TASK}}

{{TASK_SPEC}} {{CONTEXT_FILES}}

## Docs

Update/create project `README.md`: (1) summary, (2) directory tree, (3) how to run, (4) how to test.
