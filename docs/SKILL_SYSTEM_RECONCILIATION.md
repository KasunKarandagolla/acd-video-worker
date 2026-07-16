> **Historical analysis. Current ownership and production behavior are defined only by `FINAL_ARCHITECTURE.md`, `IMPLEMENTATION_CONTRACT.md`, and `THIN_ORCHESTRATION_MODULE_MAP.md`. The Football Emotion skills remain complete; old recommendations for a Python stage wrapper are superseded.**

# Football Emotion V7 Skill System Reconciliation

**Inspection Date:** 2026-07-11  
**Source:** `/tmp/audit/football_emotion_skill_system_v7_final_runtime/`  
**Validation Status:** PASSED (225 checks, 0 warnings, 0 errors)

---

## 1. V7 Validation Result

The Football Emotion V7 skill system **passes all internal validators**:
- All 23 skills have valid `SKILL.md` with required frontmatter (`name`, `description`)
- Frontmatter names match folder names
- All 78 required shared references/contracts exist
- All 8 required tools exist and are non-trivial
- `evals/evals.json` valid with proper structure
- No missing cross-references between skills and shared files

**Validator:** `tools/validate_skill_system.py` — checks structure, frontmatter, references, contracts, evals, tools

---

## 2. Active Skills (23) — Inventory

| # | Skill | Purpose | Activation Trigger |
|---|-------|---------|-------------------|
| 1 | `football-audio-music-director` | Direct music/audio per story section | After clip selection, before edit planning |
| 2 | `football-audio-quality-control` | QA audio mix, loudness, ducking | Final QC gate |
| 3 | `football-caption-thumbnail-direction` | Caption plan + thumbnail candidates | During edit planning |
| 4 | `football-clip-scoring` | Rank clips against story plan | After timestamp extraction |
| 5 | `football-commentary-ducking-mixer` | Duck music under commentary | Audio plan refinement |
| 6 | `football-fact-provenance-gate` | Verify factual claims before artifact write | Before any fact enters canonical artifact |
| 7 | `football-footage-rights-transformative-risk-assessor` | Assess transformative use risk for match footage | Before using third-party footage |
| 8 | `football-match-identification` | Identify exact match from vague user query | When user mentions current/latest match |
| 9 | `football-music-library-selector` | Select music/SFX from free catalogs | After story plan, before audio plan |
| 10 | `football-narration-scriptwriting` | Write narration script around selected clips | After clip scoring, before edit planning |
| 11 | `football-platform-export-validator` | Validate export profile per platform | Final delivery gate |
| 12 | `football-pro-cutting-pacing` | Cut rhythm, pacing, transition decisions | During edit planning |
| 13 | `football-retention-quality-control` | Full QA (technical, editorial, platform, reused-content, vibe) | Pre-delivery |
| 14 | `football-rights-safe-audio-license-checker` | Verify music/SFX licenses, commentary rights | Gates all audio asset use |
| 15 | `football-source-discovery` | Find & rank candidate source videos | First skill — converts brief to candidates |
| 16 | `football-story-strategy` | Parse brief → emotional question, story structure, runtime | After source discovery (or user-provided brief) |
| 17 | `football-timestamp-extraction` | Convert scene analysis → timestamped clip candidates | After visual scene analysis |
| 18 | `football-visual-scene-analysis` | Review extracted frames/audio → scene-level intelligence | After source discovery flags deep-analysis candidates |
| 19 | `hermes-football-memory-learning` | Distill project lessons into Hermes MEMORY.md/USER.md | Post-run |
| 20 | `hermes-openmontage-repo-bridge` | Bridge skills to actual Hermes + OpenMontage repos | Before any repo-backed execution |
| 21 | `openmontage-audio-operation-mapper` | Convert audio_plan → OpenMontage track-shaped operations | After audio plan, before compose |
| 22 | `openmontage-edit-planning` | Assemble story+clips+audio → OpenMontage edit_decisions | After all creative decisions |
| 23 | `social-edit-reasoning` | Stage router + editorial journey state machine | Every stage transition |

---

## 3. Reusable Files (No Changes Needed)

### 3.1 Skills — Core Logic Sound
| Skill | Reason |
|-------|--------|
| `football-source-discovery` | Pure search/reasoning logic; no tool assumptions beyond "search YouTube" (Hermes has `web` toolset) |
| `football-story-strategy` | Pure editorial reasoning; outputs `user_instruction_profile`, `story_plan`, `brief_interpretation` — schema-valid |
| `football-clip-scoring` | Pure rubric application; outputs `clip_candidate` with scores — schema-valid |
| `football-timestamp-extraction` | Pure scene→timestamp conversion; requires verified scene analysis input |
| `football-narration-scriptwriting` | Pure writing skill; outputs script sections tied to clip IDs |
| `football-pro-cutting-pacing` | Pure editorial methodology; references `pro-editing-methodology.md` |
| `football-caption-thumbnail-direction` | Pure caption/thumbnail planning; outputs `caption_plan`, `thumbnail_candidate` |
| `football-music-library-selector` | Pure catalog lookup; references `music-sfx-catalog.md`, `full-candidate-music-sfx-catalog.md` |
| `football-rights-safe-audio-license-checker` | Pure checklist process; outputs `license_verification_record`, `commentary_rights_check` |
| `football-footage-rights-transformative-risk-assessor` | Pure risk assessment; outputs `footage_rights_risk_record` |
| `football-fact-provenance-gate` | Pure verification discipline; outputs `fact_provenance_report` |
| `football-audio-music-director` | Pure audio planning; outputs `audio_plan_segment` |
| `football-commentary-ducking-mixer` | Pure ducking logic; refines `audio_plan` |
| `football-audio-quality-control` | Pure QA checklist; outputs `qc_report` |
| `football-retention-quality-control` | Pure QA checklist; outputs `full_qa_report` with loopbacks |
| `football-platform-export-validator` | Pure export validation; outputs `export_profile` |
| `social-edit-reasoning` | Stage router + `editorial_journey_state` machine — **critical orchestrator** |
| `hermes-football-memory-learning` | Pure memory distillation; outputs `hermes_memory_update` (fits 2.2K/1.375K char budgets) |

### 3.2 Shared Contracts (Canonical, No Changes)
| File | Status |
|------|--------|
| `shared/contracts/pipeline-artifacts.md` | **Canonical** — all artifact schemas defined here; V7 adds V3/V5 extensions additively |
| `shared/contracts/openmontage-artifact-bridge.md` | **Canonical** — maps football artifacts → OpenMontage artifacts with `adapter_facing_plan` vs `openmontage_native_operations` modes |

### 3.3 Shared References (Editorial Methodology — Reusable)
| File | Reusability |
|------|-------------|
| `shared/references/emotion-pattern-library.md` | Core clip-type priorities per story type — reusable across categories |
| `shared/references/pro-editing-methodology.md` | Cut/pacing/transition/effect/caption rules — reusable |
| `shared/references/verification-standard.md` | Confidence/verification field discipline — reusable |
| `shared/references/pipeline-routing-guide.md` | Pipeline selection logic — reusable |
| `shared/references/llm-decision-boundaries.md` | What LLM decides vs. what tools decide — reusable |
| `shared/references/editorial-journey/*.md` (13 files) | Professional editorial workflow — **reusable for future skill systems** |

---

## 4. Files Requiring Correction

### 4.1 Skills with Outdated/Incorrect Hermes Assumptions

| Skill | Issue | Correction Needed |
|-------|-------|-------------------|
| `football-source-discovery` | **V4 rule**: "Use OpenMontage's `tools/analysis/` frame-sampling tool if available" — but OpenMontage's `video_analyzer` does download+transcribe+scene+frames as a monolith; no standalone frame-sampler tool exposed in registry. | Update reference to use `video_analyzer` tool directly or call `frame_sampler` as sub-tool if registered. Verify via `tool_registry` preflight. |
| `football-visual-scene-analysis` | **Refers to**: `references/frame-extraction-approach.md` which describes illustrative ffmpeg fallback. OpenMontage has real `frame_sampler` and `scene_detect` tools. | Replace illustrative approach with actual `tool_registry` tool calls after preflight confirms availability. |
| `football-match-identification` | Assumes Hermes has "current event fact lock" via `match_fact_lock` gate but doesn't specify *how* Hermes verifies (no live sports API in Hermes). | Clarify: this skill produces `match_fact_lock` artifact for *human* verification; Hermes memory doesn't auto-verify live scores. |
| `hermes-openmontage-repo-bridge` | **Install path**: `/home/kasun/Music/Director/Hermes-Agent/optional-skills/creative/football-emotion-video/` — hardcoded to original author's machine. | Make install path configurable via `HERMES_HOME` or Hermes' external skill directory mechanism. |
| `openmontage-edit-planning` | **Render runtime**: "This project's prior architecture uses HyperFrames" — but OpenMontage preflight shows `hyperframes: false`, `remotion: false`, only `ffmpeg: true` by default. | Remove HyperFrames assumption; implement runtime selection per `openmontage-zero-key-capability-envelope.md` (FFmpeg-first, user-confirmed). |

### 4.2 Skills with Outdated OpenMontage Assumptions

| Skill | Issue | Correction Needed |
|-------|-------|-------------------|
| `openmontage-edit-planning` | **V4 rule**: "Read `pipeline_defs/documentary-montage.yaml` locally" — but the skill doesn't enforce *reading the stage director skills* (`skills/pipelines/documentary-montage/*-director.md`) before producing `edit_decisions`. | Add explicit step: load pipeline manifest → read stage director skill for `edit` stage → produce artifact matching that stage's expectations. |
| `openmontage-edit-planning` | **Schema mapping**: `openmontage_edit_plan` in `pipeline-artifacts.md` has fields (`sections[].clips[]`, `cut_style`, `transition_in/out`, `effect`, `audio_priority`, `music_action`, `sfx`) that don't directly match OpenMontage's `edit_decisions.schema.json` (`cuts[]` with `source`, `in_seconds`, `out_seconds`, `speed`, `layer`, `transform`, `transition_in/out`, `reason`; `overlays[]`; `audio.narration/music/sfx`; `subtitles`; `renderer_family`, `render_runtime`, `composition_mode`, `bespoke`). | **Must complete `openmontage_schema_lock` bridge** before writing native `edit_decisions`. Map each field explicitly. |
| `openmontage-audio-operation-mapper` | Outputs `openmontage_audio_operations` with `tracks[]`, `silence_cuts[]`, `master` — but OpenMontage's `edit_decisions.audio` has different structure (`narration.segments[]`, `music`, `sfx`, `subtitles`). | Map to `edit_decisions.audio` schema; `silence_cuts` → not directly represented (handled by `silence_cutter` tool pre-compose). |
| `football-source-discovery` | **V4 rule**: "Treat `documentary-montage` as default candidate pipeline... but confirm by reading `pipeline_defs/documentary-montage.yaml` locally." — Skill doesn't enforce this confirmation step. | Add mandatory preflight: read local pipeline manifest before assuming pipeline structure. |

### 4.3 Missing Verification (Assumptions Not Validated)

| Area | Assumption | Verification Required |
|------|------------|----------------------|
| `football-visual-scene-analysis` → `frame_sampler` | "Use OpenMontage's frame-sampling tool if available" | Run `tool_registry` preflight; confirm `frame_sampler` is registered and `AVAILABLE` |
| `football-visual-scene-analysis` → `scene_detect` | "Use OpenMontage's scene detection" | Confirm `scene_detect` tool availability and `content`/`threshold`/`adaptive` methods |
| `football-source-discovery` → YouTube search | "Hermes `web` toolset can search YouTube" | Hermes `web` toolset uses search API (Tavily/DuckDuckGo/etc.) — **not YouTube Data API**. Cannot directly search YouTube. Need custom tool or `browser` tool. |
| `football-source-discovery` → `video_analyzer` | "OpenMontage `video_analyzer` can analyze YouTube URLs" | `video_analyzer` uses `yt-dlp` + `youtube-transcript-api` — works for public videos but **no auth/cookies** (blocked: no CAPTCHA bypass, no stolen cookies per locked decisions). |
| `hermes-football-memory-learning` → Hermes memory write | "Hermes has a memory-write tool accessible to skills" | Hermes `memory` tool (`tools/memory_tool.py`) writes to `MEMORY.md`/`USER.md` — skills can call it via tool invocation. **Verify tool name and schema**. |
| `social-edit-reasoning` → stage routing | "Hermes will trigger skills in order per `editorial_journey_state`" | Hermes skill activation is **description-based matching**, not explicit pipeline orchestration. Need wrapper agent logic to enforce stage order. |

---

## 5. Outdated Hermes Assumptions (Classified)

| # | Assumption | Classification | Evidence |
|---|------------|----------------|----------|
| 1 | Hermes has "ToolInterceptor" hook for skills to intercept tool calls | **INCORRECT** | Hermes repo has no such hook; term comes from separate FireRed-OpenStoryline project (confirmed in `hermes-agent-contract.md:25-26`) |
| 2 | Skills can register custom tools in Hermes | **OUTDATED** | Hermes tools are registered at import time in `tools/`; skills are `SKILL.md` only. Custom tools require Hermes core modification or plugin toolset. |
| 3 | Hermes skill activation follows explicit pipeline order | **INCORRECT** | Hermes activates skills by **description matching** against user request. No built-in pipeline orchestrator. |
| 4 | Hermes memory (`MEMORY.md`/`USER.md`) can store unlimited project records | **INCORRECT** | Hard limits: ~2,200 chars (MEMORY), ~1,375 chars (USER). Large records must go to project files with pointer in memory. |
| 5 | Hindsight Cloud works out-of-box on Kaggle | **BLOCKED** | Kaggle has no outbound internet; Hindsight Cloud requires API. Only `local_embedded` or `local_external` modes possible. |
| 6 | Browser tools work on Kaggle | **BLOCKED** | Playwright/Chromium needs display/daemon; Kaggle blocks background processes. Camofox binary unlikely present. |
| 7 | Hermes profiles map to Kaggle sessions 1:1 | **UNVERIFIED** | Profiles persist to `~/.hermes/profiles/` — ephemeral on Kaggle unless `HERMES_HOME=/kaggle/working/.hermes`. |

---

## 6. Outdated OpenMontage Assumptions (Classified)

| # | Assumption | Classification | Evidence |
|---|------------|----------------|----------|
| 1 | `documentary-montage` pipeline accepts YouTube footage via stock tools | **INCORRECT** | Its `asset-director` uses `direct_clip_search` / `corpus_builder` / `clip_search` for Pexels/Archive.org/NASA/Wikimedia/Unsplash — **no YouTube tool**. |
| 2 | `video_analyzer` tool can be called as a skill sub-step | **PARTIAL** | `video_analyzer` is a registered tool (`capability: analysis`, `provider: multi`), but it's a **monolithic orchestrator** (download → transcribe → scene → frames → motion → audio). Not granular. |
| 3 | `frame_sampler` and `scene_detect` are independently callable tools | **CONFIRMED AVAILABLE** | Both registered in `tool_registry` under `analysis` capability, provider `ffmpeg`/`local`. Status depends on FFmpeg/OpenCV availability. |
| 4 | Custom pipeline manifest (`football-emotion-story.yaml`) registers without core changes | **ASSUMPTION** | Manifest loader uses `jsonschema` validation; `extensions.custom_skills: true` in manifest allows custom skills. **Not directly verified** — Phase 4 in impl plan. |
| 5 | `edit_decisions` schema matches `openmontage_edit_plan` 1:1 | **INCORRECT** | Schema mismatch documented in §4.2. Requires `openmontage_schema_lock` bridge. |
| 6 | Remotion/HyperFrames available by default | **INCORRECT** | Preflight shows `remotion: false`, `hyperframes: false`, only `ffmpeg: true`. Requires `npm install` + Node ≥18/22. |
| 7 | `audio_mixer` tool exists for ducking | **CONFIRMED** | `tools/audio/audio_mixer.py` exists, registered, `capability: audio_processing`, provider `ffmpeg`. |
| 8 | Checkpoint protocol enforces human gates automatically | **CONFIRMED** | `lib/checkpoint.py::_stage_requires_approval()` reads `human_approval_default` from manifest; fail-closed on unknown pipeline. |

---

## 7. Football-Footage-Finder — Not Found as Separate Skill

**Finding:** No separate `football-footage-finder` skill ZIP exists in `/home/kasun/Music/Director/` or subdirectories.

**Replacement:** The V7 package includes **`football-source-discovery`** (skill #15) which performs:
- Discovery (multi-query YouTube search strategies)
- Candidate ranking (7-axis rubric, 0-10)
- Rejection rules (generic highlights, AI fakes, watermarks, shorts-only, unverified current events, copyrighted music, exploitative emotion)
- Verification discipline (`verification_status` per `verification-standard.md`)
- Handoff to `football-visual-scene-analysis` for deep analysis

**What `football-source-discovery` does NOT do (gaps):**
- **No automated download** — relies on Hermes `browser` tool or external `yt-dlp` invocation
- **No failure handling/retry** — rejection rules are static; no "abandon and replace strategically" loop
- **No memory recording of failed candidates** — `source_video_candidate` has `reason_for_rejection` but not persisted to Hermes memory
- **No CAPTCHA/proxy/IP rotation** — correctly avoided per locked decisions
- **No browser automation** — assumes Hermes `web` toolset can search YouTube (it cannot directly; needs `browser` tool or custom search tool)

**Components Worth Keeping from `football-source-discovery`:**
- Multi-query strategy (story/moment/editing-style/official/non-English)
- 7-axis discovery rubric with thresholds
- Rejection rules (especially "exploitative emotion" and "current-event unverified")
- Verification discipline (metadata ≠ visual review)
- `source_video_candidate` schema (compatible with `source_media_review` artifact)

**Components to Reject/Rewrite:**
- YouTube search assumption → replace with Hermes `browser` tool + `yt-dlp` via `video_downloader` tool (OpenMontage) or custom Hermes tool
- "Hand off to visual-scene-analysis" → make explicit: output `source_media_review` artifact for OpenMontage `assets` stage
- No download/resume logic → add `football-footage-acquisition` skill (new) that wraps `video_downloader` + checkpoint + replacement loop

---

## 8. Exact Future Correction Actions

| # | Action | Target File(s) | Priority |
|---|--------|----------------|----------|
| 1 | Replace `frame-extraction-approach.md` illustrative ffmpeg with actual `tool_registry` calls to `frame_sampler` + `scene_detect` after preflight | `skills/football-visual-scene-analysis/references/frame-extraction-approach.md`, `SKILL.md` | HIGH |
| 2 | Complete `openmontage_schema_lock` bridge: map every `openmontage_edit_plan` field to `edit_decisions.schema.json` | `shared/references/repo-bridge/openmontage-schema-lock.md`, `skills/openmontage-edit-planning/SKILL.md` | HIGH |
| 3 | Map `openmontage_audio_operations` → `edit_decisions.audio` schema | `skills/openmontage-audio-operation-mapper/SKILL.md` | HIGH |
| 4 | Remove HyperFrames default assumption; implement runtime selection per `openmontage-zero-key-capability-envelope.md` (FFmpeg-first, user-confirmed) | `skills/openmontage-edit-planning/SKILL.md`, `references/openmontage-handoff-notes.md` | HIGH |
| 5 | Make `hermes-openmontage-repo-bridge` install path configurable (`HERMES_HOME` or Hermes external skill dir) | `skills/hermes-openmontage-repo-bridge/SKILL.md`, `shared/references/repo-bridge/hermes-runtime-skill-install.md` | MEDIUM |
| 6 | Add mandatory pipeline manifest preflight step to `football-source-discovery` and `openmontage-edit-planning` | Respective `SKILL.md` files | MEDIUM |
| 7 | Create new `football-footage-acquisition` skill: wraps `video_downloader` (yt-dlp), handles sequential acquisition, failure replacement, checkpointing, `source_media_review` output | New skill folder under `skills/` | HIGH |
| 8 | Verify Hermes `memory` tool schema and invocation pattern for `hermes-football-memory-learning` | `tools/memory_tool.py` in Hermes repo | MEDIUM |
| 9 | Document that Hermes skill activation is description-based, not pipeline-ordered; add orchestrator agent logic in implementation | `IMPLEMENTATION_CONTRACT.md`, Session 2 plan | HIGH |
| 10 | Replace `football-match-identification` "fact lock" with explicit human-verification gate (no live API) | `skills/football-match-identification/SKILL.md` | MEDIUM |
| 11 | Add `repo_setup_status` and `openmontage_schema_lock` artifact generation to `hermes-openmontage-repo-bridge` workflow | `skills/hermes-openmontage-repo-bridge/SKILL.md`, `tools/bridge_preflight.py` | HIGH |
| 12 | Update all skills to reference `shared/references/repo-bridge/repo-source-lock.md` for pinned commits | All `SKILL.md` files referencing repos | MEDIUM |

---

## 9. Summary Classification

| Category | Count | Examples |
|----------|-------|----------|
| **Valid (reusable as-is)** | 17 skills + 15 shared refs + 2 contracts | Editorial methodology, scoring rubrics, verification standards, memory distillation |
| **Outdated (Hermes assumptions)** | 7 items | ToolInterceptor, skill-ordered pipeline, unlimited memory, Hindsight Cloud on Kaggle, browser on Kaggle, custom tool registration, profile persistence |
| **Outdated (OpenMontage assumptions)** | 8 items | YouTube in documentary-montage, granular video_analyzer tools, Remotion/HyperFrames default, edit_decisions schema match, custom pipeline auto-registration |
| **Incorrect** | 3 items | ToolInterceptor existence, web toolset = YouTube search, video_analyzer as granular sub-tool |
| **Missing Verification** | 11 items | Tool registry preflight, Hermes memory tool schema, browser tool YouTube capability, yt-dlp auth limits, custom pipeline registration, stage director skill reading |
| **Reusable with Modification** | 6 skills + 1 new skill needed | `football-source-discovery` → add acquisition; `football-visual-scene-analysis` → use real tools; `openmontage-edit-planning` → schema lock; `openmontage-audio-operation-mapper` → schema map; `hermes-openmontage-repo-bridge` → configurable paths; `football-match-identification` → human gate; **NEW: `football-footage-acquisition`** |
