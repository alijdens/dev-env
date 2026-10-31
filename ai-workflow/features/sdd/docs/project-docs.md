# Task Workflow: Project Docs

Two short docs at the data root give every planning and review session the context a task alone doesn't carry:

- `goal.md`: why the project exists, for whom, what success looks like, what it won't do. Planning checks every feature and ADR against it.
- `principles.md`: the rules every change must respect (stack boundaries, compatibility, security, quality, definition of done). Reviews check changes against it; ADRs decide within it.

`sdd doc new <name>` writes the template, whose comments brief each section; `sdd doc list` shows which docs are missing, draft or ok; `sdd doc check` fails while any is a draft (guidance comments left, empty sections, over the length limit). `sdd validate` warns about missing docs and fails on drafts, so a half-written doc doesn't merge.

Both are optional: a project without them still works, planning just has less to check against.

## When to run the interview

- **Right after setup** (`sdd init`): offer both docs, in that order, and say what each is for in a line. The user may skip either; note in the final report that `sdd validate` will keep warning until they exist.
- **Later, on request**: "write the project goal", "we don't have principles yet", "the goal changed", "review the principles". A skipped doc is written from scratch; an existing one is revised.
- **When planning or reviewing notices a gap**: a feature nobody can tie to the goal, or a review arguing about a rule that isn't written down. Don't start the interview then; tell the user and offer to run it.

## The interview

The agent writes the doc; the user supplies the facts. Section by section, in the template's order:

1. Ask one or two questions for the section, in the user's terms, with the section's brief from the template comment as the yardstick. Offer a guess when the code, README or earlier answers make one obvious ("the README suggests the users are X, right?"), so the user corrects rather than dictates.
2. Draft the section from the answers, within the limits below, and show it. Keep the user's wording where it's precise; tighten it where it isn't.
3. Confirm or adjust, then move on. Don't revisit confirmed sections unless a later answer contradicts them.

Keep the user inside the doc's scope. When an answer drifts, say where it belongs and carry on:

- Implementation detail or architecture ("we use Postgres with a queue in front"): an ADR, or at most a line under principles' stack section if it's a commitment.
- A decision made during the conversation ("let's go with per-key limits"): an ADR, once there's a feature to attach it to.
- A feature or piece of work ("we need an admin page"): a task or a spec, not a goal.
- A preference without a consequence ("we like clean code"): drop it; a principle a reviewer can't check is noise.
- History and justification of the current state: leave it out unless it constrains the future.

Limits, enforced by `sdd doc check`, that the draft must respect: `goal.md` under 60 lines, `principles.md` under 80 lines with at most about 15 principles, every section filled. A section that genuinely has nothing gets `None.` so it reads as decided, never a placeholder.

When the sections are confirmed: remove the template comments, write the file, run `sdd doc check`, and in shared mode commit it through a PR like any planning change (`sdd validate` must pass). In local mode it just stays in the data root.

## Revising an existing doc

Read the current doc first and show it, then ask what changed instead of re-interviewing from scratch. Edit only the sections the change touches, keep the limits, and re-run `sdd doc check`.

A changed goal or principle can invalidate planned work: after the edit, go through `sdd list` and the accepted ADRs and list the ones that no longer fit (a task serving a dropped goal, an ADR relying on a dropped principle). Report them; the user decides whether to re-plan (`sdd-planning` skill) or leave them. Don't rewrite history: an ADR that a new principle overrides gets a new ADR superseding it, not an edit.

## Who checks what

- **The agent running the interview** keeps the docs in scope and within the limits, and writes the sections.
- **`sdd doc check` / `sdd validate`**: sections present and filled, no guidance left, length. Whoever opens a PR runs it; CI, if the repo has it, can run `sdd validate` too.
- **The user** owns the content: a goal or principle the user didn't confirm doesn't go in.
- **Planning** reads both docs before designing and says in each ADR's Context which goal or principle it serves; a feature that serves no goal is raised with the user before any task is created.
- **Reviews** flag changes that break a principle or work against a non-goal, citing the line.
- **Not here**: how to verify a particular decision in a particular area belongs under that ADR or spec's `## Review checks` (`overview.md`), not in `principles.md`. A principle is a rule for every change; a check is for changes in an area.
