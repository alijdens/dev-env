# sdd-decisions

A one-line band above the Claude Code prompt for projects that use the task workflow (`sdd` CLI): how many questions are open, the skill that walks through them, and the decision that alone keeps the most work from starting.

```
85 open questions, /sdd-answer-questions to resolve · ⚠ 1 blocks 34 tasks: How should the public routes' rate limit identify a client? (bookings-api)
```

It runs `sdd blockers --json --main` at session start, every minute, and after a `gh pr merge`, `git pull` or `sdd` command the session runs, so it reflects what main has rather than a checkout that may be behind. It shows nothing in a project without the workflow or with no open questions, and no warning when no open question is the only thing holding up a task. Nothing goes through the model: the band is drawn from the command's output alone, and `sdd` must be on `PATH` (the `ai-workflow` installer puts it there).

Install: `ai-workflow/install.sh` renders this folder into `.rendered/plugins/claude-code/` and links it into `~/.claude/skills/` when the `sdd` feature is installed for Claude Code; Claude Code loads it at session start. Develop: `claude plugin validate .` and `claude plugin test .`; `tsc -p .` needs the API types Claude Code lays under `.claude-plugin/types/` (gitignored) of the copy it loads, i.e. the rendered one, so run it there or copy them over.
