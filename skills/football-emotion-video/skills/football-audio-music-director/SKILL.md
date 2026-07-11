---
name: football-audio-music-director
description: >-
  Use when deciding the section-by-section audio hierarchy for a football emotion video — e.g. "plan the audio for this video", "should commentary or music dominate this section", "direct the audio for the climax", "what should be playing during the penalty walkup". Activates once edit sections and clips are known and an audio timeline decision is needed — commentary vs crowd vs silence vs music vs SFX priority, music mood, ducking needs, and SFX placement. Never marks a music/SFX asset as usable without football-rights-safe-audio-license-checker having approved it first.
---

# Football Audio & Music Director

Decides, section by section, what should dominate the audio: real commentary, crowd, silence,
narration, music, or SFX — and which approved music/SFX asset to use when music is called for.
This is the central creative-audio decision skill; it does not select candidate assets itself
(that's `football-music-library-selector`) and it does not clear licenses (that's
`football-rights-safe-audio-license-checker`).

## When to use this

- Edit sections and clips are known
- An audio hierarchy or music-mood decision is needed for a section
- The video risks sounding like a lazy highlight montage because audio hasn't been deliberately directed

## Required inputs

- `story_type` / `target_emotion`
- Edit sections with: timeline range, emotional role, whether real commentary/crowd/narration is present, emotional intensity, pacing
- Only **approved** `music_sfx_candidate`s (status `approved` from the license checker) — do not build a plan around unapproved candidates

## Workflow

1. Read `shared/references/audio-emotion-playbook.md` in full before making section decisions — this is the operational core of this skill.
2. For each section, decide `dominant_audio` using the priority order: commentary > crowd > silence > narration > music > SFX, checking against the "when X must dominate" rules in the playbook.
3. Where music is the right call, pick a category (sad_piano / cinematic_rise / epic_orchestral / dark_ambient / heartbeat_tension / motivational / documentary_piano) matching the section's emotional role — never epic orchestral before the story has earned it, never sad piano in every section (variety matters, see failure modes).
4. Reference only **approved** assets from the license checker when specifying `music_asset_id`.
5. Set `music_action` (start/rise/duck/drop/remove/continue) per the story-stage audio map.
6. Note silence beats explicitly — silence is a deliberate edit decision here, not a gap to fill.
7. Keep SFX sparse and check against the per-video caps in the playbook (e.g. max 3 bass hits).
8. Output `audio_plan_segment` rows (see `shared/contracts/pipeline-artifacts.md`).
9. Hand off to `football-commentary-ducking-mixer` for the detailed ducking pass around any real commentary/crowd audio present in the selected clips.

## Decision rules

- Never add music before deciding whether commentary, crowd, or silence should dominate that section first.
- Never use epic orchestral music before the story has earned the moment.
- Never use SFX to compensate for weak clip selection.
- Always keep a fallback plan: silence or crowd-only can be the stronger choice over generic background music, and should be considered explicitly, not just defaulted away from.
- Vary music types across the video — three sad-piano sections in one project reads as repetitive even if each individually fits its section.

## Failure modes to avoid

(See `shared/references/audio-emotion-playbook.md`'s full failure-mode list — the most consequence-heavy ones specific to this skill's decisions:)
- Music drowning commentary
- Music mismatched to the visual emotional beat
- Front-loading all emotional music early then going flat
- Silence used on a minor moment, killing momentum instead of building it

## Handoff

Output: `audio_plan` (section-by-section). Next skills: `football-commentary-ducking-mixer`
(detailed ducking), then `football-audio-quality-control` (pre-finalization audio QC), then
`openmontage-audio-operation-mapper` (conversion to OpenMontage audio tracks).

## References

- `shared/references/audio-emotion-playbook.md` — the full hierarchy, music-type table, story-stage map, mixing defaults, and SFX rules this skill applies directly

## v3 Music-First Assembly Rule

Read `shared/references/editorial-journey/audio-music.md` and `shared/references/editorial-journey/assembly-workflow.md` when the edit will be built to music. Music should be selected after brief intake and license approval, then marked for intro/build/drop/breakdown/outro before final trimming. Commentary, crowd, silence, narration, music, and SFX must be prioritized by emotional purpose, not by default volume.


## V4 OpenMontage music rule

At proposal time, surface the music situation explicitly: user `music_library/`, available music-generation tools from the registry, royalty-free external candidate track supplied by user, or no-music path. Do not let music failure appear late at assets/edit stage.

## V5 patch addendum — native-language commentary

For national-team stories, consult `shared/references/native-language-commentary.md`. First search for emotionally authentic native-language commentary and treat it as a possible primary audio anchor.

This is a creative priority, not a rights approval. Direct commentary audio still needs commentary rights checks and reused-content risk assessment.

## V6 patch addendum — direct commentary requires rights check

When choosing real commentary as dominant audio, do not assume it is usable. Add `commentary_rights_check_required: true` to the relevant `audio_plan_segment`. If no `commentary_rights_check` is available, mark direct commentary as `candidate_only` and offer safer alternatives: crowd-only, paraphrased narration, short on-screen quote, or user-supplied licensed clip.
