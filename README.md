# Fresh Setup Overview — AI Creative Director Video Pipeline

## Purpose

This repository is being rebuilt from a clean starting point.

This document describes only the basic setup components needed for the fresh rebuild.

No architecture decisions, workflow decisions, or technical design choices are finalized here.

---

## 1. Runtime Environment

### Kaggle

Kaggle will be used as the main runtime environment.

The same existing Kaggle notebook and existing Kaggle secrets will be used.

Required Kaggle setup:

- Enable Internet access
- Use the existing Kaggle Secrets
- Clone this GitHub repo inside /kaggle/working/
- Run setup and testing from a fresh Kaggle session when needed

Required Kaggle secrets:

- GITHUB_TOKEN
- PRIVATE_REPO_URL
- LLM_API_KEY
- LLM_BASE_URL
- LLM_MODEL
- DISCORD_WEBHOOK_URL
- TAVILY_API_KEY

---

## 2. Discord Setup

Discord will be used for runtime notifications and status updates.

Required setup:

- Discord server/channel
- Discord webhook URL
- Webhook saved in Kaggle Secrets as DISCORD_WEBHOOK_URL

Expected notification use:

- Run started
- Run failed
- Run completed
- Output/report location shared

---

## 3. Core Components

### Hermes-Agent

Hermes-Agent will be included as the agent/runtime component.

Expected location:

external/Hermes-Agent/

Setup role:

- Agent runtime
- Memory system
- Tool/skill usage

### OpenMontage

OpenMontage will be included as the video/montage component.

Expected location:

external/OpenMontage/

Setup role:

- Video editing / montage generation
- Rendering support
- FFmpeg-based output flow where required

---

## 4. Skill System

The custom football emotion skill system will be included as a ZIP package.

Expected package:

packages/football_emotion_skill_system_v7_final_runtime.zip

Expected install location:

skills/football-emotion/

Skill system should include:

- Football story strategy
- Source discovery guidance
- Clip selection guidance
- Montage/cutting guidance
- Music/SFX guidance
- Legal-risk review guidance
- Quality review guidance

---

## 5. Optional Additional Repo

### Claude Video Editor

Claude Video Editor can be considered as an optional open-source component.

It should only be included after checking:

- Repository URL
- License
- Install requirements
- Runtime cost
- Kaggle compatibility
- Whether it overlaps or conflicts with OpenMontage

Placeholder location:

external/claude-video-editor/

Status:

Optional / not finalized

---

## 6. Basic Folder Layout

acd-video-worker/
├── bootstrap/
├── jobs/
├── packages/
│   └── football_emotion_skill_system_v7_final_runtime.zip
├── skills/
│   └── football-emotion/
├── external/
│   ├── Hermes-Agent/
│   ├── OpenMontage/
│   └── claude-video-editor/   # optional
├── scripts/
├── state/
│   └── runs/
└── outputs/

---

## 7. Fresh Setup Checklist

- [ ] Use current GitHub repo
- [ ] Use existing Kaggle notebook
- [ ] Use existing Kaggle secrets
- [ ] Clone project in Kaggle
- [ ] Clone Hermes-Agent
- [ ] Clone OpenMontage
- [ ] Install runtime dependencies
- [ ] Install football skill ZIP
- [ ] Validate skill system
- [ ] Check LLM endpoint
- [ ] Check Discord webhook
- [ ] Check source/search tools
- [ ] Run basic smoke test

---

## 8. Important Note

This repository is currently only a clean setup base.

Architecture, pipeline flow, agent responsibilities, memory behavior, model selection, source acquisition strategy, and rendering strategy must be decided separately in a clean design document.
