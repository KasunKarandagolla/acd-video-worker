# Session 2 Build Plan — Infrastructure & Skill Installation

**Scope:** Exact work for next large OpenCode session  
**Goal:** Install, validate, and wire Hermes + OpenMontage + Football Emotion skills; achieve **Setup Validation** gate  
**Duration Target:** 1 session (4-6 hours)  
**Prerequisites:** This architecture doc set completed; upstream repos cloned at pinned commits

---

## 1. Files to Create

| Path | Purpose | Dependencies |
|------|---------|--------------|
| `bootstrap/install_hermes.sh` | Clone Hermes at pinned commit, run `setup-hermes.sh`, create profile `football-emotion` | `upstream-lock.json` |
| `bootstrap/install_openmontage.sh` | Clone OpenMontage at pinned commit, run `make setup`, verify tool registry | `upstream-lock.json` |
| `bootstrap/install_skills.sh` | Extract football V7 ZIP to `~/.hermes/skills/football-emotion-video/` (or Hermes external skill dir) | `packages/football_emotion_skill_system_v7_final_runtime.zip` |
| `bootstrap/validate_setup.py` | Run `bridge_preflight.py` + `validate_skill_system.py` + tool registry preflight; exit 0 only if all pass | Hermes, OpenMontage, Skills installed |
| `bootstrap/kaggle_persistence.sh` | Create symlinks: `~/.hermes → /kaggle/working/.hermes`, `OPENMONTAGE_PROJECTS_DIR=/kaggle/working/projects` | Kaggle environment |
| `scripts/acd_worker.py` | Skeleton orchestrator: create Hermes session, load skills, enforce editorial journey, manage project workspace, Discord notify | Hermes CLI/API, OpenMontage `lib/checkpoint.py` |
| `scripts/football_footage_acquisition.py` | NEW skill implementation: sequential download via `video_downloader`, failure replacement, `source_media_review` builder | OpenMontage `video_downloader`, `audio_probe`, `frame_sampler`, `transcriber` |
| `skills/football-emotion-video/football-footage-acquisition/SKILL.md` | Skill definition for acquisition subsystem | `pipeline-artifacts.md` contracts |
| `docs/SESSION_02_NOTES.md` | Session log: commands run, outputs, issues, decisions | — |

---

## 2. Files to Modify

| Path | Change |
|------|--------|
| `packages/football_emotion_skill_system_v7_final_runtime/skills/football-source-discovery/SKILL.md` | Add explicit step: "Output candidates to `football-footage-acquisition` skill" |
| `packages/football_emotion_skill_system_v7_final_runtime/skills/hermes-openmontage-repo-bridge/SKILL.md` | Make install path configurable via `HERMES_HOME` / external skill dir |
| `packages/football_emotion_skill_system_v7_final_runtime/skills/openmontage-edit-planning/SKILL.md` | Remove HyperFrames default; add schema-lock gate enforcement |
| `packages/football_emotion_skill_system_v7_final_runtime/skills/openmontage-audio-operation-mapper/SKILL.md` | Map `openmontage_audio_operations` → `edit_decisions.audio` schema |
| `packages/football_emotion_skill_system_v7_final_runtime/skills/football-visual-scene-analysis/references/frame-extraction-approach.md` | Replace illustrative ffmpeg with `tool_registry` calls to `frame_sampler` + `scene_detect` |
| `packages/football_emotion_skill_system_v7_final_runtime/skills/football-match-identification/SKILL.md` | Replace "fact lock" with explicit human verification gate |

---

## 3. Setup Work (Commands to Execute)

```bash
# 0. Ensure working directory
cd /home/kasun/Music/Director/acd-video-worker

# 1. Clone upstream repos at pinned commits
git clone https://github.com/NousResearch/Hermes-Agent.git external/Hermes-Agent
cd external/Hermes-Agent && git checkout 5ecc07986f46463ca3096679b03a46402eb19cee && cd ../..

git clone https://github.com/calesthio/OpenMontage.git external/OpenMontage
cd external/OpenMontage && git checkout f633b5f428b9be9a2afecba851dfddd101619756 && cd ../..

# 2. Install Hermes
bash external/Hermes-Agent/setup-hermes.sh
# → Creates ~/.hermes, installs uv venv, symlinks hermes CLI

# 3. Create football-emotion profile (isolated workspace)
hermes profile create football-emotion --clone-all
# → ~/.hermes/profiles/football-emotion/ with config, skills, memory

# 4. Install OpenMontage
cd external/OpenMontage && make setup && cd ../..
# → Python venv, npm install (Remotion), Piper TTS, HyperFrames cache-warm

# 5. Extract football V7 skills
mkdir -p ~/.hermes/profiles/football-emotion/skills/football-emotion-video
unzip -o packages/football_emotion_skill_system_v7_final_runtime.zip -d ~/.hermes/profiles/football-emotion/skills/football-emotion-video/

# 6. Validate skill system
python3 ~/.hermes/profiles/football-emotion/skills/football-emotion-video/tools/validate_skill_system.py \
  ~/.hermes/profiles/football-emotion/skills/football-emotion-video/

# 7. Run bridge preflight
python3 ~/.hermes/profiles/football-emotion/skills/football-emotion-video/tools/bridge_preflight.py \
  --base /home/kasun/Music/Director --stdout

# 8. OpenMontage tool registry preflight
cd external/OpenMontage && python3 -c "
from tools.tool_registry import registry
import json
registry.discover()
print(json.dumps(registry.provider_menu_summary(), indent=2))
" > /tmp/om_provider_menu.json && cd ../..

# 9. Kaggle persistence (if on Kaggle)
ln -sf /kaggle/working/.hermes ~/.hermes
mkdir -p /kaggle/working/projects
export OPENMONTAGE_PROJECTS_DIR=/kaggle/working/projects
```

---

## 4. Tests to Pass (Completion Gates)

| Gate | Command | Success Criteria |
|------|---------|------------------|
| **Hermes Install** | `hermes --version` | Shows version, no errors |
| **Hermes Profile** | `hermes -p football-emotion chat -q "hello"` | Responds in football-emotion profile |
| **Skill Load** | `hermes -p football-emotion skills list` | Lists all 23 football-emotion skills |
| **Skill Validation** | `python3 .../validate_skill_system.py ...` | **PASSED** (0 errors, 0 warnings) |
| **Bridge Preflight** | `python3 .../bridge_preflight.py --base ... --stdout` | `repo_setup_status.preflight_possible: true`, `allowed_next_action: proceed` |
| **OpenMontage Install** | `cd external/OpenMontage && python3 -c "import lib.config_model; print('OK')"` | Imports cleanly imports clean |
| **Tool Registry** | `cat /tmp/om_provider_menu.json` | Shows `ffmpeg: true` for composition_runtimes; analysis/audio tools available |
| **Pipeline Load** | `cd external/OpenMontage && python3 -c "from lib.pipeline_loader import load_pipeline; p=load_pipeline('documentary-montage'); print(p['name'])"` | Loads `documentary-montage` manifest |
| **Schema Validation** | `cd external/OpenMontage && python3 -c "from schemas.artifacts import validate_artifact; validate_artifact('edit_decisions', {'version':'1.0','cuts':[],'render_runtime':'ffmpeg'})"` | No validation error |

---

## 5. Session 2 Deliverables Checklist

- [ ] `external/Hermes-Agent/` at commit `5ecc079`
- [ ] `external/OpenMontage/` at commit `f633b5f`
- [ ] `~/.hermes/profiles/football-emotion/` with skills installed
- [ ] `validate_skill_system.py` → **PASSED**
- [ ] `bridge_preflight.py` → `repo_setup_status.allowed_next_action: proceed`
- [ ] OpenMontage tool registry preflight JSON saved
- [ ] `documentary-montage` pipeline loads + stage director skills readable
- [ ] `scripts/acd_worker.py` skeleton runs (creates session, loads profile)
- [ ] `scripts/football_footage_acquisition.py` downloads 1 test clip → `source_media_review` valid
- [ ] Kaggle persistence symlinks created (if on Kaggle)
- [ ] `docs/SESSION_02_NOTES.md` written

---

## 6. Commands for Next Session to Execute (Copy-Paste Ready)

```bash
# --- BEGIN SESSION 2 COMMANDS ---
cd /home/kasun/Music/Director/acd-video-worker

# 1. Clone & pin repos
git clone https://github.com/NousResearch/Hermes-Agent.git external/Hermes-Agent
cd external/Hermes-Agent && git checkout 5ecc07986f46463ca3096679b03a46402eb19cee && cd ../..

git clone https://github.com/calesthio/OpenMontage.git external/OpenMontage
cd external/OpenMontage && git checkout f633b5f428b9be9a2afecba851dfddd101619756 && cd ../..

# 2. Install Hermes
bash external/Hermes-Agent/setup-hermes.sh

# 3. Create football-emotion profile
hermes profile create football-emotion --clone-all

# 4. Install OpenMontage
cd external/OpenMontage && make setup && cd ../..

# 5. Extract skills
mkdir -p ~/.hermes/profiles/football-emotion/skills/football-emotion-video
unzip -o packages/football_emotion_skill_system_v7_final_runtime.zip -d ~/.hermes/profiles/football-emotion/skills/football-emotion-video/

# 6. Validate skills
python3 ~/.hermes/profiles/football-emotion/skills/football-emotion-video/tools/validate_skill_system.py \
  ~/.hermes/profiles/football-emotion/skills/football-emotion-video/

# 7. Bridge preflight
python3 ~/.hermes/profiles/football-emotion/skills/football-emotion-video/tools/bridge_preflight.py \
  --base /home/kasun/Music/Director --output /tmp/bridge_preflight.md

# 8. OpenMontage tool registry preflight
cd external/OpenMontage && python3 -c "
from tools.tool_registry import registry
import json
registry.discover()
print(json.dumps(registry.provider_menu_summary(), indent=2))
" > /tmp/om_provider_menu.json && cd ../..

# 9. Verify pipeline
cd external/OpenMontage && python3 -c "
from lib.pipeline_loader import load_pipeline, list_pipelines
print('Pipelines:', list_pipelines())
p = load_pipeline('documentary-montage')
print('Loaded:', p['name'])
print('Stages:', [s['name'] for s in p['stages']])
" && cd ../..

# 10. Kaggle persistence (if on Kaggle)
ln -sf /kaggle/working/.hermes ~/.hermes
mkdir -p /kaggle/working/projects
export OPENMONTAGE_PROJECTS_DIR=/kaggle/working/projects

# --- END SESSION 2 COMMANDS ---
```

---

## 7. Known Risks for Session 2 (Pre-Mitigated)

| Risk | Mitigation |
|------|------------|
| Hermes `setup-hermes.sh` fails on uv/Node/Playwright | Run in Docker if local env problematic; Kaggle has uv/Node preinstalled |
| OpenMontage `make setup` fails on Remotion npm install | `make install` (skip Remotion) → FFmpeg-only path works; Remotion optional |
| Skill validation warnings on frontmatter names | V7 validator already passed 225/0/0 — should be clean |
| Bridge preflight misses local repo paths | `bridge_preflight.py` defaults to `/home/kasun/Music/Director` — matches our structure |
| Tool registry shows `remotion: false`, `hyperframes: false` | **Expected** — FFmpeg-only is our locked render path for Kaggle |
| `documentary-montage` pipeline `reference_input.supported: false` | Correct — we supply local footage via `source_media_review` in `assets` stage |

---

## 8. What Session 2 Does NOT Do

- ❌ Build full orchestration loop (Session 3+)
- ❌ Implement all football skills (only `football-footage-acquisition` + corrections)
- ❌ Run end-to-end video production
- ❌ Discord integration (skeleton only)
- ❌ Hindsight memory provider setup (optional, later)
- ❌ Custom OpenMontage pipeline manifest (Phase 4 per impl plan)

---

## 9. Go/No-Go for Session 3

**Session 3 proceeds ONLY if ALL gates in Section 4 pass.**

If any gate fails → Session 2.5 (debug) required before Session 3.