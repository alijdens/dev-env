# Task Workflow: Orchestrating Tasks

The orchestrator takes ready tasks through claim, implementation, review and fixes using sub-agents, and merges the PRs its merge policy allows. It coordinates and decides; it doesn't implement or review itself. If the tool can't spawn sub-agents, stop and say so.

## Inputs

- **Concurrency** (default 1): how many tasks are in flight at once. Each in-flight task has at most one agent running at a time (its worker or its reviewer), so this also caps the number of agents.
- **Merge policy** (default `none`): which implementation PRs the orchestrator merges, by the risk the reviewer rated:
  - `none`: merge nothing, leave the PRs to the user.
  - `low`, `medium`, `high`: merge PRs rated up to that level.
  - `all`: merge anything, critical included.
- **Approve** (default `yes`): `approve=no` skips step 5; the PRs are marked ready for review but not approved.
- **Tasks** (optional): limit the run to these slugs (and only start them once they're ready). Otherwise, the run's task set is every task on main when the run starts, plus the tasks this run's own merges make ready, including the rest of a task a worker split (`working.md`). Tasks that others add to main during the run are not started: a planning session running in parallel would otherwise keep the run going indefinitely. They go in the report for the next run.
- **Target** (optional): one task to reach as soon as possible. The run's task set is the target plus every unfinished task it waits on, transitively; the run ends once the target is done or nothing in that set can start (e.g. the target is already in progress outside the run). It takes the place of Tasks: if the user gives both, ask which one they meant.
- **Budget** (optional): a number of tasks or a duration. Once reached, no new task starts and in-flight ones finish.

When the user changes the inputs mid-run, restate the new reading in one line and wait for the answer before acting on it: a misread merge policy or a skipped step is cheap to confirm and expensive to undo. "Stop" means: pick no new task, let in-flight PRs finish their current round, then report. "Stop now" means: also stop the running agents, leave their branches pushed, and report where each task stands.

Invoking the orchestrator authorizes merging every claim PR, whatever the policy (they only move a task file), merging the implementation PRs its policy allows, shipping planning changes it is told to make (scope changes, held questions, below), and creating the worktrees below. It never authorizes bypassing branch protection (no `--admin`) or merging a PR whose checks fail.

## Setup

`sdd root` must succeed. Keep the user's working copy untouched: give the orchestrator its own worktree at `origin/main` (e.g. `../<repo>-worktrees/orchestrator`) and refresh it with `git fetch` and a reset to `origin/main` before every pick, so `sdd ready` sees what main sees. Record the commit main was at when the run started: the report reads the questions raised since then from it.

With a target, flag early what only the user can clear, so the run isn't stuck on it later. Before the first pick, if the stderr of `sdd ready --for <target>` names anything besides the run's own in-flight tasks, tell the user in one line, with each item and what it waits for. This is a notice, not a question; if the tool keeps a list of pending items for the user, add it there. Repeat it on a refresh only when that list changes.

On every refresh, before resetting, diff the in-flight tasks' files and the specs they link between the old and new `origin/main` (`git diff <old> <new> -- <data root>/tasks/in-progress/ <data root>/specs/`). A planning session may have merged a change to a task, or to the feature spec, that a worker is implementing: forward the new definition to that worker with the same prompt rules as a scope change, and schedule a re-review of its PR. A task that was removed or moved out of `in-progress` by someone else is dropped from the run and reported. Also check whether a held task's question (below) has been answered: if so, it gets a fix round with the answer.

## Loop

While a slot is free and a task in the set is ready, start one; when nothing is in flight and nothing can be started, stop.

1. **Pick** a ready task that isn't in flight. `sdd ready` lists them with the number of tasks waiting behind each, most first: take the first one not in flight. With a target, use `sdd ready --for <target>` instead: it lists only the target and the tasks it waits on, longest chain to the target first, since the target can't start until every chain is done; its stderr names what holds the target up that finishing ready tasks won't free (open questions, `needs`, unknown prerequisites, tasks in progress, which include the run's own in-flight ones). If `sdd ready` reports a dependency cycle, don't fix it: report it. It already leaves out tasks blocked by an open question; never answer a question to free one up, and don't ask the user mid-run: the questions go in the final report (a held PR gets a one-line notice, see "Held PRs"). Skip tasks whose `needs` column isn't empty (a credential, the user's go-ahead) unless the user named them in the inputs, and report them.
2. **Work.** Create a worktree for it at `origin/main` (e.g. `../<repo>-worktrees/<slug>`) and spawn a worker. Its prompt must be self-contained: use the `sdd-claim-task` skill to create a PR for `<slug>` (name the skill's `SKILL.md` path too, so a worker whose tool doesn't list the skill reads it from disk), work only in `<worktree>`, claim with `sdd start <slug> --merge --branch` (the run authorizes merging the claim), never merge the implementation PR, and report back the PR link or why it stopped. If the claim fails (someone else got the task) or the task needs re-planning, drop it and report it; don't re-plan.
3. **Review.** Spawn a fresh reviewer with the `sdd-review-task` skill on the PR, so the review isn't anchored on the worker's reasoning. It returns findings and a risk level.
4. **Fix.** Decide which findings to apply; reject the ones you judge wrong and record why. Send the accepted ones to the worker (or a new worker on the same branch and worktree); then review again, giving the reviewer the commit range of the fixes and the findings accepted and rejected so far, so it verifies the fixes and the changed hunks instead of starting over (`reviewing.md`, "Re-reviews"). A **round** is one review and the fix that follows it; the first review opens round 1. A round whose findings are all `low` ends the loop: send the lows to the worker as one last fix without a re-review when each fix stays within the lines its finding names (a test, a doc line, a guard), skip them otherwise, list them in the report, and go on to approve and merge per the policy. That is the only case where a fix lands unreviewed. From the 4th round on, run the worker (and reviewer) on a more capable model than the one used so far. After 5 rounds with accepted findings still open, stop on that PR and report it. A worker on its own stops before committing, so the fix prompt must be explicit: the findings verbatim, the PR link, work only in `<worktree>` on branch `<slug>`, commit and push the fixes, update the PR description if the change affects it, never merge, and report back what changed or which findings it disagrees with and why.
5. **Approve.** Once the review leaves nothing to fix, mark the PR ready for review and, unless `approve=no`, approve it (`gh pr review --approve`). Approving is best effort: GitHub refuses self-approval unless the account is allowed to, so on failure note it and carry on.
6. **Merge** if the policy allows the PR's risk: wait for its checks, then `gh pr merge`. If the checks fail, send the failure to the worker as a finding (step 4). If GitHub refuses the merge (missing approval, branch protection), leave the PR for the user. When the data lives in a separate repo or in local mode, the merged PR didn't move the task: run `sdd done <slug>` yourself right after merging (it opens a PR in the data repo, which you merge like a claim PR; in local mode it just moves the file), or dependents never become ready. Remove the worktree once the PR is merged or handed over.

Merging a PR can make others conflict with main: the worker rebases onto `origin/main` and pushes, and the PR is reviewed again if resolving the conflicts changed code. Tasks depending on an unmerged PR stay blocked; work on other ready tasks meanwhile. Some collisions aren't git conflicts: two PRs allocating from one shared sequence (migration numbers, enum values, port numbers) both apply cleanly and break at runtime. When a project review check names such a sequence, merge those PRs in allocation order and have the worker renumber on rebase.

## What the orchestrator doesn't decide

The orchestrator applies the plan; it doesn't change it. Three things are the user's, whatever the merge policy says:

- **A finding that changes an accepted decision**, breaks a principle, or shows a criterion the code can't meet. It isn't resolved by picking a side, by "keep the behaviour and add a proposed ADR", or by rewording the criterion.
- **A decision a worker added.** An implementation PR that adds a `proposed` ADR or business rule carries a decision the user hasn't seen: it may merge under the policy, but the report lists every such record under "decisions awaiting acceptance". One that amends or supersedes an accepted record is a hold (below).
- **Facts not in the plan.** Context added to a worker's prompt is quoted from the task, its ADRs, business rules, specs or questions, with the source named. What the orchestrator can't source that way isn't sent as context; if the worker needs it, it's a question.

### Held PRs

When one of the above comes up on a PR that already exists, the run holds it instead of guessing or discarding the work:

1. The worker applies the findings that don't depend on the decision, records the decision as a question with `sdd ask ... --blocks <slug>` (Question and Context per `overview.md`) on its branch, pushes, and marks the PR draft with a comment naming the question.
2. The orchestrator ships the question file to main (`sdd ship --title "Hold <slug>: <question>" --merge`, a planning change within the run's authorization), so `sdd blockers` and the decisions band show it while the PR waits. The task stays `in-progress`.
3. The slot is freed. Tell the user in one line that the PR is held and on what; a notice, not a question, and if the tool keeps a list of pending items for the user, add it there.
4. When the question is answered on main (checked on each refresh, and at the start of a later run from `sdd blockers`' held rows), the worker gets a fix round with the answer verbatim, and the loop continues at step 3.

## Scope changes during a run

When the user changes what an in-flight task must deliver, the change goes to main before the worker hears of it, so a planning session elsewhere sees the same task the worker is building. Edit the task file (acceptance criteria, Notes) in the orchestrator's worktree and ship it with `sdd ship --title "..." --merge` (planning changes are within the run's authorization), then tell the worker to fetch and implement against the updated task. Never put the change only in the worker's prompt, and the worker must not write it into the task file inside its implementation PR: that PR carries the task's move to done, not its definition. A change big enough to split the task or add dependencies is re-planning: drop the task from the run and report it.

A worker that must change another task's criteria (an interface it changed) follows `working.md`: a task downstream of its own may be edited in the implementation PR; any other task's edit is a planning PR the worker opens with `sdd ship` and reports, and the orchestrator merges it.

In local mode, claims are plain file moves; the rest is the same, but the merge policy usually can't apply to repos you don't own.

## Limits

Sub-agents can stall or loop, so every one of them runs under a bound, and reaching a bound is a reportable outcome, not a reason to try harder:

- Give each worker and reviewer prompt an explicit stop condition: report back after one PR (worker), one review (reviewer) or one fix round, and stop with a report when stuck for more than a few attempts at the same step (claim, checks, push) instead of retrying indefinitely.
- A time bound as well as an attempt bound: a worker whose worktree hasn't changed (no new commit, no modified file) for 30 minutes, or a reviewer silent that long, is taken as stalled, typically on a command waiting for input. Stop it; it counts as a failed attempt under the next rule.
- At most 5 fix rounds per PR (step 4) and 2 rebase rounds per PR; past that, hand the PR to the user as is.
- If a sub-agent returns without a usable report (no PR link, no findings, or an error), or was stopped as stalled, retry it once with the same prompt; on a second failure drop the task and report it.
- A run ends when its task set is exhausted or its budget is reached; in-flight tasks finish either way.

## Report

At the end, one row per task: PR link, risk, final state (merged, held and on which question, ready for the user, blocked and why, dropped and why), rejected findings with their reason, and steps that failed (e.g. approval refused, a screenshot left as a placeholder, with the reason the worker gave). Then: proposed ADRs and business rules the merged PRs added (decisions awaiting acceptance); tasks skipped for their `needs`; tasks that appeared on main during the run; the tasks still waiting on unmerged PRs; with a target, whether it was reached and, if not, what `sdd ready --for <target>` says still holds it up besides the run's own PRs; any dependency cycle `sdd ready` reported. Finally the open questions: first `sdd blockers`, the ones that alone keep a task from starting or hold a built PR, with the work waiting behind each; then the rest from `sdd questions --since <start commit>`, the questions raised during the run, each with the tasks it blocks, so the user can answer them before the next run.
