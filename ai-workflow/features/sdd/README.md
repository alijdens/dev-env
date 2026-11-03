# sdd: the task workflow


An opt-in, per-project workflow for features too big for one PR. Agents record the design as architecture decision records (ADRs) and split the work into tasks with dependencies, all kept as files, so the reasoning behind the code stays reviewable and several people or agents can work on tasks in parallel without duplicating effort.

It needs `python3` (3.9+) and, for shared mode, `gh` logged in to the repo's GitHub host; `graphviz` (`dot`) is optional, for rendering the dependency graph.

You drive it by asking your agent; the installed skills and the `sdd` CLI do the rest. A typical sequence:

```text
# 1. Once per repo: pick the mode, optionally write the goal and principles
/sdd-setup-task-workflow

# 2. Per feature: design it into a spec, ADRs, rules and tasks (in shared mode, merge its PR)
/sdd-planning add rate limiting to the API

# 3. In a new session: run the tasks, optionally only the path to a target task
/sdd-orchestrate 3 merge=low for=add-rate-limit-middleware

# 4. Answer the open questions: in another session while the run goes on (held PRs pick
#    the answers up), or in the orchestrator's session once it reports
/sdd-answer-questions
```

Step by step:

1. **Set up** a repo once: "set up the task workflow". Pick a mode:
   - **Shared**, for repos you own or collaborate on: the data lives in the repo (or a separate one), and `AGENTS.md` gets a section telling agents about it.
   - **Local**, for repos you don't own: the data lives only on your machine and nothing about the workflow reaches the repo, its commits or its PRs. Agents don't see it until you ask for one of the steps below.

   The agent then offers to write two short project docs, `goal.md` (the problem, the users, what success looks like, non-goals) and `principles.md` (what every change must respect), through a section-by-section interview that keeps them in scope and within a length limit. Both are optional and can be written or revised later ("write the project goal", "the goal changed"); planning and reviews read them so no feature is designed in isolation.
2. **Plan** a feature: `/sdd-planning` or "plan feature X". Called without a feature, it asks whether to plan something new or pick up a recorded idea that is ready. The agent first restates the feature and builds a reading list of what it builds on (`sdd context`: the foundation ADRs, the ADRs and specs in the feature's areas or cited by the code it touches, the tasks that used them, and the questions and ideas on them), confirming it with you. It then proposes the feature's shape, the rules it introduces or must keep, the decisions and the tasks, sized to the feature, and once you agree writes them: a feature spec that every task links and workers settle open details from, ADRs, business rules, and tasks. Business rules are product rules the code must keep whatever feature touches it ("a user posts at most 3 pictures a day"): the same kind of record as ADRs, listed to every planning session whatever its area, and cited from the code that enforces them (`rule: <name>`). ADRs and rules are immutable once accepted (a changed decision or rule is a new record that amends or supersedes the old one); specs describe how things are and are updated by the PRs that change them. Either can end with a short `## Review checks` list, the project-specific things a reviewer verifies on changes in its areas; `sdd checks` collects them per area or task, so a bugfix in one area gets a few checks and a feature across three gets the union, with nothing global beyond `principles.md`. In shared mode this goes to main through a PR before any task starts.
3. **Work** on a task: "work on task X" (or "what tasks are ready?"). The agent claims it, branches and implements, and stops before committing. In shared mode the claim is a PR, so each task has exactly one owner; merge it to let the agent continue.
4. **Finish**: "create a PR for task X" commits the work and opens the PR. When the task data lives in the code repo, merging that PR also marks the task done; with a separate data repo or in local mode, `sdd done X` runs after the merge instead.
5. **Review**: "review the PR for task X". The agent checks the PR against its task and ADRs: scope, unplanned breaking changes, task/ADR references, the task's state after merging, whether the tests actually test the feature, and redundant tests. It reports findings and the PR's risk level without changing anything.
6. **Orchestrate** (optional): the agent runs ready tasks end to end with worker agents: each claims and implements a task, a reviewer agent reviews the PR, the worker applies the feedback, and the orchestrator approves the PR (when GitHub allows it) and merges it if its risk is within the merge policy. Claim PRs are always merged. A PR whose review turns up a decision only you can make is held with a blocking question on main, and resumes once you answer. The run works through the tasks that were on main when it started (tasks marked `needs: user` or similar are left to you) and reports where each ended up. Invoke it as `/sdd-orchestrate [concurrency] [merge=none|low|medium|high|all] [approve=yes|no] [slug...]` (defaults: 1 worker, `merge=none`, `approve=yes`), or the same in words:

   ```text
   /sdd-orchestrate                                  # 1 worker, leave every PR for you to merge
   /sdd-orchestrate 3 merge=low                      # 3 workers, merge low-risk PRs
   /sdd-orchestrate 2 merge=all add-rate-limit-store add-rate-limit-middleware
   orchestrate the tasks with 3 workers, merging up to medium risk
   ```

Follow-ups and shortcuts found along the way become tech-debt tasks. Ideas worth designing later, rather than now, become idea files (`sdd idea`, or ask any session to "record an idea"): never startable, they can wait on tasks (`--after`), `sdd ideas` lists them ready to plan first, and planning sessions find them by area and close them into the tasks and ADRs they became. Open questions become files too (`sdd ask`): each links the tasks and ADRs it concerns and must carry enough context to be answered without the conversation that raised it, and a question that blocks a task keeps it out of `sdd ready` until you answer it. `/sdd-answer-questions` walks you through them one at a time, most blocking first: a few lines on where each came up and why it matters, more on request, then your answer is recorded and turned into tasks or ADRs where it calls for them (`sdd questions` lists them, `sdd blockers` only those that are the only thing holding up a task, with the work waiting behind it, `sdd answer <slug>` closes one). `sdd --help` lists the commands for checking state yourself (`sdd ready`, `sdd list`, `sdd show <slug>`, `sdd brief <slug>` for a task with everything linked to it, `sdd --main ...` to read main instead of your checkout). The agent-facing details are in `docs/`; `docs/lessons.md` records the cases that shaped its checks, for whoever changes them next.

## Parts

- `skills/sdd-*` — the skills above. They hold only triggers and skill-specific instructions and point to `docs/` (rendered as `docs/sdd/`) for the shared ones.
- `docs/` — the agent-facing workflow docs. They reference core's docs (`../planning.md`, `../pull-requests.md`, ...), which are always installed.
- `bin/sdd` — the CLI the skills and docs drive.
- `plugins/claude-code/sdd-decisions` — a Claude Code band with the open questions and the decision holding up the most work ([README](plugins/claude-code/sdd-decisions/README.md)).
- `tests/` — pytest suite for `bin/sdd`, driving it against throwaway git repos and bare remotes.
