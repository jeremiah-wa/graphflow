# Agent documentation

This directory contains guidance for coding agents and human contributors working on GraphFlow.

Start with the root [`CLAUDE.md`](../../CLAUDE.md), then use these supporting docs:

- [`agent-workflow.md`](agent-workflow.md) - how agents should approach work in this repo
- [`coding-standards.md`](coding-standards.md) - engineering and style guidance
- [`manifest-guidelines.md`](manifest-guidelines.md) - conventions for GraphFlow manifests
- [`review-checklist.md`](review-checklist.md) - checklist for reviewing changes

Operational GitHub templates now live under `.github/` so GitHub can detect and apply them automatically:

- [`../../.github/pull_request_template.md`](../../.github/pull_request_template.md) - pull request template
- [`../../.github/ISSUE_TEMPLATE/feature.yml`](../../.github/ISSUE_TEMPLATE/feature.yml) - feature issue form
- [`../../.github/ISSUE_TEMPLATE/task.yml`](../../.github/ISSUE_TEMPLATE/task.yml) - task issue form
- [`../../.github/ISSUE_TEMPLATE/bug.yml`](../../.github/ISSUE_TEMPLATE/bug.yml) - bug issue form
- [`../../.github/ISSUE_TEMPLATE/spike.yml`](../../.github/ISSUE_TEMPLATE/spike.yml) - spike issue form

## Agent priorities

1. Keep the v0.1 graph-building loop small and working.
2. Put product logic in `packages/graphflow_core`.
3. Keep CLI/API/worker/web layers thin.
4. Avoid introducing heavy platform dependencies too early.
5. Update docs alongside architecture or manifest changes.
