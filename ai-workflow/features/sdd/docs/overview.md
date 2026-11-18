# Task Workflow

Projects that opt into the task workflow keep their architecture decisions (ADRs), business rules, tasks and task dependencies as files, so the reasoning behind the code stays reviewable later. All of it is managed through the `sdd` CLI (`sdd --help`): don't edit task frontmatter or move task files by hand, and don't walk the files to answer questions; use `sdd ready`, `sdd show`, `sdd brief`, `sdd list`, `sdd render`.

If `sdd root` fails, the project doesn't use the workflow: say so and stop instead of improvising a layout (setting it up is the `sdd-setup-task-workflow` skill).

This doc is what every session needs. Sessions that plan, answer questions, maintain the data or orchestrate also read `managing.md`: syncing with main, how records change, and the lifecycle of questions and ideas.

## Data root and modes

`sdd root` prints the data root and the mode, or fails if the project isn't set up:

- **shared**: the repo's `AGENTS.md`/`CLAUDE.md` has a `sdd: <path>` line. The data lives in the repo (usually `docs/`), or in a separate repo the path points to. Claims, releases and planning changes go through PRs against main.
- **local**: the clone's git config has `sdd.root`. For repos you don't own: the data stays on this machine, claims and releases are plain file moves, and code, commits and PRs never mention task slugs, ADRs or the workflow.

`sdd --dir <path> <command>` uses the data at `<path>` instead of the repo's configuration (shared if `<path>` is inside a git repo, local otherwise). When working against such a directory, pass `--dir` on every `sdd` command.

In shared mode the checkout may lag behind main, and a change to the data that isn't part of a task's PR reaches main with `sdd ship` (`managing.md`, "Syncing with main").

## Layout

```
goal.md                                  why the project exists, for whom, what it won't do (optional)
principles.md                            what every change must respect (optional)
arch/2026-10-12-rate-limit-strategy.md   architecture decision records (ADRs): what was chosen, what for, and what was rejected
rules/2026-10-12-calendars-in-sync.md    business rules: what the product wants, stated so it answers the questions later work runs into
specs/data-model.md                      what a component (or a planned feature) is and why, above the level of the code, updated by the PRs that change it
tasks/todo/<slug>.md                     planned
tasks/tech-debt/<slug>.md                known shortcuts / follow-ups, startable like todo
tasks/in-progress/<slug>.md              claimed by someone
tasks/done/2026-10-14/<slug>.md          history, grouped by the date `sdd done` ran
questions/open/<slug>.md                 open questions, linked to the tasks and ADRs they concern
questions/answered/<slug>.md             answered, kept as history
ideas/open/<slug>.md                     ideas waiting for a planning session, by area
ideas/closed/<slug>.md                   planned or dropped, kept as history
```

A task's state is the directory its file is in, and its prerequisites are the `after: [...]` list in its frontmatter (`after: [a]` on `b`: `a` must be done before `b` starts), so each task is one self-contained file and branches that add or finish different tasks merge cleanly. A task that needs something an agent can't provide on its own (a credential, the user's go-ahead for a live run, access to an external system) says so in `needs: [...]` (`sdd new --needs user secret ...`); `sdd ready` prints it in its last column, `sdd show` as a line, and orchestrated runs skip such tasks unless asked for them. `sdd ready --for <slug>` lists only that slug and the ready tasks it waits on, longest chain to it first, and prints to stderr what else holds it up (open questions, `needs`, work in progress). `sdd new` can't create a dependency cycle and `sdd dep add` rejects one; one can still come from a hand edit or from two branches whose dependencies only form a cycle once both merge, which `sdd validate` fails on and `sdd ready` warns about. `sdd render` derives the dependency graph; done tasks keep their `after:` as history. Slugs are kebab-case and unique across all states; the slug is also the task's branch name and, in shared mode, how code refers to it.

A file's relative links (`[x](../../arch/<adr>.md)`) are rewritten when `sdd` moves it, but a link to a task or question goes stale once that one moves; `sdd validate` warns about links that don't resolve, and naming a task or question beats linking its path.


## ADRs, business rules and specs

These records answer what the code can't: why it is this way, and what to do in a case nobody planned. A worker who is unsure reads them before asking, so each one says what it is for, and leaves the details to the code.

- **Business rule** (`sdd rule`, `rules/`): what the product wants, in one general statement that work in any area follows: "external calendars stay in sync with ours", "an invoice is never deleted, only voided". With the first one recorded, "if a user cancels on our site, is the event in their calendar removed too?" needs no one's answer (`planning.md`, "Business rules").
- **ADR** (`sdd adr`, `arch/`): one architecture decision: what it is for (its Intent), what was chosen, the alternatives rejected and what it costs, in under 100 lines (`planning.md`, "Architecture decisions"). ADRs and business rules are the same kind of record, handled by the same commands.
- **Spec** (`sdd spec`, `specs/`): what a component is, how its parts fit and why, linking the ADRs and rules behind it and updated by the PRs that change it. It opens with a `## Summary`: what the component is for and what others may rely on, in a few lines, which is all a task that only uses the component reads. `sdd validate` flags ADRs that read as specs (too long, no alternatives).
- **Feature spec** (`sdd spec --feature`): a planning session's agreed proposal, the target its tasks are built and reviewed against, deleted once the last one is done (`planning.md`, "Feature spec").

A task links a spec it changes with `spec:` and gets all of it; it links a component it only depends on with `uses:` and `sdd brief` prints the Summary alone, so a task that checks a permission doesn't load how permissions are resolved.

None of them repeats what the code says: function, file and job names, error codes, lists of call sites, current values. Those change with every PR, and a document that names them is wrong after the next one. A record or spec keeps what stays true (the intent, the choice, the contract others rely on) and names a thing in the code only when that thing is the contract.

Records start `proposed` and are accepted once the user agrees to them. An accepted record is the decision as it stands, in one place: no exceptions or amendments are added to it, and a case its wording doesn't fit goes through `planning.md`, "Changing a record" (how records change: `managing.md`).

Code cites the record its shape follows from, in a one-line comment: `adr: <name>` where a reader would otherwise question the design, `rule: <name>` where the code enforces a business rule, ideally the one place every path goes through, with a test pinning it. `sdd validate` warns about citations naming a record that doesn't exist or has been superseded, so code doesn't silently keep enforcing an old rule. Local mode keeps code free of these citations (`working.md`).

ADRs, rules and specs carry `areas:` in their frontmatter, slash paths from generic to specific (`backend`, `backend/auth`, `web/forms`); `sdd areas` lists the ones in use, so reuse them instead of inventing synonyms. `sdd context` finds the records for areas, words or code paths, and `sdd link` adds links to an existing file in any state, so frontmatter is never edited by hand (`managing.md`, "Finding and linking records").

An ADR, business rule or spec may end with a `## Review checks` section: a short bullet list of project-specific things a reviewer verifies on any change in its areas ("every migration has a tested down step", "new endpoints appear in `openapi.yaml`"), each one checkable against a diff, and none that a test, a lint or a generated-file check already enforces. `sdd checks [--area <area>...] [--task <slug>]` collects them: with `--task`, the checks of the records and specs the task links, and no others; with `--area`, every check in those areas, which is what a reviewer adds for the areas a diff touches. They live next to the record or description they come from, so a rule has one home, a worker reads only the checks of what the task links, and a reviewer adds those of the areas the change touches. A check is how to verify something, not the thing itself: what must hold is stated in the record's body, and a check is added only when verifying it on a diff isn't obvious from that. It is also a test nobody has written yet: whatever a test can hold belongs in the acceptance criteria of the task that builds it ("a test fails when ..."), and from then on the suite keeps it. A standing check is for what only a reader can judge. `sdd brief` prints a task's checks, so the worker keeps them from the start; `sdd validate` warns when a section isn't a bullet list or runs past ten items. A rule that applies to every change regardless of area is a principle, not a check.

## Questions

Open questions raised in a conversation are forgotten by the next session, so they are files too: `sdd ask <slug> --title "..." --task <slug>... [--arch <adr>...] [--rule <rule>...] [--blocks <slug>...]` creates `questions/open/<slug>.md`, and an open question that `blocks:` a task keeps it out of `sdd ready` until it's answered, like an unmet prerequisite. `sdd show <slug>` lists the ones linked to a task; `sdd questions [--task <slug>] [--arch <adr>] [--rule <rule>] [--all]` finds them.

A question is read long after the conversation that raised it, by someone who wasn't there, so it must stand alone. Its file has three sections, and `sdd validate` fails while the first two are empty:

- **Question**: the actual question, with the options if there are a few.
- **Context**: what a reader needs to answer it without the conversation: where it came up (pointers into the code, the task or ADR), why it matters, what was assumed meanwhile and what that assumption cost if it turns out wrong. Every claim about what the code, a doc or a standard says points at its source (file and line, section); what is recalled rather than checked is marked so, since the reviewer and the user will act on it.
- **Answer**: empty until answered. `sdd answer <slug>` moves the file to `answered/` once it's written. If the answer changes a decision or a rule, its record is changed (`planning.md`, "Changing a record") and the answer links it.

Whoever raises a question (planner, worker or reviewer agent) writes Question and Context and links the task and ADRs, in the same PR as the work that raised it. The reviewer judges whether the Context is enough to answer from, and whether the PR made assumptions it didn't record as questions. Only the user answers; an agent may draft an Answer from what the user says, but never decides on its own (the rest of who does what: `managing.md`, "Questions").

## Ideas

An idea is something worth designing later, not now: it comes up mid-task or mid-planning, and a conversation would forget it. It is neither a tech-debt task, which is scoped and ready to build, nor a question, which is a decision waiting on the user. `sdd idea <slug> --title "..." --areas <area>... [--after <task>...] [--task <slug>...] [--arch <adr>...] [--rule <rule>...]` creates `ideas/open/<slug>.md`, with `--after` naming the tasks that must be done before it can be planned. Ideas are never startable: `sdd ready` and orchestrated runs never see them; planning sessions do (`managing.md`, "Ideas").

Like a question, it's read long after the conversation that raised it. **Idea** says what and why; **Context** says where it came up (pointers into the code, the task or ADR) and what's known so far, with sources. `sdd validate` fails while either is empty.

Anyone records them: the user by asking any session, a worker or reviewer for a follow-up that needs design, a planner for what stays out of the plan's scope. The idea file rides in the PR of the work that raised it.
