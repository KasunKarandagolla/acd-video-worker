# OpenMontage Agent Contract for This Skill System

Use this reference before producing or executing any OpenMontage plan.

## Rule zero

OpenMontage production is pipeline-driven. Do not bypass it with ad-hoc scripts.

The agent must work through:

1. `pipeline_defs/` — select and read the pipeline manifest.
2. `skills/pipelines/<pipeline>/...` — read the stage director skill for the current stage.
3. `tools/tool_registry.py` — discover actual configured tools and providers.
4. `schemas/artifacts/` — validate canonical stage artifacts.
5. `projects/<project-id>/checkpoint_<stage>.json` — write checkpoints for Backlot and human gates.

## OpenMontage layout this bridge expects

```text
OpenMontage/
├── AGENT_GUIDE.md
├── PROJECT_CONTEXT.md
├── pipeline_defs/
├── skills/
│   ├── core/
│   ├── creative/
│   ├── meta/
│   └── pipelines/
├── .agents/skills/
├── tools/
│   ├── analysis/
│   ├── audio/
│   ├── avatar/
│   ├── capture/
│   ├── character/
│   ├── enhancement/
│   ├── graphics/
│   ├── subtitle/
│   ├── video/
│   ├── base_tool.py
│   └── tool_registry.py
├── schemas/
├── backlot/
├── remotion-composer/
└── projects/
```

## First files to read in OpenMontage

Before a real run:

1. `AGENT_GUIDE.md`
2. `PROJECT_CONTEXT.md`
3. selected `pipeline_defs/<pipeline>.yaml`
4. selected stage director skill under `skills/pipelines/`
5. registry output from `tools.tool_registry`

## Pipeline choice for football emotion videos

Default candidate pipeline:

```text
documentary-montage
```

Use it when the video is real-footage, sourced-footage, archive, World Cup, football emotion, comeback, heartbreak, legacy, or montage-style.

Alternative candidates:

- `clip-factory`: when starting from one long source video and extracting multiple clips.
- `hybrid`: when combining real footage with AI support visuals, title cards, graphics, maps, or generated inserts.
- `cinematic`: when the deliverable is more trailer/teaser than documentary montage.

Never choose from memory only. Read the actual manifest first.

## Stage artifact alignment

OpenMontage standard stage flow:

```text
research -> proposal -> script -> scene_plan -> assets -> edit -> compose
```

This skill package's editorial journey maps onto that flow but does not replace it. The bridge mapping lives in `shared/references/repo-bridge/openmontage-stage-skill-map.md`.

## Backlot/project workspace rule

Every production artifact must live under:

```text
OpenMontage/projects/<project-id>/
```

Do not write real production outputs into the repo root, `/tmp`, or random working folders. Backlot and checkpoints depend on the project workspace.

## Human gate rule

If the selected pipeline manifest says a stage requires human approval, stop at `awaiting_human`, present the artifact summary, and wait. Do not continue in the same turn.
