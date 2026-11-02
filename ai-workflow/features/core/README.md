# core

The general instructions and what they rely on; always installed.

- `AGENTS.md` — installed as each tool's global instructions file. It references `docs/` through the `{{AI_WORKFLOW_DOCS_DIR}}` placeholder (see the [top-level README](../../README.md)).
- `docs/` — loaded conditionally from `AGENTS.md` (`pull-requests.md`, `planning.md`, `testing.md`, `documentation.md`). Other features' docs reference them, e.g. `../planning.md`.
- `bin/pull-pr-description` — syncs a PR's description into a local file, used by `docs/pull-requests.md`.
- `shell/git-push-reminder.sh` — wraps `git` so a `git push` reminds the agent to update the PR description.
- `plugins/claude-code/pending-items` — a band above the prompt with the decisions and approvals the model is still waiting on ([README](plugins/claude-code/pending-items/README.md)).
