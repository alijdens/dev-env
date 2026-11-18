# Task Workflow: Designing a Feature

Complements `../planning.md`: the design is still shaped as described there, from the goal to the outer shape to pseudocode and signatures that make the shape clear, but its durable output lands as a feature spec, ADRs, business rules and tasks. This is for features that break up into several smaller steps; a very small fix needs none of it, just do it.

The aim is a plan a worker can implement on its own. The core questions are settled while planning, so what comes up during implementation are details the worker records as questions without stopping the main work; a question that really blocks a task should be rare. Keep the session proportional to the feature: for a simple one, a round of context, a short proposal and a task or two.

## Start from main

Main is the only plan everyone can see; a checkout behind it shows tasks as unclaimed that someone is already implementing, and re-planning them produces two plans for the same work. So, before anything else, in shared mode:

- `sdd stale`: it fetches and fails if the data root is behind `origin/main` or has uncommitted changes. `sdd stale --fix` drops the uncommitted changes that already match main (leftovers of work shipped through a worktree) and fast-forwards; whatever it keeps is real unshipped work, to ship (`sdd ship`) or ask the user about. Don't plan on a stale view; while the checkout isn't synced, `sdd --main show|context|questions ...` read main directly.
- Before changing an existing task (its scope, prerequisites, ADRs, or splitting it), check `sdd show <slug>` and `gh pr list --search <slug> --state open`. If it's `in-progress` or has an open PR, it belongs to whoever holds it: leave it alone and plan follow-up tasks `--after` it instead. Changing what it must deliver is a scope change (see `orchestrating.md`), agreed with its owner and merged to main before they continue.

In local mode the data isn't shared, so there's nothing to sync.

## Pick what to plan

When the user names no feature, don't assume one: ask whether to plan something new or pick up a recorded idea (`managing.md`, "Ideas"). For an idea, list `sdd ideas --ready` grouped by area, a line each, and say in one line how many more wait on unfinished tasks (`sdd ideas`); one of those is planned only if the user insists, after saying what it waits on. The picked idea's Idea and Context are the feature description, and its areas, tasks and ADRs seed the search below.

## Understand, then load context

What to search for depends on what the feature is, and what is read changes what the feature turns out to be:

1. **Understand.** In a few lines: what the feature does and for whom, which goal in `goal.md` it serves, the components and files it likely changes (a look at the repo layout), the areas it touches (from `sdd areas`, not invented), and its key words. If it serves no goal, or works against a non-goal, raise that with the user before going further.
2. **Search.** `sdd context --area <areas> [--grep <words>] [--path <files or dirs>]` lists the foundation ADRs; the ADRs, business rules and specs in those areas, matching those words, or cited in `adr:`/`rule:` comments by the code at those paths (in-repo data only: local mode keeps the code free of them); the business rules of other areas, since a feature may have to keep a rule set elsewhere; the tasks that used them (done ones show what exists, in-progress ones what is being built); and the questions and ideas on them. Add the ready tech-debt tasks that touch the same code (`sdd ready`): the feature may absorb or obsolete them. A long reading list is shown to the user in a few lines first, to add or drop items; a short one is just read and named in the proposal. Read ADRs, rules and specs in full, done tasks' Goal and Notes, answered questions' Answer (they often carry requirements), open questions so they aren't asked twice, open ideas the feature may cover, closed ones so a dropped idea isn't proposed again without its reason; and the code the feature will change.
3. **Refine.** Correct the understanding with what was read. When it points at more (an ADR cited by one just read, a component the feature turns out to touch), search once more and name each addition in a line. Ask the questions that would change the design as they come up; for the rest, state what you assume.

## Propose

One proposal, sized to the feature, agreed with the user before any file is written:

- **Goal and behaviour**: what the feature does from the user's side, with a few concrete examples (a command and its output, a request and its response).
- **Shape**: the new and changed components and how they fit into the existing code: interfaces, signatures, data layout, and pseudocode where it makes an idea clear without being the implementation; a Mermaid diagram when several components interact.
- **Rules**: the general statements that answer the questions this feature's work will run into. Find them by asking what a worker will be unsure about (what happens to X when Y is cancelled? may the assistant do this too? which side wins when the two disagree?) and what the user would say; the statement behind several of those answers is the rule. List the ones the feature introduces and the existing ones it follows (the business rules `sdd context` listed, from any area), each with two or three questions it settles. For each, ask the user what it costs and where it stops, since a rule with no limit gets applied to everything. A rule is the user's: it comes from the goal, a principle, or what they said, quoted. One the planner inferred is put to them as a question, not written down as theirs. What the product wants is a business rule (see "Business rules"), what a design choice is for is that ADR's Intent, and what every change must respect is a principle to raise with the user. A contract others rely on (a format, compatibility) and a convention in the code belong in the component's spec.
- **Decisions**: which choices become ADRs, and which existing records the feature changes (see "Architecture decisions" and "Changing a record"). Few: a plan that needs many is recording details.
- **Tasks**: each with its goal, what it delivers to the tasks after it, its prerequisites and a rough size; then the open questions and what is assumed meanwhile.

If writing the files turns up something that changes what was agreed (a task that has to split, a rule that needs the user's call), take it back to the user before shipping.

## Feature spec

After the session, the agreed proposal is the feature's guideline: a worker settles from it what its task leaves open, and a reviewer checks the PR against it. It is kept as a spec, `sdd spec <feature> --feature --title "..." --areas <every area it governs> --arch <adr>... --rule <rule>...`, with:

- **Goal**: what the feature is for and for whom, in a few lines.
- **How it works**: the behaviour from the user's side, with the examples.
- **Shape**: what the feature adds (new components, interfaces, pseudocode and diagram), at the level of the proposal. A component that already has its own spec isn't described again: the Shape points at it, and the tasks that change the component update that spec, so each component keeps one description.
Business rules and ADRs are records of their own, linked from the spec (`--rule`, `--arch`). Every task of the feature links it (`--spec`), so `sdd brief` prints it to the worker. It describes the target until the last task is done. By then what lasts is in component specs, ADRs and business rules, and the feature spec's file is deleted, by the last task's PR or a maintenance session (`sdd validate` warns while one is left behind). A feature that fits in one task and introduces no rule needs no spec: the task's Goal and Notes hold it.

## Architecture decisions

Write an ADR only for decisions that are hard to reverse, span several components, constrain future work, or pick between real alternatives (storage, protocols, module boundaries, key libraries, infrastructure). Most large features and infra changes have some. A choice that is local to a task and obvious from its code has none, and neither does the way a decision is carried out (a key's format, where a file lives, a limit's value): that is the code, plus a line in the spec where a reader needs it. A description of how something is, with nothing rejected (a data model, an API's conventions), is a spec, not an ADR: `sdd spec`, linking the ADRs that shaped it. The same test applies whenever a record is about to be written: while planning, implementing or answering a question.

- `sdd adr <slug> --title "..." --areas <area>... [--supersedes <adr>...]` creates `arch/<today>-<slug>.md` with sections: Intent, Context, Decision, Alternatives considered, Consequences. Status starts as `proposed`; set it to `accepted` when the plan is agreed.
- **Intent** comes first: what the decision is for, in a line or two, in the user's words where they gave them ("the agent should be able to do what the page does"). It says what is wanted, not how, because a case the Decision doesn't cover is settled from it. `sdd brief` prints the Intent and the Decision to every worker; the other sections are for whoever asks why later.
- The title says what the decision achieves ("Rate limits are per API key, so one client can't starve the rest"), not the feature ("Rate limiting") nor the mechanism ("The limiter reads the key from Redis"), since titles are what `sdd context` and readers scan.
- Keep them short and durable (see `../documentation.md` and "Wording a record"): the problem, the decision, the rejected options and why, and what it costs. Under 100 lines; `sdd validate` warns past that while the ADR is proposed.
- What a later change could break is held by a test first: the task that builds the decision gets it as an acceptance criterion ("a test fails when a new operation lacks its description"). Only what no test can hold, because it takes a reader's judgement, goes under the record's `## Review checks` (see `overview.md`), where every later task that links the record reads it. A rule that would apply to every change is a principle to raise with the user, not a check.

## Business rules

A business rule is what the product wants, said once and generally, so later work in any area follows it without asking: "external calendars stay in sync with ours", "the assistant can do whatever the user can do on the page", "an invoice is never deleted, only voided". It is the first thing a worker reads when unsure how to proceed, and it outlives the feature that introduced it.

- A rule earns its place by the questions it answers. With "external calendars stay in sync with ours" recorded, "if the user cancels on our site, is the event in their calendar removed too?" and "does moving the event move the booking?" need no one's answer. A statement that settles only the case in front of it is a detail of that feature: the task or the spec holds it.
- `sdd rule <slug> --title "..." --areas <area>... [--supersedes <rule>...]` creates `rules/<today>-<slug>.md` with sections: Rule (the statement, in a sentence or two), Why (what the user wants it for, in their words where they gave them) and Questions it answers (two or three, each with its answer). The title is the rule itself, since titles are what `sdd context` lists.
- A rule says where it stops. Followed without limit, most rules do harm: "access is audited" becomes a database write for every row read, "customers are told" becomes a message for every event. So the Why says what the rule is for, which is what lets a worker tell when more of it stops serving that, and names what it costs (storage, writes, calls to a provider, someone's attention). At least one of the questions it answers is answered "no, that would be too much": "does every read during a support session get an audit row? No: the access is recorded, and what it changed".
- A number is rarely the rule. "A user posts at most 3 pictures a day" is today's setting of "no one user floods a feed": the rule states the second and may mention the first as the current value, so changing the number is a code change, not a new record.
- It starts `proposed` and is accepted once the user agrees: a rule is the user's intent, so one they neither stated nor confirmed isn't written as accepted.
- Every task the rule bears on links it (`--rule`), so `sdd brief` shows it to the worker. Where it comes down to one check in the code, suggest in the task's Notes enforcing it in one place every path goes through, with a test that pins it, and citing it there (`rule: <name>`); that's good practice, not a requirement.

## Wording a record

A record is read by someone deciding a case nobody planned, so it says what is wanted and why before anything else.

- State the default and the reasons to leave it, not a prohibition and its exceptions. "The page calls the API through the hooks that show the agent what it uses; a call opts out for security, privacy, or because the agent has no use for it" still holds when the next opt-out arrives. "No code calls the API outside the hooks" has to be changed for it.
- "Never", "only", "always", "every", "forbidden" and closed lists are for real invariants: security, privacy, money, data that can't be recovered. Anywhere else they are wrong by the next feature. Where one is meant, the record says what breaks without it.
- No code: no file, function or job names, no error codes, no lists of call sites, no current values. They are in the code and change with it. Name a thing only when it is the contract (an API field others read, a file format).
- Short. A Decision or Rule that needs more than a few bullets is describing the implementation, which is the code's job and, above it, the spec's.

## Changing a record

An accepted record changes only with the user's agreement (`managing.md`, "How records change"). When a case doesn't fit one, or a plan needs it to say something else:

1. Read its Intent, or the rule's Why. If that answers the case, follow it; nothing is written.
2. If the intent wants what the wording forbids, the wording is at the wrong level. Restate the record in place so the case is no longer special, and show the user the old statement next to the new one.
3. If the change would be an exception ("except for", "the one case where", one more entry in a list), stop: needing an exception means the decision is wrong or too specific. Propose to the user what it should say instead. A record that already carries exceptions or amendments is restated whole, not extended.
4. If the decision is replaced by a different one, write the new record with `--supersedes`.

`--amends` exists for older data. Don't create new amendments: a decision spread over several records is read with all of them, and nobody restates it.

## Tasks

- One task is one reviewable PR that leaves main working. Size it against the target in `../pull-requests.md`, as a best effort: an implementer splits a task only along a cut the feature spec, rules and ADRs already draw (`working.md`), and stops with a question otherwise, so a task planned too big costs a split or a round trip to the user.
- `sdd new <slug> --title "..." [--after <prereq>...] [--arch <adr>...] [--rule <rule>...] [--spec <spec>...] [--uses <spec>...] [--tech-debt] [--needs user|secret|...]` creates the file with its prerequisites, ADRs, business rules and specs in the frontmatter. ADRs and rules are referenced by file name without `.md` (e.g. `2026-10-12-rate-limit-strategy`). `--needs` marks a task an agent can't do alone (a live run against a real account, a credential only the user has): `sdd ready` shows it and orchestrated runs leave it to the user.
- Fill in the template: **Goal** (what and why, in a few lines), **Acceptance criteria** (verifiable), **Notes** (constraints, pointers into the code, anything an implementer needs that isn't in the ADRs and the feature spec). A task plus its ADRs and specs must be enough context to implement it without the planning conversation.
- `arch:` lists every ADR that constrains the task, including older ones the plan didn't write, `rules:` every business rule it enforces or must keep, and `spec:` every spec it implements or changes, the feature spec included; a worker reads only what's linked. A component the task relies on without changing goes in `uses:` instead: the worker then reads that spec's Summary, not its inner workings. Link as little as the task needs, since every link is read by the worker and again by the reviewer. The Notes name what each prerequisite delivered that the task builds on (the interface, where the code is), or point at the done task, and what this task must deliver to its dependents: a shape the next task can't use is rework.
- `sdd rm <slug>` deletes a planned task nothing depends on.

## Dependencies

- Add a dependency only when a task genuinely can't start without another one being merged (it needs its code, schema or interface). Preferred ordering is not a dependency: every extra edge reduces how much can run in parallel. But a required order is one: "run the smoke test before its dependents start" is `after:` on the dependents, never a sentence in Notes, which a worker reads only after claiming and an orchestrator never does.
- `sdd dep add <task> <prereq>...` / `sdd dep rm <task> <prereq>...` edit the task's `after:` list. The CLI rejects cycles.

## Open questions

`../planning.md` asks for open questions and assumptions to be listed instead of guessed. Here they become files (`sdd ask`, see `overview.md`), so they survive the planning conversation:

- Ask the user the questions that shape the design while understanding and proposing; record the ones that stay open.
- A question that a task can't be implemented without gets `--blocks <task>`; the rest just link the tasks, ADRs and rules they concern (`--task`, `--arch`, `--rule`) and the task's Notes say what to assume meanwhile.
- `sdd questions` before planning: answered questions may already settle a design point, and open ones on related ADRs shouldn't be asked twice.
- Answers that change a decision or a rule change its record (see "Changing a record"), and tasks that depended on what it said are re-planned. Until that happens each such task is held with a blocking question (`sdd ask replan-<slug> --title "Re-plan <slug> after <record>" --blocks <slug> --arch <adr>` or `--rule <rule>`), so `sdd ready` leaves it out; re-planning it answers the question. A note in the task file holds nothing: workers find it only after claiming.

## Ideas

- Ask the user whether the plan should cover the open ideas in its areas; those it covers are closed with it.
- A covered idea gets its Outcome (what it became, in a line or two) and `sdd close-idea <slug> --into <tasks, ADRs, rules and the feature spec>`. One the user decides against gets the reason as Outcome and `sdd close-idea <slug>`. Only the user drops an idea.
- What comes up but stays out of the plan's scope is recorded with `sdd idea` instead of growing the plan, with `--after` the tasks it must wait for.

## Steps

1. Read `goal.md` and `principles.md` if they exist (`sdd doc list`). Understand the feature and load its context, then propose (above). Every design choice stays within the principles; wanting to break one is a question for the user, not a decision.
2. Once the user agrees, write the feature spec (`sdd spec --feature`, when the feature needs one), each ADR (`sdd adr`) and each business rule (`sdd rule`). An ADR's Intent, or a rule's Why, names the goal or principle it follows from, when there is one, so a reader can tell a forced choice from a free one. Each follows "Wording a record".
3. Create the tasks with `sdd new`, linking their ADRs, business rules, the feature spec and their prerequisites, and fill them in.
4. Record the open questions with `sdd ask` and fill in their Question and Context sections. Close the ideas the plan covers and record the ones it leaves out (see "Ideas").
5. Dry-run the plan's tasks, at least the ones others wait on: give a sub-agent that wasn't in the session only a task's brief (`sdd brief <slug>`) and the code, and have it work out how it would build and test each acceptance criterion, without writing code. It reports what it needed that the brief didn't say (and whether the code, another doc or nothing answered it), which parts of the brief it never used, and what in the brief contradicts the code. A design choice it couldn't settle is a gap in the plan: decide it with the user and put it in the task now. A part it never used is a link to drop.
6. Run `sdd validate` (frontmatter, prerequisites exist and form a DAG, ADR and question references exist, questions and ideas filled in). For a visual review: `sdd render | dot -Tsvg > graph.svg`. Its warnings about amended ADRs, finished feature specs, stale questions, review checks per area and broken links are for a maintenance session (`sdd-maintenance` skill): mention them to the user, don't fold them into this plan.
7. In shared mode, the planning changes must be merged to main before any of the tasks is started: main is what claims are checked against. Once the user agrees to the plan, `sdd accept <name>...` the new ADRs and business rules and `sdd ship --title "Plan <feature>" --body "..." --merge` (without `--merge` when the user wants to read the PR first; the body follows `../pull-requests.md`). In local mode, the files are simply there.

Re-planning later (splitting a task, changing dependencies) follows the same steps, including going to main first in shared mode.
