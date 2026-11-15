# A plan's tasks are dry-run before the plan ships

## Intent

Find out before any code is written whether a task can be built from what it links, and how much of that it needs.

## Decision

Before a plan ships, a sub-agent that wasn't in the planning session gets only a task's brief and the code, works out how it would build and test each acceptance criterion without writing code, and reports what it needed that the brief didn't say, which parts it never used, and what contradicts the code. An undecided design choice goes back to the user and into the task; an unused part is a link to drop.

## Alternatives considered

- **Find the gaps while implementing.** Each one is then a question that holds a PR, or a guess a review has to catch.
- **Check a plan by reading it.** The five tasks tested had all been planned and read; each still had a choice nobody had made, such as a response type returned by four operations where the task named two.

## Consequences

- It costs one sub-agent per task tested, so it is for the tasks others wait on first.
- The same run measures a change to the workflow: it is how the narrowed review checks were evaluated.
