# Task Workflow: Reviewing a Task's PR

A review checks that a PR delivers its task as planned, and nothing else. It is read-only: report the findings, and don't fix, comment on, approve or merge the PR unless asked. If the PR isn't checked out, fetch it into a temporary worktree instead of switching the working copy. Read-only extends to the machine: don't remove or rebuild caches, containers or volumes that other agents' checks share; a probe you need to run goes in a scratch copy with a cache of its own.

When a check below is added or changed because something slipped through a review, the case goes in `lessons.md`, so the reason survives the edit.

## Load context

1. Find the task: the PR's branch is named after its slug, and in shared mode the title carries it too. If neither matches a task, ask instead of guessing.
2. `sdd brief <slug> --review`, on the PR's branch so what the PR added counts, prints in one go: the task's state, prerequisites and dependents; the task file, its ADRs and specs and the questions linked to it, in full; `goal.md` and `principles.md` when they exist; the dependents' task files (see "Dependents can build on it"); and the project's review checks (`sdd checks --task <slug>`). Read it instead of opening those files one by one.
3. Read the PR description and the full diff against the base branch.
4. If the diff touches an area outside the task's ADRs and specs (`sdd areas`), add its checks with `sdd checks --area <area>`.

## Checks

### Scope matches the task

- Every acceptance criterion is met by the diff, not just claimed in the description.
- Every behavioral claim in the PR description, and every guarantee the task's Goal or an ADR states in words ("verified", "single-use", "never returned", "bounded"), is checked against the diff too: it maps to an observable artifact (a column, a flag, a response field, a code path with a test) or it is a finding. The criteria are the minimum, not the whole promise.
- For each bound or limit the task, an ADR or the description claims (a max depth, a retry count, "queries bounded by ..."), find the test that exercises it at and past the boundary, and check what cached or memoized state the error path leaves behind: a bound that errors but keeps the work going isn't a bound.
- Anything the diff does beyond the task's goal is flagged: unrelated refactors, extra features, drive-by fixes. Out-of-scope follow-ups belong in tech-debt tasks (`sdd new <slug> --tech-debt`), not in the PR.
- Implementation choices contradicting an ADR are flagged. Changing a decision needs a new ADR, not a quiet deviation, and not a question that leaves the code as is.
- ADRs whose decisions the diff's shape follows from are linked in the task's `arch:` (`sdd context --grep` on the diff's key terms finds candidates). A missing link is a planning finding, fixed with `sdd link`.
- The PR doesn't edit an accepted ADR's body (`sdd validate` fails on it); errata lines and new ADRs with `--amends`/`--supersedes` are the only ways to change one. Specs the change affects are updated in the PR and listed in the task's `spec:`.

### Serves the goal, respects the principles

Only when `goal.md` and `principles.md` exist (`sdd doc list`); say which were absent otherwise.

- The PR doesn't work against a non-goal or build toward something the goal excludes. A task that does is a planning finding, not the implementer's fault, but it is still flagged.
- Every principle the diff touches is respected. Cite the principle's line for each violation; a change that needs an exception needs an ADR, not a reviewer's blessing. Principles about what data reaches whom (a model, a log, a client) apply to list and read endpoints too, not only to the operation that creates the data: a token or contact detail in every row of a listing is sent on every listing.

### Project review checks

Each bullet `sdd checks` printed is verified against the diff like an acceptance criterion, and reported by the ADR or spec it comes from. A check the diff can't meet because the decision no longer fits is a finding, not a reason to skip it: the fix is a new ADR.

When something slipped through a review and a project-specific check would have caught it, add the bullet to the `## Review checks` of the ADR or spec it belongs to (an accepted ADR takes that edit), the way `lessons.md` does for these generic checks. A check that doesn't fit any ADR or spec's areas is a sign the rule is a principle, or the thing needs a spec.

### No unplanned breaking changes

Flag only changes that aren't backwards compatible; additive changes (a new optional field, a new endpoint) are fine. Rate each one by what it breaks:

- **Database** (high): schema or data changes need a migration that loses no data and works with the code that is still deployed while it runs (e.g. add a column, backfill, switch reads, drop later, not a rename in one step). A migration that runs statements outside a transaction must be safe to re-run if the process dies before the version is recorded.
- **Public API** (critical): endpoints, SDKs or libraries used by clients you don't control. Removed or renamed fields, changed types, response shapes or status codes break them on deploy; they need versioning or a deprecation period.
- **Internal API** (low): interfaces only used inside the project, when the PR updates every consumer in the same change. Raise it to high when consumers deploy separately and the old and new versions overlap (e.g. services, workers, mobile apps).
- **Persisted or exchanged formats** (high): files, caches, queue messages or events that old and new code read or write side by side, so it needs to read both or migrate. A model or schema defined in code (an authorization model, a config shape) counts when rows written under the old one stay in the database: say what a check or read does with them.
- **CLI, config and env vars** (medium): removed or renamed flags, keys or variables, and changed defaults, break scripts and deployments without any error at build time.
- **Behavior** (medium): same interface, different semantics that callers rely on (ordering, error handling, defaults, side effects).

For each one, say whether the task or an ADR plans it, and whether the PR includes what it needs (migration, versioning, deprecation, updated consumers). An unplanned breaking change is a finding at its category's severity, even if it looks harmless.

### Authentication and authorization hold up

Only when the diff touches authentication, authorization, sessions, tokens or secrets; say so when it doesn't. The risk level already rates these PRs `high`; this check is what earns it, and it is done by walking the code, not by reading the tests.

- **Trust boundaries.** List each claim the code takes from outside (a provider's verified-email flag, a token's subject, a header, a role in a request body), what validates it, and what happens when it is missing, empty or duplicated. An identifier the code relies on to be present or unique is checked, not assumed.
- **Settings that gate trust** (a `trust...` flag, an allowlist): what happens to rows persisted while the setting was off once it is turned on. A row recorded under weaker rules must not become a link, grant or login target under stronger ones unless the row carries how it was proven.
- **Hand-written checks.** A handler or service that branches on the principal's id, or on a role in the request, to decide access instead of using a declared permission is flagged unless an ADR or a recorded question covers it. Note that such a check fails at runtime on a typo, where declared permissions fail at startup.
- **Concurrent writes.** For each multi-statement write transaction that deletes or replaces an object together with its derived rows (tuples, grants, caches, projections), walk the statement order against one concurrent insert on an MVCC engine, not only on a single-writer database, unless the project's principles let it rely on the single writer. The row that holds the lock goes first.

### Dependents can build on it

`sdd show <slug>` lists the tasks that depend on this one; read their acceptance criteria and, for each, name the primitive in this PR it will call. Flag:

- Logic a dependent would have to copy: a projection (row to tuple), a validation, an upsert kept unexported, or one already built in two places.
- An operation a dependent must compose into one transaction with its own writes, offered only as a self-contained call with no transaction-taking variant.
- A return type or interface with no room for what a dependent must add (a bare principal where scopes or an origin will be needed): an additive result struct now saves changing every implementation later.
- A response a dependent UI or agent will act on that doesn't carry the outcome it needs (a failed delivery answered as success, a retry that reports the previous attempt's timestamp).
- A port or interface another todo task implements, changed by this PR without that task's criteria updated on main (see `orchestrating.md`, scope changes).

### References

In shared mode:

- The PR title has the slug, and the description links the task file and its ADRs (see `../pull-requests.md`).
- ADRs added by the PR are listed in the task's `arch:` frontmatter.
- Code references follow the rule in `working.md`: an `adr:` or `task:` reference is required where the code's shape follows from a decision a reader would otherwise question, and is noise anywhere else. Flag both missing and gratuitous ones, and check that each referenced ADR or task exists.

In local mode it is the opposite: flag any mention of task slugs, ADRs or the workflow in code, commits, branch-external docs or the PR title and description. The branch name is exempt: it is the slug by design (see `working.md`).

### Task state

A task left in the wrong state blocks the workflow: a task stuck in `in-progress` after its PR merges keeps its dependents from ever becoming ready, and one marked done too early lets them start on missing work. So check what main will look like once the PR merges:

- Data in the code repo: the PR moves the task from `in-progress` to `done/<date>` (`sdd done <slug>`) and touches no other task's state. It doesn't change the task's own definition either (Goal, acceptance criteria, prerequisites): a scope change belongs on main before the implementation (see `orchestrating.md`), so a definition edited inside the PR means the plan on main and the code disagree. Flag it, and check the implementation against the task as main has it.
- Notes the PR adds to its own task may record what was built. A choice they introduce that the criteria, an ADR or an answered question don't settle (a status code, a filter, a stricter rule) is still an unrecorded assumption (see "Questions stand alone"); writing it in the Notes doesn't settle it.
- Separate data repo: the PR can't carry the move, so the task is still `in-progress` and the description says `sdd done` follows in the data repo once this PR merges.
- Local mode: the task is `in-progress` until the PR merges, not still `todo` or already in another state.
- `done` is only right if every acceptance criterion is met. If some are deliberately left out, the remaining work must be a new task (tech-debt, or a planned task with the right dependencies) instead of a silently incomplete one, and the done task's file says in a dated line where each criterion went, so it doesn't claim work its PR didn't do. A criterion the code contradicts, recorded only as an open question, is not met.
- New tasks the PR adds (e.g. tech-debt) have their prerequisites set, and `sdd validate` passes on the branch.
- `sdd ready` on the branch lists the dependents this task was blocking, once their other prerequisites are done.

### Questions stand alone

`sdd validate` already fails on empty sections and dangling links; the reviewer checks what it can't:

- Every question the PR adds can be answered by someone who wasn't in the conversation: the Context says where it came up, why it matters, and what was assumed meanwhile. "See discussion" or a bare option list is a finding.
- Choices the PR made that neither the task, an ADR nor an answered question settles are flagged as unrecorded assumptions; the fix is to record them with `sdd ask`, not to ask in the review. When an ADR names a reference system or semantics (OpenFGA, OAuth, a standard), being stricter or looser than it is such a choice.
- A question marked answered whose answer changes a decision has a new ADR linked from its Answer.
- Nothing in the PR is blocked by an open question (`sdd show <slug>` on the branch): if the implementation went ahead anyway, say whether the assumption it took is cheap to reverse.

### Tests test the feature

For each new or changed test, ask whether it would fail if the feature were broken. Flag tests that wouldn't:

- The unit under test is itself mocked, or the mocks are configured to return the result the test then asserts.
- Assertions only check that a mock was called, where the actual output or effect is observable.
- No meaningful assertion: only "doesn't raise", truthiness, or a snapshot nobody would read. The mirror image counts too: an assertion that only checks "some error" where a specific one is expected, so a failure for the wrong reason passes.
- They pin implementation details (private calls, call order) instead of behavior, so they break on refactors and miss real bugs.
- A parameter chosen below the limit under test (a fan-out of 10 for a depth limit of 25): the test's name claims a property it never exercises.
- A concurrency test that doesn't deterministically reach the race branch (goroutines that may all take the fast path), or that can't distinguish the claim from the naive implementation on the test database. The latter is acceptable when the test's comment says so instead of implying proof.
- An invariant test that asserts the primary rows but not the derived ones the invariant covers (projections, tuples, caches), so an orphan passes.
- A route that declares a permission is tested only with a principal that has everything and one that has nothing: that can't tell routes apart, so a wrong declaration passes. Each declared permission needs a denial from a principal that holds the neighbouring permissions but not that one.
- A wait on real time: a sleep, a polling loop, or a timeout that the test depends on to pass, including a raised timeout as the fix for a flake. Following `../testing.md`, the fix is a fake clock, resolving the deferred work up front, or an event the mocked job signals; a timeout is only acceptable as a guard against hanging the run.

Also flag acceptance criteria and error paths with no test at all, when they're testable at a reasonable cost, and:

- A migration that rebuilds a table without a test asserting every index, trigger and constraint is back.
- An assumption recorded in a question the PR adds with no test pinning it, so the answer can't be applied by changing a test.
- Wiring in the composition root (main, the DI container) that a wrong value would silently defeat (a provider name that never matches, a feature that never fires), with no test through it.

### Redundant tests

Following `../testing.md`, flag tests, new or existing, that can be removed or merged:

- The same behavior tested at several layers, when the upper layer should only check the wiring.
- New tests duplicating existing ones.
- Near-identical cases that should be one parametrized test.
- Existing tests made obsolete by the change, like ones for removed behavior or superseded by better new ones.

## Re-reviews

A round after fixes comes with the commit range of the fixes and the findings decided so far. Verify that each accepted finding is fixed, review the changed hunks with the checks above, and re-run `sdd validate`; don't re-review code the round didn't touch, and don't raise what was rejected. New findings are for regressions and for what the fixes introduced. The report still ends with the risk level, rated on the PR as it now stands.

## Report

List the findings grouped by check, most severe first, each with its file and line, what's wrong and a concrete suggestion. Say explicitly which checks passed, and which couldn't be done (e.g. the task can't be found), instead of leaving them out.

End with the PR's risk level (`low`, `medium`, `high` or `critical`) and a one-line reason. It rates how bad it would be if the PR as it stands had a bug that slipped through, so open findings raise it and fixed ones don't count:

- The highest breaking change severity, whether planned or not: a planned DB migration is still `high`.
- At least `high` for changes to authentication, authorization, payments, secrets, infrastructure or deletion of data.
- Otherwise `low` for changes that are small, well tested and easy to revert, and `medium` for the rest.
