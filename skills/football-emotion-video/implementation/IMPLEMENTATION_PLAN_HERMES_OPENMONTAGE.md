# Implementation Plan — Hermes + OpenMontage Integration

## Status of this plan

This is a **greenfield integration plan against the two real upstream repos**
(`NousResearch/hermes-agent`, `calesthio/OpenMontage`), not a patch to an existing local
installation — no local project was found at the originally-assumed path (see
`analysis/02_repo_analysis.md` for why, and what was analyzed instead). Every claim below is
labeled `CONFIRMED` (sourced from official docs/repo files) or `ASSUMPTION` (reasonable inference,
not directly verified). Do not treat `ASSUMPTION` items as settled until checked against a real
checkout.

## What was actually found (confirmed facts, condensed — full detail in analysis/02)

**Hermes (`NousResearch/hermes-agent`):**
- `CONFIRMED`: Skills live at `~/.hermes/skills/[category/]<name>/SKILL.md`, using the exact
  `agentskills.io` open standard — the same shape Claude Code uses. No format translation needed.
- `CONFIRMED`: Skill activation is description-based matching against the user's request text.
- `CONFIRMED`: Skill loading is progressive — a compact `skills_list()` index (~3k tokens for
  *all* installed skills combined) loads at session start; full `SKILL.md` bodies and individual
  reference files load only on demand.
- `CONFIRMED`: Memory is split between small curated files (`MEMORY.md` ~2,200 chars, `USER.md`
  ~1,375 chars, injected into every session) and a SQLite+FTS5 session-search store for larger
  historical recall.
- `CONFIRMED`: No "ToolInterceptor" hook exists in Hermes' documented architecture — that term is
  specific to the person's own separate FireRed-OpenStoryline project, not a Hermes extension point.

**OpenMontage inspection target (`calesthio/OpenMontage`, canonical status unconfirmed):**
- `CONFIRMED`: Also skill-driven internally (`skills/pipelines/`, `skills/core/`, `skills/meta/`),
  with declarative YAML `pipeline_defs/` and Python tools in `tools/{video,audio,graphics,
  enhancement,analysis,avatar,subtitle}/`.
- `CONFIRMED`: `tools/analysis/` provides transcription, scene detection, and frame sampling —
  directly reusable by this package's visual-analysis and timestamp-extraction skills.
- `CONFIRMED`: A `documentary-montage` pipeline already exists for real-footage editing, but its
  source corpus (Archive.org, NASA, Wikimedia, Pexels) doesn't cover YouTube match footage — this
  package's discovery skill cannot reuse its retrieval tool, only its downstream editing/QC pattern.
- `CONFIRMED`: Canonical artifact chain is `brief → script → scene_plan → asset_manifest →
  edit_decisions → render_report → publish_log`, schema-validated.
- `CONFIRMED`: `render_runtime` (Remotion/HyperFrames/FFmpeg) selection requires explicit user
  confirmation when multiple runtimes are installed — OpenMontage treats silent defaulting as a
  governance violation.
- `ASSUMPTION` (high confidence, not directly verified): the pipeline/tool registry will accept a
  new custom pipeline manifest without core code changes, since the architecture is explicitly
  "no code orchestrator, agent reads declarative YAML."
- `NOT CONFIRMED`: exact field names in the real `schemas/artifacts/edit_decisions.json`;
  exact contents of `skills/meta/reviewer.md` / `checkpoint-protocol.md`.

## Repo target clarification

Use `calesthio/OpenMontage` as the current inspection target only. Do not treat it as canonical until the local `/home/kasun/Music/Director/` checkout is matched against it. If the local repo differs, prefer the local repo and update the handoff notes/contracts before coding.

## Phased plan (thin adapters before heavy rewrites, per the task's own constraint)

### Phase 0 — Verify against a real checkout (prerequisite, ~1-2 hours)
1. `git clone` both repos locally.
2. Run this package's `tools/validate_skill_system.py` (already passing structurally).
3. Diff `shared/contracts/pipeline-artifacts.md`'s `openmontage_edit_plan` and
   `openmontage_audio_operations` shapes against the real `schemas/artifacts/edit_decisions.json`
   (or equivalent) and reconcile field names.
4. Confirm the real signature of `tools/analysis/`'s scene-detection and frame-sampling tools
   (exact CLI flags / Python API) referenced illustratively in
   `football-visual-scene-analysis/references/frame-extraction-approach.md`.
5. Read the real `skills/meta/reviewer.md` and reconcile against
   `football-retention-quality-control`'s checklist so the two don't duplicate or contradict work.

### Phase 1 — Install as a Hermes skill directory, no OpenMontage wiring yet (~30 min)
1. Copy `skills/` into `~/.hermes/skills/football-emotion/` (or add this package's `skills/`
   folder as an external skill directory per Hermes' documented external-dirs mechanism).
2. Run a few of the discovery/story-strategy/clip-scoring skills manually to sanity-check
   activation phrasing against real Hermes description-matching behavior — this is the cheapest
   possible validation step before touching OpenMontage at all.
3. Confirm the combined skill index token cost is acceptable (Hermes' own docs cite ~3k tokens for
   *all* skills combined as the healthy baseline — verify this package doesn't blow that budget
   alongside whatever else is already installed).

### Phase 2 — Wire the audio subsystem's mandatory gate (~1-2 hours)
Per this package's own architecture decision, the minimum-viable production gate is:
`football-rights-safe-audio-license-checker`, `football-audio-music-director`,
`football-commentary-ducking-mixer`, `openmontage-audio-operation-mapper`. Get these four working
end-to-end on a manually-provided test case *before* wiring up the full discovery→scoring→editing
chain — this is the highest-consequence part of the system (real copyright/Content-ID risk) and
should be validated in isolation first.

### Phase 3 — Connect to The inspected OpenMontage target's `tools/analysis/` (~2-4 hours)
1. Point `football-visual-scene-analysis` and `football-timestamp-extraction` at OpenMontage's
   real frame-sampling/scene-detection/transcription tools (replacing the illustrative ffmpeg
   fallback in the reference file with the confirmed real invocation).
2. Test on one real football video end-to-end: extraction → frame viewing → scene analysis →
   timestamp extraction → clip scoring.

### Phase 4 — Build (or adapt) a custom OpenMontage pipeline manifest (~half day, higher uncertainty)
1. Draft `pipeline_defs/football-emotion-story.yaml` modeled on `documentary-montage`'s manifest
   shape (once read), with stages matching this package's orchestration flow (see
   `analysis/04_skill_architecture_decision.md`).
2. Register `openmontage-edit-planning`'s output as the stage director skill for the `edit` stage,
   consuming this package's `openmontage_edit_plan` contract, translated to match the real
   `edit_decisions` schema per Phase 0's reconciliation.
3. Keep `documentary-montage`'s existing `edit` stage gate (human-approval-required) as the model —
   this package's own `football-retention-quality-control` gate should sit *before* that approval
   step, not replace it.
4. This phase carries the most integration risk in the whole plan, since the pipeline-manifest
   loader's exact requirements were not directly verified (Phase 0, item 3) — budget extra time and
   be ready to fall back to "agent manually drives OpenMontage's existing tools using this
   package's plan as a written brief" if a fully custom pipeline manifest proves harder to register
   than the architecture documentation suggests.

### Phase 5 — Wire Hermes memory (~1 hour)
1. Confirm `hermes-football-memory-learning`'s output actually fits Hermes' real MEMORY.md/USER.md
   write mechanism (likely via whatever memory-write tool/command Hermes exposes to skills — check
   Hermes' developer docs for the exact tool name, not assumed here).
2. Confirm `session_search` (SQLite FTS5) is the right fallback for the
   `full_project_record_path` pointer pattern this package uses for anything too large for
   MEMORY.md, or whether a simpler "write to a project file and just mention the path in memory" is
   sufficient without needing FTS5 integration at all.

## What this plan deliberately does NOT do

- Does not require any paid API at any phase.
- Does not require a local LLM/VLM — visual understanding is achieved via OpenMontage's
  frame-extraction tools plus the coding agent's own multimodal viewing throughout.
- Does not modify OpenMontage's or Hermes' own core code — every integration point is either a new
  skill folder (Hermes-native mechanism) or a new declarative pipeline manifest (OpenMontage-native
  mechanism), consistent with "thin adapters before heavy rewrites."
- Does not build automated beat-detection, loudness-normalization, or Content-ID-database tooling —
  these remain documented, scoped gaps (see
  `football-audio-quality-control/references/beat-loudness-manual-checklist.md`) with a clear
  future-tool recommendation, not silently assumed to exist.

## Production blockers before the first real video (be honest about these)

1. **Phase 0 must actually happen.** Every OpenMontage-facing contract in this package is a
   best-effort design based on documented conventions, not a verified schema match.
2. **The audio license-verification gate is a process, not automation.** Someone (human or agent)
   still has to actually open each asset's exact page and read the license — this package defines
   the checklist and refusal behavior, not a scraper.
3. **Beat/loudness targets are unmeasured specifications**, not verified output, until real audio
   tooling (OpenMontage's `tools/audio/`, or a future `beat_detector`/`loudness_normalizer`) is
   wired in and actually run.
4. **The custom pipeline-manifest registration path (Phase 4) is the least-verified part of this
   entire plan** — budget the most schedule risk there.

## Immediate next action

Run Phase 0 against real checkouts of both repos. Everything past that point depends on what Phase
0 actually finds.


---

## V3 Editorial Journey Implementation Addendum

Before wiring new code, register `social-edit-reasoning` and the `shared/references/editorial-journey/` files. The first runtime integration should not be a renderer change; it should be a stage-state artifact.

### New minimum runtime artifacts

1. `brief_interpretation.yaml` — created before sourcing.
2. `editorial_journey_state.yaml` — updated at every stage.
3. `visual_cohesion_plan.yaml` — required before final OpenMontage plan.
4. `graphics_text_plan.yaml` — required if text/captions/thumbnail direction exist.
5. `assembly_plan.yaml` — build-to-music/cuts-first decision and critical sync markers.
6. `full_qa_report.yaml` — final QA with loopback instructions.

### Adapter priority

1. Add artifact files first; do not change OpenMontage internals yet.
2. Teach the agent to call stage references in order.
3. Add OpenMontage mappings for visual cohesion, graphics/text, and assembly_plan only after the artifact shape is stable.
4. Keep license/audio gates unchanged.

### First live test

Use a 30-60 second football comeback edit before a long-form 8-12 minute video. The short test makes stage skipping easier to see while still exercising brief → sourcing → curation → music → assembly → QA.


## V4 repo bridge note

The v4 bridge supersedes earlier uncertainty about the OpenMontage repo. Use `calesthio/OpenMontage` and `NousResearch/Hermes-Agent`, but still inspect the local pinned commits before modifying code. Do not bypass OpenMontage's pipeline manifests, stage director skills, tool registry, or checkpoint protocol.

See `implementation/HERMES_OPENMONTAGE_REPO_BRIDGE_PLAN.md` for the execution-safe plan.
