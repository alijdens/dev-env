# A brief carries the checks of what its task links, and a check is a test not yet written

## Intent

Review checks should not be what every worker reads. The user: "Review checks could be part of the tasks so the spec remains light? They should probably be tests later."

## Decision

- `sdd brief` and `sdd checks --task` print the checks of the records and specs the task links, and none by area. A reviewer adds the checks of the areas the diff touches.
- What a test can hold is an acceptance criterion of the task that builds it, and the suite keeps it from then on. A standing check on a record is for what only a reader can judge.
- A check that applied and that the worker couldn't have known of is a planning finding, a missing link, not the implementer's.

## Alternatives considered

- **Every check in every area of every linked record** (what it was). In five real briefs, checks were 40% of the bytes and 7% of the bullets applied.
- **Checks only in the task that introduced them.** The next task in the same area would not see them, so this holds only for what has become a test.

## Consequences

- The wide listing had been covering for tasks that didn't link what governs them. On one of two tasks re-tested after the change, a worker would have broken three checks of a record its task should have linked. Planning's dry run is what catches that now.
