# Repo Source Lock — Hermes + OpenMontage

This package is now bridged to these exact upstream repositories:

| Role | Repository | Local path expected | Why it is locked |
|---|---|---|---|
| Reasoning agent, long-term learning, user interaction, skills | `https://github.com/NousResearch/Hermes-Agent` | `/home/kasun/Music/Director/Hermes-Agent` | Hermes provides CLI/TUI, provider/model switching, tools, gateway, memory/learning loop, skills, and subagent-style work. |
| Video production engine, pipeline manifests, tool registry, Backlot, render/composition | `https://github.com/calesthio/OpenMontage` | `/home/kasun/Music/Director/OpenMontage` | OpenMontage is pipeline-driven and exposes `pipeline_defs/`, `skills/`, `.agents/skills/`, `tools/`, `schemas/`, `backlot/`, and `remotion-composer/`. |

## Hard boundary

The football emotion skill system is not a replacement for either repo.

- Hermes remains the reasoning/runtime host.
- OpenMontage remains the video production engine.
- This package is the bridge layer: editorial intelligence + football emotion specialization + audio/license safety + artifact handoff rules.

## Pinning commands

```bash
cd /home/kasun/Music/Director/Hermes-Agent
git rev-parse HEAD > ../HERMES_AGENT_PINNED_COMMIT.txt

cd /home/kasun/Music/Director/OpenMontage
git rev-parse HEAD > ../OPENMONTAGE_PINNED_COMMIT.txt
```

Do not treat docs in this skill package as newer than the local pinned commits. If local repo behavior differs, inspect the local source and update this bridge.
