# Fresh Setup Overview — AI Creative Director Video Pipeline

## Purpose

This repository is being rebuilt from a clean starting point.

This document describes only the basic setup components for the fresh rebuild.

No architecture decisions, workflow decisions, agent responsibilities, pipeline flow, or technical design choices are finalized here.

---

## 1. Runtime Environment

### Kaggle

Kaggle will be used as the main runtime environment.

The same existing Kaggle notebook and existing Kaggle secrets will be used.

Required Kaggle setup:

- Enable Internet access
- Use the existing Kaggle notebook
- Use the existing Kaggle Secrets
- Clone this GitHub repo inside `/kaggle/working/`
- Run setup/testing from a fresh Kaggle session when needed

Required Kaggle secrets:

- `GITHUB_TOKEN`
- `PRIVATE_REPO_URL`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `DISCORD_WEBHOOK_URL`
- `TAVILY_API_KEY`

---

## 2. Discord Setup

Discord will be used for runtime notifications and status updates.

Required setup:

- Discord server/channel
- Discord webhook URL
- Webhook saved in Kaggle Secrets as `DISCORD_WEBHOOK_URL`

Expected notification use:

- Run started
- Run failed
- Run completed
- Output/report location shared

---

## 3. Current Included Project File

The only required project file currently stored in this repo is the football emotion skill system ZIP.

Expected file:

```text
packages/football_emotion_skill_system_v7_final_runtime.zip
```

This ZIP contains the custom football emotion skill system.

The ZIP should be installed/extracted later during setup into a runtime skill directory such as:

```text
skills/football-emotion/
```

---

## 4. External Components To Be Added Later

These components are not currently stored in the clean repo.

They are expected to be cloned, installed, or connected later during setup.

No technical design decision is finalized here.

---

### Hermes-Agent

Expected future location:

```text
external/Hermes-Agent/
```

Purpose in setup:

- Agent runtime
- Memory system
- Tool/skill usage

---

### OpenMontage

Expected future location:

```text
external/OpenMontage/
```

Purpose in setup:

- Video editing / montage generation
- Rendering support
- FFmpeg-based output flow where required

---

### Claude Video Editor

Claude Video Editor can be considered later as an optional open-source component.

It should only be included after checking:

- Correct repository URL
- License
- Install requirements
- Runtime cost
- Kaggle compatibility
- Whether it overlaps with or conflicts with OpenMontage

Expected future placeholder:

```text
external/claude-video-editor/
```

Status:

```text
Optional / not finalized
```

---

## 5. Current Actual Repo Structure

Current clean repo structure:

```text
acd-video-worker/
├── README.md
└── packages/
    └── football_emotion_skill_system_v7_final_runtime.zip
```

---

## 6. Future Runtime Folder Structure

The runtime folder structure may later become:

```text
acd-video-worker/
├── README.md
├── packages/
│   └── football_emotion_skill_system_v7_final_runtime.zip
├── skills/
│   └── football-emotion/
├── external/
│   ├── Hermes-Agent/
│   ├── OpenMontage/
│   └── claude-video-editor/   # optional
├── bootstrap/
├── scripts/
├── jobs/
├── state/
│   └── runs/
└── outputs/
```

This future structure is only a setup expectation, not an architecture decision.

---

## 7. Fresh Setup Checklist

Current completed base:

- [x] Use current GitHub repo
- [x] Use existing Kaggle notebook
- [x] Use existing Kaggle secrets
- [x] Add football emotion skill system ZIP

Future setup tasks:

- [ ] Clone project in Kaggle
- [ ] Clone Hermes-Agent
- [ ] Clone OpenMontage
- [ ] Optionally inspect Claude Video Editor
- [ ] Install runtime dependencies
- [ ] Install/extract football skill ZIP
- [ ] Validate skill system
- [ ] Check LLM endpoint
- [ ] Check Discord webhook
- [ ] Check source/search tools
- [ ] Run basic smoke test

---

## 8. Important Note

This repository is currently only a clean setup base.

The following must be decided separately in a clean design document:

- Architecture
- Pipeline flow
- Agent responsibilities
- Hermes memory behavior
- Model selection
- Source acquisition strategy
- Rendering strategy
- OpenMontage usage
- Claude Video Editor usage
- Validation and testing strategy