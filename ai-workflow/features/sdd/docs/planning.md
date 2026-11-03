# Task Workflow: Designing a Feature

Complements `../planning.md`: the design is still shaped as described there, from the goal to the outer shape to pseudocode and signatures that make the shape clear, but its durable output lands as a feature spec, ADRs, business rules and tasks. This is for features that break up into several smaller steps; a very small fix needs none of it, just do it.

The aim is a plan a worker can implement on its own. The core questions are settled while planning, so what comes up during implementation are details the worker records as questions without stopping the main work; a question that really blocks a task should be rare. Keep the session proportional to the feature: for a simple one, a round of context, a short proposal and a task or two.

## Start from main

Main is the only plan everyone can see; a checkout behind it shows tasks as unclaimed that someone is already implementing, and re-planning them produces two plans for the same work. So, before anything else, in shared mode:

- `sdd stale`: it fetches and fails if the data root is behind `origin/main` or has uncommitted changes. `sdd stale --fix` drops the uncommitted changes that already match main (leftovers of work shipped through a worktree) and fast-forwards; whatever it keeps is real unshipped work, to ship (`sdd ship`) or ask the user about. Don't plan on a stale view; while the checkout isn't synced, `sdd --main show|context|questions ...` read main directly.
- Before changing an existing task (its scope, prerequisites, ADRs, or splitting it), check `sdd show <slug>` and `gh pr list --search <slug> --state open`. If it's `in-progress` or has an open PR, it belongs to whoever holds it: leave it alone and plan follow-up tasks `--after` it instead. Changing what it must deliver is a scope change (see `orchestrating.md`), agreed with its owner and merged to main before they continue.

In local mode the data isn't shared, so there's nothing to sync.

## Pick what to plan

When the user names no feature, don't assume one: ask whether to plan something new or pick up a recorded idea (`overview.md`, "Ideas"). For an idea, list `sdd ideas --ready` grouped by area, a line each, and say in one line how many more wait on unfinished tasks (`sdd ideas`); one of those is planned only if the user insists, after saying what it waits on. The picked idea's Idea and Context are the feature description, and its areas, tasks and ADRs seed the search below.

## Understand, then load context

What to search for depends on what the feature is, and what is read changes what the feature turns out to be:

1. **Understand.** In a few lines: what the feature does and for whom, which goal in `goal.md` it serves, the components and files it likely changes (a look at the repo layout), the areas it touches (from `sdd areas`, not invented), and its key words. If it serves no goal, or works against a non-goal, raise that with the user before going further.
2. **Search.** `sdd context --area <areas> [--grep <words>] [--path <files or dirs>]` lists the foundation ADRs; the ADRs, business rules and specs in those areas, matching those words, or cited in `adr:`/`rule:` comments by the code at those paths (in-repo data only: local mode keeps the code free of them); the business rules of other areas, since a feature may have to keep a rule set elsewhere; the tasks that used them (done ones show what exists, in-progress ones what is being built); and the questions and ideas on them. Add the ready tech-debt tasks that touch the same code (`sdd ready`): the feature may absorb or obsolete them. A long reading list is shown to the user in a few lines first, to add or drop items; a short one is just read and named in the proposal. Read ADRs, rules and specs in full, done tasks' Goal and Notes, answered questions' Answer (they often carry requirements), open questions so they aren't asked twice, open ideas the feature may cover, closed ones so a dropped idea isn't proposed again without its reason; and the code the feature will change.
3. **Refine.** Correct the understanding with what was read. When it points at more (an ADR cited by one just read, a component the feature turns out to touch), search once more and name each addition in a line. Ask the questions that would change the design as they come up; for the rest, state what you assume.

## Propose

One proposal, sized to the feature, agreed with the user before any file is written:

- **Goal and behaviour**: what the feature does from the user's side, with a few concrete examples (a command and its output, a request and its response).
- **Shape**: the new and changed components and how they fit into the existing code: interfaces, signatures, data layout, and pseudocode where it makes an idea clear without being the implementation; a Mermaid diagram when several components interact.
- **Rules**: what must stay true from now on, so later changes keep it. Look for them on purpose, since a rule nobody stated is what surfaces later as a mid-implementation question or a review finding: product rules (limits, eligibility, what may never happen to the data), contracts others rely on (formats, compatibility), trust boundaries, error behaviour, how the component is documented, what it deliberately won't do. List both the rules the feature introduces and the existing ones it must keep (the business rules `sdd context` listed, from any area). Each says where it comes from (the goal, a principle, an ADR, a convention in the code) or that it needs the user's call, and where it lands: a product rule is a business rule (see "Business rules"), a rule that follows from an architecture choice is stated in that ADR, a convention with no choice behind it is a review check in the component's spec.
- **Decisions**: which choices become ADRs (see "Architecture decisions").
- **Tasks**: each with its goal, what it delivers to the tasks after it, its prerequisites and a rough size; then the open questions and what is assumed meanwhile.

If writing the files turns up something that changes what was agreed (a task that has to split, a rule that needs the user's call), take it back to the user before shipping.

## Feature spec

After the session, the agreed proposal is the feature's guideline: a worker settles from it what its task leaves open, and a reviewer checks the PR against it. It is kept as a spec, `sdd spec <feature> --feature --title "..." --areas <every area it governs> --arch <adr>... --rule <rule>...`, with:

- **Goal**: what the feature is for and for whom, in a few lines.
- **How it works**: the behaviour from the user's side, with the examples.
- **Shape**: what the feature adds (new components, interfaces, pseudocode and diagram), at the level of the proposal. A component that already has its own spec isn't described again: the Shape points at it, and the tasks that change the component update that spec, so each component keeps one description.
Business rules and ADRs are records of their own, linked from the spec (`--rule`, `--arch`). Every task of the feature links it (`--spec`), so `sdd brief` prints it to the worker. It describes the target until the last task is done, and isn't kept current after that: what lasts lives in component specs, ADRs and business rules. A feature that fits in one task and introduces no rule needs no spec: the task's Goal and Notes hold it.

## Architecture decisions

Write an ADR only for decisions that are hard to reverse, span several components, constrain future work, or pick between real alternatives (storage, protocols, module boundaries, key libraries, infrastructure). Most large features and infra changes have some; a small change or a choice that is local to a task and obvious from its code doesn't. A description of how something is, with nothing rejected (a data model, an API's conventions), is a spec, not an ADR: `sdd spec`, linking the ADRs that shaped it.

- `sdd adr <slug> --title "..." --areas <area>... [--amends <adr>...] [--supersedes <adr>...]` creates `arch/<today>-<slug>.md` with sections: Context, Decision, Alternatives considered, Consequences. Status starts as `proposed`; set it to `accepted` when the plan is agreed.
- The title names the component and the decision ("Rate limits stored in Redis per API key"), not the feature ("Rate limiting"), since titles are what `sdd context` and readers scan.
- Keep them short and durable (see `../documentation.md`): the problem, the decision, the rejected options and why, and what it costs. Under 100 lines; `sdd validate` warns past that while the ADR is proposed (once accepted the body is history, so the warning would never go away).
- Once accepted, an ADR is history (see `overview.md`): a factual slip gets an Errata line, a changed decision gets a new ADR that `--amends` (part of it) or `--supersedes` (all of it) the old one. Don't edit or delete the old text.
- A rule the decision imposes on later changes ("the CLI's `--help` is its only documentation") is stated in its Decision or Consequences, which can't change once the ADR is accepted. When reviewers need something concrete to verify it on every later change in its areas, add that under `## Review checks` (see `overview.md`): checks may grow as reviews learn, the rule doesn't. A rule that would apply to every change is a principle to raise with the user, not a check.

## Business rules

A product rule the code must keep whatever feature touches it is a business rule, not an ADR: "a user posts at most 3 pictures a day", "an invoice is never deleted, only voided". It outlives the feature that introduced it, and a later feature in another area must keep it too.

- `sdd rule <slug> --title "..." --areas <area>... [--amends <rule>...] [--supersedes <rule>...]` creates `rules/<today>-<slug>.md` with sections: Rule (what must hold, stated so a reader can tell whether code keeps it), Why, and Alternatives considered when there were real ones. The title is the rule itself ("Users post at most 3 pictures a day"), since titles are what `sdd context` lists.
- Like an ADR, it starts `proposed`, is accepted with the plan, and is history once accepted: a changed rule, the value included, is a new rule that `--supersedes` the old one.
- Every task that enforces it or must keep it links it (`--rule`), so `sdd brief` shows it to the worker. Suggest, in the task's Notes, enforcing it in one place every path goes through, with a test that pins it, and citing it there (`rule: <name>`); that's good practice, not a requirement.

## Tasks

- One task is one reviewable PR that leaves main working. Size it against the target in `../pull-requests.md`, as a best effort: an implementer splits a task only along a cut the feature spec, rules and ADRs already draw (`working.md`), and stops with a question otherwise, so a task planned too big costs a split or a round trip to the user.
- `sdd new <slug> --title "..." [--after <prereq>...] [--arch <adr>...] [--rule <rule>...] [--spec <spec>...] [--tech-debt] [--needs user|secret|...]` creates the file with its prerequisites, ADRs, business rules and specs in the frontmatter. ADRs and rules are referenced by file name without `.md` (e.g. `2026-10-12-rate-limit-strategy`). `--needs` marks a task an agent can't do alone (a live run against a real account, a credential only the user has): `sdd ready` shows it and orchestrated runs leave it to the user.
- Fill in the template: **Goal** (what and why, in a few lines), **Acceptance criteria** (verifiable), **Notes** (constraints, pointers into the code, anything an implementer needs that isn't in the ADRs and the feature spec). A task plus its ADRs and specs must be enough context to implement it without the planning conversation.
- `arch:` lists every ADR that constrains the task, including older ones the plan didn't write, `rules:` every business rule it enforces or must keep, and `spec:` every spec it implements or changes, the feature spec included; a worker reads only what's linked. The Notes name what each prerequisite delivered that the task builds on (the interface, where the code is), or point at the done task, and what this task must deliver to its dependents: a shape the next task can't use is rework.
- `sdd rm <slug>` deletes a planned task nothing depends on.

## Dependencies

- Add a dependency only when a task genuinely can't start without another one being merged (it needs its code, schema or interface). Preferred ordering is not a dependency: every extra edge reduces how much can run in parallel. But a required order is one: "run the smoke test before its dependents start" is `after:` on the dependents, never a sentence in Notes, which a worker reads only after claiming and an orchestrator never does.
- `sdd dep add <task> <prereq>...` / `sdd dep rm <task> <prereq>...` edit the task's `after:` list. The CLI rejects cycles.

## Open questions

`../planning.md` asks for open questions and assumptions to be listed instead of guessed. Here they become files (`sdd ask`, see `overview.md`), so they survive the planning conversation:

- Ask the user the questions that shape the design while understanding and proposing; record the ones that stay open.
- A question that a task can't be implemented without gets `--blocks <task>`; the rest just link the tasks, ADRs and rules they concern (`--task`, `--arch`, `--rule`) and the task's Notes say what to assume meanwhile.
- `sdd questions` before planning: answered questions may already settle a design point, and open ones on related ADRs shouldn't be asked twice.
- Answers that change a decision or a rule become a new ADR or business rule, and tasks that depended on the old one are re-planned. Until that happens each such task is held with a blocking question (`sdd ask replan-<slug> --title "Re-plan <slug> after <record>" --blocks <slug> --arch <adr>` or `--rule <rule>`), so `sdd ready` leaves it out; re-planning it answers the question. A note in the task file holds nothing: workers find it only after claiming.

## Ideas

- Ask the user whether the plan should cover the open ideas in its areas; those it covers are closed with it.
- A covered idea gets its Outcome (what it became, in a line or two) and `sdd close-idea <slug> --into <tasks, ADRs, rules and the feature spec>`. One the user decides against gets the reason as Outcome and `sdd close-idea <slug>`. Only the user drops an idea.
- What comes up but stays out of the plan's scope is recorded with `sdd idea` instead of growing the plan, with `--after` the tasks it must wait for.

## Steps

1. Read `goal.md` and `principles.md` if they exist (`sdd doc list`). Understand the feature and load its context, then propose (above). Every design choice stays within the principles; wanting to break one is a question for the user, not a decision.
2. Once the user agrees, write the feature spec (`sdd spec --feature`, when the feature needs one), each ADR (`sdd adr`) and each business rule (`sdd rule`). An ADR's Context, or a rule's Why, names the goal or principle it follows from, when there is one, so a reader can tell a forced choice from a free one.
3. Create the tasks with `sdd new`, linking their ADRs, business rules, the feature spec and their prerequisites, and fill them in.
4. Record the open questions with `sdd ask` and fill in their Question and Context sections. Close the ideas the plan covers and record the ones it leaves out (see "Ideas").
5. Run `sdd validate` (frontmatter, prerequisites exist and form a DAG, ADR and question references exist, questions and ideas filled in). For a visual review: `sdd render | dot -Tsvg > graph.svg`.
6. In shared mode, the planning changes must be merged to main before any of the tasks is started: main is what claims are checked against. Once the user agrees to the plan, `sdd accept <name>...` the new ADRs and business rules and `sdd ship --title "Plan <feature>" --body "..." --merge` (without `--merge` when the user wants to read the PR first; the body follows `../pull-requests.md`). In local mode, the files are simply there.

Re-planning later (splitting a task, changing dependencies) follows the same steps, including going to main first in shared mode.
