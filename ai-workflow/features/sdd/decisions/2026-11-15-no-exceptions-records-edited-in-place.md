# No exceptions are added to a record, and accepted records are edited in place

## Intent

The user: "if an ADR has many exceptions, it's a smell that it's wrong", and having many amendments and conflicts between records is the same smell. A decision should be readable in one place, as it stands.

## Decision

- An accepted record is edited in place when the user agrees; git keeps what it said before. `sdd validate` warns that it changed.
- A case a record's wording doesn't allow is settled from its Intent. If the intent wants what the wording forbids, the record is restated; an exception is never appended.
- `--supersedes` is for a decision replaced by a different one. `--amends` stays only for existing data and warns.
- A record that collected amendments is restated from what it is for, with the user, and a reviewer that didn't write it compares the result with the old text.

## Alternatives considered

- **Immutable records, changed only by a new record that amends them** (what it was). In one project it gave 197 ADRs in a month with two of three amending another, and no step ever asked whether the original was stated at the wrong level.
- **Consolidate the amendments into one text, adding nothing.** A record merged that way had eight amendments again two days later.

## Consequences

- The append-only trail is in git, not in the files.
- A restatement can drop or distort something. In every one done so far the reviewer found statements that were wrong or lost, so that step is not optional.
