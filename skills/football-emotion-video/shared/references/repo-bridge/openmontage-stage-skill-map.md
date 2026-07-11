# OpenMontage Stage ↔ Football Skill Map

This map prevents the agent from losing its journey inside OpenMontage.

OpenMontage is the execution engine. The football skills are decision helpers that produce or enrich canonical OpenMontage artifacts.

| OpenMontage stage | OpenMontage artifact | Football/editorial skills to consult | Purpose |
|---|---|---|---|
| research | research brief / source notes | `social-edit-reasoning`, `football-source-discovery`, `football-visual-scene-analysis` | Convert brief into searchable football story, collect source candidates, verify facts. |
| proposal / idea | brief / production plan | `social-edit-reasoning`, `football-story-strategy`, `football-audio-music-director`, `football-music-library-selector` | Lock emotional question, platform, runtime, tone, pipeline, music situation, and user approval path. |
| script | script | `football-narration-scriptwriting`, `football-story-strategy` | Create faceless narration/commentary structure that transforms clips into a story. |
| scene_plan | scene_plan | `football-timestamp-extraction`, `football-clip-scoring`, `football-pro-cutting-pacing`, `football-caption-thumbnail-direction` | Assign clips to arc phases, define timing, text beats, captions, visual treatment. |
| assets | asset_manifest | `football-source-discovery`, `football-rights-safe-audio-license-checker`, `football-music-library-selector`, `football-visual-scene-analysis` | Link exact media paths, license records, source provenance, and review status. |
| edit | edit_decisions | `openmontage-edit-planning`, `openmontage-audio-operation-mapper`, `football-commentary-ducking-mixer`, `football-audio-quality-control` | Convert story/scene/audio decisions into executable edit decisions. |
| compose | render_report | `football-retention-quality-control`, `football-audio-quality-control` | Validate before/after render: audio, visuals, captions, timing, Content ID/reused-content risk. |
| post-run memory | memory update | `hermes-football-memory-learning` | Store reusable lessons and avoid repeating failures. |

## Routing order

1. Read `social-edit-reasoning` for stage routing.
2. Read the selected OpenMontage pipeline stage director skill.
3. Read only the football skill needed for that stage's decision.
4. Produce the canonical OpenMontage artifact.
5. Run reviewer/checkpoint policy according to the manifest.

## No duplicate pipeline

Do not create a parallel football pipeline outside OpenMontage unless a later local repo analysis proves OpenMontage cannot accept this workflow. Use the existing pipeline mechanism first.
