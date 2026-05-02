# Issue template

Use this template when creating new GitHub issues manually or through an agent.

## Title

Use an action-oriented title.

Examples:

- Implement `SourceSpec` manifest model
- Add CSV parser for local file sources
- Validate duplicate node keys before graph load
- Document Neo4j sink behaviour

## Template

```md
## Goal

Describe the outcome this issue should achieve.

## Context

Explain why this matters and how it fits the roadmap.

## Scope

- Item 1
- Item 2
- Item 3

## Out of scope

- Thing deliberately not included
- Thing deferred to later issue

## Acceptance criteria

- [ ] Observable outcome 1
- [ ] Observable outcome 2
- [ ] Tests/docs updated where relevant

## Notes

Any implementation hints, links, or follow-up ideas.
```

## Label guidance

Use one type label:

- `Epic`
- `Feature`
- `Task`
- `Bug`
- `Spike`

Use one or more area labels:

- `Product`
- `Core`
- `Config`
- `Repo`
- `Ingestion`
- `Mapping`
- `Graph Sink`
- `Extraction`
- `Entity Resolution`
- `API`
- `Web`
- `Infra`
- `Demo`

Use one priority label:

- `P0`
- `P1`
- `P2`

Use one release label where known:

- `v0.1`
- `v0.2`
- `v0.3`

## Sizing guidance

A good task issue should be completable in a focused coding session.

If the issue needs multiple PRs or spans multiple subsystems, it is probably an epic or feature issue.
