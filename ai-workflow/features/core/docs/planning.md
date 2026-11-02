# Writing an Implementation Plan

Load this file only when asked to produce an implementation plan. These are general preferences; a repository's own docs (e.g. a repo-level `docs/planning.md`) take precedence when they conflict.

## Shape of a plan

Go from the outside in. Projects may prescribe their own sections; when they don't, follow this order:

1. **Goal.** State explicitly what the change is for. Every decision in the plan is made towards that goal, and anything that deviates from it must be called out and revisited, e.g.: if the goal is decoupling concerns, no step may re-couple them; if the goal is performance, any abstraction that costs performance is flagged; if the goal is a new feature, the plan must deliver it working as described.
2. **Outer technical shape.** How the result looks from the outside before any internals: the API surface for a backend change, the final data layout for a pipeline, how the interface is used for a tool, etc.
3. **Deeper details.** Expand the design with pseudocode and concrete examples: key domain models, interfaces, function signatures, payloads, branching logic.

Size the plan to the change — a small change needs a short plan.

## Examples and diagrams

- Do not produce only a list of files and descriptions; lead with design and interfaces.
- Keep examples focused on design decisions; do not reproduce the full implementation in the plan.
- Include Mermaid diagrams when the change involves multiple layers, components, transports, or asynchronous steps. Architecture diagrams show layer boundaries and labeled communication paths; sequence diagrams show the important flows between them.

## Decisions and rationale

- Record a decision and its *why* only when it is non-obvious and matters for the final result. Do not include rationale that only makes sense in the context of the conversation that produced the plan (e.g. "this is a float, not an integer" because an earlier message asked for a float).
- Leave out meta details that don't matter for the final result: planning-process instructions, notes to the user, references to how the plan was produced.
- List open questions or assumptions explicitly instead of silently guessing.

## Baseline

- Treat the current working tree, including uncommitted changes, as the implementation baseline.
- Do not describe baseline work as a prior PR, phase, or in-progress change unless the user explicitly asks for that historical framing.
