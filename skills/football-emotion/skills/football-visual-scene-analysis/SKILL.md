---
name: football-visual-scene-analysis
description: Use when a football source video has been selected for deep analysis and its actual visual/audio content needs to be reviewed scene-by-scene — e.g. "analyze this match video for emotional scenes", "review the frames from this Ronaldo video", "what's actually in this footage". Activates after football-source-discovery flags a candidate, or whenever frames/audio have been extracted from a football video and need scene-level interpretation. Requires actually viewing extracted frames/audio, not describing from title or memory.
---

# Football Visual Scene Analysis

Turns a selected source video into scene-level intelligence by actually reviewing extracted
frames and audio — not by inferring from the title, thumbnail, or general knowledge of the match.

## When to use this

- A `source_video_candidate` was marked `deep_analysis_candidate: yes` or `maybe`
- Frames, a transcript, or audio have been extracted from a football video and need interpretation
- An existing scene analysis needs re-review because it was marked `unverified`

## Required inputs

- The video file or URL
- Extracted frames (use OpenMontage's `tools/analysis/` frame-sampling tool if available, or any
  equivalent frame-extraction step — see `references/frame-extraction-approach.md`)
- Extracted/transcribed audio if available
- The `target_emotion` / `story_type` from the `user_instruction_profile`, to focus attention on relevant scene types

## Workflow

1. **Extract, don't assume.** If frames haven't been sampled yet, run the frame-sampling step first (see reference file for the concrete approach — this project has no bundled VLM, so "analysis" means the coding agent actually looking at extracted frames it can view).
2. Go through frames/audio in order and classify each notable moment using the scene taxonomy below.
3. For each scene, answer the seven editor questions (see reference file) — a scene row that can't answer them isn't ready.
4. Assign `confidence` honestly: `high` only if you actually viewed the frame/audio for that exact moment.
5. Flag anything uncertain with `manual_review_needed: true` rather than guessing.
6. Output a `video_scene_analysis` (see `shared/contracts/pipeline-artifacts.md`).

## Scene taxonomy

hook moment · player close-up · silent emotional face · crowd reaction · fan crying · commentator
line · narrator setup · slow-motion skill · goal buildup · decisive goal · missed chance · penalty
moment · trophy moment · defeat moment · celebration · opponent reaction · coach reaction ·
scoreboard/final result · silence moment · text quote moment · flashback · montage · climax ·
outro/reflection

## Editor timeline model (target for 8-12 minute videos — not a claim about a specific source)

| Time | Role | Purpose | Preferred clips | Audio logic |
|---|---|---|---|---|
| 0:00–0:20 | Hook | instant emotional destination | crying face, trophy lift, whistle, commentator scream, shocking scoreboard | raw commentary, silence, or one soft cue |
| 0:20–1:30 | Context | why the moment matters | past failures, doubts, prior tournament clips, player intro | low music bed, clear narrator/comms |
| 1:30–3:30 | Pressure build | stakes increasing | close-ups, crowd tension, missed chances, coach reactions | tension bed, heartbeat only if justified |
| 3:30–6:30 | Conflict/reversal | setback or turn | equalizer, red card, penalty miss, injury, opponent goal | music dips or dark ambient |
| 6:30–9:30 | Climax | decisive emotional moment | goal, save, penalty, whistle, trophy, tunnel walk | commentary/silence dominates |
| 9:30–12:00 | Aftermath/meaning | closure | tears, hugs, fans, trophy, empty stadium | sad piano, crowd-only, or reflective |

## Failure modes to avoid

- Hallucinating visual details not actually present in the reviewed frames
- Treating all goals as equally important regardless of story role
- Missing reaction shots because attention stayed on the action only
- Ignoring editability (watermarks, resolution, overedited source) when scoring usefulness
- Marking something `verified` because it "should" be there based on knowing the match, rather than because it was actually seen

## Handoff

Output: `video_scene_analysis`. Next skill: `football-timestamp-extraction` to convert this into
timestamped clip candidates.

## References

- `references/frame-extraction-approach.md` — how to get frames to actually look at (OpenMontage tool usage, fallback approaches, what "verified" requires here)
- `shared/references/verification-standard.md` — confidence/verification field discipline
- `shared/references/emotion-pattern-library.md` — what scene types matter most for which story type

## V5 patch addendum — broadcast overlays and HDR

For sports footage, populate `broadcast_overlay_map` from `shared/references/broadcast-overlay-map.md` whenever scorebugs, clocks, logos, lower thirds, or watermarks are visible.

Populate `video_color_metadata` from `shared/references/hdr-sdr-handling.md` before recommending LUTs or color grades. Do not apply ordinary LUT advice before HDR/SDR status is known.

Add `emotion_evidence` when claiming a scene expresses grief, heroism, relief, collapse, disbelief, or national pride.
