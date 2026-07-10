---
name: football-audio-quality-control
description: Use before finalizing a football emotion video's audio to catch over-music, bad silence placement, SFX spam, or masked commentary — e.g. "check the audio quality of this plan", "is the music too loud anywhere", "audit this audio plan before we finalize". Activates once an audio plan and OpenMontage audio operations exist and a pre-delivery audio-specific QC pass is needed, distinct from the whole-video retention QC done by football-retention-quality-control.
---

# Football Audio Quality Control

Audits a finished audio plan for the audio-specific failure modes this pipeline cares most about:
commentary getting buried, SFX overuse, bad silence placement, and mismatched music. This is
audio-only QC — the full-video retention/professionalism pass is
`football-retention-quality-control`'s job.

## When to use this

- An `audio_plan` and `openmontage_audio_operations` exist and need a pre-finalization audio check
- Before a plan is handed off for actual rendering

## Required inputs

- `audio_plan` (ducking-annotated)
- `openmontage_audio_operations`
- The story plan, to check whether music/silence choices actually match section emotional roles

## Workflow — checklist (every item is a pass/fail finding)

1. **Commentary audibility.** For every section marked commentary-dominant, would the ducking amount specified actually leave the words audible? (Check against the -6dB/-12dB ducking guidance in `shared/references/audio-emotion-playbook.md` — a section duck-ing music by only -3dB when commentary should dominate is a finding.)
2. **Music-emotion match.** Does each section's music category match its emotional role (no sad piano during celebration, no epic orchestral before the story has earned it)?
3. **Music variety.** Has the same music category been used 3+ times across the video? Flag as a repetition finding.
4. **Silence placement.** Is every silence beat placed on a genuinely decisive moment (penalty, final whistle, emotional face), not a minor beat where it would kill momentum instead of building it?
5. **SFX caps.** Check every SFX type against its per-video maximum (e.g. bass hit ≤3) from the playbook's SFX table. Flag any type exceeding its cap.
6. **Front-loading.** Is emotional music concentrated entirely in the first 1-2 minutes with a flat remainder? Flag if so — emotional peaks should be spread.
7. **Fade discipline.** Does the plan end with an abrupt cut rather than a fade (minimum 0.5s)? Flag if so.
8. **Crowd authenticity.** Has real crowd audio been replaced by generic music anywhere it should have been preserved? Flag if so.
9. **License gate integrity.** Does every referenced `music_asset_id` trace to an `approved` license record? This is a blocking finding if not — no audio plan should reach delivery referencing an unapproved asset.
10. **Beat/loudness note (manual-tooling caveat).** Per this project's current scope, beat detection and loudness normalization are not automated (see `openmontage-audio-operation-mapper`'s stated limitation) — this QC pass checks the *specification* against target values, not a measured final mix. Say so explicitly in the report rather than implying the numbers were verified against real audio.

## Output

```yaml
qc_report:
  qc_type: audio
  pass: boolean
  findings:
    - finding: string
      severity: low | medium | high | blocking
      section_id: string | null
      required_fix: string
  overall_risk_level: low | medium | high | unknown
```
A `blocking` finding (commentary inaudible, unapproved asset referenced) means `pass: false`
regardless of how good the rest of the plan is.

## Failure modes this skill exists to catch

All ten items in the workflow checklist above are themselves the failure-mode list — this skill's
entire purpose is checking for them systematically rather than trusting that upstream skills got
everything right by construction.

## Handoff

Output: `qc_report` (audio). If `pass: false`, loop back to `football-audio-music-director` and/or
`football-commentary-ducking-mixer` for fixes before proceeding to
`football-retention-quality-control`'s whole-video pass.

## References

- `shared/references/audio-emotion-playbook.md` — the target values (ducking dB, SFX caps, fade durations) this checklist verifies against
- `references/beat-loudness-manual-checklist.md` — the BPM/LUFS/crossfade detail tables preserved from the source research, for manual reference until automated tooling exists

## v3 Audio QA Alignment

Use `shared/references/editorial-journey/quality-assurance.md` during audio QC: speech must be intelligible, music/SFX must not create random loud jumps, sync drift must be checked at multiple cut points, and dead air is allowed only when silence was an intentional edit decision.

## V5 patch addendum — measured loudness gate

This skill may no longer mark loudness as passed from targets alone. It must require an `audio_loudness_measurement` with `measured_by: ffmpeg_loudnorm` or equivalent.

If no measurement exists, output `pass: false` or `manual_review_needed`, not `passed`.

Use `tools/ffmpeg_loudness_check.py` when a rendered or mixed audio file exists.
