# Implementation Contract — AI Creative Director Football Video System

**Status:** LOCKED — All future coding sessions must comply  
**Date:** 2026-07-11  
**Authority:** Derived from locked product decisions + upstream compatibility + skill reconciliation

---

## 1. Locked Decisions (Non-Negotiable)

| # | Decision | Reference |
|---|----------|-----------|
| 1 | Hermes-Agent is the permanent primary agent | Product decision |
| 2 | Hermes skills, session history, Hindsight memory are part of final system | Product decision |
| 3 | OpenMontage is the primary editing/rendering engine | Product decision |
| 4 | FFmpeg remains part of permanent rendering backbone | Product decision |
| 5 | Kaggle is the main runtime environment | Product decision |
| 6 | OpenCode is used for development | Product decision |
| 7 | YouTube is the main automatic footage source | Product decision |
| 8 | Programme must discover footage automatically when user provides no links | Product decision |
| 9 | User-provided YouTube links must also be supported | Product decision |
| 10 | Footage acquisition stays outside OpenMontage; hands local footage to OpenMontage | Product decision |
| 11 | No proxies, CAPTCHA solving, stolen cookies, IP rotation, bot-protection bypass | Product decision |
| 12 | Blocked footage candidates abandoned and replaced strategically | Product decision |
| 13 | Football Emotion V7 skill system used after validation/correction | Product decision |
| 14 | Future video categories use separate skill systems | Product decision |
| 15 | Licensing automation outside current target | Product decision |
| 16 | This is final-product architecture, not temporary MVP | Product decision |

---

## 2. Rules Future Coding Sessions Must Follow

### 2.1 Upstream Modification Restrictions
- **NEVER** modify `external/Hermes-Agent/` or `external/OpenMontage/` source code
- All integration via: Hermes skills (agentskills.io standard), OpenMontage pipeline manifests + stage director skills, tool registry discovery
- If upstream lacks a capability, build a **thin adapter skill** or **custom tool** in our repo — not a patch

### 2.2 Schema Validation Rules
- All artifacts must validate against schemas in `shared/contracts/pipeline-artifacts.md` (football) and `OpenMontage/schemas/artifacts/*.schema.json` (OpenMontage)
- **Before** writing any OpenMontage-native artifact (`edit_decisions`, `asset_manifest`, `scene_plan`, `script`, `render_report`):
  - `openmontage_schema_lock.bridge_status` MUST be `passed`
  - Mapping documented in `shared/references/repo-bridge/openmontage-schema-lock.md`
- Adapter-facing plans (`openmontage_edit_plan`, `openmontage_audio_operations`) allowed before schema lock
- `jsonschema` validation required at each checkpoint write

### 2.3 Source Acquisition Rules
- **Automatic discovery:** Hermes `browser` tool → YouTube search → extract video IDs/URLs
- **User-provided links:** Accepted as supplementary input to `football-source-discovery`
- **Download:** OpenMontage `video_downloader` tool (yt-dlp) via Hermes `terminal` tool
- **Sequential acquisition:** One clip at a time; verify before next
- **Failure handling:** On download/verify failure → mark rejected → fetch next ranked candidate (max 3 per slot)
- **No retry loops** on same URL; no parallel downloads
- **Manifest:** Every acquired file → `source_media_review` + `asset_manifest` entry with provenance

### 2.4 Memory Rules
- **Hermes MEMORY.md:** ≤ 2,200 chars total; only distilled lessons (1 sentence each)
- **Hermes USER.md:** ≤ 1,375 chars total; only user preferences
- **Full project records:** `projects/<id>/football_emotion/project_record.json` (unlimited size)
- **Memory update:** Only via `hermes-football-memory-learning` skill after QA/delivery
- **No unverified claims:** Current-event facts, legal assessments, performance metrics → stored as `provenance: estimated_by_editor` or `creative_hypothesis`, never `verified_from_source`
- **Hindsight (if enabled):** `local_embedded` mode only; bank_id `hermes-{profile}`

### 2.5 Testing Gates (Must pass
| Gate | When | Criteria |
|------|------|----------|
| **Setup Validation** | Session start | `bridge_preflight.py`: repos exist, pinned commits match, tool registry preflight runs |
| **Skill System Validation** | After skill install | `validate_skill_system.py`: 0 errors, 0 warnings |
| **Schema Lock** | Before first native OpenMontage artifact | `openmontage_schema_lock.bridge_status: passed` with all fields mapped |
| **Pipeline Preflight** | Before pipeline run | Manifest loads, stage director skills readable, tool registry shows required providers |
| **Stage Checkpoint** | Each OpenMontage stage | Artifact validates against schema; human gate if `human_approval_default: true` |
| **QA Gate** | Before compose | `football-retention-quality-control` + `football-audio-quality-control` + `football-platform-export-validator` all `pass: true` |
| **Render Validation** | After compose | `render_report` exists, video file playable, `export_profile.pass: true` |
| **Memory Update** | After delivery | `hermes-football-memory-learning` produces `hermes_memory_update`; MEMORY.md/USER.md size enforced |

---

## 3. Source Acquisition Rules (Detailed)

### 3.1 Discovery (football-source-discovery)
- **Trigger:** User request + `user_instruction_profile` (or inferred)
- **Queries:** 5 styles per topic (story, moment, editing-style, official, non-English)
- **Ranking:** 7-axis rubric (0-10); ≥8 deep-analysis, 6-7.9 manual inspect, 4-5.9 topic-only, <4 reject
- **Rejection Rules:** Generic highlights, goals-only, AI fakes, watermarks, shorts-only, unverified current events, copyrighted music, exploitative emotion
- **Output:** `source_video_candidate[]` with `verification_status: unverified`

### 3.2 Acquisition (football-footage-acquisition — NEW)
- **Input:** Ranked `source_video_candidate[]` with `deep_analysis_candidate: yes`
- **Process per clip:**
  1. `video_downloader` (yt-dlp) → local file `projects/<id>/sources/<candidate_id>.mp4`
  2. `audio_probe` → technical metadata
  3. `frame_sampler` (4 frames) → visual verification
  4. `transcriber` (if audio) → transcript summary
  5. Build `source_media_review` entry
  6. On any failure → reject candidate → try next ranked
- **Output:** Complete `source_media_review` artifact + updated `asset_manifest`

### 3.3 Analysis (football-visual-scene-analysis)
- **Input:** `source_media_review` entries with `deep_analysis_candidate: yes`
- **Tools:** `frame_sampler` (scene_guided), `scene_detect` (content), `transcriber`
- **Output:** `video_scene_analysis` with `confidence` + `manual_review_needed` per scene

### 3.4 No Unsafe Assumptions
- Browser tool may fail (YouTube layout changes, consent walls) → skill handles gracefully
- yt-dlp may fail (geo-block, age-gate, removed) → replacement logic mandatory
- No API keys for YouTube Data API (not in locked secrets)
- No cookie authentication (locked decision)

---

## 4. Testing Gates (Expanded)

### 4.1 Unit/Contract Tests (Run in Session 2+)
```bash
# Skill system
python3 tools/validate_skill_system.py skills/football-emotion-video/

# OpenMontage schemas
python3 -m pytest tests/contracts/ -v

# Tool registry preflight
cd external/OpenMontage && python3 -c "from tools.tool_registry import registry; registry.discover(); print(registry.provider_menu_summary())"
```

### 4.2 Integration Tests (Session 3+)
- **Footage acquisition smoke test:** Download 1 public domain football clip → verify `source_media_review`
- **Pipeline dry-run:** `documentary-montage` with synthetic artifacts → all 5 checkpoints pass
- **End-to-end (short):** 30s football comeback edit → render → validate → Discord notify

### 4.3 Kaggle Compatibility Tests
- `HERMES_HOME=/kaggle/working/.hermes` persistence across kernel restarts
- `OPENMONTAGE_PROJECTS_DIR=/kaggle/working/projects` checkpoint survival
- FFmpeg-only render path works without Node/Remotion/HyperFrames
- No network calls in inference mode (all cloud providers unavailable)

---

## 5. Definition of a Completed Final System

The system is **complete** when ALL of the following are true:

### 5.1 Infrastructure
- [ ] `bootstrap/install_hermes.sh` → Hermes runs with football-emotion skills loaded
- [ ] `bootstrap/install_openmontage.sh` → OpenMontage `make setup` passes, tool registry discovers providers
- [ ] `bootstrap/install_skills.sh` → ZIP extracted to `~/.hermes/skills/football-emotion-video/`, validation passes
- [ ] `bootstrap/validate_setup.py` → bridge_preflight + skill validation = 0 errors
- [ ] Kaggle persistence symlinks work; kernel restart preserves Hermes memory + OpenMontage projects

### 5.2 Orchestration
- [ ] `scripts/acd_worker.py` accepts user request (Discord/CLI) → creates Hermes session → runs full workflow
- [ ] `social-edit-reasoning` enforces editorial journey stage order
- [ ] Project workspace created at `OPENMONTAGE_PROJECTS_DIR/<project-id>/`
- [ ] Checkpoints written per OpenMontage stage; resume from last completed stage works
- [ ] Discord notifications: start, stage transitions, failure (with context), completion (with output path)

### 5.3 Footage Acquisition
- [ ] Automatic YouTube discovery via Hermes `browser` tool finds ≥5 candidates for test topic
- [ ] `football-source-discovery` ranks candidates per rubric; rejects per rules
- [ ] `football-footage-acquisition` downloads sequentially, builds `source_media_review`
- [ ] Failed download → next candidate tried (max 3) → slot filled or gap reported
- [ ] User-provided YouTube links accepted and integrated into candidate pool

### 5.4 Analysis & Editorial
- [ ] `football-visual-scene-analysis` uses `frame_sampler` + `scene_detect` → `video_scene_analysis`
- [ ] `football-timestamp-extraction` + `football-clip-scoring` produce ranked `clip_candidate[]` with scores
- [ ] `football-story-strategy` + `football-narration-scriptwriting` produce script tied to clips
- [ ] `football-pro-cutting-pacing` + `football-audio-music-director` + `football-commentary-ducking-mixer` produce edit/audio plans
- [ ] `football-caption-thumbnail-direction` produces caption/thumbnail plans
- [ ] `football-fact-provenance-gate` + `football-footage-rights-transformative-risk-assessor` + `football-rights-safe-audio-license-checker` all pass

### 5.5 OpenMontage Pipeline Execution
- [ ] `documentary-montage` pipeline selected; manifest + stage director skills read
- [ ] `idea-director` → `brief` (thematic question, tone, duration, music, end-tag)
- [ ] `scene-director` → `scene_plan` (slots mapped to our clips)
- [ ] `asset-director` → `asset_manifest` (ingests our local files + provenance)
- [ ] `openmontage-edit-planning` → `openmontage_edit_plan` → **after schema lock** → `edit_decisions`
- [ ] `openmontage-audio-operation-mapper` → `edit_decisions.audio`
- [ ] `compose-director` → `render_report` (FFmpeg render, `render_runtime: ffmpeg`)

### 5.6 Quality & Delivery
- [ ] `football-retention-quality-control` → `full_qa_report.pass: true`
- [ ] `football-audio-quality-control` → `qc_report.pass: true` (loudness -14 LUFS, true peak -1dB)
- [ ] `football-platform-export-validator` → `export_profile.pass: true`
- [ ] Video file exists at `projects/<id>/output/final.mp4`, playable, correct specs
- [ ] Discord webhook delivers completion message with output location

### 5.7 Memory & Learning
- [ ] `hermes-football-memory-learning` → `hermes_memory_update` written to Hermes memory
- [ ] MEMORY.md ≤ 2,200 chars, USER.md ≤ 1,375 chars enforced
- [ ] Full project record at `projects/<id>/football_emotion/project_record.json`
- [ ] Hindsight (if enabled) retains semantic recall

### 5.8 Extensibility Proven
- [ ] New skill category (e.g., `tech-review-video/`) can be added under `~/.hermes/skills/` without modifying football skills
- [ ] Shared infrastructure (`social-edit-reasoning`, repo bridge, editorial journey refs) reused
- [ ] New pipeline manifest can be added to OpenMontage without core changes

---

## 6. Prohibited Patterns (Will Fail Review)

| Pattern | Why |
|---------|-----|
| `import hermes_agent.*` or `import openmontage.*` in our code | Upstream modification prohibition |
| Writing artifacts outside `projects/<id>/` | Breaks Backlot/checkpoints |
| Silent `render_runtime` default (no user confirmation) | Governance violation |
| Storing legal claims as verified facts in memory | Liability + memory corruption |
| Parallel video downloads | Resource contention, no strategic replacement |
| Using `web` toolset for YouTube search | Doesn't work; requires `browser` tool |
| Assuming `video_analyzer` is granular sub-tool | It's monolithic; use `frame_sampler`/`scene_detect` directly |
| Skipping `openmontage_schema_lock` before native artifacts | Schema drift guaranteed |
| Hardcoding `/home/kasun/Music/Director/` paths | Not portable; use `HERMES_HOME`, `OPENMONTAGE_PROJECTS_DIR` |
| Writing to `MEMORY.md` directly (bypassing skill) | Breaks drift detection, size limits, threat scanning |

---

## 7. Version Locks (from upstream-lock.json)

```json
{
  "hermes_agent": {
    "repository": "https://github.com/NousResearch/Hermes-Agent",
    "commit": "5ecc07986f46463ca3096679b03a46402eb19cee",
    "branch": "main",
    "inspection_date": "2026-07-11"
  },
  "openmontage": {
    "repository": "https://github.com/calesthio/OpenMontage",
    "commit": "f633b5f428b9be9a2afecba851dfddd101619756",
    "branch": "main",
    "inspection_date": "2026-07-11"
  }
}
```

All implementation must target these exact commits. Do not upgrade without explicit architecture review session.