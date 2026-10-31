---
name: sdd-answer-questions
description: >-
  Walks the user through the project's open questions one at a time, with just enough context per question, records the answers and converts them into tasks or ADRs.
  Use only when the user invokes /sdd-answer-questions or asks to go through, triage, or answer the open questions of a project that uses the task workflow.
---

# Answering Open Questions

Read and follow, in order:

1. [overview.md]({{AI_WORKFLOW_DOCS_DIR}}/task-workflow/overview.md): the `sdd` CLI, modes and layout.
2. [answering.md]({{AI_WORKFLOW_DOCS_DIR}}/task-workflow/answering.md): the order, the one-question-at-a-time flow, and what to do with each answer.

Don't load the planning, working or reviewing docs. If `sdd root` fails, the project doesn't use the task workflow: say so and stop.

## Where to work

Questions are files that other sessions merge to main, so a checkout that is behind shows fewer of them and may list one that is already answered, and every answer is a change that should reach main as soon as it is made. So in shared mode the session never works in the user's checkout: `git fetch origin`, create a worktree at `../<repo>-worktrees/answers` on a branch `answers/<first question slug>` from `origin/main` (reuse the path if it exists and is clean; otherwise pick a fresh one), and pass `--dir <worktree>/<data root>` on every `sdd` command so all reads and writes happen there. Don't ask the user to pull and don't pull, stash or switch branches in their working copy. Invoking this skill authorizes that worktree and its branches, nothing else; merging a PR needs the user's yes to the Ship step for that PR. Say in one line where the session is working.

In local mode there is nothing to sync or ship: work in place, and skip the Ship step.

If `sdd blockers` and `sdd questions` are both empty, say there's nothing open and stop.
