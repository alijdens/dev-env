# Task Workflow: Maintenance

A session that shrinks what accumulates in the task data. Every plan adds records, questions and review checks, and every worker and reviewer reads them: `sdd brief` prints a linked ADR with everything that amends it, and `sdd checks` every check in a task's areas. Most items are mechanical. Restating a record is not: it asks what the decision was for, and the answer is the user's.

## Where to work

Like an answering session (`answering.md`): each item is a change that should reach main as soon as it is made, and the lists are only as complete as the checkout they read. So in shared mode, work in a worktree at `origin/main` on a branch `maintenance/<first item>` and pass `--dir <worktree>/<data root>` on every `sdd` command; the skill says where. In local mode, work in place and skip the Ship step.

## Order

`sdd validate` warns about each kind of item, with the command that lists it. Show the user the counts in a few lines (ADRs to restate, finished feature specs, the docs that cost most to read, areas over the check limit, stale questions, files with broken links) and let them pick; without a preference, start with the ADR linked by the most live tasks, since every brief of those tasks shrinks. Then one item at a time: do it, have it agreed, ship it, re-run `sdd validate` for the next.

## Records to restate

A record that keeps being amended, or whose Decision has grown a list of exceptions, is stated at the wrong level: it describes cases, and the next case needs another change. Merging the amendments into one text keeps the problem, and the new record collects amendments again. The fix is to say what the decision is for and state it so the exceptions stop being special. `sdd adrs --amended` lists the candidates, most amended first, with the live tasks linking them and two lists of amendments:

- **Own**: they amend only this ADR, directly or through each other. The restated record takes them in and supersedes them.
- **Shared**: they also amend other ADRs. Their effect on this one is folded into its restatement; they stay in force for the others until those are restated.

One record per PR. Skip one while an amendment of it is still proposed (`sdd adrs --amended` marks them): that plan isn't settled. Then:

1. **Find the intent.** Read the record and its amendments, including their Context and the user's words quoted in them. Say in a line or two what the decision was for, and for each amendment whether that intent already implied it (the usual case: the original wording was narrower than what was wanted), whether it is a detail of how the decision is carried out, or whether it changed the decision.
2. **Propose** to the user, before editing anything: the Intent, the restated Decision following `planning.md`, "Wording a record" (the default and the reasons to leave it, no code, a few bullets), and what happens to each amendment: implied by the intent and dropped, moved to a spec, or kept as a clause. If the intent turns out to be a product-wide statement ("the assistant can do whatever the page can"), it is a business rule the ADR then follows: propose that too. The user corrects the intent; don't settle for one they only half recognise.
3. **Edit the record in place**: add `## Intent`, replace the Decision, and keep Context, Alternatives considered and Consequences only where they still say why. Details worth keeping go to the component's spec, at its level (`overview.md`); what only restates the code goes nowhere.
4. `sdd link <record> --supersedes <its own amendments>`, and `sdd retire <amendment> --into <spec>` for one that was only a detail. Review checks of the amendments move to the record without duplicates, minus those a test already enforces.
5. **Check the restatement** with a reviewer sub-agent that didn't write it: give it the record before and after, the amendments and the specs touched, and ask for every statement the old texts made that is now neither in the record, nor implied by its Intent, nor in a spec, and every new statement that none of them made, each pointing at the record and line. Show the user that list: each item is either a detail dropped on purpose or a change of meaning they agree to.
6. Link every live task (todo, in-progress, tech-debt) that links a superseded or retired amendment to the record (`sdd link <task> --arch <record>`); done tasks keep their links. Code citing one (`adr: <name>`) now cites the record; `sdd validate` lists the citations. When the data lives in the code repo they go in the same PR; otherwise, say which repo needs a PR.
7. The user's yes to the restated record is its acceptance; the PR says which records it took in.

## Details recorded as decisions

A record that fails the test in `planning.md`, "Architecture decisions" (nothing hard to reverse, one component, no real alternative: a key's format, a size limit, where a control sits) costs every worker in its areas a read and tends to be amended by the next detail. Going through `sdd adrs --area <area>` with the user, propose which ones are details. For each agreed one, look at what it would leave behind. If it holds a reason or a choice a later reader would miss, make sure the spec says it (often one line), then `sdd retire <record> --into <spec>`, and relink live tasks and code citations as above. If it is outdated, or says nothing the code and the specs don't already say, delete it: `sdd retire <record> --delete`, then remove the code comments that cite it (`sdd validate` lists them). A file that only points elsewhere is one more thing to read. A business rule that is only a number goes the same way when a general rule covers it; otherwise restate it as what the number is for (`planning.md`, "Business rules").

## Finished feature specs

A feature spec is the target while its tasks are built (`planning.md`, "Feature spec"). `sdd validate` warns once every task linking one is done. Check that what should last is in a component spec, an ADR or a business rule, move what isn't, and delete the file; done tasks keep its name as history. One PR may take several.

## Docs that cost the most to read

Every worker and reviewer reads what their task links, so a doc's cost is its size times the tasks that load it. `sdd cost` lists the docs by that product, with the median brief of the live tasks; `sdd validate` warns when the median is large. For the docs at the top, with the user:

- **Tasks that only use the component:** link its spec with `uses:` in place of `spec:` (`sdd link <task> --uses <spec>`), and give the spec a `## Summary` of what it is for and what others may rely on, if it has none.
- **A spec that spans areas** (the backend and the web of one feature): split it by area, each half with its own Summary, so a task on one side doesn't read the other.
- **A record linked by many tasks out of habit:** unlink it where the task doesn't touch what it decides; a business rule in force is listed to planning anyway.

A long doc that few tasks load is left alone: splitting it saves nothing. One doc per PR.

## Specs that restate the code

A spec says what a component is and why, above the code (`overview.md`). One that walks through functions, jobs, error codes and conditions is as long as the code and wrong after the next PR. For a spec the user names, or the longest ones, propose a cut: keep the purpose, how the parts fit, the contracts others rely on and the reasons; drop what a reader finds faster in the code. Show the user what goes, since a spec is what workers build from. One spec per PR, and not while an in-progress task is changing it.

## Review checks per area

A check is how to verify something on a diff (`overview.md`). One that a test, a generated-file check or a lint now enforces verifies nothing the suite doesn't, yet every reviewer in its areas reads it. For the area the warning names, go through `sdd checks --area <area>` with the user, one record at a time, and propose for each bullet whether something enforces it, naming the test or check. Remove the agreed ones from their record's `## Review checks` and name what enforces each in the PR. A bullet nothing enforces yet stays; if it should be enforced, the fix is a tech-debt task for the test (`sdd new --tech-debt`), not a longer check. One PR per area.

## Stale questions

An open question whose linked tasks are all done won't be answered by the work it was raised on. Follow `answering.md`, "Stale questions", over `sdd questions --stale`, including its Ship step.

## Broken links

A relative link in a record that doesn't resolve usually points at a task or question that has moved since (`sdd done`, `sdd answer`). Fix each to the file's current path, or replace it with the record's name where the link would go stale again. Point the link at the file's current path, and when the file doesn't exist any more (or never did), replace the link with its text. The links are history, not decisions, so a whole batch is one PR without asking per link.

## Ship

In shared mode, offer in one line to open a PR for the item and merge it, with "PR only" and "later" as the alternatives, as `answering.md`'s Ship step does: `sdd ship --title "..." --body "..." [--merge]`, the body following `../pull-requests.md` and, for a restated record, giving its old and new statement, the records it took in and the tasks it relinked. A change outside the data root (code citations) doesn't go through `sdd ship`: commit it with the data on the worktree's branch and open the PR with `gh pr create`. The user's yes is the authorization to merge that PR, no other. The next item starts on a new branch from `origin/main`.

## Ending

When the user stops or nothing is left, report in a few lines: what was restated, retired, deleted, closed or fixed, the PRs opened or merged, and what `sdd validate` still warns about. Unshipped work gets one last Ship offer; if declined, push the branch, say its name and leave the worktree. Remove the worktree once nothing unshipped remains on it.
