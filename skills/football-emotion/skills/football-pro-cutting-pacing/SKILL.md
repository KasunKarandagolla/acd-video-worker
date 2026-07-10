---
name: football-pro-cutting-pacing
description: Use when deciding cut rhythm, hold durations, or pacing for a football emotion video's sections — e.g. "how fast should this section cut", "should this be a hold shot or fast cuts", "set the pacing for the climax section". Activates once timeline sections/roles are drafted and specific cutting-rhythm decisions (hold vs fast-cut vs beat-cut vs reaction-cut) are needed for each section.
---

# Football Pro Cutting & Pacing

Applies professional cutting rhythm to a drafted timeline — deciding, section by section, whether
to hold, fast-cut, cut-on-beat, or cut-to-reaction, and for how long.

## When to use this

- Timeline sections/roles are drafted (from `story_plan` or an in-progress `openmontage_edit_plan`)
- Specific pacing decisions are needed per section or per clip

## Required inputs

- Section roles (hook/context/pressure/reversal/climax/aftermath)
- Clip energy/emotional content for each section
- Music BPM/shape if an audio plan already exists (optional — can proceed without and flag as provisional)

## Workflow

1. Read `shared/references/pro-editing-methodology.md`'s cutting-technique table and pacing-by-section rules.
2. For each section, choose a dominant cut style: fast cuts for energy/buildup, hold shots for emotion, cut-on-beat for montage/skill sections, cut-to-reaction after any decisive action.
3. Assign approximate hold/shot durations using the technique table (e.g. 2.5-6s+ for genuine emotional holds, 0.4-1.2s/shot for high-energy sequences).
4. Vary rhythm within a section — a mechanically identical cut pattern throughout reads as templated, even within a "fast cut" section.
5. Flag any section where the same pace has been used as the previous section for too long — pacing needs to shift across the video, not stay flat.

## Decision rules

- Fast cuts increase energy; they should never be used to disguise a weak story, and never on crying faces, penalty pauses, trophy emotion, or final-walk moments.
- Hold longer than instinct suggests on genuine emotional faces — cutting away too quickly out of fear of "slow pace" is a documented failure mode.
- Reaction must land within 1-3 seconds of the action it responds to; for shock moments, showing reaction before replay can build curiosity.
- Repeat a moment only if it's genuinely iconic — repeating ordinary goals is filler regardless of how the repeat is structured.

## Failure modes to avoid

- Same pace throughout the whole video
- Cutting away from emotional faces too quickly
- Cutting on every beat mechanically (reads as templated)
- Using fast cuts to compensate for weak clip selection rather than fixing the selection

## Handoff

Output: cut-rhythm decisions per section, feeding into `openmontage-edit-planning`'s
`cut_style`/`transition` fields.

## References

- `shared/references/pro-editing-methodology.md` — the full cutting-technique and pacing-by-section rules this skill applies

## v3 Pacing & Assembly Alignment

Read `shared/references/editorial-journey/pacing-rhythm-cuts.md` for phase rhythm and `shared/references/editorial-journey/assembly-workflow.md` before final cut timing. Rough phase pacing comes before micro-sync. Only the 3-5 most important cuts need exact musical alignment; the rest should support the emotional rhythm without becoming mechanical.
