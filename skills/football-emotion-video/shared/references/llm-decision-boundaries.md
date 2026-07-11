# LLM Decision Boundaries for Reusable Video Skills

This package is a reusable skill system, not a single-video recipe.

## What the skills decide

Skills define:

- required stages and their order
- mandatory gates before execution
- artifact shapes and handoff contracts
- verification/provenance rules
- license/rights refusal behavior
- quality-control checks
- reusable editorial heuristics
- when to stop, loop back, ask the user, or run a tool

## What the LLM must still decide

The reasoning agent must still decide, per project:

- which verified match/story is strongest
- which emotional question fits the actual evidence
- which clips are most useful after visual/audio review
- which pacing best serves the actual footage and music
- whether silence, commentary, crowd, narration, or music should dominate a moment
- whether documentary, stylized, or seamless visual cohesion fits the source mix
- what to ask the user when choices are genuinely preference-dependent

## Anti-overfitting rule

Do not add exact match facts, exact scorelines, exact timestamps, exact LUT values, exact clip scores, exact music keys, exact percentages, or fixed platform tricks as general skill rules.

Those belong in project artifacts only after they are verified or measured.

## When the LLM may go beyond a named template

If verified footage contradicts the closest template, the LLM may synthesize a project-specific arc. It must:

1. Record the deviation in `arc_revision_gate`.
2. Preserve the universal chain: pressure -> action -> reaction -> meaning.
3. Keep exact factual claims provenance-labelled.
4. Avoid creating a new reusable rule from one project unless it works across multiple runs.

## Good reusable guidance vs. bad overfit guidance

Good:

- "Use native-language commentary as a preferred candidate for national-team stories, subject to rights check."
- "For penalty sequences, capture walk-up, kick/save, immediate reaction, and redemption/aftermath if the miss is used as a hook."
- "If public expectation evidence is missing, soften titles like 'Nobody Expected'."

Bad:

- "Use TEAM_A vs TEAM_B as if it were a verified current-event default."
- "Always use a warm LUT for Atlanta Stadium."
- "Final 15 seconds must have no clip longer than 1.2s."
- "Use HyperFrames for every football edit."
