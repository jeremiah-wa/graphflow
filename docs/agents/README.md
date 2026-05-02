# Agent documentation

This directory contains guidance for coding agents and human contributors working on GraphFlow.

Start with the root [`CLAUDE.md`](../../CLAUDE.md), then use these supporting docs:

- [`agent-workflow.md`](agent-workflow.md) - how agents should approach work in this repo
- [`coding-standards.md`](coding-standards.md) - engineering and style guidance
- [`manifest-guidelines.md`](manifest-guidelines.md) - conventions for GraphFlow manifests
- [`issue-template.md`](issue-template.md) - suggested issue format
- [`pull-request-template.md`](pull-request-template.md) - suggested PR format
- [`review-checklist.md`](review-checklist.md) - checklist for reviewing changes

## Agent priorities

1. Keep the v0.1 graph-building loop small and working.
2. Put product logic in `packages/graphflow_core`.
3. Keep CLI/API/worker/web layers thin.
4. Avoid introducing heavy platform dependencies too early.
5. Update docs alongside architecture or manifest changes.
