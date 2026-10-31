# Claude Code plugins

Plugins that hook into Claude Code's interface itself (bands, panes, status line entries), as opposed to skills, which the model reads. Each lives in its own directory with a `.claude-plugin/plugin.json` manifest, a `hooks/` module and a README; see the `plugin-authoring` skill bundled with Claude Code for the API.

`./install.sh` symlinks every plugin here into `~/.claude/skills/`, where Claude Code loads plugins at session start and reloads them when their files change; `./install.sh --uninstall` removes the links. The top-level `ai-workflow/install.sh` offers this step when installing for Claude Code.

- [`sdd-decisions`](sdd-decisions/README.md): a band above the prompt with the task workflow's open questions and the decision holding up the most work.
- [`pending-items`](pending-items/README.md): a band above the prompt with the decisions and approvals the model is still waiting on from you, kept by the model through two tools; independent of the task workflow.
