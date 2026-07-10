# Frame Extraction Approach (reference for football-visual-scene-analysis)

This project has no bundled vision-language model (per the task's "no local LLM/VLM requirement").
"Visual scene analysis" here means: extract frames mechanically, then have the coding agent (which
already has multimodal viewing capability) actually look at them. This file describes the concrete
approach, in priority order.

## Priority 1 — use OpenMontage's existing analysis tools

OpenMontage ships `tools/analysis/` with transcription, scene-detection, and frame-sampling
capability (documented in the OpenMontage repo; see this package's
`implementation/IMPLEMENTATION_PLAN_HERMES_OPENMONTAGE.md` for what's confirmed vs. assumed about
exact tool names/APIs). If OpenMontage is installed as a sibling project, call its scene-detection
and frame-sampling tools via terminal rather than writing new extraction code:

```bash
# illustrative — confirm the exact CLI/API against the installed OpenMontage version
python tools/analysis/scene_detect.py --input <video_path> --output <scenes.json>
python tools/analysis/frame_sample.py --input <video_path> --scenes <scenes.json> --output <frames_dir>
```

Then use the file-viewing tool to actually open the sampled frames from `<frames_dir>` and
describe what's in them. This satisfies both "no bundled VLM required" (the coding agent's own
multimodal capability does the looking) and "no fake timestamps" (frames are tied to real
extracted positions in the source file).

## Priority 2 — direct ffmpeg extraction (if OpenMontage isn't available)

```bash
# extract one frame every 2 seconds as a fallback sampling strategy
ffmpeg -i <video_path> -vf fps=1/2 <frames_dir>/frame_%04d.png
```
Then view the frames directly. This is coarser than scene-aware sampling but keeps the
"actually look at real extracted frames" discipline intact.

## Priority 3 — audio-only or transcript-only analysis

If frames genuinely can't be extracted (e.g., only a transcript is available), scene analysis can
proceed on audio/commentary alone, but every `visual_description` field in the output must be left
empty or marked `unusable` rather than inferred from the transcript — audio evidence does not
verify visual claims.

## What counts as "verified" here

- `high` confidence: the agent viewed an actual frame at/near that timestamp AND has audio/transcript
  confirming the same moment.
- `medium` confidence: only one of the two (frame or audio) was reviewed.
- `low` confidence: neither was reviewed — the row is based on plausible inference from context
  (e.g., "this match is known to have had a penalty shootout" without having viewed that segment).
- `unusable`: no reliable access to the source at all.

Never silently promote a `low`/`medium` row to `high` because the surrounding context makes the
claim seem obviously true. The whole point of this discipline is to protect downstream skills
(timestamp extraction, clip scoring, edit planning) from inheriting a confident-sounding guess.

## The seven editor questions

Every scene row should be able to answer these (from the source pack's timestamp methodology):

1. What exactly happens visually?
2. What exactly happens in audio/commentary/music?
3. What is the scene's emotional job?
4. Why should this clip be kept or rejected?
5. Where should it appear in an 8-12 minute story?
6. What edit treatment should OpenMontage apply?
7. What reusable lesson should Hermes remember?

A row that can only answer 2-3 of these isn't a finished scene analysis — either do more review or
mark it `manual_review_needed: true` and move on.
