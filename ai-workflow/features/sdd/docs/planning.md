# Task Workflow: Designing a Feature

Complements `../planning.md`: the design is still shaped as described there, but its durable output lands as ADRs and tasks. This is for features that break up into several smaller steps; a very small fix needs neither, just do it.

## Start from main

Main is the only plan everyone can see; a checkout behind it shows tasks as unclaimed that someone is already implementing, and re-planning them produces two plans for the same work. So, before anything else, in shared mode:

- `sdd stale`: it fetches and fails if the data root is behind `origin/main` or has uncommitted changes. `sdd stale --fix` drops the uncommitted changes that already match main (leftovers of work shipped through a worktree) and fast-forwards; whatever it keeps is real unshipped work, to ship (`sdd ship`) or ask the user about. Don't plan on a stale view; while the checkout isn't synced, `sdd --main show|context|questions ...` read main directly.
- Before changing an existing task (its scope, prerequisites, ADRs, or splitting it), check `sdd show <slug>` and `gh pr list --search <slug> --state open`. If it's `in-progress` or has an open PR, it belongs to whoever holds it: leave it alone and plan follow-up tasks `--after` it instead. Changing what it must deliver is a scope change (see `orchestrating.md`), agreed with its owner and merged to main before they continue.

In local mode the data isn't shared, so there's nothing to sync.

## Load context

A feature is designed on top of what was already decided and built, so before designing:

1. Name the areas the feature touches (`sdd areas` lists the ones in use; pick from the goal's glossary and the feature description) and run `sdd context --area <areas> [--grep <key words>]`. It lists the foundation ADRs, the ADRs and specs in those areas, the tasks that used them (done ones show what already exists, in-progress ones what is being built) and the questions on them.
2. Show the user the list in a few lines as the proposed reading, and let them add or drop items. Then read what's left: ADRs and specs in full, done tasks' Goal and Notes, answered questions' Answer (they often carry requirements), open questions so they aren't asked twice.
3. Include ready tech-debt tasks in those areas (`sdd ready`): the feature may absorb or obsolete them.

Say in one or two lines what prior decisions and work the design builds on before proposing anything.

## Architecture decisions

Write an ADR only for decisions that are hard to reverse, span several components, constrain future work, or pick between real alternatives (storage, protocols, module boundaries, key libraries, infrastructure). Most large features and infra changes have some; a small change or a choice that is local to a task and obvious from its code doesn't. A description of how something is, with nothing rejected (a data model, an API's conventions), is a spec, not an ADR: `sdd spec`, linking the ADRs that shaped it.

- `sdd adr <slug> --title "..." --areas <area>... [--amends <adr>...] [--supersedes <adr>...]` creates `arch/<today>-<slug>.md` with sections: Context, Decision, Alternatives considered, Consequences. Status starts as `proposed`; set it to `accepted` when the plan is agreed.
- The title names the component and the decision ("Rate limits stored in Redis per API key"), not the feature ("Rate limiting"), since titles are what `sdd context` and readers scan.
- Keep them short and durable (see `../documentation.md`): the problem, the decision, the rejected options and why, and what it costs. Under 100 lines; `sdd validate` warns past that.
- Once accepted, an ADR is history (see `overview.md`): a factual slip gets an Errata line, a changed decision gets a new ADR that `--amends` (part of it) or `--supersedes` (all of it) the old one. Don't edit or delete the old text.
- When a decision gives reviewers something to verify on every later change in its areas that they couldn't infer from the decision itself (a test every migration needs, a file every endpoint must update), add it as a bullet under `## Review checks` (see `overview.md`). Most ADRs have none; a rule that would apply to every change is a principle to raise with the user, not a check.

## Tasks

- One task is one reviewable PR that leaves main working (see the size target in `../pull-requests.md`). Split anything bigger.
- `sdd new <slug> --title "..." [--after <prereq>...] [--arch <adr>...] [--tech-debt]` creates the file with its prerequisites and ADRs in the frontmatter. ADRs are referenced by file name without `.md` (e.g. `2026-10-12-rate-limit-strategy`).
- Fill in the template: **Goal** (what and why, in a few lines), **Acceptance criteria** (verifiable), **Notes** (constraints, pointers into the code, anything an implementer needs that isn't in the ADRs). A task plus its ADRs and specs must be enough context to implement it without the planning conversation.
- `arch:` lists every ADR that constrains the task, including older ones the plan didn't write, and `--spec` every spec it implements or changes; a worker reads only what's linked. The Notes name what each prerequisite delivered that the task builds on (the interface, where the code is), or point at the done task.
- `sdd rm <slug>` deletes a planned task nothing depends on.

## Dependencies

- Add a dependency only when a task genuinely can't start without another one being merged (it needs its code, schema or interface). Preferred ordering is not a dependency: every extra edge reduces how much can run in parallel.
- `sdd dep add <task> <prereq>...` / `sdd dep rm <task> <prereq>...` edit the task's `after:` list. The CLI rejects cycles.

## Open questions

`../planning.md` asks for open questions and assumptions to be listed instead of guessed. Here they become files (`sdd ask`, see `overview.md`), so they survive the planning conversation:

- Ask the user the questions that shape the design before writing ADRs; record the ones that stay open.
- A question that a task can't be implemented without gets `--blocks <task>`; the rest just link the tasks and ADRs they concern (`--task`, `--arch`) and the task's Notes say what to assume meanwhile.
- `sdd questions` before planning: answered questions may already settle a design point, and open ones on related ADRs shouldn't be asked twice.
- Answers that change a decision become a new ADR, and tasks that depended on the old one are re-planned. Until that happens each such task is held with a blocking question (`sdd ask replan-<slug> --title "Re-plan <slug> after <adr>" --blocks <slug> --arch <adr>`), so `sdd ready` leaves it out; re-planning it answers the question. A note in the task file holds nothing: workers find it only after claiming.

## Steps

1. Read `goal.md` and `principles.md` if they exist (`sdd doc list`), then design the feature following `../planning.md`. Say in one line which goal the feature serves; if it serves none, or works against a non-goal, raise that with the user before going further. Every design choice stays within the principles; wanting to break one is a question for the user, not a decision.
2. Record each important decision with `sdd adr` and fill it in. Its Context names the goal or principle it follows from, when there is one, so a reader can tell a forced choice from a free one. Add `## Review checks` only for what reviewers of later changes must verify.
3. Create the tasks with `sdd new`, referencing their ADRs and prerequisites, and fill them in.
4. Record the open questions with `sdd ask` and fill in their Question and Context sections.
5. Run `sdd validate` (frontmatter, prerequisites exist and form a DAG, ADR and question references exist, questions filled in). For a visual review: `sdd render | dot -Tsvg > graph.svg`.
6. In shared mode, the planning changes must be merged to main before any of the tasks is started: main is what claims are checked against. Once the user agrees to the plan, `sdd accept <adr>...` the new decisions and `sdd ship --title "Plan <feature>" --body "..." --merge` (without `--merge` when the user wants to read the PR first; the body follows `../pull-requests.md`). In local mode, the files are simply there.

Re-planning later (splitting a task, changing dependencies) follows the same steps, including going to main first in shared mode.
