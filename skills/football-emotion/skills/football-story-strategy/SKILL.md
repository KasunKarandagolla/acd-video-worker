---
name: football-story-strategy
description: Use at the start of a football emotional video project to turn a request into a concrete story arc — e.g. "make a Messi proving everyone wrong video", "I want a Ronaldo heartbreak story", "plan a video about an underdog team", "what story structure fits this request". Activates on any new football-emotion video request before source discovery begins, or whenever the emotional/narrative structure of an existing project needs to be chosen or reconsidered.
---

# Football Story Strategy

Turns a user's football-emotion request into a specific, structured story plan — the emotional
architecture everything else in the pipeline builds around. This is usually the first skill to run
in a new project.

## When to use this

- A new football-emotion video request has been made
- An existing project's story structure feels wrong for the requested emotion (e.g. it's been
  forced into a generic comeback arc when the request was actually about heartbreak)

## Required inputs

The raw user request. If key details are missing (target emotion, specific player/match, duration
target), infer the most likely intent from phrasing and proceed — state the assumption rather than
blocking, unless the request is genuinely ambiguous between two very different stories (e.g.
"Ronaldo heartbreak" could mean several different tournament exits — ask which one, or state
you'll default to the most recent/most referenced one and let the user correct it).

## Workflow

1. Parse the request into a `user_instruction_profile` (see `shared/contracts/pipeline-artifacts.md`).
2. Read `shared/references/emotion-pattern-library.md` and select a story structure based on the **requested emotion**, not on which arc is easiest or most common. A humiliation/collapse request forced into a comeback arc, or a heroic-failure request forced into a triumph arc, breaks the story's honesty.
3. Pick one hook pattern from the library that fits the chosen story structure.
4. Define the section-by-section `story_plan`: timeline ranges, emotional role per section, required clip types per section, and the minimum clip package this story type needs.
5. Hand off to `football-source-discovery` (if no footage exists yet) or directly to `football-clip-scoring` (if candidates already exist and just need arranging against this plan).

## Decision rules

- Choose structure based on emotion, not player popularity — a request about a beloved player doesn't automatically mean triumph.
- Always include pressure → action → reaction → meaning as the underlying chain, regardless of which named structure is chosen.
- Prefer a specific-match story over a generic motivational arc when the request names a specific event.
- If the request is ambiguous between two structures (e.g. "prove everyone wrong" could be legacy-completion or doubt-to-proof), pick the one that better matches any named match/tournament in the request; if none is named, ask.

## Failure modes to avoid

- Forcing every request into a comeback formula
- A hook/story mismatch (e.g. a triumphant hook on a story that's actually about heroic failure)
- Flattening heartbreak/heroic-failure nuance into generic "sad video" framing
- Treating "national pride" requests as generic patriotism rather than keeping an individual player's story present

## Handoff

Output: `user_instruction_profile` + `story_plan`. Next skills: `football-source-discovery` (find
footage) and, once clips are selected, `football-narration-scriptwriting`.

## References

- `shared/references/emotion-pattern-library.md` — the full story-structure and hook-pattern library this skill selects from

## v3 Editorial Journey Alignment

Before choosing a football story structure, run Stage 1 brief interpretation. Read `shared/references/editorial-journey/brief-interpretation.md` and lock:

- one emotional question;
- tonal flavor;
- runtime target;
- platform;
- non-negotiable moments.

Do not hand off to sourcing until those fields are clear enough to drive search and clip budgets. If the user only gives a generic theme, convert it into a specific story hypothesis first.

## V5 patch addendum — dynamic arc and defending champion template

For Argentina 2026 or any defending champion/favorite nearly collapsing, consider the template in `shared/references/football-playbooks-defending-champion.md`:

`Champion expectation → vulnerability exposed → pressure grows → survival moment → vindication → legacy question`.

After verification, run `arc_revision_gate` from `shared/references/dynamic-arc-revision.md`. If real footage tells a different story, revise the emotional question and re-flow forward.

Do not use `nobody expected` unless supported by `public_expectation_evidence`.

## V6 patch addendum — first-class reusable story structures

Treat the following as first-class story structure options, not only as references:

1. `defending_champion_under_siege` — Champion expectation → vulnerability exposed → pressure grows → survival moment → vindication → legacy question. Use for any champion/favorite that nearly collapses, not only Argentina.
2. `public_doubt_to_proof` — Public expectation/evidence → pressure → proof moment → reaction → meaning. Use only when public-expectation evidence exists.
3. `penalty_wound_to_redemption` — penalty failure/save → emotional wound → team response → redemption beat. Use only when the later footage actually resolves the penalty moment.

If the title contains phrases like `Nobody Expected`, `No One Believed`, `Everyone Doubted`, or `Impossible Win`, do not treat that as verified public sentiment. Default to one of these actions:

- `evidence_required`: keep the title as a hypothesis and require `public_expectation_evidence`;
- `soften_title`: use safer framing such as `Harder Than Expected`, `The Win That Felt Like Survival`, or `Almost Slipped Away`;
- `ask_user`: ask whether the user wants the stronger title even if evidence is not yet available.

Record the chosen action in `brief_interpretation.title_claim_policy`.

## V7 addendum — reusable guidance, not single-video overfit

This skill may name reusable story structures, but it must not hardcode one project's opponent, scoreline, timestamp, or exact event as a general rule.

If no named template fits verified footage, the LLM may synthesize a project-specific arc. It must record:

```yaml
arc_revision_gate:
  template_used: existing | synthesized_project_specific
  base_templates_combined: [string]
  reason_verified_footage_required_change: string
  reusable_rule_created: false
```

A synthesized arc is allowed for the current project. It does not become a new reusable playbook until multiple runs show it works.
