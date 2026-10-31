# sdd-decisions

A one-line band above the Claude Code prompt for projects that use the task workflow (`sdd` CLI): how many questions are open, the skill that walks through them, and the decision that alone keeps the most work from starting.

```
85 open questions, /sdd-answer-questions to resolve · ⚠ 1 blocks 34 tasks: How should the public routes' rate limit identify a client? (bookings-api)
```

It runs `sdd blockers --json --main` at session start, every minute, and after a `gh pr merge`, `git pull` or `sdd` command the session runs, so it reflects what main has rather than a checkout that may be behind. It shows nothing in a project without the workflow or with no open questions, and no warning when no open question is the only thing holding up a task. Nothing goes through the model: the band is drawn from the command's output alone, and `sdd` must be on `PATH` (the `ai-workflow` installer puts it there).

Install: `plugins/claude-code/install.sh` links this folder into `~/.claude/skills/`, where Claude Code loads it at session start. Develop: `claude plugin validate .`, `claude plugin test .`, and `tsc -p .` once a session has loaded it (that lays the API types under `.claude-plugin/types/`, gitignored).
