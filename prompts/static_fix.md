# Static analysis failures — {{TASK}}

All tests are passing but the following type-check / lint errors must be fixed
before this task can be considered complete.

Fix **only** the reported issues. Do not refactor unrelated code, change logic,
or alter function signatures beyond what is strictly required to silence the
errors.

After applying fixes, re-run the IDE diagnostic check:
- **VS Code** — call the `get_errors` tool and confirm zero errors remain in
  the files you edited.
- **Headless** — re-run the same CLI command that produced this output and
  confirm it exits clean.

Do not finish until the check is clean.

## Static analysis output

```
{{TRUNCATED_LOGS}}
```
