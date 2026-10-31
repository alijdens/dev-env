# pending-items

A one-line band above the Claude Code prompt with what the model is still waiting on from you: approvals ("merge PR 214?"), choices between options, a go-ahead it asked for. In a long session those questions scroll away and the conversation moves on; the band stays until each item is resolved.

```
⚑ 2 waiting on you: Approve merging PR 214 +1 more · /pending
```

The model keeps the list itself. The plugin adds a short section to the system prompt telling it to call the `add` tool when it asks for a decision or approval that work waits on or that is hard to reverse, and `resolve` once you answered or the item no longer applies. Routine clarifications don't go in. `/pending` lists the items, `/pending done <id>` resolves one, `/pending clear` drops them all. The items live in the session's state, so a hot reload keeps them; nothing is written to disk and nothing depends on any project tooling.

Install: `plugins/claude-code/install.sh` links this folder into `~/.claude/skills/`, where Claude Code loads it at session start. Develop: `claude plugin validate .`, `claude plugin test .`, and `tsc -p .` once a session has loaded it (that lays the API types under `.claude-plugin/types/`, gitignored).
