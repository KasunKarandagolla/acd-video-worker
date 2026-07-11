---
name: football-clip-scoring
description: Use when ranking or selecting between candidate clips for a football emotion video — e.g. "score these clips", "which of these clips should I use", "rank the clip candidates for the climax section", "pick the best clips for this story". Activates whenever multiple clip candidates compete for the same story role, or a final clip selection needs to be justified against the story plan rather than chosen by visual appeal alone.
---

# Football Clip Scoring

Ranks clip candidates objectively against the story plan, so selection is based on emotional/story
fit rather than which clip merely looks flashiest.

## When to use this

- `clip_candidate` rows exist from `football-timestamp-extraction`
- Multiple candidates compete for the same story-plan section
- A selection needs to be justified/reviewable rather than taken on instinct

## Required inputs

- `clip_candidate` list
- `story_plan` (which sections need which clip types — see `shared/contracts/pipeline-artifacts.md`)
- `user_instruction_profile` (target emotion, to weight relevance correctly)

## Scoring rubric (/10)

```yaml
clip_scorecard:
  emotional_strength_2:    # real visible emotion, high stakes, human reaction
  visual_clarity_2:        # clear subject, clean framing, readable action/emotion
  story_relevance_2:       # directly supports the requested arc
  audio_commentary_value_1: # useful commentary, crowd, silence, or clean audio
  uniqueness_1:            # not generic/overused, or has an unusual angle/reaction
  editability_1:           # usable duration/resolution, no heavy watermark, not overedited
  rights_reused_content_risk_1: # lower risk when short, transformed, contextualized, or official/licensed route considered
  total_10: sum
```
Decision: `8-10` core story clip · `6-7.9` supporting clip · `4-5.9` context-only, replace if a
better source appears · `<4` reject.

## Workflow

1. Read `shared/references/emotion-pattern-library.md` for the clip-type importance ranking (face close-up and immediate reaction outrank generic celebration, for instance) — this informs the `emotional_strength` and `story_relevance` sub-scores, not just gut feel.
2. Score every candidate against the rubric. Show the sub-scores, not just the total — a reviewer needs to see *why* a clip scored 6 vs 8.
3. Reject high-visual-quality clips if `story_relevance` is weak — a beautiful shot that doesn't serve this story's arc is still filler.
4. Check the mandatory clip package for the chosen story type (below) — flag if any required category has no clip scoring ≥6.
5. Assign `recommended_use` per section role, and note `openmontage_notes` — anything the edit-planning skill needs to know about this clip (e.g. "only usable if trimmed to 8s, watermark visible after 0:12").

## Mandatory clip package by story type (minimum categories needed, not exhaustive)

- **Comeback:** pain/low point, pressure buildup, turning point, decisive comeback action, reaction/release, meaning/legacy ending
- **Heartbreak:** hope/setup, final chance, decisive failure/loss, player emotional reaction, crowd/team reaction, respectful aftermath
- **Legacy:** past failure/context, present pressure, decisive proof, celebration/trophy, reflective close
- **Underdog:** underdog context, opponent strength, suffering/defending, shock moment, collective release
- **Iconic skill:** stakes before the skill, full skill visible, outcome, reaction, meaning line

If a required category is missing or all its candidates score below 6, that's a signal to go back
to `football-source-discovery` for more footage — don't force a weak clip into a required slot
just to fill the package.

## Rights/reused-content scoring notes

The `rights_reused_content_risk_1` sub-score is not a legal judgment — it's a relative signal.
Lower risk for: short necessary segments, clips that will carry original narration/analysis over
them, clips drawn from a diverse set of sources rather than one dominant source. Higher risk for:
clips that are most of the video's runtime from one source, clips whose only value is the original
copyrighted music track, or re-editing an existing fan edit. The actual risk gate is
`football-retention-quality-control`'s reused-content check — this score just feeds it.

## Failure modes to avoid

- Choosing visually flashy but emotionally/story-irrelevant clips
- Ignoring the rights/risk sub-score because a clip is otherwise excellent
- Filling a required story-package slot with a sub-6 clip just to check the box

## Handoff

Output: scored, ranked `clip_candidate` list with `recommended_use` assigned. Next skills:
`football-narration-scriptwriting` (writes around the selected clips) and
`openmontage-edit-planning` (assembles the final timeline).

## References

- `shared/references/emotion-pattern-library.md` — clip-type importance ranking and per-story-type required packages

## v3 Curation Discipline

Read `shared/references/editorial-journey/clip-selection.md` before scoring. The score is not just arithmetic; every selected clip must perform a job in the emotional journey and every required arc phase must have at least one credible clip. If the fall, pressure, or payoff phase is visually weak, return to sourcing rather than hiding the gap with captions.

## V5 patch addendum — emotion evidence and rights risk

Before assigning `emotional_strength_2 = 2`, require at least two evidence categories from:

```yaml
emotion_evidence:
  visual_body_language: []
  audio_evidence: []
  context_evidence: []
  emotion_claim_confidence: low | medium | high
```

Use `football-footage-rights-transformative-risk-assessor` for risky match footage. Do not let `rights_reused_content_risk_1` blindly destroy every World Cup clip, but also do not call footage legally safe. Use `usable_with_risk`, `avoid`, `user_must_supply_rights`, or `needs_legal_review`.

Exact clip scores are `estimated_by_editor` until the clip has frame/audio review evidence.
