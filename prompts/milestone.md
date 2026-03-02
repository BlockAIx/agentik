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

## Checklist

Read files as needed, report ✔/⚠/✗ per item:

1. **Tests** — all passing? Missing coverage for public APIs?
2. **Deps** — all runtime libs in manifest? Versions pinned?
3. **Integration** — modules wired together, reachable from entry point?
4. **Regressions** — any refs to moved/renamed/deleted code?
5. **Config** — tsconfig/deno.json/package.json match actual usage?
6. **Security** — secrets in env vars only? No hardcoded creds?
7. **Docs** — README current?

Report: ✔/⚠/✗ per item, specific findings (file+line), prioritised issues. Real problems only.
