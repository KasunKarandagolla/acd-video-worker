---
name: openmontage-edit-planning
description: Use when assembling a football emotion story, selected clips, and audio/caption decisions into an executable OpenMontage edit plan — e.g. "build the edit plan for this video", "turn this into an OpenMontage timeline", "assemble the final edit decisions". Activates once selected clips, story plan, and script exist and a concrete, section-by-section OpenMontage-executable timeline is needed. Produces the edit_decisions-shaped artifact OpenMontage consumes; does not itself render video.
---

# OpenMontage Edit Planning

Turns story + selected clips + audio/caption/effect decisions into a concrete, executable edit
plan shaped to match OpenMontage's own `edit_decisions` artifact convention. This skill assembles;
it doesn't invent new creative decisions that other skills own (audio hierarchy comes from
`football-audio-music-director`, cut rhythm from `football-pro-cutting-pacing`, captions from
`football-caption-thumbnail-direction`).

## When to use this

- Selected clips, story plan, and script exist
- An OpenMontage-ready timeline is needed, or an existing plan needs revision

## Required inputs

- `story_plan`
- Scored/selected `clip_candidate` list
- Narration/script text
- Caption plan (if ready — can proceed without and flag as pending)
- Cut/pacing decisions from `football-pro-cutting-pacing` (if ready — can proceed with defaults from `shared/references/pro-editing-methodology.md` otherwise, clearly marked as provisional)
- Audio plan from `football-audio-music-director` (if ready — same provisional-marking rule)

## Workflow

1. For each story-plan section, assign the clips selected for it (`clips: [clip_id]`).
2. Apply cut style per `shared/references/pro-editing-methodology.md`'s decision hierarchy: emotional purpose → story role → clip clarity → audio priority → pacing → effect/caption.
3. Assign transitions using the transition table in that reference — hard cut is the default; anything else needs a reason.
4. Assign effects only per the `effect_policy` table (scene-type-driven, not decorative).
5. Attach caption text if available.
6. Attach audio priority/music action per section from the audio plan (or provisional defaults, clearly marked).
7. **Render runtime**: this project's prior architecture uses HyperFrames, but OpenMontage requires presenting both Remotion and HyperFrames to the user when both are installed and getting explicit confirmation before locking `render_runtime` — this skill states the recommendation but does not silently finalize the choice. See `references/openmontage-handoff-notes.md`.
8. Run the pre-finalization checklist (below) before marking the plan complete.
9. Output `openmontage_edit_plan` (see `shared/contracts/pipeline-artifacts.md`).

## Pre-finalization quality checklist

- Does the hook show emotion within 5-10 seconds?
- Does every major action have a reaction?
- Are emotional moments allowed to breathe (no premature cuts on holds)?
- Is music lower than commentary wherever commentary matters?
- Are effects scene-motivated per the effect policy table?
- Are captions short and useful?
- Is the ending meaningful, not just the last goal?
- Does the plan avoid a reused-content/compilation feel?

This checklist overlaps with `football-retention-quality-control` by design — that skill re-checks
the *finished* plan independently; this checklist just prevents obviously broken plans from being
handed off in the first place.

## Failure modes to avoid

- Vague edit instructions ("make it emotional") instead of concrete per-scene decisions
- Overusing transitions/effects without a stated reason
- Failing to control audio hierarchy (letting music dominate where commentary should)
- Silently locking a render runtime without the OpenMontage-required user confirmation step

## Handoff

Output: `openmontage_edit_plan`. Next skills: `openmontage-audio-operation-mapper` (audio-specific
conversion) and `football-retention-quality-control` (final QC gate before delivery).

## References

- `shared/references/pro-editing-methodology.md` — cutting/pacing/transition/effect/caption rules this skill applies
- `references/openmontage-handoff-notes.md` — what's confirmed vs. assumed about OpenMontage's actual artifact schema and runtime-selection governance
- `shared/references/repo-bridge/openmontage-pipeline-manifest-preflight.md` — manifest-first execution rule
- `shared/references/repo-bridge/openmontage-zero-key-capability-envelope.md` — zero-key/free-first capability guidance

## v3 Timeline Assembly & Visual Cohesion

Before producing final `openmontage_edit_plan`, read:

- `shared/references/editorial-journey/assembly-workflow.md` for build-to-music timeline construction, layer order, handles, and refinement;
- `shared/references/editorial-journey/visual-cohesion.md` for archive/stylized/seamless treatment, aspect ratio decisions, color consistency, and mismatch strategy;
- `shared/references/editorial-journey/graphics-typography.md` for text placement and safe zones.

The edit plan must not be only a sequence of clips. It must include a timeline construction strategy, layer logic, visual cohesion treatment, and places where music-sync matters.


## V4 repo bridge execution rule

Before converting any plan into OpenMontage execution, use `hermes-openmontage-repo-bridge` and read `shared/references/repo-bridge/openmontage-agent-contract.md` plus `shared/references/repo-bridge/openmontage-stage-skill-map.md`.

Do not invent OpenMontage tool calls. Select the pipeline from `pipeline_defs/`, read the stage director skill in `skills/pipelines/`, discover actual tools through `tools.tool_registry`, and only then write `edit_decisions` or auxiliary `projects/<project-id>/football_emotion/` files.

## V5 patch addendum — schema lock and export handoff

Before generating real OpenMontage-native operations, require `openmontage_schema_lock.bridge_status: passed`.

If the schema lock is missing or degraded, output only an `adapter_facing_plan` and list unmapped fields.

After assembly and QC, hand off to `football-platform-export-validator` for export profile and post-render checks.

## V7 addendum — OpenMontage manifest and runtime confirmation

Before converting an adapter-facing plan into native OpenMontage `edit_decisions`, require:

1. selected pipeline manifest read from `pipeline_defs/`;
2. current stage director skill read from `skills/pipelines/`;
3. `tools.tool_registry` provider/support output captured;
4. `openmontage_schema_lock.bridge_status: passed`;
5. render runtime user confirmation if more than one runtime is available.

Render-runtime recommendation language must stay conditional:

```yaml
render_runtime_decision:
  recommendation: remotion | hyperframes | ffmpeg_only | user_confirmation_required
  reason: string
  alternatives_presented: [remotion, hyperframes, ffmpeg_only]
  user_confirmed: false
```

Do not silently lock HyperFrames just because prior project notes preferred it. Do not silently lock Remotion just because OpenMontage uses React scenes. The manifest, provider envelope, project style, and user approval govern the final choice.
