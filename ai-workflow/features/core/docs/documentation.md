# Documentation and Comments

These are general preferences; a repository's own docs take precedence when they conflict.

## Document what the code can't tell you

Comments and docs are for knowledge a reader can't recover from the code alone:

- **Why** something is done a certain way, especially when the obvious approach was rejected.
- **Constraints** that shaped it: backwards compatibility, performance, memory, time, or cost limits, external API quirks.
- **Intentional omissions**: things deliberately simplified or not supported, so nobody "fixes" them by accident.
- **Invariants and assumptions** that must keep holding (e.g. "called only after X is initialized", "IDs are unique per org").
- **Architecture**: how components fit together and where responsibilities live, at a level above any single file.

## Don't document what the code already says

- No comments restating *what* the code does (`// increment the counter`, `// loop over users`) or narrating each step of a function.
- No docstrings that just repeat implementation details, those can be inferred from code alone.
- No comments about the change itself (`// added for feature X`, `// fixed bug`, `// now uses Y instead of Z`); that belongs in the commit/PR.
- If code needs a comment to explain *what* it does, prefer making the code clearer (better names, smaller functions) first.

## Keep docs durable

Write docs for things that stay true long-term: architecture, decisions, invariants. Avoid documenting details that change often (exact file lists, current config values, step-by-step walkthroughs of implementation) — they rot quickly and become misleading. Link to the code instead of copying it.

## Example

```python
# Bad: restates the code
# Retry the request up to 3 times
for attempt in range(3):
    ...

# Good: explains a non-obvious why
# The vendor API returns transient 502s during their deploys (a few seconds);
# 3 attempts covers that without masking real outages.
for attempt in range(3):
    ...
```
