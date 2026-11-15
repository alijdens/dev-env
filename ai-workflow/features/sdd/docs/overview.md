# Task Workflow

Projects that opt into the task workflow keep their architecture decisions (ADRs), business rules, tasks and task dependencies as files, so the reasoning behind the code stays reviewable later. All of it is managed through the `sdd` CLI (`sdd --help`): don't edit task frontmatter or move task files by hand, and don't walk the files to answer questions; use `sdd ready`, `sdd show`, `sdd brief`, `sdd list`, `sdd render`.

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


## ADRs, business rules, specs and finding them

These records answer what the code can't: why it is this way, and what to do in a case nobody planned. A worker who is unsure reads them before asking, so each one says what it is for, and leaves the details to the code.

- **Business rule** (`sdd rule`, `rules/`): what the product wants, in one general statement that work in any area follows: "external calendars stay in sync with ours", "an invoice is never deleted, only voided". With the first one recorded, "if a user cancels on our site, is the event in their calendar removed too?" needs no one's answer (`planning.md`, "Business rules").
- **ADR** (`sdd adr`, `arch/`): one architecture decision: what it is for (its Intent), what was chosen, the alternatives rejected and what it costs, in under 100 lines (`planning.md`, "Architecture decisions"). ADRs and business rules are the same kind of record, handled by the same commands below.
- **Spec** (`sdd spec`, `specs/`): what a component is, how its parts fit and why, linking the ADRs and rules behind it and updated by the PRs that change it. It opens with a `## Summary`: what the component is for and what others may rely on, in a few lines, which is all a task that only uses the component reads. `sdd validate` flags ADRs that read as specs (too long, no alternatives).
- **Feature spec** (`sdd spec --feature`): a planning session's agreed proposal, the target its tasks are built and reviewed against, deleted once the last one is done (`planning.md`, "Feature spec").

**A task reads as little as it needs.** A task links a spec it changes with `spec:` and gets all of it; it links a component it only depends on with `uses:` and `sdd brief` prints the Summary alone, so a task that checks a permission doesn't load how permissions are resolved. What matters is not how long a doc is but what it costs across the tasks that load it: `sdd cost` lists the docs by their size times the live tasks loading them, with the median brief. A doc is split when most tasks that load it need only part of it, along who reads it: by area (a backend task shouldn't read the web's side), and by using a component versus changing it.

None of them repeats what the code says: function, file and job names, error codes, lists of call sites, current values. Those change with every PR, and a document that names them is wrong after the next one. A record or spec keeps what stays true (the intent, the choice, the contract others rely on) and names a thing in the code only when that thing is the contract.

Records start `proposed`; `sdd accept <name>...` marks ADRs and rules accepted once the user agrees to them. An accepted record is the decision as it stands, in one place, and git keeps what it said before. What changes one:

- **The decision or rule changes but its intent holds** (it was worded too narrowly, a case showed it wrong, it grew): the record is edited so it states the whole decision again. `sdd validate` warns that an accepted record changed, and the user agrees to the change before it merges, as for a new record.
- **It is replaced by a different decision**: a new record with `--supersedes <old>`. The old one keeps its text and gets `superseded-by:` and status `superseded`, and `sdd brief` prints the new one in its place.
- **It recorded a detail, not a decision**: `sdd retire <name> --into <spec>`, once the spec says it. When it is outdated or says nothing the code and the specs don't, it is deleted instead: `sdd retire <name> --delete` removes the file, unlinks it from live tasks, specs, questions and ideas, and turns the links to it in other docs into their text.
- A slip (a wrong name, a stale path) is just fixed, and `## Review checks` (below) change as reviews learn.
- Its title or its areas: `sdd set <name> --title "..." --areas <area>...`, since frontmatter isn't edited by hand. A record that turns out to be a decision of its own, not a change to the one it was said to amend, drops that relation with `sdd unlink <name> --amends <old>`.

A record in force, or one whose reasons a later reader would miss, is never deleted by hand: tasks and code comments reference it by name. Done tasks and answered questions keep a deleted record's name as history, and git keeps its text.

**No exceptions are added to a record.** A case its wording doesn't allow is settled in this order: if its Intent, or a business rule, already answers the case, follow that and change nothing; if the intent wants what the wording forbids, the wording is wrong, so the record is restated, usually as a default and the reasons to leave it in place of a prohibition and a list; if the intent itself is in doubt, that is a question for the user (`planning.md`, "Changing a record"). A record that has collected exceptions or amendments is stated at the wrong level. Older data may hold records that `--amends` another: they are read with it until a maintenance session restates it (`maintenance.md`; `sdd adrs --amended` lists them, and `sdd validate` warns). `sdd rules` lists the rules in force, `sdd adrs` the ADRs by how many tasks reference them.

Code cites the record its shape follows from, in a one-line comment: `adr: <name>` where a reader would otherwise question the design, `rule: <name>` where the code enforces a business rule, ideally the one place every path goes through, with a test pinning it. `sdd validate` warns about citations naming a record that doesn't exist or has been superseded, so code doesn't silently keep enforcing an old rule. Local mode keeps code free of these citations (`working.md`).

ADRs, rules and specs carry `areas:` in their frontmatter, slash paths from generic to specific (`backend`, `backend/auth`, `web/forms`); `sdd areas` lists the ones in use, so reuse them instead of inventing synonyms. `sdd context --area <area>... [--grep <word>...] [--path <code path>...]` prints a reading list: the foundations (ADRs referenced by a large share of tasks), the ADRs, business rules and specs matching the areas or words or cited by the code at those paths, the other business rules (all of them while there are few, a count per area past that), the tasks that used them, and the questions and ideas on them, open and closed. `sdd link` adds links to an existing file in any state, including done tasks and accepted records, so frontmatter is never edited by hand: `sdd link <task> --arch <adr>... --rule <rule>... --spec <spec>...`, `sdd link <question> --task <slug>... --blocks <slug>... --arch <adr>... --rule <rule>...`, `sdd link <spec> --arch ... --rule ...`, `sdd link <adr or rule> --supersedes <old>...` (the old ones get their back-links and status as at creation). Fixing a missing link is history, not re-planning. Repeated flags accumulate (`--task a --task b` equals `--task a b`).

An ADR, business rule or spec may end with a `## Review checks` section: a short bullet list of project-specific things a reviewer verifies on any change in its areas ("every migration has a tested down step", "new endpoints appear in `openapi.yaml`"), each one checkable against a diff, and none that a test, a lint or a generated-file check already enforces. `sdd checks [--area <area>...] [--task <slug>]` collects them: with `--task`, the checks of the records and specs the task links, and no others; with `--area`, every check in those areas, which is what a reviewer adds for the areas a diff touches. They live next to the record or description they come from, so a rule has one home, a worker reads only the checks of what the task links, and a reviewer adds those of the areas the change touches. A check is how to verify something, not the thing itself: what must hold is stated in the record's body, and a check is added only when verifying it on a diff isn't obvious from that. It is also a test nobody has written yet: whatever a test can hold belongs in the acceptance criteria of the task that builds it ("a test fails when ..."), and from then on the suite keeps it. A standing check is for what only a reader can judge. `sdd brief` prints a task's checks, so the worker keeps them from the start; `sdd validate` warns when a section isn't a bullet list or runs past ten items. A rule that applies to every change regardless of area is a principle, not a check.

The two project docs are the context every task belongs to: planning designs features to serve `goal.md` within `principles.md`, and reviews check changes against them. They are written and revised through the interview in `project-docs.md` (`sdd-setup-task-workflow` skill), never free-form; `sdd doc list` shows whether they exist.

## Questions

Open questions raised in a conversation are forgotten by the next session, so they are files too: `sdd ask <slug> --title "..." --task <slug>... [--arch <adr>...] [--rule <rule>...] [--blocks <slug>...]` creates `questions/open/<slug>.md`, and an open question that `blocks:` a task keeps it out of `sdd ready` until it's answered, like an unmet prerequisite. `sdd questions [--task <slug>] [--arch <adr>] [--rule <rule>] [--all]` finds them; `sdd show <slug>` lists the ones linked to a task. `sdd blockers [--json] [--main]` lists only the open questions that are the only thing holding up work right now: a startable task (its prerequisites are done) or an in-progress task whose PR is held for the answer (marked `in-progress`, `held` in the JSON), with the work waiting behind it; `--main` reads the data as the remote main branch has it instead of the checkout. It is what the `sdd-decisions` Claude Code plugin draws above the prompt. `sdd questions --since <commit>` lists the questions added since a commit, for a run's report, and `--stale` the open ones whose linked tasks are all done, to close (`answering.md`, "Stale questions").

A question is read long after the conversation that raised it, by someone who wasn't there, so it must stand alone. Its file has three sections, and `sdd validate` fails while the first two are empty:

- **Question**: the actual question, with the options if there are a few.
- **Context**: what a reader needs to answer it without the conversation: where it came up (pointers into the code, the task or ADR), why it matters, what was assumed meanwhile and what that assumption cost if it turns out wrong. Every claim about what the code, a doc or a standard says points at its source (file and line, section); what is recalled rather than checked is marked so, since the reviewer and the user will act on it.
- **Answer**: empty until answered. `sdd answer <slug>` moves the file to `answered/` once it's written. If the answer changes a decision or a rule, its record is changed (`planning.md`, "Changing a record") and the answer links it.

Who does what:

- **Whoever raises it** (planner, worker or reviewer agent) writes Question and Context and links the task and ADRs, in the same PR as the work that raised it.
- **`sdd validate`** does the mechanical part: sections filled, linked tasks and ADRs exist, no done task still blocked by an open question (an in-progress one may be: its PR is held for the answer, see `orchestrating.md`). Whoever opens a PR runs it; the reviewer re-runs it.
- **The reviewer** judges what the CLI can't: whether the Context is enough to answer from, and whether the PR made assumptions it didn't record as questions.
- **The user** answers, usually in an `sdd-answer-questions` session (`answering.md`): one question at a time, in priority order, with context on request, and each answer converted into tasks or ADRs. An agent may draft an Answer from what the user says, but never decides on its own; the orchestrator in particular never answers questions.
- **The planner** changes the records an answer bears on and re-plans blocked tasks if needed.

## Ideas

An idea is something worth designing later, not now: it comes up mid-task or mid-planning, and a conversation would forget it. It is neither a tech-debt task, which is scoped and ready to build, nor a question, which is a decision waiting on the user. `sdd idea <slug> --title "..." --areas <area>... [--after <task>...] [--task <slug>...] [--arch <adr>...] [--rule <rule>...]` creates `ideas/open/<slug>.md`. Ideas are never startable: `sdd ready` and orchestrated runs never see them; planning sessions do.

- **Dependencies**: `after:` lists the tasks that must be done before the idea can be planned, since designing on code that doesn't exist yet gets redone. `sdd ideas` lists the open ones, ready to plan first (`--ready` only those, `--area` to filter, `--all` with the closed ones); `sdd dep add|rm <idea> <task>...` edits the list. Ideas wait only on tasks: an idea that needs another idea planned first is part of it.
- **Found by area**: `sdd context` lists the ideas in the areas being planned (and those linking its ADRs or matching its words), so an idea surfaces when related work is designed even if nobody remembers it. Reuse the areas in `sdd areas`; `sdd validate` warns about an open idea without any.
- **Stands alone**: like a question, it's read long after the conversation that raised it. **Idea** says what and why; **Context** says where it came up (pointers into the code, the task or ADR) and what's known so far, with sources. `sdd validate` fails while either is empty.
- **Closed by planning**: when a plan covers it, **Outcome** says what it became and `sdd close-idea <slug> --into <task|adr|rule|spec>...` moves it to `closed/`. An idea the user decides against gets the reason in Outcome and `sdd close-idea <slug>` without `--into`. Closed ideas stay as history, so `sdd context` shows a planner what was already planned or turned down.

Anyone records them: the user by asking any session, a worker or reviewer for a follow-up that needs design, a planner for what stays out of the plan's scope. The idea file rides in the PR of the work that raised it; without one, `sdd ship` sends it on its own.
