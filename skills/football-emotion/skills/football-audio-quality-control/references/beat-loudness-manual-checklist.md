# Beat/Loudness Manual Checklist (reference for football-audio-quality-control)

This content was originally proposed as its own skill (`football-beat-loudness-sync-engine`) in
the source pack. Per this package's architecture decision (see
`analysis/04_skill_architecture_decision.md`), it's kept here as a manual/heuristic reference
rather than a standalone skill, because no bundled beat-detection or loudness-measurement tool is
assumed to exist in this project's current scope. Treat every value below as a **target to check
by ear / by manual review**, not a number this pipeline currently measures automatically.

## Per-music-type technical specs (targets, not measured output)

| Music type | Trigger | BPM | Key | Duration range |
|---|---|---|---|---|
| Sad piano | player crying, career ending, team elimination, injury, post-match devastation | 60-80 | Minor | 10-120s |
| Cinematic rise | pre-match buildup, comeback beginning, legacy setup, trophy approach | 80-140 (building) | Minor→Major | 20-90s |
| Epic orchestral | trophy lift, championship celebration, legacy confirmation, national triumph | 120-140 | Major | 15-90s |
| Dark ambient | pressure buildup, burden of expectation, pre-comeback hopelessness | N/A (drone) | Atonal | 15-120s |
| Heartbeat tension | penalty shootout, final minutes, decisive free kick, VAR check | 60-80 (matches human heart) | N/A | 10-60s |
| Motivational buildup | training montage, comeback sequence, "proving doubters wrong" | 120-140 | Major (often Major→Minor→Major) | 30-180s |
| Documentary piano | flashback narration, historical context, legacy reflection, outro | 70-90 | Minor/Major | 20-120s |

## Story-stage mixing targets (by section)

| Stage | Music level | Commentary level | SFX level |
|---|---|---|---|
| Hook (0:00-0:30) | -14 LUFS | -20 LUFS (if used) | -12 LUFS |
| Buildup (0:30-3:00) | -16 LUFS (building) | -22 LUFS | -16 LUFS |
| Climax (3:00-6:00) | drops to ~-30 LUFS at peak, returns to -14 LUFS after | peaks at -12 LUFS | natural audio at -10 LUFS |
| Cooldown (6:00-end) | fades from -16 to -60 LUFS over ~15s | fades to -30 LUFS | minimal |

## Manual beat-matching approach (no automated detection)

1. Listen to the candidate music track and tap along to identify the approximate BPM by ear, or
   use a simple tap-tempo approach against a stopwatch.
2. Identify obvious structural points (a build, a drop, a clear downbeat after a pause) by
   listening, and note their approximate timestamps.
3. When cutting on beat (fast-cut/buildup sections only — see `football-pro-cutting-pacing`), align
   cuts to these manually-identified points rather than assuming a fixed BPM grid.
4. This is coarser than automated beat detection but avoids fabricating precision the pipeline
   doesn't actually have.

## Manual loudness-check approach (no automated LUFS measurement)

1. Use standard playback tools to sanity-check that dialogue/commentary is clearly audible against
   the music bed at normal listening volume — if it isn't, that's the practical signal to act on,
   regardless of what a LUFS meter would say.
2. Check for obvious clipping/distortion by ear on any source audio before using it — this is a
   simpler, sufficient check for this pipeline's current scope.
3. When OpenMontage's own audio tools are used for final mixing (`tools/audio/` — mixing,
   enhancement), lean on whatever loudness tooling is already available there rather than assuming
   this skill package needs to duplicate it.

## When to build the real automated tools

Per the source pack's own gap-severity ratings, beat detection and loudness normalization
automation are rated "Nice to Have (can fix during first 10 videos)," not a hard production
blocker. If/when this project scales past manual review being sufficient, the recommended future
tools are `beat_detector` (e.g. via a Python audio library such as librosa) and
`loudness_normalizer` (EBU R128 measurement + gain/limiting) — see
`implementation/IMPLEMENTATION_PLAN_HERMES_OPENMONTAGE.md` for how these would slot into the
pipeline without requiring a rewrite of the skills in this package.
