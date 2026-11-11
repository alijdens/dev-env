# Task Workflow: Maintenance

A session that shrinks what accumulates in the task data. Every plan adds ADRs, amendments, questions and review checks, and every worker and reviewer reads them: `sdd brief` prints a linked ADR with all its amendments, and `sdd checks` every check in a task's areas. Nothing here designs anything new: each item is mechanical except one rewrite, and the user decides.

## Where to work

Like an answering session (`answering.md`): each item is a change that should reach main as soon as it is made, and the lists are only as complete as the checkout they read. So in shared mode, work in a worktree at `origin/main` on a branch `maintenance/<first item>` and pass `--dir <worktree>/<data root>` on every `sdd` command; the skill says where. In local mode, work in place and skip the Ship step.

## Order

`sdd validate` warns about each kind of item, with the command that lists it. Show the user the counts in a few lines (ADRs to consolidate, areas over the check limit, stale questions, files with broken links) and let them pick; without a preference, start with the ADR linked by the most live tasks, since every brief of those tasks shrinks. Then one item at a time: do it, have it agreed, ship it, re-run `sdd validate` for the next.

## Amended ADRs

An accepted ADR is changed by amending it, so its decision as it stands is the ADR plus every amendment, and amendments of those. Consolidating writes it once. `sdd adrs --amended` lists the candidates, most amended first, with the live tasks linking them and two lists of amendments:

- **Own**: they amend only this ADR, directly or through each other. The consolidated record supersedes them.
- **Shared**: they also amend other ADRs. They stay in force, since those ADRs still need them, but their effect on this one is folded into the new record. Once this ADR is superseded they count only for the others.

One ADR per PR, so the diff can be checked against the records it replaces. Skip an ADR while one of its amendments is still proposed (`sdd adrs --amended` marks them): that plan isn't settled. Then:

1. `sdd adr <slug> --title "..." --areas <every area of the records it replaces> --supersedes <the ADR> <its own amendments>`. The superseded records keep their text and point to the new one.
2. **Context**: one line naming what it consolidates. **Decision**: the decision as it stands, from the ADR and all its amendments, own and shared. Keep every clause that still binds, drop the ones an amendment replaced, keep the amendment's wording where the two differ, and add nothing: a consolidation decides nothing new. **Alternatives considered** and **Consequences**: a line saying they are in the superseded records.
3. **Review checks**: the bullets of the superseded records, verbatim, without duplicates.
4. **Check the rewrite** with a reviewer sub-agent that didn't write it: give it the paths of the new record, the superseded ones and the shared amendments, and ask it to list every clause of the new Decision that is in none of them nor a merge of their clauses, every clause dropped that no later amendment replaced, and every changed wording, each pointing at the record and line. Fix what it finds, or keep a finding the user overrules.
5. Link every live task (todo, in-progress, tech-debt) that links a superseded record to the new one (`sdd link <task> --arch <new>`); done tasks keep their links, as history. `sdd brief` prints a superseded record as a pointer to its successor.
6. Code citing a superseded record (`adr: <name>`) now cites the new one; `sdd validate` lists the citations. When the data lives in the code repo they go in the same PR; otherwise, say which repo needs a PR.
7. Show the user the new Decision next to what the reviewer checked. On their yes, `sdd accept <new>`: the rewrite is the risky step, and the acceptance is its check.

## Review checks per area

A check is how to verify something on a diff (`overview.md`). One that a test, a generated-file check or a lint now enforces verifies nothing the suite doesn't, yet every reviewer in its areas reads it. For the area the warning names, go through `sdd checks --area <area>` with the user, one record at a time, and propose for each bullet whether something enforces it, naming the test or check. Remove the agreed ones from their record's `## Review checks` (an accepted record allows it) and name what enforces each in the PR. A bullet nothing enforces yet stays; if it should be enforced, the fix is a tech-debt task for the test (`sdd new --tech-debt`), not a longer check. One PR per area.

## Stale questions

An open question whose linked tasks are all done won't be answered by the work it was raised on. Follow `answering.md`, "Stale questions", over `sdd questions --stale`, including its Ship step.

## Broken links

A relative link in a record that doesn't resolve usually points at a task or question that has moved since (`sdd done`, `sdd answer`). Fix each to the file's current path, or replace it with the record's name where the link would go stale again. In an accepted ADR or business rule only the target may change, so `sdd validate` still holds its wording: point the link at the file's current path, and when the file doesn't exist any more (or never did), leave the link and add a dated `## Errata` line saying where its target went. The links are history, not decisions, so a whole batch is one PR without asking per link.

## Ship

In shared mode, offer in one line to open a PR for the item and merge it, with "PR only" and "later" as the alternatives, as `answering.md`'s Ship step does: `sdd ship --title "..." --body "..." [--merge]`, the body following `../pull-requests.md` and, for a consolidation, listing the records it supersedes and the tasks it relinked. A change outside the data root (code citations) doesn't go through `sdd ship`: commit it with the data on the worktree's branch and open the PR with `gh pr create`. The user's yes is the authorization to merge that PR, no other. The next item starts on a new branch from `origin/main`.

## Ending

When the user stops or nothing is left, report in a few lines: what was consolidated, retired, closed or fixed, the PRs opened or merged, and what `sdd validate` still warns about. Unshipped work gets one last Ship offer; if declined, push the branch, say its name and leave the worktree. Remove the worktree once nothing unshipped remains on it.
