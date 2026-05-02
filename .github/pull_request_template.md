## Summary

Briefly describe what changed.

## Linked issue

Closes #ISSUE_NUMBER

## Changes

- Change 1
- Change 2
- Change 3

## How to test

Describe the commands or manual steps used to verify the change.

```bash
# example
graphflow config validate examples/simple_csv
```

## Screenshots or output

Add screenshots, CLI output, or logs if useful.

## Checklist

- [ ] Change is scoped to the linked issue
- [ ] Core logic lives in `packages/graphflow_core` where appropriate
- [ ] Tests added or updated where practical
- [ ] Docs updated if behaviour, architecture, or manifests changed
- [ ] No real secrets or API keys committed
- [ ] No paid API dependency added to the v0.1 happy path
- [ ] Follow-up work is captured in issues or TODOs linked to issues

## PR expectations

Good PRs should be small and easy to review.

Avoid mixing unrelated changes such as:

- Manifest model changes plus frontend UI work
- Neo4j sink implementation plus LLM extraction
- Repo restructuring plus business logic changes

If a PR touches multiple areas, explain why in the summary.
