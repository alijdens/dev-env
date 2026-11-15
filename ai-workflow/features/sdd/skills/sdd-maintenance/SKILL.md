---
name: sdd-maintenance
description: >-
  Shrinks what accumulates in a project's task workflow data, one item at a time with the user: restates ADRs that collected amendments or exceptions from what they are for, retires records that hold details and review checks that tests already enforce, deletes finished feature specs, trims specs that restate the code, closes stale open questions and fixes broken links.
  Use when the user invokes /sdd-maintenance or asks to restate or consolidate ADRs, clean up or maintain the task data, or act on the warnings `sdd validate` prints about them.
---

# Maintaining the Task Data

Read and follow, in order:

1. [overview.md]({{AI_WORKFLOW_DOCS_DIR}}/sdd/overview.md): the `sdd` CLI, modes and layout.
2. [maintenance.md]({{AI_WORKFLOW_DOCS_DIR}}/sdd/maintenance.md): the items, their order and how to do each.
3. For stale questions only, [answering.md]({{AI_WORKFLOW_DOCS_DIR}}/sdd/answering.md), "Stale questions" and its Ship step.

If `sdd root` fails, the project doesn't use the task workflow: say so and stop. If the user named an item (an ADR, an area), start there.

## Where to work

In shared mode the session never works in the user's checkout: `git fetch origin`, create a worktree at `../<repo>-worktrees/maintenance` on a branch `maintenance/<first item>` from `origin/main` (reuse the path if it exists and is clean; otherwise pick a fresh one), and pass `--dir <worktree>/<data root>` on every `sdd` command. Don't pull, stash or switch branches in the user's working copy. Invoking this skill authorizes that worktree and its branches, nothing else; merging a PR needs the user's yes to the Ship step for that PR. Say in one line where the session is working.

In local mode there is nothing to sync or ship: work in place.
