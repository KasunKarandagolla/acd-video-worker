---
name: football-commentary-ducking-mixer
description: Use when real commentary or crowd audio needs to be preserved against a music bed in a football emotion video — e.g. "duck the music under this commentary", "make sure the commentary is audible here", "mix this section so the crowd isn't buried". Activates once an audio_plan exists and specific sections contain real commentary, player speech, or crowd audio that music/SFX must not bury. Produces the detailed ducking plan football-audio-music-director's high-level hierarchy decisions need to actually be mixed correctly.
---

# Football Commentary Ducking Mixer

Preserves real commentary, player speech, and crowd audio against a music bed. Real audio is
often the strongest emotional proof in the whole video — this skill exists specifically to stop
music from quietly burying it.

## When to use this

- An `audio_plan` exists with sections marked `dominant_audio: commentary` or `crowd`
- A specific section's real audio needs a concrete ducking specification, not just a "commentary should dominate" note

## Required inputs

- `audio_plan` from `football-audio-music-director`
- Which sections contain real commentary/player-speech/crowd audio (from the source clip's `audio_signs` / `audio_description`)

## Workflow

1. Identify every section where real commentary, player speech, or crowd audio is present and important.
2. Classify each into a priority tier (highest to lowest, per `shared/references/audio-emotion-playbook.md`):
   1. Player speech / emotional words — always audible; duck music hard
   2. Iconic commentary line — duck music substantially
   3. Crowd roar / natural celebration — usually no music at all, let it breathe
   4. Buildup music with no specific match audio — no ducking needed
   5. Silence — full audio cut
3. For "must-hear" moments (iconic lines, decisive words, player names spoken at the key moment), specify deeper ducking than the section's default.
4. Set concrete ducking parameters per the mixing defaults reference: e.g. music ducks -6dB on a commentary peak, -12dB when crowd roars over commentary; fast attack, slower release so it doesn't pump audibly.
5. Output the ducking-annotated `audio_plan_segment` rows, with `ducking_required: true` and a `volume_notes` field precise enough for `openmontage-audio-operation-mapper` to convert directly into track-level operations.

## Decision rules

- If the viewer can't hear the words during a section marked commentary-dominant, the ducking amount is wrong — treat that as the primary correctness test for this skill's output, not just "does it sound nice."
- Crowd roar generally needs no ducking — let it breathe at a high level rather than compressing it down to fit under music.
- Silence-marked sections get a full cut, not a "very quiet" music bed — that's a different decision than silence and should be labeled as such if that's actually what's intended.

## Manual process note (until automated commentary extraction exists)

This project does not assume automated voice-activity-detection or commentary extraction tooling
is available (per the requirements' no-local-ML-model constraint and the source pack's own gap
audit, which lists commentary extraction/auto-ducking as a documented gap, not a built tool).
Until that exists, this skill's job is to specify *where* and *how much* ducking should happen
based on the agent's own review of the clip's audio (per `football-visual-scene-analysis`'s
`audio_description` field) — a human or the OpenMontage audio pipeline then applies the actual gain
automation. State this plainly in the output rather than implying automatic detection occurred.

## Failure modes to avoid

- Ducking too little, so music buries the emotional proof
- Ducking too much/too often, making commentary sound artificially isolated
- Applying uniform ducking regardless of whether the moment is "must-hear" or just background chatter
- Implying an automated VAD pass happened when it didn't

## Handoff

Output: ducking-annotated `audio_plan`. Next skills: `football-audio-quality-control` (verifies
the plan meets mix-level targets) and `openmontage-audio-operation-mapper` (converts to track ops).

## References

- `shared/references/audio-emotion-playbook.md` — priority tiers and mixing defaults (dB levels, attack/release) this skill applies

## V5 patch addendum — ducking regions and clarity repair

Create `speech_ducking_regions` before mapping audio operations:

```yaml
speech_ducking_regions:
  method: vad | transcript | manual_marker | user_supplied
  regions:
    - start: string
      end: string
      speech_type: commentary | interview | narration
      music_gain_db: number
      attack_ms: number
      release_ms: number
  verification_status: verified | estimated | manual_review_needed
```

Use `shared/references/commentary-crowd-clarity.md` for practical EQ/sidechain guidance. Do not require custom spectral separation unless OpenMontage preflight confirms an available tool.
