# A rule says what it costs and where it stops

## Intent

A rule followed without limit does harm. Agreeing to a rule that access by outsiders is audited, the user added: "we should be careful because auditing too much can be harmful (storage and DB writes)". On notifications: "what I want is to make something usable and not annoying".

## Decision

- A rule's Why says what it is for and what it costs (storage, writes, calls to a provider, someone's attention).
- At least one of the questions it answers is answered "no, that would be too much".
- Planning asks the user, for each rule, what it costs and where it stops.
- A review flags a rule applied past what it is for, like one that is ignored.

## Alternatives considered

- **State the rule and leave proportion to each worker.** The first rule drafted this way would have meant a database write on every read.
