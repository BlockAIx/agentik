# Milestone Review — {{PROJECT_NAME}} v{{VERSION}}

All tasks up to this checkpoint are implemented and tests are passing. Before
tagging **v{{VERSION}}** on main, verify the project is in a releasable state.

**Project:** `{{PROJECT_NAME}}` | **Package:** `{{PKG}}`

## File tree

```
{{LISTING_TEXT}}
```

## ROADMAP

```markdown
{{ROADMAP}}
```

## Task specification

{{TASK}}

{{TASK_SPEC}}

## Checklist

Read any files you need, then report on each item:

1. **Tests** — do all test suites pass? Any obviously missing coverage for
   public APIs delivered so far?
2. **Dependencies** — all runtime libs declared in the manifest? Versions pinned
   where reproducibility matters?
3. **Integration** — are the modules delivered up to this milestone wired
   together and reachable from the entry point?
4. **Regressions** — does any completed task's output reference code that was
   later moved, renamed, or deleted?
5. **Config files** — do `tsconfig.json`, `deno.json`, `package.json`, etc.
   match what the codebase actually uses?
6. **Security** — secrets in env vars? No hardcoded credentials?
7. **Documentation** — README up to date with the current feature set?

## Output

- ✔ / ⚠ / ✗ status per item.
- Specific findings with filename + line where possible.
- Prioritised issue list (critical → nice-to-have).

Report real problems only. If everything looks good, confirm the milestone is
ready to tag.
