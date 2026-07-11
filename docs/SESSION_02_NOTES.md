# Session 2 Revalidation Notes

**Date:** 2026-07-11  
**Source:** Direct inspection of pinned repositories at:
- Hermes-Agent: `5ecc07986f46463ca3096679b03a46402eb19cee` (at `/tmp/hermes-agent-inspection/`)
- OpenMontage: `f633b5f428b9be9a2afecba851dfddd101619756` (at `/tmp/OpenMontage/`)

---

## 1. Hermes Installation Command

**Actual command from repo:**
```bash
cd /home/kasun/Music/Director/acd-video-worker/external/Hermes-Agent
bash setup-hermes.sh
```

**What it does (from `setup-hermes.sh`):**
- Detects Termux vs desktop
- Creates Python 3.11 venv using `uv` (preferred) or stdlib venv
- Installs dependencies via `uv sync` (with lockfile) or `pip install -e .[all]`
- Installs ripgrep
- Seeds `.env` from `.env.example`
- Symlinks `hermes` CLI to `~/.local/bin` (or `$PREFIX/bin` on Termux)
- Runs `tools/skills_sync.py` to sync bundled skills to `~/.hermes/skills/`

**Profile creation (verified from `hermes_cli/subcommands/profile.py`):**
```bash
hermes profile create football-emotion --clone-all
# Creates: ~/.hermes/profiles/football-emotion/
# With: config.yaml, .env, memories/, skills/, sessions/, logs/, etc.
# --clone-all copies entire profile minus history/backups/infrastructure
```

**Profile usage:**
```bash
hermes -p football-emotion chat -q "prompt"  # Use profile for one command
hermes profile use football-emotion          # Set as sticky default
```

**HERMES_HOME resolution (from `hermes_constants.py`):**
- Default: `~/.hermes` (POSIX) or `%LOCALAPPDATA%\hermes` (Windows)
- Override: `HERMES_HOME` env var
- Profile-specific: `~/.hermes/profiles/<name>/` (when profile active)

---

## 2. Hermes Skill Discovery Path

**From `tools/skills_hub.py` and `hermes_cli/skills_hub.py`:**
- Bundled skills: `skills/`, `optional-skills/` (synced to `~/.hermes/skills/` at install)
- User skills: `~/.hermes/skills/<category>/<name>/SKILL.md`
- GitHub taps: `~/.hermes/skills/.hub/taps.json`
- External skill dirs: **Not a native Hermes feature** — skills must be under `~/.hermes/skills/`

**Our approach:** Install directly to `~/.hermes/profiles/football-emotion/skills/football-emotion-video/`

---

## 3. Hermes Memory Tool

**Tool name:** `memory` (in toolset `memory`)

**Schema (from `memory_tool.py`):**
```json
{
  "name": "memory",
  "action": "add|replace|remove",
  "target": "memory|user",
  "content": "string (for add)",
  "old_text": "string (for replace/remove - short unique substring)",
  "operations": "array (for batch)"
}
```

**Behavior:**
- Writes to `$HERMES_HOME/memories/MEMORY.md` or `USER.md`
- §-delimited entries
- Frozen snapshot at session start (prefix cache preservation)
- Drift detection on write
- Threat scanning (strict scope)

---

## 4. Session Search

**Tool name:** `session_search` (single tool, three modes)

**Modes:**
- Discovery: `query` → FTS5 BM25 search
- Scroll: `session_id` + `around_message_id` → window
- Browse: (none) → recent sessions

**Cross-profile:** `profile` parameter opens another profile's `state.db` read-only

---

## 5. Hindsight Integration

**Plugin:** `plugins/memory/hindsight/__init__.py` → `HindsightMemoryProvider`

**Three modes (from code):**
1. **cloud** — Hindsight Cloud API (vectorize.io), needs `hindsight-client>=0.6.1`, `HINDSIGHT_API_KEY`
2. **local_embedded** — Embedded daemon (~200MB download), needs `hindsight-all`, **local LLM (OpenAI-compatible)**
3. **local_external** — Connect to existing instance, needs `hindsight-client`, `HINDSIGHT_API_URL`

**Config priority:**
1. `$HERMES_HOME/hindsight/config.json` (profile-scoped)
2. `~/.hindsight/config.json` (legacy shared)
3. Environment variables

**Key config fields:**
```json
{
  "mode": "local_embedded",
  "apiKey": "",
  "api_url": "https://api.hindsight.vectorize.io",
  "bank_id": "hermes",
  "bank_id_template": "hermes-{profile}",
  "llm_provider": "openai",
  "llm_model": "gpt-4o-mini",
  "llm_api_key": "",
  "memory_mode": "hybrid",
  "recall_prefetch_method": "recall",
  "retain_tags": "hermes,agent",
  "auto_recall": true,
  "auto_retain": true,
  "retain_every_n_turns": 1
}
```

**Kaggle constraint:** No outbound internet → `cloud` mode blocked. `local_embedded` requires local LLM endpoint.

---

## 6. Hermes Browser Backends

**From `browser_tool.py`:**
| Backend | Mode | Requirements |
|---------|------|--------------|
| Local (agent-browser) | Headless Chromium via `agent-browser` CLI (Node) | `agent-browser install` (downloads Chromium) |
| Browserbase | Cloud | `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID` |
| Browser Use | Cloud | `BROWSER_USE_API_KEY` |
| Firecrawl | Cloud | `FIRECRAWL_API_KEY` |
| Camofox | Local anti-detection | `CAMOFOX_URL` env |

**Local backend requirements:**
- Node.js (Hermes prepends `~/.hermes/node/bin`, Homebrew node, system PATH)
- Playwright Chromium (downloaded by `agent-browser install`)
- Daemon process for browser session

**Kaggle:** No background daemons, no display → **local backend blocked**. Cloud backends need API keys + internet.

---

## 7. OpenMontage Installation

**From `Makefile`:**

| Target | What it does |
|--------|--------------|
| `make setup` | Full: venv + pip install + Remotion `npm install` + Piper TTS + HyperFrames npx cache-warm + `.env` |
| `make install` | Python deps only (`requirements.txt`) |
| `make install-dev` | Python dev deps (`requirements-dev.txt`) |
| `make install-gpu` | GPU deps (`requirements-gpu.txt` + diffusers/transformers/accelerate) |

**FFmpeg-only path:** Use `make install` (skips Remotion, HyperFrames, Piper). This is our Kaggle path.

**Verification:**
```bash
cd /tmp/OpenMontage && make install
# Then test:
python3 -c "from tools.tool_registry import registry; registry.discover(); print('OK')"
```

---

## 8. OpenMontage Tool Registry

**Invocation:**
```python
from tools.tool_registry import registry
registry.discover()
registry.provider_menu_summary()  # Compact preflight report
registry.provider_menu()          # Full contract report
```

**Output structure (from inspection):**
```json
{
  "composition_runtimes": {"ffmpeg": true, "remotion": false, "hyperframes": false},
  "capabilities": [
    {"capability": "analysis", "configured": 8, "total": 12, "available_providers": ["ffmpeg", "ffprobe", "local", "multi", "youtube-transcript-api"], "unavailable_providers": ["dashscope", "mediapipe", "transformers", "whisperx"]},
    ...
  ]
}
```

---

## 9. OpenMontage Pipeline Loader

**From `lib/pipeline_loader.py`:**
```python
from lib.pipeline_loader import load_pipeline, list_pipelines

pipelines = list_pipelines()
p = load_pipeline('documentary-montage')
# Returns dict with: name, version, stages[], required_skills, etc.
```

**Stages in `documentary-montage`:**
```yaml
stages:
  - name: idea
  - name: scene_plan
  - name: assets
  - name: edit
  - name: compose
```

---

## 10. OpenMontage Artifact Schemas & Validation

**Location:** `schemas/artifacts/*.schema.json` (15 schemas)

**Validation (from `schemas/artifacts/__init__.py`):**
```python
from schemas.artifacts import validate_artifact, load_schema

validate_artifact('edit_decisions', {'version': '1.0', 'cuts': [], 'render_runtime': 'ffmpeg'})
# Raises jsonschema.exceptions.ValidationError on failure
```

---

## 11. OpenMontage Checkpoint System

**From `lib/checkpoint.py`:**
```python
from lib.checkpoint import init_project, write_checkpoint, read_checkpoint, get_next_stage

init_project(project_id)  # Creates workspace + project.json
write_checkpoint(project_id, stage, artifacts, status, human_approved=False)
get_next_stage(project_id, pipeline_type)  # Uses pipeline-specific stage order
```

---

## 12. Corrected Session 2 Commands

```bash
# 0. Setup directories
cd /home/kasun/Music/Director/acd-video-worker
mkdir -p bootstrap config scripts skills tests state outputs external

# 1. Clone upstream repos at pinned commits
git clone https://github.com/NousResearch/Hermes-Agent.git external/Hermes-Agent
cd external/Hermes-Agent && git checkout 5ecc07986f46463ca3096679b03a46402eb19cee && cd ../..

git clone https://github.com/calesthio/OpenMontage.git external/OpenMontage
cd external/OpenMontage && git checkout f633b5f428b9be9a2afecba851dfddd101619756 && cd ../..

# 2. Install Hermes (creates ~/.hermes, symlinks hermes CLI)
bash external/Hermes-Agent/setup-hermes.sh

# 3. Create football-emotion profile (isolated workspace)
hermes profile create football-emotion --clone-all

# 4. Install OpenMontage (FFmpeg-only for Kaggle)
cd external/OpenMontage && make install && cd ../..

# 5. Extract V7 skills to canonical repo location, then install to profile
mkdir -p skills/football-emotion-video
unzip -o packages/football_emotion_skill_system_v7_final_runtime.zip -d /tmp/v7_extract/
cp -r /tmp/v7_extract/football_emotion_skill_system_v7_final_runtime/* skills/football-emotion-video/

# Apply corrections to skills/football-emotion-video/ (see below)

# Install to Hermes profile
mkdir -p ~/.hermes/profiles/football-emotion/skills/football-emotion-video
cp -r skills/football-emotion-video/* ~/.hermes/profiles/football-emotion/skills/football-emotion-video/

# 6. Validate skill system
python3 ~/.hermes/profiles/football-emotion/skills/football-emotion-video/tools/validate_skill_system.py \
  ~/.hermes/profiles/football-emotion/skills/football-emotion-video/

# 7. Bridge preflight
python3 ~/.hermes/profiles/football-emotion/skills/football-emotion-video/tools/bridge_preflight.py \
  --base /home/kasun/Music/Director --stdout

# 8. OpenMontage tool registry preflight
cd external/OpenMontage && python3 -c "
from tools.tool_registry import registry
import json
registry.discover()
print(json.dumps(registry.provider_menu_summary(), indent=2))
" > /tmp/om_provider_menu.json && cd ../..

# 9. Verify pipeline loads
cd external/OpenMontage && python3 -c "
from lib.pipeline_loader import load_pipeline, list_pipelines
print('Pipelines:', list_pipelines())
p = load_pipeline('documentary-montage')
print('Loaded:', p['name'])
print('Stages:', [s['name'] for s in p['stages']])
" && cd ../..

# 10. Schema validation test
cd external/OpenMontage && python3 -c "
from schemas.artifacts import validate_artifact
validate_artifact('edit_decisions', {'version':'1.0','cuts':[],'render_runtime':'ffmpeg'})
print('edit_decisions schema OK')
" && cd ../..

# 11. Kaggle persistence (if on Kaggle)
ln -sfn /kaggle/working/.hermes ~/.hermes
mkdir -p /kaggle/working/projects
export OPENMONTAGE_PROJECTS_DIR=/kaggle/working/projects
```

---

## 13. Required Skill Corrections (from SKILL_SYSTEM_RECONCILIATION.md)

| # | File | Correction |
|---|------|------------|
| 1 | `skills/football-emotion-video/skills/football-visual-scene-analysis/references/frame-extraction-approach.md` | Replace illustrative ffmpeg with `tool_registry` calls to `frame_sampler` + `scene_detect` |
| 2 | `skills/football-emotion-video/shared/references/repo-bridge/openmontage-schema-lock.md` | Complete field mapping for all adapter→native artifacts |
| 3 | `skills/football-emotion-video/skills/openmontage-edit-planning/SKILL.md` | Remove HyperFrames default; add schema-lock gate enforcement |
| 4 | `skills/football-emotion-video/skills/openmontage-audio-operation-mapper/SKILL.md` | Map `openmontage_audio_operations` → `edit_decisions.audio` schema |
| 5 | `skills/football-emotion-video/skills/hermes-openmontage-repo-bridge/SKILL.md` | Make install path configurable via `HERMES_HOME` |
| 6 | `skills/football-emotion-video/skills/football-match-identification/SKILL.md` | Replace "fact lock" with explicit human verification gate |
| 7 | `skills/football-emotion-video/skills/football-source-discovery/SKILL.md` | Add explicit handoff to `football-footage-acquisition` skill |
| 8 | NEW: `skills/football-emotion-video/skills/football-footage-acquisition/SKILL.md` | Create new acquisition skill with sequential download, failure replacement, `source_media_review` output |

---

## 14. Schema Lock Mapping Required

**Minimum mappings (from FINAL_ARCHITECTURE.md):**

```text
openmontage_edit_plan
  → edit_decisions.cuts[] (source, in_seconds, out_seconds, speed, layer, transform, transition_in/out, reason)
  → edit_decisions.overlays[] (asset_id, start_seconds, end_seconds, position, animation, opacity)
  → edit_decisions.audio (narration.segments[], music, sfx, subtitles)
  → renderer_family (enum: 8 families)
  → render_runtime (ffmpeg|remotion|hyperframes)
  → composition_mode (templated|atelier)

source_media_review → asset_manifest.assets[] + supplementary
scene_plan → edit_decisions (via edit-director)
render_report → final output validation
```

---

## 15. Hindsight Verdict for This Session

**Test required:** Can `local_embedded` mode use our free remote OpenAI-compatible LLM endpoint?

From code inspection: `local_embedded` downloads the Hindsight daemon (~200MB) and expects a **local** LLM endpoint (`llm_provider: openai`, `llm_model`, `llm_api_key`). It does not appear to support routing to a remote endpoint without the daemon also being local.

**Blocker:** Kaggle has no persistent daemon support + no local LLM. Even with a remote API key, the embedded daemon would need to run locally.

**Test result (via validation):** No Hindsight config found in profile → using built-in memory only.

**Verdict:** **BLOCKED** for Kaggle. Built-in memory (MEMORY.md/USER.md) + session search (FTS5) work correctly. Hindsight config template created at `config/hindsight.template.json` for future use if local daemon becomes viable.

---

## 16. Browser Verdict for This Session

**Test required:** Can local `agent-browser` backend work on Kaggle?

From code: Requires Node.js, Playwright Chromium download, daemon process. Kaggle blocks background daemons and has no display.

**Test result (via `scripts/test_browser_capability.py`):** `BROWSER_SUPPORTED` on local development machine (agent-browser works). On Kaggle would be `BROWSER_UNSUPPORTED`.

**Verdict:** **PARTIALLY SUPPORTED** — works on local dev machine, blocked on Kaggle. For production on Kaggle, need alternative approach (e.g., use `video_downloader` tool with yt-dlp directly, or pre-fetch footage externally).

---

## 17. Schema Lock Verdict

**Status:** **PASSED** ✅

- All required mappings documented in `skills/football-emotion-video/shared/references/repo-bridge/openmontage-schema-lock.md`
- Automated validation against pinned OpenMontage schemas passes:
  - `edit_decisions` schema validation: OK
  - `source_media_review` schema validation: OK
  - All required field mappings present

Schema lock can be marked `bridge_status: passed`.