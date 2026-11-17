# core

The general instructions and what they rely on; always installed.

- `AGENTS.md` — installed as each tool's global instructions file. It references `docs/` through the `{{AI_WORKFLOW_DOCS_DIR}}` placeholder (see the [top-level README](../../README.md)).
- `docs/` — loaded conditionally from `AGENTS.md` (`pull-requests.md`, `planning.md`, `testing.md`, `documentation.md`). Other features' docs reference them, e.g. `../planning.md`.
- `bin/pull-pr-description` — syncs a PR's description into a local file, used by `docs/pull-requests.md`.
- `bin/secrets` — checks whether a secret is set, and where, and lists names across the env and the common env files (one markdown section per source), and prints a value only for piping (the file patterns and what redaction treats as a secret are configurable in `~/.config/secrets-cli/config.json`), so agents never read a secret to find out if it exists; `secrets --help` documents it. Tested by `tests/test_secrets.py`.
- `shell/git-push-reminder.sh` — wraps `git` so a `git push` reminds the agent to update the PR description.
- `plugins/claude-code/pending-items` — a band above the prompt with the decisions and approvals the model is still waiting on ([README](plugins/claude-code/pending-items/README.md)).
- `plugins/claude-code/redact-secrets` — replaces secret values in tool results with `[REDACTED:NAME]` and a note, using `secrets redact` ([README](plugins/claude-code/redact-secrets/README.md)).
