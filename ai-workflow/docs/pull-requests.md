# Committing and Writing a Pull Request

Load this file only when asked to commit or open a PR. These are general preferences; a repository's own docs (e.g. a repo-level `docs/pull-requests.md`) take precedence when they conflict.

## Commit mechanics

- Branch off the current branch unless told so; never commit directly to the main branch.
- Write commit messages as a short imperative subject line, plus a body only when the diff alone doesn't explain the *why*.
- Run the repository's checks (format/lint/type/tests, pre-commit hooks) before committing or opening the PR.
- Before committing, make sure there are no unrelated files in the index to avoid accidentally including unrelated changes.

## PR description

A PR description should let a reviewer understand *what* changed, *how to use it*, and *why it is built this way* — in that order, from the outside in. Favor incremental, concrete detail over prose.

### Formatting rules

- Use fenced code blocks for examples (with a language) and `mermaid` blocks for diagrams.
- Keep Mermaid node labels on a single line each (embedded newlines break rendering).
- Prefer short, punchy bullets over long paragraphs, especially for decisions.

### Structure by PR type

Pick the structure matching what the PR is; for mixed PRs, lead with the dominant type.

**Features** — sections in order:

1. **Feature overview** — a short summary of what the change adds: the problem first, then the one-line shape of the solution. No implementation detail here.
2. **Code example** — a *user-level* example of how the feature is used: the smallest snippet a consumer would write, plus the observable runtime behavior (inputs, outputs, notable states). This anchors the reviewer in the public surface before any internals.
3. **Implementation details** — a layered, outside-in explanation of how the data flows:
   - Lead with a **data-flow** description, with a `mermaid` chart when it clarifies the path (entry point → transport/persistence → runtime → effect).
   - Then a **layered pieces** list: each component and its single responsibility.
   - Then a **Key decisions** subsection: short bullets, one per non-obvious choice, each stating the decision and the *why* in a sentence or two — trade-offs, alternatives rejected, layering/constraint reasons. This is where design intent lives; keep it tight.

**Bug fixes** — sections in order:

1. **The bug** — what is broken and its root cause.
2. **How it manifests** — the observable symptom: what a user/system sees, and how to reproduce it if non-obvious.
3. **The fix** — how the change resolves it, plus any Key decisions if the fix involved non-obvious choices.

**Config, docs, chores** — no code example. A short overview of what changed and why is usually enough; add Key decisions only if a choice was non-obvious.

Only include sections that carry signal. Skip Tests/Docs sections unless a reviewer needs specific guidance about them — the diff already shows the tests.

When not specified, default to opening PRs in "draft" rather than ready to review.
