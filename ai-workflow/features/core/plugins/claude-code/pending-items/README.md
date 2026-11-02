# pending-items

A one-line band above the Claude Code prompt with what the model is still waiting on from you: approvals ("merge PR 214?"), choices between options, a go-ahead it asked for. In a long session those questions scroll away and the conversation moves on; the band stays until each item is resolved.

```
⚑ 2 waiting on you: Approve merging PR 214 +1 more · /pending
```

The model keeps the list itself. The plugin adds a short section to the system prompt telling it to call the `add` tool when it asks for a decision or approval that work waits on or that is hard to reverse, and `resolve` once you answered or the item no longer applies. Routine clarifications don't go in. `/pending` lists the items, `/pending work` puts a prompt in the input box that has the model go through them with you one at a time, oldest first, `/pending done <id>` resolves one, `/pending clear` drops them all.

The items belong to the session: they're kept in its state and in the plugin's store under the session id, so a hot reload keeps them and `claude --resume` brings them back. `/clear` deletes them, since the model loses the context they were raised in. The store forgets a session once its list is empty, once it's untouched for 30 days (Claude Code's default transcript retention, past which it can't be resumed anyway), and beyond the 50 most recently updated sessions.

Install: `ai-workflow/install.sh` renders this folder into `.rendered/plugins/claude-code/` and links it into `~/.claude/skills/` with every Claude Code install; Claude Code loads it at session start. Develop: `claude plugin validate .` and `claude plugin test .`; `tsc -p .` needs the API types Claude Code lays under `.claude-plugin/types/` (gitignored) of the copy it loads, i.e. the rendered one, so run it there or copy them over.
