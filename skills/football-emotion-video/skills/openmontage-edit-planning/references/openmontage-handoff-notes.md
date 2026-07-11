# OpenMontage Handoff Notes (reference for openmontage-edit-planning and openmontage-audio-operation-mapper)

## What is documented about the current OpenMontage inspection target (from repo analysis, see `analysis/02_repo_analysis.md`)

- The inspected OpenMontage target is agent-driven — there is no separate orchestrator process to hand a JSON file to.
  "Handoff" in practice means: the agent (Claude Code, Hermes, etc.) reads this skill's output and
  then itself drives OpenMontage's pipeline (`pipeline_defs/`, `skills/pipelines/`, tools) using
  that output as its production plan.
- The inspected OpenMontage target documents artifacts named `brief → script → scene_plan → asset_manifest →
  edit_decisions → render_report → publish_log`, validated against JSON Schemas in
  `schemas/artifacts/`.
- `render_runtime` (Remotion / HyperFrames / FFmpeg) is chosen at the proposal stage and locked
  through `edit_decisions`. OpenMontage's own governance rule: if both Remotion and HyperFrames are
  installed, the agent MUST present both to the user and get explicit approval — silently picking
  one, even a documented "default," is treated as a governance violation in OpenMontage's own
  contract.
- The inspected OpenMontage target's `documentary-montage` pipeline is the closest existing analog (real-footage
  retrieval + editing) but its source corpus (Archive.org, NASA, Wikimedia, Pexels) doesn't include
  YouTube match footage, so this package's discovery skill cannot simply call that pipeline's
  retrieval tool — the two systems meet at the edit-planning/audio-mapping stage, not at discovery.
- The inspected OpenMontage target's `tools/analysis/` (transcription, scene detection, frame sampling) is real and
  reusable — this package's visual-scene-analysis and timestamp-extraction skills should call it.

## What's NOT confirmed — verify before wiring up a real integration

- The exact field names inside the real `schemas/artifacts/edit_decisions.json` schema were not
  retrieved. This package's `openmontage_edit_plan` contract (see
  `shared/contracts/pipeline-artifacts.md`) is designed to be *structurally compatible in spirit*
  (per-section clips/cut-style/transitions/audio/captions) but has not been diffed field-by-field
  against the real schema. **Before wiring this into an actual OpenMontage run, fetch the real
  schema file and reconcile field names.**
- Whether OpenMontage's pipeline/tool registry accepts a wholly new pipeline manifest (e.g. a
  `football-emotion-story.yaml` alongside the 12 shipped pipelines) without core code changes was
  not directly confirmed — the documented architecture strongly suggests yes (pipelines are
  declarative YAML, "no code orchestrator"), but this is an assumption, not a verified fact.
- Exact behavior of `skills/meta/reviewer.md` and `skills/meta/checkpoint-protocol.md` were not
  retrieved — only that they exist and are advisory (reviewer: max 2 rounds). This package's own
  `football-retention-quality-control` skill should be reconciled against the real reviewer skill
  during implementation rather than assumed compatible.

## Practical rule for this skill

State the `render_runtime` field in `openmontage_edit_plan` as a **recommendation** (defaulting to
`hyperframes` per this project's prior architecture decisions), but the SKILL.md body must not
claim this is a final, locked choice — OpenMontage's own proposal-stage confirmation flow governs
the actual lock-in, and this package doesn't override that.
