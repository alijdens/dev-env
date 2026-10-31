---
name: sdd-setup-task-workflow
description: >-
  Sets up or updates the task and architecture decision workflow in a repository, and writes or revises its project docs (goal, principles) through a guided interview.
  Use when the user asks to initialize, set up, configure, or update the task workflow in a repo, or to write, review, or update the project's goal or principles.
---

# Setting up the Task Workflow

Read [overview.md]({{AI_WORKFLOW_DOCS_DIR}}/task-workflow/overview.md) for the modes and layout, then pick the mode with the user:

- **Shared** (repos you own or collaborate on): `sdd init [path]`. `path` is relative to the repo root (default `docs`). It creates the layout and adds a section with the `sdd: <path>` line and instructions for agents to the repo's agent file: `--agent-file AGENTS.md|CLAUDE.md` picks it; without the flag it's the file that already has the section, else the first of those that exists, else `AGENTS.md`. Claude Code only loads `CLAUDE.md`, so when the section lands in `AGENTS.md` and the repo is used with Claude Code, tell the user to add a `CLAUDE.md` with an `@AGENTS.md` line (or pass `--agent-file CLAUDE.md`). Pointing `path` at another checkout (e.g. `../project-tasks`) keeps the data in a separate repo, which then has to be cloned at the same relative location on every machine.
- **Local** (repos you don't own): `sdd init --local <path>`, with `path` outside the repo (e.g. `~/task-data/<project>`). It creates the layout there and records it only in the clone's git config; no tracked file changes.

## Project docs

Right after a first `sdd init`, offer to write `goal.md` and `principles.md`, and run the interview in [project-docs.md]({{AI_WORKFLOW_DOCS_DIR}}/task-workflow/project-docs.md) for the ones the user wants. The same doc covers writing a skipped one later and revising an existing one when the goal or the rules change: read it before touching either file, and don't write them any other way.

## Updating

Re-running `sdd init` (or `sdd init --local`) without a path keeps the current one. It recreates missing state directories and their `.gitkeep` files, and in shared mode rewrites the section between `<!-- sdd:start -->` and `<!-- sdd:end -->` in the agent file with the current instructions. Passing a path moves the configuration to it; it doesn't move existing data.


## Verifying

`sdd root` shows the data root and mode; `sdd doc list` the project docs' status; `sdd validate` checks the data.
