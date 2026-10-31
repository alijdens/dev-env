# Task Workflow

Projects that opt into the task workflow keep their architecture decisions (ADRs), tasks and task dependencies as files, so the reasoning behind the code stays reviewable later. All of it is managed through the `sdd` CLI (`sdd --help`): don't edit task frontmatter or move task files by hand, and don't walk the files to answer questions; use `sdd ready`, `sdd show`, `sdd brief`, `sdd list`, `sdd render`.

If `sdd root` fails, the project doesn't use the workflow: say so and stop instead of improvising a layout (setting it up is the `sdd-setup-task-workflow` skill).

## Data root and modes

`sdd root` prints the data root and the mode, or fails if the project isn't set up:

- **shared**: the repo's `AGENTS.md`/`CLAUDE.md` has a `sdd: <path>` line. The data lives in the repo (usually `docs/`), or in a separate repo the path points to. Claims, releases and planning changes go through PRs against main.
- **local**: the clone's git config has `sdd.root`. For repos you don't own: the data stays on this machine, claims and releases are plain file moves, and code, commits and PRs never mention task slugs, ADRs or the workflow.

`sdd --dir <path> <command>` uses the data at `<path>` instead of the repo's configuration (shared if `<path>` is inside a git repo, local otherwise). When working against such a directory, pass `--dir` on every `sdd` command.

In shared mode the checkout may lag behind main. `sdd stale` says whether the data root is behind `origin/main` or has uncommitted changes; `sdd stale --fix` drops the changes that already match main (the leftovers of work shipped through a worktree or pulled in by hand), fast-forwards, and keeps anything that differs. `sdd --main <command>` runs a read-only command (`ready`, `show`, `brief`, `context`, `questions`, `blockers`, `validate`, ...) against the remote main branch instead of the checkout, so a session can see what everyone merged without syncing first.

Changes to the data (a plan, an answer) reach main with `sdd ship --title "..." [--body "..."] [--merge]`: it takes the uncommitted changes under the data root, commits them on a branch from `origin/main` in a throwaway worktree, validates them, opens the PR and, with `--merge`, merges it and drops the now-redundant local copies. The checkout's branch and anything outside the data root stay as they are. A session that works in a worktree of its own writes there and never in the user's checkout: files edited in one place and committed from another are what leaves a checkout dirty and stale.

## Layout

```
goal.md                                  why the project exists, for whom, what it won't do (optional)
principles.md                            the rules every change must respect (optional)
arch/2026-10-12-rate-limit-strategy.md   architecture decision records (ADRs): the why, immutable once accepted
specs/data-model.md                      living descriptions of how things are, updated by the PRs that change them
tasks/todo/<slug>.md                     planned
tasks/tech-debt/<slug>.md                known shortcuts / follow-ups, startable like todo
tasks/in-progress/<slug>.md              claimed by someone
tasks/done/2026-10-14/<slug>.md          history, grouped by the date `sdd done` ran
questions/open/<slug>.md                 open questions, linked to the tasks and ADRs they concern
questions/answered/<slug>.md             answered, kept as history
```

A task's state is the directory its file is in, and its prerequisites are the `after: [...]` list in its frontmatter (`after: [a]` on `b`: `a` must be done before `b` starts), so each task is one self-contained file and branches that add or finish different tasks merge cleanly. `sdd render` derives the dependency graph; done tasks keep their `after:` as history. Slugs are kebab-case and unique across all states; the slug is also the task's branch name and, in shared mode, how code refers to it.


## ADRs, specs and finding them

An ADR records one decision: context, the decision, the alternatives rejected and the consequences, in under 100 lines. A description of how something currently is (the data model, API conventions, a module's shape) is a **spec** (`sdd spec <slug> --title "..." --areas ... --arch <adr>...`): it lives in `specs/`, links the ADRs behind it, and the PRs that change the thing update it. `sdd validate` flags ADRs that read as specs (too long, no alternatives).

Status starts as `proposed`; `sdd accept <adr>...` marks the decisions accepted once the plan is agreed. Once accepted, an ADR's body is history and `sdd validate` fails if it changes. What may change:

- While `proposed`: anything.
- A factual correction (a wrong variable name, a stale path): a dated line under a `## Errata` section at the end.
- Its `## Review checks` (below): how to verify the decision holds may grow as reviews learn, the decision doesn't.
- The decision itself, partly or entirely: a new ADR with `--amends <old>` or `--supersedes <old>`. The old one keeps its text and gets `amended-by:` / `superseded-by:` in its frontmatter (and status `superseded` when replaced), so readers are pointed forward. Never delete an ADR: tasks, code comments and PRs reference it by name.

ADRs and specs carry `areas:` in their frontmatter, slash paths from generic to specific (`backend`, `backend/auth`, `web/forms`); `sdd areas` lists the ones in use, so reuse them instead of inventing synonyms. `sdd context --area <area>... [--grep <word>...]` prints a reading list: the foundations (ADRs referenced by a large share of tasks), the ADRs and specs matching the areas or words, the tasks that used them and the questions on them, open and answered. `sdd adrs [--area ...]` lists ADRs by how many tasks reference them. `sdd link <slug> --arch <adr>... --spec <spec>...` adds links to a task in any state, including done ones: fixing a missing link is history, not re-planning.

An ADR or spec may end with a `## Review checks` section: a short bullet list of project-specific things a reviewer verifies on any change in its areas ("every migration has a tested down step", "new endpoints appear in `openapi.yaml`"), each one checkable against a diff. `sdd checks [--area <area>...] [--task <slug>]` collects them: with `--task`, the checks of the task's ADRs and specs and of everything in their areas. They live next to the decision or description they come from, so a rule has one home and a reviewer reads only the checks for the areas a change touches; `sdd validate` warns when a section isn't a bullet list or runs past ten items. A rule that applies to every change regardless of area is a principle, not a check.

The two project docs are the context every task belongs to: planning designs features to serve `goal.md` within `principles.md`, and reviews check changes against them. They are written and revised through the interview in `project-docs.md` (`sdd-setup-task-workflow` skill), never free-form; `sdd doc list` shows whether they exist.

## Questions

Open questions raised in a conversation are forgotten by the next session, so they are files too: `sdd ask <slug> --title "..." --task <slug>... [--arch <adr>...] [--blocks <slug>...]` creates `questions/open/<slug>.md`, and an open question that `blocks:` a task keeps it out of `sdd ready` until it's answered, like an unmet prerequisite. `sdd questions [--task <slug>] [--arch <adr>] [--all]` finds them; `sdd show <slug>` lists the ones linked to a task. `sdd blockers [--json] [--main]` lists only the open questions that are the only thing holding up a startable task (its prerequisites are done), with the work waiting behind it; `--main` reads the data as the remote main branch has it instead of the checkout. It is what the `sdd-decisions` Claude Code plugin draws above the prompt.

A question is read long after the conversation that raised it, by someone who wasn't there, so it must stand alone. Its file has three sections, and `sdd validate` fails while the first two are empty:

- **Question**: the actual question, with the options if there are a few.
- **Context**: what a reader needs to answer it without the conversation: where it came up (pointers into the code, the task or ADR), why it matters, what was assumed meanwhile and what that assumption cost if it turns out wrong.
- **Answer**: empty until answered. `sdd answer <slug>` moves the file to `answered/` once it's written. If the answer changes a decision, it goes into a new ADR and the answer links it.

Who does what:

- **Whoever raises it** (planner, worker or reviewer agent) writes Question and Context and links the task and ADRs, in the same PR as the work that raised it.
- **`sdd validate`** does the mechanical part: sections filled, linked tasks and ADRs exist, open questions still blocking claimed tasks. Whoever opens a PR runs it; the reviewer re-runs it.
- **The reviewer** judges what the CLI can't: whether the Context is enough to answer from, and whether the PR made assumptions it didn't record as questions.
- **The user** answers, usually in an `sdd-answer-questions` session (`answering.md`): one question at a time, in priority order, with context on request, and each answer converted into tasks or ADRs. An agent may draft an Answer from what the user says, but never decides on its own; the orchestrator in particular never answers questions.
- **The planner** turns answers that change a decision into ADRs and re-plans blocked tasks if needed.
