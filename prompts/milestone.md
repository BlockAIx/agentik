# Milestone Review — {{PROJECT_NAME}} v{{VERSION}}

All tasks through this checkpoint pass tests. Verify releasable state before tagging **v{{VERSION}}**.

**Project:** `{{PROJECT_NAME}}` | **Package:** `{{PKG}}`

## Files
```
{{LISTING_TEXT}}
```

## ROADMAP
```markdown
{{ROADMAP}}
```

## Spec
{{TASK}}

{{TASK_SPEC}}

## Rules

- **Do NOT run tests, builds, or any project commands.** The pipeline already
  guarantees all tests pass before reaching this milestone. Your job is to
  **read and review code only** using file tools and the allowed inspection
  commands (git log/diff/show, cat, find, ls, head, tail, wc, grep).
- Do not attempt `pnpm`, `npm`, `jest`, `vitest`, `pytest`, `cargo`, `go`,
  `deno`, `node`, or any build/test runner.

## Checklist

Read files as needed, report ✔/⚠/✗ per item:

1. **Tests** — test files exist for public APIs? Reasonable coverage by inspection?
2. **Deps** — all runtime libs in manifest? Versions pinned?
3. **Integration** — modules wired together, reachable from entry point?
4. **Regressions** — any refs to moved/renamed/deleted code?
5. **Config** — tsconfig/deno.json/package.json match actual usage?
6. **Security** — secrets in env vars only? No hardcoded creds?
7. **Docs** — README current?

Report: ✔/⚠/✗ per item, specific findings (file+line), prioritised issues. Real problems only.
