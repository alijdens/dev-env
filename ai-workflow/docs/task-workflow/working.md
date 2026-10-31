# Task Workflow: Working on a Task

The claim exists to prevent duplicated effort, so it is a prerequisite of working on a task:

- "Work on task X" means claim it (including its claim PR in shared mode), branch, and implement. Stop there: don't commit or open the implementation PR.
- "Create a PR for task X" means all of the above, plus finishing it (step 6).
- "Can you claim task X?" is a question: answer it, take no action.

## Claims in shared mode

`sdd start <slug>` re-checks on the remote main that the task is `todo`/`tech-debt` with all prerequisites done, then opens a claim PR (branch `claim/<slug>`, not a draft) that moves it to `in-progress` and stamps a unique `claimed:` field. It runs in a throwaway worktree, so a dirty checkout doesn't matter. A second claim of the same task fails to push the same branch while the first PR is open; if it gets through anyway, its PR conflicts with main once the first claim merges. So main shows exactly one owner per task.

The claim PR must be merged before implementing. Unless authorized to merge it, give the user the PR link and wait.

## Steps

1. **Pick.** If the user didn't name a task, `sdd ready` lists the ones whose prerequisites are done. It reads your checkout, which may be stale; `sdd start` re-checks against the remote main.
2. **Load context.** `sdd brief <slug>` prints the task's state, prerequisites and dependents, then the task file, its ADRs and specs and the questions linked to it, in full (answered questions may settle something the task file predates). Read it instead of opening those files one by one. When the Notes don't say what a prerequisite delivered, read that task's file too. Nothing else from the task data: if the task seems to need an ADR that isn't linked, that's a planning gap; link it with `sdd link <slug> --arch <adr>` and say so in the PR.
3. **Claim.** `sdd start <slug>`. If it fails or its PR conflicts with main, someone else got the task first: close the PR if there is one, report it, and don't work around it. In local mode it just moves the file. When merging the claim is authorized (an orchestrated run, or the user said so), `sdd start <slug> --merge --branch` also merges the claim PR and does step 4; it refuses if GitHub won't merge yet or the checkout has uncommitted changes.
4. **Branch.** Once the claim is on main, implement in a branch named `<slug>` created from the remote main (`git fetch` first). If the working copy has uncommitted changes, ask before switching branches. The branch name is the one place the slug appears in local mode too: slugs read as ordinary branch names, and it's how a reviewer finds the task.
5. **Implement** against the task's acceptance criteria.
   - **Code references** tell a reader which ADR to load for the full reasoning, instead of a long comment block or nothing at all. Add one only where the code's shape follows from a decision a reader would otherwise question: a one-line reason plus the ADR, e.g. `# Limits are per API key, not per user (adr: 2026-10-12-rate-limit-strategy)`. Use `task: <slug>` only for context specific to a task rather than a lasting decision (e.g. a temporary shim until another task lands). Don't tag code just to mark that it changed: blame plus the PR links cover provenance.
   - If an important decision comes up, add an ADR (`sdd adr`) and list it in the task's `arch:` frontmatter.
   - Out-of-scope follow-ups or shortcuts become `sdd new <slug> --tech-debt --title "..."`.
   - When the task or its ADRs leave something open that you'd otherwise guess, don't guess silently and don't leave it in chat: `sdd ask <slug> --title "..." --task <this task>` and fill in Question and Context (see `overview.md`), including the assumption you went on with. If you can't proceed without the answer, add `--blocks <this task>`, stop, and tell the user. If it decides how a dependent task must be built, `--blocks` that task instead. The question file rides in the implementation PR. A question is for something only the user can decide; a fix you could just make (a missing link, a typo in a doc) is a tech-debt task or part of the PR, not a question.
   - If the change alters how something described in a spec works, update that spec in the same PR; specs are kept current by the PRs that change them. Before the PR, `sdd checks --task <slug>` prints what the reviewer will verify in the task's areas. ADRs are never edited (see `overview.md`): a decision the task can't follow is a question.
   - If the task needs re-planning (split, new dependencies), stop and tell the user: planning changes go to main first.
   - If the change alters a port or interface that another todo task is planned to implement, that task's criteria change on main too (a small planning PR), not only in this PR: the reviewer checks it.
   - Notes added to the task file may record what was built, but they don't settle a choice: anything they introduce that the criteria or ADRs don't cover is still a question.
6. **Finish** (only when asked for the PR). Run `sdd validate`, then commit and open the PR following `../pull-requests.md`, with the slug in the title and links to the task file and its ADRs in the description. When the task is marked done depends on where the data lives, because dependents become ready the moment it is:
   - Data in the code repo (the usual shared setup): `sdd done <slug>` on the branch before committing, so merging the PR is what marks the task done.
   - Separate data repo or local mode: the task stays `in-progress` until the PR merges. Whoever merges it (the user, or the orchestrator) then runs `sdd done <slug>`, which opens a PR in the data repo, or just moves the file in local mode. Say so in the PR description in the separate-repo case.
7. **Abandon.** `sdd release <slug>` (add `--tech-debt` to park it there) opens a release PR moving it back, so someone else can pick it up.

In local mode, none of the code, commits or PRs mention task slugs, ADRs or the workflow, the branch name aside: skip code references and the slug/links in step 6.
