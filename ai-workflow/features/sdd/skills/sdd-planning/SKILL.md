---
name: sdd-planning
description: >-
  Designs a feature in a project that uses the task workflow and records it as architecture decisions, tasks and their dependencies.
  Use when the user invokes /sdd-planning or asks to plan or design a feature that breaks up into several steps in such a project, or to plan one of its recorded ideas.
---

# Planning a Feature

## Data root

- If the user gave a directory (e.g. `/sdd-planning ../foo-docs`), pass `--dir <directory>` on every `sdd` command. If it has no task layout yet, ask before creating it with `sdd --dir <directory> init`.
- Otherwise `sdd root` must succeed. If the project isn't set up, stop and ask where the data should live (setting it up is the `sdd-setup-task-workflow` skill).
- Then `sdd stale` must pass: it fails when the data root is behind `origin/main` or has uncommitted changes. `sdd stale --fix` syncs when nothing would be lost; if it keeps changes, ship or ask about them first. Never plan on a stale view (why: `sdd/planning.md`, "Start from main").

## What to plan

If the user named no feature, don't assume one: ask whether to plan something new or pick up a recorded idea, offering the ones ready to plan (`sdd/planning.md`, "Pick what to plan").

## Instructions

Read and follow, in order:

1. [overview.md]({{AI_WORKFLOW_DOCS_DIR}}/sdd/overview.md): the `sdd` CLI, modes and layout.
2. The project's `goal.md` and `principles.md` at the data root, when they exist (`sdd doc list`): the feature is designed to serve the goal within the principles, never in isolation. If a doc is missing or a draft, say so once and continue; writing it is the `sdd-setup-task-workflow` skill.
3. [planning.md]({{AI_WORKFLOW_DOCS_DIR}}/planning.md): how to shape the design.
4. [sdd/planning.md]({{AI_WORKFLOW_DOCS_DIR}}/sdd/planning.md): loading the prior decisions and work the feature builds on (`sdd context`), then turning the design into ADRs, specs, tasks and dependencies.
