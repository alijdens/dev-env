# A task reads as little as it needs

## Intent

The user: "the criteria to split documentation is that it minimizes what details are read on a task on average. For example, a backend task should have little to no data about frontend. A task unrelated to permissions should not load the full inner workings on permissions. A task that uses permissions should ideally load only high level info."

## Decision

- What matters is a doc's cost across tasks, its size times the tasks that load it, not its length. `sdd cost` lists docs by that, with the median brief.
- A task links a spec it changes with `spec:` and gets all of it; it links a component it only relies on with `uses:` and gets the spec's Summary.
- A doc is split when most tasks that load it need only part of it, along who reads it: by area, and by using versus changing a component.
- A long doc that few tasks load is left alone.

## Alternatives considered

- **A size limit per file.** It splits docs nobody loads and leaves alone a short record that sixty tasks load.
- **Let the worker open what it wants.** Then nothing says what a task depends on, and reviewers can't tell what the worker knew.
