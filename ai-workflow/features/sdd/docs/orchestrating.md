# Task Workflow: Orchestrating Tasks

The orchestrator takes ready tasks through claim, implementation, review and fixes using sub-agents, and merges the PRs its merge policy allows. It coordinates and decides; it doesn't implement or review itself. If the tool can't spawn sub-agents, stop and say so.

## Inputs

- **Concurrency** (default 1): how many tasks are in flight at once. Each in-flight task has at most one agent running at a time (its worker or its reviewer), so this also caps the number of agents.
- **Merge policy** (default `none`): which implementation PRs the orchestrator merges, by the risk the reviewer rated:
  - `none`: merge nothing, leave the PRs to the user.
  - `low`, `medium`, `high`: merge PRs rated up to that level.
  - `all`: merge anything, critical included.
- **Tasks** (optional): limit the run to these slugs (and only start them once they're ready). Otherwise, all ready tasks.

When the user changes the inputs mid-run, restate the new reading in one line and wait for the answer before acting on it: a misread merge policy or a skipped step is cheap to confirm and expensive to undo.

Invoking the orchestrator authorizes merging every claim PR, whatever the policy (they only move a task file), merging the implementation PRs its policy allows, and creating the worktrees below. It never authorizes bypassing branch protection (no `--admin`) or merging a PR whose checks fail.

## Setup

`sdd root` must succeed. Keep the user's working copy untouched: give the orchestrator its own worktree at `origin/main` (e.g. `../<repo>-worktrees/orchestrator`) and refresh it with `git fetch` and a reset to `origin/main` before every pick, so `sdd ready` sees what main sees.

On every refresh, before resetting, diff the in-flight tasks' files between the old and new `origin/main` (`git diff <old> <new> -- <data root>/tasks/in-progress/`). A planning session may have merged a change to a task that a worker is implementing: forward the new definition to that worker with the same prompt rules as a scope change, and schedule a re-review of its PR. A task that was removed or moved out of `in-progress` by someone else is dropped from the run and reported.

## Loop

While a slot is free and a task is ready, start one; when nothing is in flight and nothing can be started, stop.

1. **Pick** a ready task that isn't in flight. `sdd ready` lists them with the number of tasks waiting behind each, most first: take the first one not in flight. It already leaves out tasks blocked by an open question; never answer a question to free one up, and don't ask the user mid-run: the questions go in the final report.
2. **Work.** Create a worktree for it at `origin/main` (e.g. `../<repo>-worktrees/<slug>`) and spawn a worker. Its prompt must be self-contained: use the `sdd-claim-task` skill to create a PR for `<slug>`, work only in `<worktree>`, claim with `sdd start <slug> --merge --branch` (the run authorizes merging the claim), never merge the implementation PR, and report back the PR link or why it stopped. If the claim fails (someone else got the task) or the task needs re-planning, drop it and report it at the end; don't re-plan.
3. **Review.** Spawn a fresh reviewer with the `sdd-review-task` skill on the PR, so the review isn't anchored on the worker's reasoning. It returns findings and a risk level.
4. **Fix.** Decide which findings to apply; reject the ones you judge wrong and record why. Send the accepted ones to the worker (or a new worker on the same branch and worktree); then review again, giving the reviewer the commit range of the fixes and the findings accepted and rejected so far, so it verifies the fixes and the changed hunks instead of starting over (`reviewing.md`, "Re-reviews"). A round whose findings are all `low` ends the loop: go on to approve and merge per the policy, and list those findings in the report. From the 4th round on, run the worker (and reviewer) on a more capable model than the one used so far. After 5 rounds with accepted findings still open, stop on that PR and report it. A worker on its own stops before committing, so the fix prompt must be explicit: the findings verbatim, the PR link, work only in `<worktree>` on branch `<slug>`, commit and push the fixes, update the PR description if the change affects it, never merge, and report back what changed or which findings it disagrees with and why.
5. **Approve.** Once the review leaves nothing to fix, mark the PR ready for review and approve it (`gh pr review --approve`). Approving is best effort: GitHub refuses self-approval unless the account is allowed to, so on failure note it and carry on.
6. **Merge** if the policy allows the PR's risk: wait for its checks, then `gh pr merge`. If the checks fail, send the failure to the worker as a finding (step 4). If GitHub refuses the merge (missing approval, branch protection), leave the PR for the user. When the data lives in a separate repo or in local mode, the merged PR didn't move the task: run `sdd done <slug>` yourself right after merging (it opens a PR in the data repo, which you merge like a claim PR; in local mode it just moves the file), or dependents never become ready. Remove the worktree once the PR is merged or handed over.

Merging a PR can make others conflict with main: the worker rebases onto `origin/main` and pushes, and the PR is reviewed again if resolving the conflicts changed code. Tasks depending on an unmerged PR stay blocked; work on other ready tasks meanwhile.

## Scope changes during a run

When the user changes what an in-flight task must deliver, the change goes to main before the worker hears of it, so a planning session elsewhere sees the same task the worker is building. Edit the task file (acceptance criteria, Notes) in the orchestrator's worktree and ship it with `sdd ship --title "..." --merge` (planning changes are within the run's authorization), then tell the worker to fetch and implement against the updated task. Never put the change only in the worker's prompt, and the worker must not write it into the task file inside its implementation PR: that PR carries the task's move to done, not its definition. A change big enough to split the task or add dependencies is re-planning: drop the task from the run and report it.

In local mode, claims are plain file moves; the rest is the same, but the merge policy usually can't apply to repos you don't own.

## Limits

Sub-agents can stall or loop, so every one of them runs under a bound, and reaching a bound is a reportable outcome, not a reason to try harder:

- Give each worker and reviewer prompt an explicit stop condition: report back after one PR (worker), one review (reviewer) or one fix round, and stop with a report when stuck for more than a few attempts at the same step (claim, checks, push) instead of retrying indefinitely.
- At most 5 fix rounds per PR (step 4) and 2 rebase rounds per PR; past that, hand the PR to the user as is.
- If a sub-agent returns without a usable report (no PR link, no findings, or an error), retry it once with the same prompt; on a second failure drop the task and report it.
- If the user set a budget (time, tasks or tokens), stop picking new tasks once it is reached and let in-flight ones finish; without one, a run ends when the ready tasks run out.

## Report

At the end, one row per task: PR link, risk, final state (merged, ready for the user, blocked and why, dropped and why), rejected findings with their reason, and steps that failed (e.g. approval refused). Then the tasks still waiting on unmerged PRs, and the open questions: first `sdd blockers`, the ones that alone keep a task from starting, with the work waiting behind each; then the rest from `sdd questions` that workers raised during the run, each with the tasks it blocks, so the user can answer them before the next run.
