# OpenMontage Pipeline Manifest Preflight

This reference keeps the package aligned with the confirmed OpenMontage repo: `calesthio/OpenMontage`.

## Rule

OpenMontage work is pipeline-driven. The agent must not improvise a standalone video workflow while ignoring OpenMontage's own manifests, stage skills, schemas, registry, and Backlot gates.

## Required local files to inspect before execution

From the OpenMontage repo root:

```text
AGENT_GUIDE.md
PROJECT_CONTEXT.md
pipeline_defs/<selected-pipeline>.yaml
skills/pipelines/<selected-pipeline>/<stage>-director.md
schemas/artifacts/
tools/tool_registry.py
backlot/
```

If these files cannot be found, output `repo_setup_status.allowed_next_action: simulate_only | stop` and do not write native OpenMontage artifacts.

## Tool-registry commands

Run from the OpenMontage root:

```bash
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.support_envelope(), indent=2))"
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu(), indent=2))"
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu_summary(), indent=2))"
```

Record which capabilities are `passed`, `degraded`, or `blocked`.

## Pipeline selection rule

Football emotion projects usually start as `documentary-montage` candidates because they are real-footage, archive, retrieval, montage, or commentary-led edits. But this is only a candidate.

The agent must read the actual manifest before locking the pipeline.

Alternative candidates:

- `clip-factory` when the user gives one long source and wants multiple short clips.
- `hybrid` when real footage needs generated maps, graphics, title cards, or context inserts.
- `cinematic` when the result is a trailer/teaser rather than explanatory montage.

## Standard OpenMontage stage flow

OpenMontage follows this broad production flow:

```text
research -> proposal -> script -> scene_plan -> assets -> edit -> compose
```

The football-emotion editorial journey wraps around this flow. It does not replace it.

## Stage director rule

Before each real stage, read the selected OpenMontage stage director skill. Then use the football-emotion skill only as domain reasoning support.

Do not let football skills generate native `edit_decisions`, `scene_plan`, or `asset_manifest` fields until `openmontage_schema_lock.bridge_status: passed`.

## Backlot / approval rule

If the manifest or Backlot checkpoint requires human approval, write or request the checkpoint, summarize the waiting decision, and stop at `awaiting_human`.

The agent must not continue past script, asset, render-runtime, or final-export gates when the manifest requires approval.
