# Contributing to GraphFlow

Thanks for working on GraphFlow. This guide covers the rules that apply to
every change: commit size, commit message format, branches, and pull
requests. Product and architecture guidance lives in [`README.md`](README.md),
[`CLAUDE.md`](CLAUDE.md), and the [`docs/`](docs/) tree.

## Keep commits small

A commit should capture **one logical change**. Reviewers should be able to
understand the diff in a few minutes.

Rules:

- One logical change per commit. One issue per pull request.
- Do not mix refactors with behaviour changes.
- Do not mix code changes with unrelated formatting or import churn.
- Do not mix manifest model changes with frontend/UI work, sink work with
  extractor work, or repo restructuring with business logic changes (see
  [`.github/pull_request_template.md`](.github/pull_request_template.md)).
- Prefer many small commits on a feature branch over one large commit. If
  the branch ends up messy, squash on merge.
- If you find unrelated bugs or cleanups while working, open a separate
  issue and PR rather than folding them in.

If you cannot describe the commit in one short imperative sentence without
the word "and", it is probably too big.

## Commit message convention

GraphFlow uses [Conventional Commits](https://www.conventionalcommits.org/).

### Format

```text
<type>(<optional scope>): <short imperative summary>

<optional body explaining what and why, wrapped at ~72 chars>

<optional footers, e.g. "Closes #123" or "BREAKING CHANGE: ...">
```

Rules:

- The summary line is **imperative** ("Add manifest models", not "Added" or
  "Adds"), lowercase after the colon, no trailing period, and ideally
  under 72 characters.
- The body explains *why* the change is needed and any non-obvious *what*.
  Skip it for trivial commits.
- Reference issues in a footer: `Closes #1`, `Refs #5`.
- Use `!` after the type/scope to mark a breaking change, and include a
  `BREAKING CHANGE:` footer describing the impact.

### Allowed types

| Type       | Use for                                                            |
|------------|--------------------------------------------------------------------|
| `feat`     | A new user-visible feature or capability.                          |
| `fix`      | A bug fix.                                                         |
| `docs`     | Documentation-only changes.                                        |
| `refactor` | Code change that neither adds a feature nor fixes a bug.           |
| `test`     | Adding or updating tests only.                                     |
| `chore`    | Routine maintenance (deps, tooling configs, repo housekeeping).    |
| `build`    | Changes to the build system, packaging, or Docker images.          |
| `ci`       | Changes to CI configuration, workflows, or scripts.                |
| `perf`     | Performance improvements without behaviour change.                 |
| `revert`   | Reverting a previous commit.                                       |

### Optional scope

Scope is the area of the codebase touched. Prefer short, stable names that
match the repo structure:

- `core` for `packages/graphflow_core`
- `cli`, `api`, `worker`, `web` for the matching `apps/*`
- `manifests`, `sink`, `mapping`, `runner` for sub-areas of `core`
- `infra`, `docker` for deployment assets
- `docs`, `examples`

Omit scope if a change spans many areas or is repo-wide.

### Examples

```text
docs: add MVP architecture ADR

Closes #1
```

```text
feat(manifests): add Pydantic models for source and ontology

Refs #3
```

```text
fix(sink): use parameterised MERGE for relationship upserts

Closes #42
```

```text
refactor(core): extract validator from runner

No behaviour change.
```

```text
feat(api)!: rename /runs endpoint to /pipelines/runs

BREAKING CHANGE: clients must update the runs path.
```

## Branch names

See the existing guidance in
[`docs/agents/agent-workflow.md`](docs/agents/agent-workflow.md). In short:

```text
feat/<short-topic>
fix/<short-topic>
docs/<short-topic>
chore/<short-topic>
```

Match the prefix to the dominant Conventional Commits type for the work.

## Pull requests

- Use the [`pull_request_template.md`](.github/pull_request_template.md);
  fill in the summary, linked issue, changes, and how-to-test sections.
- Keep PRs focused on a single issue or small feature.
- The PR title should follow the same Conventional Commits format as the
  commit summary, since `main` is squash-merged and the PR title becomes
  the commit message on `main`.
- Update docs in `docs/` when behaviour, architecture, or manifests change.

## Enforcement

For now, these rules are enforced by review only. CI-side enforcement
(PR-title lint, `commitlint`) may be added later; if you find yourself
repeatedly correcting the same mistake in review, open an issue to add it.
