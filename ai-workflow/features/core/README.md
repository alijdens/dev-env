# core

The general instructions and what they rely on; always installed.

- `AGENTS.md` — installed as each tool's global instructions file. It references `docs/` through the `{{AI_WORKFLOW_DOCS_DIR}}` placeholder (see the [top-level README](../../README.md)).
- `docs/` — loaded conditionally from `AGENTS.md` (`pull-requests.md`, `planning.md`, `testing.md`, `documentation.md`). Other features' docs reference them, e.g. `../planning.md`.
- `bin/pull-pr-description` — syncs a PR's description into a local file, used by `docs/pull-requests.md`.
- `bin/secrets` — checks whether a secret is set, and where, and lists names across the env and the common env files (one markdown section per source), and prints a value only for piping (the file patterns and what redaction treats as a secret are configurable in `~/.config/secrets-cli/config.json`), so agents never read a secret to find out if it exists; `secrets --help` shows how to call it, and [Configuration](#secrets-configuration) below the settings. Tested by `tests/test_secrets.py`.
- `shell/git-push-reminder.sh` — wraps `git` so a `git push` reminds the agent to update the PR description.
- `plugins/claude-code/pending-items` — a band above the prompt with the decisions and approvals the model is still waiting on ([README](plugins/claude-code/pending-items/README.md)).
- `plugins/claude-code/redact-secrets` — replaces secret values in tool results with `[REDACTED:NAME]` and a note, using `secrets redact` ([README](plugins/claude-code/redact-secrets/README.md)).

## `secrets` configuration

Optional, and meant for people rather than agents (`secrets --help` is only about calling it): a JSON file at `$SECRETS_CONFIG` if set (it must exist), else `$XDG_CONFIG_HOME/secrets-cli/config.json` (`~/.config/secrets-cli/config.json`). Leave out what you don't change; unknown or mistyped settings are an error, not ignored. The defaults:

```json
{
  "files": {
    "include": [".env", ".env.*", ".secrets"],
    "exclude": ["*.example", "*.sample", "*.template", "*.dist", "*.defaults"]
  },
  "redact": {
    "names": ["*SECRET*", "*TOKEN*", "*PASSWORD*", "*PASSWD*", "*PASSPHRASE*", "*CREDENTIAL*", "*APIKEY*", "KEY", "KEY_*", "*_KEY", "*_KEY_*", "PASS", "PASS_*", "*_PASS", "*_PASS_*"],
    "excludeNames": ["*_PATH", "*_FILE", "*_DIR", "*_TTL", "*_LENGTH", "*_PREFIX", "GOOGLE_APPLICATION_CREDENTIALS"],
    "minLength": 6,
    "urlPasswords": true
  }
}
```

- `files.include`: glob patterns, relative to the current directory, of the env files `has`, `list` and `redact` read by default (a path like `config/.env*` works). `--file` is never filtered.
- `files.exclude`: file-name patterns dropped from those.
- `redact.names`: glob patterns (case-insensitive) on the whole variable name; a variable whose name matches has its value redacted. `KEY` and `PASS` are spelled as whole words so `MONKEY` and `KEYBOARD_LAYOUT` don't match; add e.g. `*SALT*`, `*WEBHOOK*` or `*_URL` as needed. Setting it replaces the list.
- `redact.excludeNames`: names that match `names` but hold config, not secrets (`TOKEN_TTL=3600`, or the path in `GOOGLE_APPLICATION_CREDENTIALS`).
- `redact.minLength`: values shorter than this are not redacted, a floor so values like `3600` or `8` aren't replaced everywhere; `0` means no minimum.
- `redact.urlPasswords`: also mask the password of any `scheme://user:password@host` in the text, whatever variable it came from. A `/` in the password, or an `@` in the user, must be percent-encoded.

How `secrets redact` matches, and its limits, are in the [redact-secrets README](plugins/claude-code/redact-secrets/README.md).
