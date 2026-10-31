# Task Workflow: Answering Open Questions

A session for the user to work through `questions/open/`, one question at a time. The user is often coming from something else, so each question is introduced with just enough to know what it's about, and expanded only on request. The agent presents, records and converts; the user decides.

## Order

Work on current main: in shared mode the session works in a worktree at `origin/main` with `--dir` (see the skill), since the lists below are only as complete as the files they read and each answer is shipped to main as it is made. Start with `sdd blockers`: the questions that alone keep a task from starting, with the work waiting behind each, most first. Then `sdd questions`, which lists the rest by priority: the ones blocking the most tasks first, then the ones linked to the most tasks, then the oldest. Walk those lists top to bottom; if the user names a question, task or ADR (`--task`, `--arch`), use that subset instead. Re-run the list after each question, since answering one can create tasks or questions.

## One question at a time

For each question, in this order, stopping after each step for the user:

1. **Introduce** it in a few lines: its title, where it came from (the linked tasks' titles and states, in words, e.g. "came up while implementing the rate-limit store, which is in progress and waiting on this"), the question itself, and one or two sentences from its Context on why it matters. Nothing else yet: no options analysis, no code, no ADR text. Then ask what the user wants: answer, more context, skip, or stop.
2. **Expand** when asked, progressively: first the full Context section and the assumption taken meanwhile; then, if asked further, the linked task's Goal and acceptance criteria, the linked ADRs' Decision sections, and the code the Context points at. Answer the user's questions about it; this is a conversation, not a briefing.
3. **Record** the answer once the user gives one: write it under `## Answer` in the user's terms, tightened, including the reasoning if they gave one, and show it in a line for confirmation.
4. **Convert** the answer into work or decisions, proposing in one line and acting on a yes:
   - It changes or makes an architecture decision: a new ADR (`sdd adr`), superseding the old one if any, linked from the Answer. Re-planning the affected tasks is the `sdd-planning` skill; say so rather than doing it here, and hold each affected task with a blocking question meanwhile (`sdd ask replan-<slug> --title "Re-plan <slug> after <adr>" --blocks <slug> --arch <adr>`, Context saying what changed), so nobody claims it before the re-plan; a Notes line doesn't keep it out of `sdd ready`.
   - It needs work that no task covers: `sdd new` (tech-debt when it's a follow-up), with `--after` and `--arch` as needed, and a Goal that quotes the answer.
   - It changes what an existing task must do: edit that task's Notes or acceptance criteria, in a line that cites the question.
   - It only unblocks: nothing to convert.
   - It's obsolete (the code moved on, the task was dropped): the Answer says so and why.
5. **Close** it with `sdd answer <slug>` and say which tasks became ready if any (`sdd ready`).
6. **Ship** it, in shared mode: offer in one line to open a PR with this answer and merge it, with "PR only" and "later" as the alternatives. On a yes: `sdd ship --title "Answer <slug>: ..." --body "..." --merge`, the body following `../pull-requests.md` (a few lines quoting the answer and listing what it created); it commits the question's files and whatever the conversion created or edited, opens the PR and merges it, and if GitHub refuses it leaves the PR link to the user. On "PR only": the same without `--merge`. Either way the next question starts on a new branch from `origin/main` (`git fetch origin && git checkout -B answers/<next slug> origin/main` in the worktree), so each PR carries one answer. On "later": stay on the branch; the next Ship offer covers every unshipped answer in one PR. The user's yes is the authorization to merge that PR, no other.

**Defer** is for "decided later, once X exists": `sdd defer <slug> --until <task>...` keeps the question open but out of the default list until those tasks are done, and any requirement the deferral imposes meanwhile goes into the task that must honor it (as `agent-transport` did for its registry). Don't mark such a question answered. **Skip** moves on without changes; the question keeps its place next time. **Stop** ends the session.

## Ending

When the list is empty or the user stops, report in a few lines: questions answered, skipped, tasks and ADRs created, tasks now ready, and the PRs opened or merged. Answers still unshipped get one last Ship offer; if the user declines, push the branch, say its name and leave the worktree in place, since the user has nothing to commit from otherwise. Remove the worktree once nothing unshipped remains on it. In local mode the files are simply updated.
