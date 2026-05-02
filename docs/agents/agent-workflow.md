# Agent workflow

This document describes how coding agents should approach work in GraphFlow.

## Before making changes

1. Read `CLAUDE.md`.
2. Read `README.md`.
3. Read `docs/roadmap.md`.
4. Identify the relevant issue and intended release label.
5. Inspect existing files before creating new abstractions.

## Work in small slices

Prefer a small complete change over a broad unfinished scaffold.

Good examples:

- Add `SourceSpec` and tests.
- Add CSV parser with a simple fixture.
- Add Neo4j connection check.
- Add one working manifest example.

Avoid:

- Adding multiple orchestration frameworks at once.
- Building unused abstract factories.
- Creating many empty modules with no tested behaviour.
- Adding LLM integrations before direct mapping works.

## Decision flow

When implementing a feature, ask:

1. Does this support the v0.1 loop?
2. Does the logic belong in `graphflow_core`?
3. Can it be tested without paid services?
4. Does it preserve future extensibility?
5. Does it require docs updates?

## Branching and PRs

Suggested branch names:

```text
feature/manifest-models
feature/neo4j-sink
feature/csv-ingestion
docs/manifest-guidelines
```

Suggested PR size:

- One issue or one small feature per PR.
- Include tests or explain why tests are not yet practical.
- Include docs changes for concepts, config, or user-facing behaviour.

## When uncertain

Prefer the simpler option that keeps the MVP moving.

Default choices:

- Neo4j only for v0.1.
- Local files before APIs.
- Direct mapping before text extraction.
- Deterministic rules before LLM calls.
- Docker Compose before Kubernetes.
- Interfaces before concrete vendor lock-in, but only where they are immediately useful.

## Output expectations

When completing a task, summarise:

- Files changed
- Behaviour added
- How to test it
- Any follow-up issues needed
