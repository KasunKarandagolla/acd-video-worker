# Hermes + OpenMontage Repo Bridge Implementation Plan

## Goal

Connect the football emotion skill system to the confirmed repos without rewriting either repo.

## Confirmed repos

- Hermes: `https://github.com/NousResearch/Hermes-Agent`
- OpenMontage: `https://github.com/calesthio/OpenMontage`

## Phase 0 — Clone and pin

```bash
cd /home/kasun/Music/Director
git clone https://github.com/NousResearch/Hermes-Agent.git Hermes-Agent
git clone https://github.com/calesthio/OpenMontage.git OpenMontage
cd Hermes-Agent && git rev-parse HEAD > ../HERMES_AGENT_PINNED_COMMIT.txt
cd ../OpenMontage && git rev-parse HEAD > ../OPENMONTAGE_PINNED_COMMIT.txt
```

## Phase 1 — Install/setup OpenMontage

```bash
cd /home/kasun/Music/Director/OpenMontage
make setup
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu_summary(), indent=2))"
```

Save output to:

```text
/home/kasun/Music/Director/openmontage_provider_menu_summary.json
```

## Phase 2 — Place skill system

Keep this package as:

```text
/home/kasun/Music/Director/football_emotion_skill_system_v4_repo_bridge
```

Expose it to Hermes by copying/symlinking `skills/` into a Hermes-supported skill path. Recommended if editing repo directly:

```text
Hermes-Agent/optional-skills/creative/football-emotion-video/
```

Do not overwrite OpenMontage core skill directories.

## Phase 3 — Add project context to OpenMontage sessions

When running a football video job in OpenMontage, always include:

```text
shared/references/repo-bridge/openmontage-agent-contract.md
shared/references/repo-bridge/openmontage-stage-skill-map.md
shared/contracts/openmontage-artifact-bridge.md
```

## Phase 4 — Build thin adapter only after schema inspection

Do not write a bridge adapter until you inspect local:

```text
OpenMontage/schemas/artifacts/
OpenMontage/pipeline_defs/documentary-montage.yaml
OpenMontage/skills/pipelines/documentary-montage/
OpenMontage/tools/tool_registry.py
```

The adapter should only translate football auxiliary artifacts into valid `edit_decisions`, `asset_manifest`, and `render_report` fields. It must not duplicate OpenMontage's pipeline runner.

## Phase 5 — Real run skeleton

1. User brief
2. `social-edit-reasoning` brief interpretation
3. OpenMontage preflight/provider menu
4. Select `documentary-montage` unless manifest proves otherwise
5. Research/source stage
6. Proposal gate including music plan
7. Script/scene_plan/assets/edit/compose through OpenMontage stage directors
8. Football skills enrich each stage only where needed
9. QA + render validation
10. Hermes memory update

## Production blockers to check early

- No legal/user-authorized football source footage path
- No video analysis/transcript/frame-sampling tools available
- No music source or no license-verifiable audio
- No available composition runtime matching proposal
- No clear OpenMontage artifact schema match for edit decisions
- Human gate not approved

## Non-goal

This phase does not patch creative weaknesses from previous simulations. It only makes the skill system repo-aware and execution-safe.
