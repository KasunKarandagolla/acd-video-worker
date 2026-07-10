---
name: openmontage-audio-operation-mapper
description: Use when converting a finished audio plan into OpenMontage-executable audio track operations — e.g. "convert this audio plan for OpenMontage", "map the audio plan to OpenMontage operations", "build the audio track JSON for this video". Activates once football-audio-music-director and football-commentary-ducking-mixer have produced a complete section-by-section audio plan and it needs converting into concrete per-track clip/fade/ducking operations OpenMontage can act on.
---

# OpenMontage Audio Operation Mapper

Converts the section-by-section `audio_plan` into OpenMontage-track-shaped operations: per-track
clips with start/end times, fades, volumes, and ducking parameters. This is a translation step —
it should not introduce new creative decisions that belong to
`football-audio-music-director` or `football-commentary-ducking-mixer`.

## When to use this

- A complete, ducking-annotated `audio_plan` exists
- An OpenMontage-executable audio operations list is needed

## Required inputs

- Ducking-annotated `audio_plan` (from `football-commentary-ducking-mixer`)
- Only **approved** music/SFX assets (`license_verification_record.status: approved`)
- Total video duration

## Workflow

1. Convert each `audio_plan_segment` into concrete track clips: `music`, `commentary`, `sfx`, `crowd` tracks, each with `start_time`/`end_time` in seconds (not the human-readable timeline ranges used upstream).
2. Apply fade defaults from `shared/references/audio-emotion-playbook.md`'s crossfade table (music→music 0.5s equal-power, music→silence 0.3s linear, silence→music 1.0s slow exponential, commentary→music 0.3s in/0.5s out equal-power, crowd→music 1.0s slow fade both ways) unless the audio plan specifies otherwise.
3. Convert `volume_notes` into `volume_db` values using the mixing-defaults table (music primary -16 LUFS, music-under-commentary -24 LUFS, commentary -16 LUFS, crowd -12 LUFS, SFX -14 LUFS) as starting points — these are targets to hit during mixing, not guarantees this mapping step measures/enforces on its own (see note below).
4. Convert ducking specs into the `ducking` object shape (`trigger`, `amount_db`, `attack_ms`, `release_ms`).
5. List `silence_cuts` explicitly with their reason.
6. Set `master` targets (-14 LUFS integrated, -1.0 dBTP true peak, target LU range).
7. Output `openmontage_audio_operations` (see `shared/contracts/pipeline-artifacts.md`).
8. Validate that every `asset_id` referenced actually has an `approved` license record — reject the mapping and flag it back to the license checker if not.

## Important limitation — state this honestly in output

This skill produces the *specification* for loudness targets and ducking parameters; it does not
itself run automated loudness measurement (EBU R128) or verify the final mix hits -14 LUFS. Per
the source pack's own gap audit, loudness-normalization automation is a documented gap, not a
built tool in this pass. The output should be treated as **mixing instructions for OpenMontage's
audio tools to execute and for a human/QC pass to verify**, not as proof the targets were already
achieved.

## Decision rules

- Never reference an asset that hasn't been through the license checker's `approved` state.
- Preserve every ducking/silence decision from the upstream audio plan exactly — don't "smooth over" a deliberate silence cut because it looks unusual in the operations list.
- If OpenMontage's actual schema (once verified — see `openmontage-edit-planning/references/openmontage-handoff-notes.md`) differs from this package's `openmontage_audio_operations` contract, reconcile field names at integration time rather than guessing during planning.

## Failure modes to avoid

- Silently dropping a ducking or silence decision during conversion
- Referencing an unapproved or rejected asset
- Presenting target loudness values as if they were already verified/measured

## Handoff

Output: `openmontage_audio_operations`. Feeds into the overall `openmontage_edit_plan` assembly and
`football-audio-quality-control`'s final check.

## References

- `shared/references/audio-emotion-playbook.md` — mixing defaults and crossfade table this skill converts into concrete operations
- `openmontage-edit-planning/references/openmontage-handoff-notes.md` — confirmed vs. assumed facts about OpenMontage's real artifact schema

## v3 Assembly Layering Alignment

Use `shared/references/editorial-journey/assembly-workflow.md` for track/layer discipline. Keep commentary/VO, music, crowd, and SFX on separate tracks so OpenMontage operations can adjust ducking, sync, fades, and silence without destroying the edit.


## V4 repo bridge execution rule

Map audio operations into OpenMontage only after registry/schema confirmation. Check the selected pipeline manifest, `schemas/artifacts/`, and the available audio/composition tools from `tools.tool_registry`. Store football-specific audio reasoning under `projects/<project-id>/football_emotion/audio_music_plan.json` when the canonical OpenMontage artifact has no matching field.

## V5 patch addendum — target versus measurement

This skill may write target values such as `target_lufs = -14` and `true_peak_db = -1`, but it must not claim those values were achieved.

Actual pass/fail requires `audio_loudness_measurement` from `tools/ffmpeg_loudness_check.py` or equivalent.

Every ducking operation should trace to `speech_ducking_regions`.

## V6 patch addendum — target loudness vs measured loudness

`openmontage_audio_operations.master.target_lufs` and `true_peak_db` are targets only. Final pass requires `audio_loudness_measurement_id` pointing to an `audio_loudness_measurement` produced by `tools/ffmpeg_loudness_check.py` or an equivalent measured tool. Do not copy target values into `measured_lufs` / `measured_true_peak_db` unless the measurement artifact exists and says `measured_by_tool`.
