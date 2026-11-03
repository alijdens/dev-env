# pending-items

A one-line band above the Claude Code prompt with what the model is still waiting on from you: approvals ("merge PR 214?"), choices between options, a go-ahead it asked for. In a long session those questions scroll away and the conversation moves on; the band stays until each item is resolved.

```
⚑ 2 items waiting on you: Approve merging PR 214 +1 more · /pending
```

The model keeps the list itself. The plugin adds a short section to the system prompt telling it to call the `add` tool when it asks for a decision or approval that work waits on or that is hard to reverse, and `resolve` once you answered or the item no longer applies. Routine clarifications don't go in. An item is one line, plus an optional `context` the model writes for itself: the options and what's at stake, so it can take the item up again after a compaction or a resume. The `list` tool gives it the items with their context; the prompts `/pending` sends point it there rather than repeating them. `/pending` opens a picker with the items: pick one to work on it with the model, or "All, one at a time" to have it go through them with you oldest first; either sends the prompt at once. Where no pane can be shown, it lists them instead. `/pending all` goes straight to all of them, `/pending done <id>` resolves one, `/pending clear` drops them all.

The items belong to the session: they're kept in its state and in the plugin's store under the session id, so a hot reload keeps them and `claude --resume` brings them back. `/clear` deletes them, since the model loses the context they were raised in. The store forgets a session once its list is empty, once it's untouched for 30 days (Claude Code's default transcript retention, past which it can't be resumed anyway), and beyond the 50 most recently updated sessions.

Install: `ai-workflow/install.sh` renders this folder into `.rendered/plugins/claude-code/` and links it into `~/.claude/skills/` with every Claude Code install; Claude Code loads it at session start. Develop: `claude plugin validate .` and `claude plugin test .`; `tsc -p .` needs the API types Claude Code lays under `.claude-plugin/types/` (gitignored) of the copy it loads, i.e. the rendered one, so run it there or copy them over.
