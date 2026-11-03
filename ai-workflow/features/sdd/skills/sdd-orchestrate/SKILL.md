---
name: sdd-orchestrate
description: >-
  Runs ready tasks from the project's task workflow backlog end to end with worker and reviewer sub-agents: claim, implement, review, fix, approve and, depending on the merge policy, merge.
  Use when the user invokes /sdd-orchestrate or asks to orchestrate or autonomously work through the tasks of a project that uses the task workflow.
---

# Orchestrating Tasks

## Inputs

`/sdd-orchestrate [concurrency] [merge=none|low|medium|high|all] [approve=yes|no] [for=<slug>] [slug...]`, or the same in words (e.g. "orchestrate with 3 workers, merge up to medium risk, without approving", "orchestrate the fastest path to <slug>"). Defaults: concurrency 1, merge `none`, approve `yes`, the tasks on main when the run starts, no target. Confirm the parsed inputs back to the user in one line before starting; if the merge policy is unclear, ask.

Invoking this skill is the user's explicit authorization, under the general "never merge PRs unless authorized" rule, to merge claim and release PRs and the implementation PRs the merge policy allows, to ship the planning changes `orchestrating.md` has the run make (scope changes, held questions), and to create worktrees for the run. It authorizes nothing beyond that.

## Instructions

Read and follow, in order:

1. [overview.md]({{AI_WORKFLOW_DOCS_DIR}}/sdd/overview.md): the `sdd` CLI, modes and layout.
2. [orchestrating.md]({{AI_WORKFLOW_DOCS_DIR}}/sdd/orchestrating.md): the inputs, loop and report.

Workers and reviewers load their own docs through their skills; don't load `working.md`, `reviewing.md` or the planning docs.
