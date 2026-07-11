---
name: hermes-openmontage-repo-bridge
description: "Use this skill whenever the user wants the football emotion skill system installed, adapted, simulated, or executed inside the confirmed NousResearch/Hermes-Agent plus calesthio/OpenMontage setup. This skill anchors all creative football-video skills to the exact repo layout, OpenMontage pipeline manifests, tool registry, Backlot checkpoints, Hermes skills/memory behavior, and local project paths so the agent does not invent tools, bypass OpenMontage pipelines, or lose the execution contract."
---

# Hermes + OpenMontage Repo Bridge

## Purpose

Bridge the football emotion editorial skill system to the confirmed repos:

- Hermes: `NousResearch/Hermes-Agent`
- OpenMontage: `calesthio/OpenMontage`

This skill does not replace any football creative skill. It tells the agent how to use those skills **inside the actual repo contracts**.

## Use when

Use this before:

- installing the skill system into Hermes
- running a football video project through OpenMontage
- writing OpenMontage edit decisions
- making a local implementation plan
- simulating the full pipeline with exact repo behavior
- debugging why a skill output does not match OpenMontage's expected artifacts

## Required references

Read these in order:

1. `shared/references/repo-bridge/repo-source-lock.md`
2. `shared/references/repo-bridge/hermes-agent-contract.md`
3. `shared/references/repo-bridge/openmontage-agent-contract.md`
4. `shared/references/repo-bridge/openmontage-tool-registry-preflight.md`
5. `shared/references/repo-bridge/openmontage-stage-skill-map.md`
6. `shared/contracts/openmontage-artifact-bridge.md`
7. `shared/references/repo-bridge/hermes-runtime-skill-install.md`
8. `shared/references/repo-bridge/openmontage-pipeline-manifest-preflight.md`
9. `shared/references/repo-bridge/openmontage-zero-key-capability-envelope.md`

## Workflow

### 1. Confirm local repo paths

Expected (configurable via `HERMES_HOME` and `OPENMONTAGE_PROJECTS_DIR`):

```text
$HERMES_HOME/../Hermes-Agent          (or HERMES_AGENT_PATH env)
$OPENMONTAGE_PROJECTS_DIR/../OpenMontage  (or OPENMONTAGE_PATH env)
```

If either path is missing, stop and report the missing clone/setup step.

### 2. Read Hermes/OpenMontage runtime contracts

Before tool calls, read `shared/references/repo-bridge/hermes-runtime-skill-install.md` and `shared/references/repo-bridge/openmontage-pipeline-manifest-preflight.md`. Hermes is the reasoning/memory host; OpenMontage is the pipeline-driven production engine.

### 3. Run OpenMontage capability preflight

From OpenMontage root, run provider/capability discovery through `tools.tool_registry`. Do not assume provider availability from docs.

Minimum command:

```bash
cd $OPENMONTAGE_PROJECTS_DIR/../OpenMontage
source .venv/bin/activate
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu_summary(), indent=2))"
```

### 4. Select OpenMontage pipeline first

For football emotion videos, start by inspecting:

```text
pipeline_defs/documentary-montage.yaml
```

Only choose another pipeline if the manifest/tool situation makes it better.

### 5. Read stage director skill

Before executing a stage, read the pipeline's stage director skill under:

```text
skills/pipelines/<pipeline>/<stage>-director.md
```

Then use the football skill only as domain reasoning support.

### 6. Keep artifacts under project workspace

All project outputs go under:

```text
$OPENMONTAGE_PROJECTS_DIR/<project-id>/
```

Football-specific auxiliary artifacts go under:

```text
$OPENMONTAGE_PROJECTS_DIR/<project-id>/football_emotion/
```

### 7. Respect human gates

If the manifest requires approval, write `awaiting_human`, summarize the artifact, and stop.

### 8. Update Hermes memory after completion

After QA/render, use `hermes-football-memory-learning` to write a memory update about what worked and what failed.

## Failure modes to avoid

- Do not call OpenMontage tools with imagined function names.
- Do not bypass `pipeline_defs/` and stage director skills.
- Do not silently downgrade render runtime.
- Do not invent music/license safety.
- Do not write assets outside `projects/<project-id>/`.
- Do not continue past a human approval gate.
- Do not treat auxiliary football artifacts as canonical OpenMontage schema fields until validated.

## V5 patch addendum — setup and schema locks

At the start of every repo-backed run, create `repo_setup_status` using `shared/references/repo-bridge/repo-setup-status.md`.

If local Hermes/OpenMontage paths are absent, the only allowed actions are `stop` or `simulate_only`; do not claim tool registry preflight passed.

After repo setup passes, create `openmontage_schema_lock` using `shared/references/repo-bridge/openmontage-schema-lock.md`. Do not produce real OpenMontage `edit_decisions`, `asset_manifest`, `scene_plan`, or `render_report` fields until `bridge_status: passed`.

## V7 addendum — manifest-first and zero-key-first

For OpenMontage-backed work, use `shared/references/repo-bridge/openmontage-pipeline-manifest-preflight.md` before choosing any pipeline as final. `documentary-montage` is a strong candidate for real-footage football montage, but it is not a universal default.

Use `shared/references/repo-bridge/openmontage-zero-key-capability-envelope.md` to prefer free/open tools first. Do not assume paid API providers, local GPU video models, or unavailable providers.

If both Remotion and HyperFrames are available, present a short user-confirmation prompt before locking render runtime:

```text
OpenMontage can render this through Remotion or HyperFrames.
- Remotion is better for React/timeline/data/caption-heavy scenes.
- HyperFrames is better for HTML/CSS/GSAP/motion-graphics-heavy scenes.
For this project I recommend: <runtime> because <reason>.
Do you approve this render runtime?
```
