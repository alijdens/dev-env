# Committing and Writing a Pull Request

Load this file only when asked to commit or open a PR. These are general preferences; a repository's own docs (e.g. a repo-level `docs/pull-requests.md`) take precedence when they conflict.

## Commit mechanics

- Branch off the current branch unless told so; never commit directly to the main branch.
- Write commit messages as a short imperative subject line, plus a body only when the diff alone doesn't explain the *why*.
- Run the repository's checks (format/lint/type/tests, pre-commit hooks) before committing or opening the PR.
- Before committing, make sure there are no unrelated files in the index to avoid accidentally including unrelated changes.

## PR size

Aim for PRs of at most ~200 LOC, excluding comments and documentation. This is a target, not a hard limit: some changes can't be split sensibly, but a 1k LOC PR is hard to review well, so try to keep them small whenever possible.

Ways to get there:

- **Stack PRs.** Split a large change into a chain of smaller PRs, each a self-contained unit of work that can be reviewed and shipped on its own, even if nothing uses it yet (e.g. a lib function, then the service using it, then the endpoint exposing it).
- **Separate refactors from behavior changes.** Mechanical moves/renames go in their own PR before the change that needs them.
- **Test smart, not redundantly.** Large PRs are often large because of tests repeating the same checks at every layer.

## PR description

A PR description should let a reviewer understand *what* changed, *how to use it*, and *why it is built this way* — in that order, from the outside in. Favor incremental, concrete detail over prose.

### Scale the description to the change

The sections below are the *maximum* structure, not a checklist. Include a section only when it tells the reviewer something the title and diff don't; an empty-calorie section is worse than none.

- **Trivial changes** (one-liners, flag removals, version/config bumps, copy tweaks): a few sentences or bullets on what and why. No headings needed.
- **Small or UI-only changes**: an overview, plus a screenshot/recording for UI (if tools available). No code example, diagram, or layered pieces.
- **Larger changes touching several components or a public surface**: the full structure for its type.

Content rules that apply at every size:

- **Describe the final state, not the PR's history.** No earlier iterations, what a bot flagged along the way, what the agent couldn't access, or who provided what.
- **Don't restate the diff.** A file-by-file list of edits adds nothing; describe components and responsibilities only when the change spans enough of them that the diff alone doesn't show how they fit.
- **Key decisions are for choices a reviewer might question.** Skip trivia (e.g. "the import stays because it's still used") and justifications for not doing things nobody would expect.

### Formatting rules

- Use fenced code blocks for examples (with a language) and `mermaid` blocks for diagrams.
- Keep Mermaid node labels on a single line each (embedded newlines break rendering).
- Prefer short, punchy bullets over long paragraphs, especially for decisions.

### Structure by PR type

Pick the structure matching what the PR is; for mixed PRs, lead with the dominant type.

**Features** — sections in order:

1. **Feature overview** — a short summary of what the change adds: the problem first, then the one-line shape of the solution. No implementation detail here.
2. **Usage example** — how the feature is used, from the consumer's side:
   - For a code/API surface (lib function, endpoint, CLI, config): the smallest snippet a consumer would write, plus the observable runtime behavior (inputs, outputs, notable states).
   - For UI: a screenshot or short recording (before/after when it's a change). If you can't capture one, leave a placeholder for the author to fill in.
   - Skip it for internal changes with no consumer-facing surface.
3. **Implementation details** — only when the change spans several components; a layered, outside-in explanation of how the data flows:
   - A `mermaid` **data-flow** chart only when the path crosses several boundaries non-obviously (entry point → transport/persistence → runtime → effect). Never for a linear chain of two or three nodes.
   - A **layered pieces** list: each component and its single responsibility.
   - A **Key decisions** subsection: short bullets, one per non-obvious choice, each stating the decision and the *why* in a sentence or two — trade-offs, alternatives rejected, layering/constraint reasons. This is where design intent lives; keep it tight.

**Bug fixes** — sections in order:

1. **The bug** — what is broken and its root cause.
2. **How it manifests** — the observable symptom: what a user/system sees, and how to reproduce it if non-obvious.
3. **The fix** — how the change resolves it, plus any Key decisions if the fix involved non-obvious choices.

For a small fix, these can collapse into a short paragraph each, or fewer if the title already says it.

**Config, docs, chores** — no usage example. A short overview of what changed and why is usually enough; add Key decisions only if a choice was non-obvious. When the change must be deployed/merged in a specific order relative to other PRs, say so explicitly.

Skip Tests/Docs sections and test-plan checklists unless a reviewer needs specific guidance about them — the diff already shows the tests.

When not specified, default to opening PRs in "draft" rather than ready to review.
