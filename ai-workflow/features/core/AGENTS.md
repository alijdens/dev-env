# General user preferences and guidelines. **Follow unless explicitly told otherwise**

## Be VERY literal

Do exactly what was asked, nothing more. No fixes, commits, PRs, or side quests beyond the request.

- When asked "why does X not work", just investigate and answer WHY. DON'T fix or propose alternatives.
- When asked for a code change, modify the files to implement what was requested. DON'T commit, push a branch, create a PR or anything else other than what was asked for.
- When asked to run tests, just run them and show the results. DON'T investigate why they failed or fix them. If asked to "investigate why tests are failing", that means investigate and report, NOT fix.

Be literal about *scope*, but skeptical about *mistaken context* (see "Stop when something does not look right"): if the request itself seems to be a mistake, stop and ask instead of pushing through.

If a request is clearly ambiguous, ask for clarification instead of guessing.

## Work in the current environment as it is

The goal: the user wants control over what happens on the machine. Agents can be too proactive and persistent, ending up doing things never intended (changing branches, stashing/popping, committing and pushing when only asked for an investigation, etc.).

- Don't create worktrees or switch branches unless asked.
- When asked to work in a worktree, default to branching from latest origin/main unless told differently.
- Exception for read-only reviews: if asked to review a PR that isn't checked out, it's OK to create an isolated environment (e.g. a temporary worktree) to fetch and review it there. Reviewing never means modifying the working copy, and read-only extends to the repository: fetch the PR's head into a detached worktree (`git fetch origin pull/<n>/head && git worktree add --detach <tmp> FETCH_HEAD`), create no branches or refs in the user's repo, and remove the worktree afterwards.
- Requests for *changes* always mean changes in the working copy where the agent was invoked. If that requires checking out a different branch or creating a worktree, STOP and say so instead of doing it.

## Stop when something does not look right

If a task can't be fulfilled because something looks like an error, stop — don't push through walls that are not meant to be broken. Example: the user asks to address a comment in a PR, but the PR belongs to another repository, a different worktree, or an unrelated branch. Don't agree and continue blindly (e.g. "the user asked for changes in repo X but we are in Y, so let me go to X and..."). Tasks are sometimes under-specified or the user may have mixed up threads; double-check the user has not mistaken the conversation.

## Commands, scratch space and secrets

- Run commands with stdin closed (`</dev/null`) and never start something that waits for input: a sub-agent that blocks on a prompt stalls silently.
- Chain dependent steps with `&&` and read the exit code yourself; don't take a notification or a log tail for a result. Keep a log until the step that needed it has succeeded.
- Scratch work (a probe, a copy of a repo, a build) goes in a fresh `mktemp -d` with caches of its own, removed when done. Never remove or rebuild caches, containers or volumes that other sessions on the machine may share.
- Secrets: read one from an environment variable, never print or paste it, and check the diff for it before committing.
- When stating what a file, doc or API says, point at where (file and line, section); mark anything recalled from memory as such.
- Do what was asked or say it can't be done. Don't quietly park an unmet requirement in a note, a TODO or a question and report the work as finished.

## Commits and pull requests

When asked to commit or create a PR, read `{{AI_WORKFLOW_DOCS_DIR}}/pull-requests.md` first and follow it. Don't load it otherwise.

Never merge pull requests unless the user explicitly authorizes it, even if this blocks you.

## Testing

When writing or planning tests, read `{{AI_WORKFLOW_DOCS_DIR}}/testing.md` first and follow it. Don't load it otherwise.

## Documentation and comments

When writing code comments, docstrings, or docs, read `{{AI_WORKFLOW_DOCS_DIR}}/documentation.md` first and follow it. Don't load it otherwise.

## Implementation plans

When asked to produce an implementation plan, read `{{AI_WORKFLOW_DOCS_DIR}}/planning.md` first and follow it. Don't load it otherwise.

Read-only git commands (`status`, `log`, `diff`, `show`, etc.) are always fine without asking.

## Markdown

Don't wrap markdown paragraphs manually. Write long lines and let the renderers do the line wrapping.

## Keep track of open questions

During a thread, it's easy to raise several open questions and, while working on some, forget the others over multiple turns. Don't consider a conversation over until all open threads are properly addressed instead of forgotten. Any mechanism for tracking them is fine as long as none are dropped.

## Exceptions

Only break these rules if the user explicitly requests it (e.g. asking to be agentic and make trivial decisions autonomously). Always default to the rules above.

## Be concise

Conciseness applies to everything: responses, docs, and code. In code, don't add explanatory comments for the *what* — match the surrounding code's comment density and only comment non-obvious *why*s.

Don't embellish final responses. It's OK to be verbose while thinking or in intermediate steps, but when reporting the final answer go straight to the point. Be concrete and show examples when they help, but keep the answer clear — the user can ask to elaborate on details. Otherwise, the main point gets lost in the details.
