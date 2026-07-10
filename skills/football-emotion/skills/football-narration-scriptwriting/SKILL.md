---
name: football-narration-scriptwriting
description: Use when writing narration, script, or voiceover text for a football emotional video — e.g. "write the script for this Ronaldo video", "give me narration lines for the hook", "write a voiceover for the pressure section". Activates once a story plan and selected clips exist and narration text is needed for hook lines, section transitions, or the closing meaning line. Does not invent facts, quotes, or statistics that weren't verified elsewhere in the pipeline.
---

# Football Narration & Scriptwriting

Writes narration that adds context and meaning without talking over the footage's own emotional
proof (commentary, crowd, silence). Never invents facts.

## When to use this

- A `story_plan` and selected clips exist and narration text is needed
- A specific line is needed: hook line, section transition, or closing meaning line

## Required inputs

- `story_plan`
- Selected/scored clips (`clip_candidate` list with `recommended_use` assigned)
- Any verified facts available (from `video_scene_analysis` / `source_video_candidate` notes) — narration must not go beyond what's actually verified
- Tone preference if given (cinematic / documentary / motivational / analysis)

## Workflow

1. Identify, section by section, whether narration is actually needed — some sections (the climax, especially) may be stronger with silence or commentary alone and no narration at all. Check `shared/references/audio-emotion-playbook.md`'s hierarchy: narration is below commentary/crowd/silence in priority.
2. Where narration is needed, write it to **set up meaning**, not describe what's visually obvious.
3. Keep language simple and specific — avoid generic motivational clichés ("he never gave up," "against all odds") unless the actual footage/context earns that specific phrase.
4. Leave explicit space (silence markers or short-line notes) for commentary/crowd audio to dominate at the moments the audio hierarchy calls for it — the script shouldn't fight the audio plan.
5. Every factual claim in the narration (a date, a score, a quote, a statistic) must trace back to something verified elsewhere in the pipeline. If it can't be traced, either cut it or explicitly flag it as needing verification before use.

## Decision rules

- Narration explains stakes, connects flashbacks, adds meaning after a raw clip, or sets up why a moment matters.
- Narration does NOT explain obvious visuals, speak over emotional commentary, lean on motivational clichés, or assert unverified facts as true.
- Style: simple, specific, respectful, emotionally restrained — not overwritten.

## Failure modes to avoid

- Talking over a moment where real commentary should be the emotional proof
- Fake or invented drama ("he had waited his whole life for this" as an assumed fact rather than something the footage/context actually supports)
- Generic "he never gave up" lines used interchangeably across every project regardless of the actual story
- Writing a line that implies a fact (a quote, a statistic, an outcome) that hasn't been verified

## Handoff

Output: section-by-section narration text (hook line, transition lines, closing meaning line).
Next skills: `football-caption-thumbnail-direction` (captions may echo or complement narration) and
`openmontage-edit-planning` (places narration into the timeline alongside audio decisions).

## References

- `shared/references/audio-emotion-playbook.md` — audio hierarchy that determines when narration should stay silent
- `shared/references/verification-standard.md` — what counts as a verified fact narration can safely reference
