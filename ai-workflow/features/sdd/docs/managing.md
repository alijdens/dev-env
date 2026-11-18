# Managing the Task Data

What sessions that change the data outside a task's PR need on top of `overview.md`: planning, answering questions, maintenance and orchestration. Workers and reviewers don't read it.

## Syncing with main

In shared mode the checkout may lag behind main. `sdd stale` says whether the data root is behind `origin/main` or has uncommitted changes; `sdd stale --fix` drops the changes that already match main (the leftovers of work shipped through a worktree or pulled in by hand), fast-forwards, and keeps anything that differs. `sdd --main <command>` runs a read-only command (`ready`, `show`, `brief`, `context`, `questions`, `blockers`, `validate`, ...) against the remote main branch instead of the checkout, so a session can see what everyone merged without syncing first.

Changes to the data (a plan, an answer) reach main with `sdd ship --title "..." [--body "..."] [--merge]`: it takes the uncommitted changes under the data root, commits them on a branch from `origin/main` in a throwaway worktree, validates them, opens the PR and, with `--merge`, merges it and drops the now-redundant local copies. The checkout's branch and anything outside the data root stay as they are. A session that works in a worktree of its own writes there and never in the user's checkout: files edited in one place and committed from another are what leaves a checkout dirty and stale.

## How records change

`sdd accept <name>...` marks ADRs and rules accepted once the user agrees to them. An accepted record is the decision as it stands, in one place, and git keeps what it said before. What changes one:

- **The decision or rule changes but its intent holds** (it was worded too narrowly, a case showed it wrong, it grew): the record is edited so it states the whole decision again. `sdd validate` warns that an accepted record changed, and the user agrees to the change before it merges, as for a new record.
- **It is replaced by a different decision**: a new record with `--supersedes <old>`. The old one keeps its text and gets `superseded-by:` and status `superseded`, and `sdd brief` prints the new one in its place.
- **It recorded a detail, not a decision**: `sdd retire <name> --into <spec>`, once the spec says it. When it is outdated or says nothing the code and the specs don't, it is deleted instead: `sdd retire <name> --delete` removes the file, unlinks it from live tasks, specs, questions and ideas, and turns the links to it in other docs into their text.
- A slip (a wrong name, a stale path) is just fixed, and `## Review checks` change as reviews learn.
- Its title or its areas: `sdd set <name> --title "..." --areas <area>...`, since frontmatter isn't edited by hand. A record that turns out to be a decision of its own, not a change to the one it was said to amend, drops that relation with `sdd unlink <name> --amends <old>`.

A record in force, or one whose reasons a later reader would miss, is never deleted by hand: tasks and code comments reference it by name. Done tasks and answered questions keep a deleted record's name as history, and git keeps its text.

**No exceptions are added to a record.** A case its wording doesn't allow is settled in this order: if its Intent, or a business rule, already answers the case, follow that and change nothing; if the intent wants what the wording forbids, the wording is wrong, so the record is restated, usually as a default and the reasons to leave it in place of a prohibition and a list; if the intent itself is in doubt, that is a question for the user (`planning.md`, "Changing a record"). A record that has collected exceptions or amendments is stated at the wrong level. Older data may hold records that `--amends` another: they are read with it until a maintenance session restates it (`maintenance.md`; `sdd adrs --amended` lists them, and `sdd validate` warns).

What matters about a doc is not how long it is but what it costs across the tasks that load it: `sdd cost` lists the docs by their size times the live tasks loading them, with the median brief. A doc is split when most tasks that load it need only part of it, along who reads it: by area (a backend task shouldn't read the web's side), and by using a component versus changing it.

## Finding and linking records

`sdd rules` lists the rules in force, `sdd adrs` the ADRs by how many tasks reference them. `sdd context --area <area>... [--grep <word>...] [--path <code path>...]` prints a reading list: the foundations (ADRs referenced by a large share of tasks), the ADRs, business rules and specs matching the areas or words or cited by the code at those paths, the other business rules (all of them while there are few, a count per area past that), the tasks that used them, and the questions and ideas on them, open and closed.

`sdd link` adds links to an existing file in any state, including done tasks and accepted records: `sdd link <task> --arch <adr>... --rule <rule>... --spec <spec>...`, `sdd link <question> --task <slug>... --blocks <slug>... --arch <adr>... --rule <rule>...`, `sdd link <spec> --arch ... --rule ...`, `sdd link <adr or rule> --supersedes <old>...` (the old ones get their back-links and status as at creation). Fixing a missing link is history, not re-planning. Repeated flags accumulate (`--task a --task b` equals `--task a b`).

## Project docs

The two project docs are the context every task belongs to: planning designs features to serve `goal.md` within `principles.md`, and reviews check changes against them. They are written and revised through the interview in `project-docs.md` (`sdd-setup-task-workflow` skill), never free-form; `sdd doc list` shows whether they exist.

## Questions

`sdd blockers [--json] [--main]` lists only the open questions that are the only thing holding up work right now: a startable task (its prerequisites are done) or an in-progress task whose PR is held for the answer (marked `in-progress`, `held` in the JSON), with the work waiting behind it; `--main` reads the data as the remote main branch has it instead of the checkout. It is what the `sdd-decisions` Claude Code plugin draws above the prompt. `sdd questions --since <commit>` lists the questions added since a commit, for a run's report, and `--stale` the open ones whose linked tasks are all done, to close (`answering.md`, "Stale questions").

Who does what, beyond whoever raises a question and the reviewer (`overview.md`, "Questions"):

- **`sdd validate`** does the mechanical part: sections filled, linked tasks and ADRs exist, no done task still blocked by an open question (an in-progress one may be: its PR is held for the answer, see `orchestrating.md`). Whoever opens a PR runs it; the reviewer re-runs it.
- **The user** answers, usually in an `sdd-answer-questions` session (`answering.md`): one question at a time, in priority order, with context on request, and each answer converted into tasks or ADRs. The orchestrator in particular never answers questions.
- **The planner** changes the records an answer bears on and re-plans blocked tasks if needed.

## Ideas

- **Dependencies**: `after:` lists the tasks that must be done before the idea can be planned, since designing on code that doesn't exist yet gets redone. `sdd ideas` lists the open ones, ready to plan first (`--ready` only those, `--area` to filter, `--all` with the closed ones); `sdd dep add|rm <idea> <task>...` edits the list. Ideas wait only on tasks: an idea that needs another idea planned first is part of it.
- **Found by area**: `sdd context` lists the ideas in the areas being planned (and those linking its ADRs or matching its words), so an idea surfaces when related work is designed even if nobody remembers it. Reuse the areas in `sdd areas`; `sdd validate` warns about an open idea without any.
- **Closed by planning**: when a plan covers it, **Outcome** says what it became and `sdd close-idea <slug> --into <task|adr|rule|spec>...` moves it to `closed/`. An idea the user decides against gets the reason in Outcome and `sdd close-idea <slug>` without `--into`. Closed ideas stay as history, so `sdd context` shows a planner what was already planned or turned down.

An idea raised outside any work's PR goes to main on its own with `sdd ship`.
