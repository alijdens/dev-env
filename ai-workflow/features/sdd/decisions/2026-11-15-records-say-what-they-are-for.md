# A record says what it is for, and business rules are guidance

## Intent

A worker who is unsure how to proceed should find the answer in the records, not have to ask. The user: "the rules should be general guidance for the agent when it is not sure how to proceed. For example, I could add an ADR to specify that 'external calendars should remain in sync with ours' so questions like 'if the user cancels on our site, should the gcal be updated too?' are self responding."

## Decision

- A business rule is a general statement of what the product wants, with why and the questions it answers, in the user's words where they gave them. A number is rarely the rule: it is the current setting of one.
- An ADR opens with its Intent, what the decision is for, and `sdd brief` prints the Intent with the Decision.
- A record states a default and the reasons to leave it. "Never", "only", "always" and closed lists are kept for real invariants.
- A rule is the user's: one they neither stated nor confirmed isn't written as accepted.

## Alternatives considered

- **Rules as limits a reader can check against the code** (what it was). It produced prohibitions and enumerated lists, each falsified by the next feature, and nowhere to write what was actually wanted.
- **Keep the reason in the ADR's Context only.** The brief leaves Context out to stay short, so workers had the mechanism without the purpose.

## Consequences

- Planning has to get the intent from the user, by asking what a worker will be unsure about.
- A decision can be right and still unbuilt: records say so in their Consequences.
