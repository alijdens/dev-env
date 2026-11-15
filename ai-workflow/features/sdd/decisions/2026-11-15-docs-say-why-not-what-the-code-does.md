# Docs say why, and what at a high level; the code has the details

## Intent

The user: "we are polluting with too much documentation that states things that already happen in the code instead of explaining why or what at a high level. For details we already have the code, doc should explain rationale so it can be used to answer future questions."

## Decision

- Records and specs keep what stays true: the intent, the choice, the contract others rely on, and what the code can't say (why a key is deliberately missing, an external system's quirk).
- They name a thing in the code only when it is the contract. No function, file or job names, error-code lists, call-site lists or current values.
- The same test for writing an ADR applies in planning, implementing and answering; "no record" is a normal outcome.
- A record that holds a detail is retired into a spec, or deleted when it is outdated and adds nothing (the user: "if the doc is really outdated and does not add anything, let's just delete it"). A feature spec is deleted once its feature is built.

## Alternatives considered

- **Specs as a full description of how things currently are.** They grew as long as the code and were wrong after the next PR.
- **Keep every record forever, marked as no longer in force.** A file that only points elsewhere is one more thing to read.

## Consequences

- Deleting needs care for what still names the record: done tasks keep the name as history, live links are removed.
