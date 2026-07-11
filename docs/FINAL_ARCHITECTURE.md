# Final Architecture — AI Creative Director Football Video System

**Status:** LOCKED — Source of truth for all implementation sessions  
**Date:** 2026-07-11  
**Upstream Locks:** Hermes-Agent `5ecc079`, OpenMontage `f633b5f`

---

## 1. Component Responsibilities

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER REQUEST (Discord/CLI)                          │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        HERMES AGENT (Reasoning Host)                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Session Context: session_id, user_instruction, profile, project    │   │
│  │  Skill Activation: Description-based matching (agentskills.io)      │   │
│  │  Memory: MEMORY.md (2.2K) + USER.md (1.375K) + Hindsight (opt)     │   │
│  │  Tools: web, browser, terminal, file, memory, session_search, ...   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ACD WORKER ORCHESTRATOR (Thin Adapter)                   │
│  • Receives user request → creates Hermes session                           │
│  • Loads Football Emotion skills from ~/.hermes/skills/football-emotion/   │
│  • Enforces stage order via social-edit-reasoning (editorial_journey_state)│
│  • Manages project workspace: /kaggle/working/projects/<project-id>/       │
│  • Persists checkpoints, artifacts, memory updates                          │
│  • Sends Discord notifications                                              │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ▼
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
┌───────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ FOOTAGE       │       │ OPENMONTAGE     │       │ HERMES MEMORY   │
│ ACQUISITION   │       │ PIPELINE        │       │ (Hindsight/     │
│ SUBSYSTEM     │──────▶│ (Editing/       │       │  Built-in)      │
│ (Hermes tools)│       │  Rendering)     │       │                 │
└───────────────┘       └─────────────────┘       └─────────────────┘
```

### 1.1 Hermes Agent (NousResearch/Hermes-Agent)
**Role:** Reasoning host, skill orchestration, memory, tool execution, user interaction  
**Locked Capabilities:**
- Skills: agentskills.io standard (`SKILL.md` + optional `references/`, `scripts/`, `templates/`, `assets/`)
- Memory: Built-in (`MEMORY.md`/`USER.md` file-backed) + pluggable providers (Hindsight local_embedded, Mem0, Honcho)
- Tools: 30+ built-in toolsets (web, browser, terminal, file, memory, session_search, etc.)
- Profiles: Isolated `HERMES_HOME` per profile (config, skills, sessions, memories, projects)
- Interfaces: CLI, ACP (VS Code), Gateway (Discord/Telegram/Slack), Web Dashboard, Cron

**Our Usage:** Hosts Football Emotion skills; executes `web`/`browser`/`terminal`/`file`/`memory` tools; persists lessons to memory after each run.

### 1.2 ACD Worker Orchestrator (Our Code — Thin Adapter)
**Role:** Glue layer between user request, Hermes session, and OpenMontage project  
**Responsibilities:**
- Initialize Hermes with football-emotion skills loaded
- Create project workspace: `OPENMONTAGE_PROJECTS_DIR=/kaggle/working/projects/<project-id>/`
- Enforce editorial journey stage order via `social-edit-reasoning` skill
- Translate Hermes skill outputs → OpenMontage artifacts (via bridge skills)
- Manage checkpoints/resume (delegate to OpenMontage `lib/checkpoint.py`)
- Discord notifications (start/fail/complete + output location)
- Kaggle persistence: symlink `~/.hermes` → `/kaggle/working/.hermes`, `projects/` → `/kaggle/working/projects/`

**Non-Responsibilities:** No video processing, no creative decisions, no tool implementation.

### 1.3 Footage Acquisition Subsystem (Hermes Tools + Custom Skill)
**Role:** Discover → Rank → Acquire → Review → Manifest local footage  
**Components:**
- `football-source-discovery` skill: Multi-query YouTube search (via Hermes `browser` tool), candidate ranking, rejection rules
- **NEW** `football-footage-acquisition` skill: Sequential download via OpenMontage `video_downloader` (yt-dlp), failure replacement, `source_media_review` artifact generation
- `football-visual-scene-analysis` skill: Frame review via OpenMontage `frame_sampler`/`scene_detect` tools → `video_scene_analysis`
- `football-timestamp-extraction` + `football-clip-scoring`: Clip candidates → scored selection
- Output: `source_media_review` (OpenMontage canonical artifact) + `clip_candidate[]` for edit planning

**Key Boundaries:**
- Acquisition **outside** OpenMontage pipelines (per locked decision)
- Hands **local file paths** to OpenMontage via `asset_manifest` + `source_media_review`
- No proxies, CAPTCHA solving, stolen cookies, IP rotation (locked decision)
- Blocked candidates abandoned → replaced strategically (skill logic)

### 1.4 OpenMontage Pipeline (calesthio/OpenMontage)
**Role:** Pipeline-driven editing, composition, rendering  
**Locked Pipeline:** `documentary-montage` (best fit for real-footage football emotion)  
**Stages (manifest-enforced):**
```
idea → scene_plan → assets → edit → compose
```
**Stage Director Skills (OpenMontage native):**
- `idea-director` → `brief` (thematic question, tone, duration, music plan, end-tag)
- `scene-director` → `scene_plan` (slots with search queries, preferred sources)
- `asset-director` → `asset_manifest` (picked clips + provenance + license)
- `edit-director` → `edit_decisions` (cuts, overlays, audio, subtitles, renderer_family, render_runtime, composition_mode)
- `compose-director` → `render_report` (video output + validation)

**Our Integration Points:**
- `football_emotion/` auxiliary artifacts under `projects/<id>/football_emotion/` (per `openmontage-artifact-bridge.md`)
- `openmontage-edit-planning` skill produces `openmontage_edit_plan` → mapped to `edit_decisions` **after** `openmontage_schema_lock: passed`
- `openmontage-audio-operation-mapper` maps `audio_plan` → `edit_decisions.audio`
- Football QA skills (`football-retention-quality-control`, `football-audio-quality-control`) run **before** OpenMontage `reviewer` gate

### 1.5 Football Emotion Skills (Domain Logic)
**23 skills** — all installed under `~/.hermes/skills/football-emotion-video/` (or Hermes external skill dir)  
**Categories:**
- **Discovery/Analysis:** `football-source-discovery`, `football-visual-scene-analysis`, `football-timestamp-extraction`, `football-clip-scoring`, `football-match-identification`
- **Story/Editorial:** `football-story-strategy`, `football-narration-scriptwriting`, `football-pro-cutting-pacing`, `social-edit-reasoning` (stage router)
- **Audio:** `football-music-library-selector`, `football-rights-safe-audio-license-checker`, `football-audio-music-director`, `football-commentary-ducking-mixer`, `football-audio-quality-control`
- **Visual/Text:** `football-caption-thumbnail-direction`
- **Rights/Fact:** `football-fact-provenance-gate`, `football-footage-rights-transformative-risk-assessor`
- **QA/Delivery:** `football-retention-quality-control`, `football-platform-export-validator`
- **Bridge/Memory:** `hermes-openmontage-repo-bridge`, `openmontage-edit-planning`, `openmontage-audio-operation-mapper`, `hermes-football-memory-learning`

**Activation:** Hermes description-based matching; orchestrator enforces order via `editorial_journey_state`.

---

## 2. Boundaries Between Components

| Boundary | Rule |
|----------|------|
| **Hermes ↔ ACD Worker** | Worker creates session, feeds user request, reads final memory update. No direct tool calls from worker. |
| **Hermes ↔ Footage Acquisition** | Skills invoke Hermes tools (`browser`, `terminal` for yt-dlp, `file` for local paths). Acquisition skills output `source_media_review` artifact. |
| **Footage Acquisition ↔ OpenMontage** | **Only** via `source_media_review` + `asset_manifest` artifacts. No shared memory, no direct tool calls. |
| **Hermes ↔ OpenMontage** | Hermes skills (`openmontage-edit-planning`, `openmontage-audio-operation-mapper`) produce **adapter-facing plans**; only after `openmontage_schema_lock: passed` are native OpenMontage artifacts written. OpenMontage tools invoked via Hermes `terminal` tool (running `python -m tools...`) or future ACP/MCP. |
| **OpenMontage ↔ FFmpeg** | Internal to OpenMontage `video_compose` (operation=`compose`). ACD worker never calls FFmpeg directly. |
| **Skills ↔ Skills** | Via shared artifacts only (`pipeline-artifacts.md` contracts). No direct function calls. |
| **Memory ↔ Everything** | `hermes-football-memory-learning` writes to Hermes memory **only**. OpenMontage has no memory access. Hindsight (if enabled) is a Hermes memory provider. |

---

## 3. Complete Workflow (Traceable to Locked Decisions)

```
1. USER REQUEST
   → Discord webhook / CLI → ACD Worker creates Hermes session (profile: football-emotion)

2. HERMES UNDERSTANDS STORY
   → social-edit-reasoning: brief_interpretation (emotional_question, tonal_flavor, runtime, platform, arc_phases)
   → football-story-strategy: user_instruction_profile + story_plan (structure, hook, sections, minimum_clip_package)

3. FOOTAGE REQUIREMENTS
   → football-source-discovery: multi-query YouTube search (Hermes browser tool)
   → candidate ranking (7-axis rubric) → source_video_candidate[] with deep_analysis_candidate flags

4. AUTOMATIC YOUTUBE-FIRST DISCOVERY
   → Hermes browser tool navigates YouTube, extracts video IDs/URLs
   → No user links required (locked: "programme must discover footage automatically")

5. CANDIDATE INSPECTION & RANKING
   → football-visual-scene-analysis: OpenMontage frame_sampler + scene_detect on each deep-analysis candidate
   → video_scene_analysis with confidence/verification_status
   → football-timestamp-extraction: scene → clip_candidate[] (editor_timeline_role, source_range)
   → football-clip-scoring: rubric scoring (emotional_strength, visual_clarity, story_relevance, audio_commentary, uniqueness, editability, rights_risk) → ranked clips

6. CAREFUL SEQUENTIAL ACQUISITION
   → football-footage-acquisition (NEW skill): for each selected clip_candidate:
        - video_downloader (yt-dlp) → local file
        - verify duration/resolution/audio
        - on failure: mark rejected, fetch next candidate from ranked list
        - build source_media_review artifact (technical_probe, content_summary, transcript_summary, quality_risks, usable_for)

7. REPLACEMENT OF FAILED CANDIDATES
   → Acquisition skill loops through ranked alternatives until quota met or exhausted
   → source_media_review.verification_status tracks each attempt

8. LOCAL FOOTAGE MANIFEST
   → asset_manifest (OpenMontage canonical) + source_media_review (supplementary)
   → All local paths under projects/<id>/football_emotion/sources/

9. OPENMONTAGE ANALYSIS (Pipeline: documentary-montage)
   → idea-director: brief (thematic_question, tone, duration, music_plan, end_tag)
   → scene-director: scene_plan (slots mapped to our clip_candidate[] via football_emotion/clip_scores.json)
   → asset-director: asset_manifest (ingests our local files, records provenance/license)
   → edit-director: edit_decisions (from openmontage-edit-planning skill output, post schema_lock)
   → compose-director: render_report (FFmpeg render, validation)

10. FOOTBALL SKILL ACTIVATION (Parallel to Pipeline Stages)
    - Stage idea: football_emotion/brief_interpretation.json → proposal
    - Stage scene_plan: football-timestamp-extraction, football-clip-scoring → football_emotion/clip_scores.json
    - Stage assets: football-source-discovery, football-visual-scene-analysis → football_emotion/source_candidates.json
    - Stage edit: openmontage-edit-planning, openmontage-audio-operation-mapper, football-pro-cutting-pacing, football-audio-music-director, football-commentary-ducking-mixer
    - Stage compose: football-retention-quality-control, football-audio-quality-control, football-platform-export-validator

11. AUTOMATIC QUALITY REVIEW
    → football-retention-quality-control: full_qa_report (technical, editorial, platform, reused-content, vibe)
    → football-audio-quality-control: qc_report (loudness, ducking, peak)
    → football-platform-export-validator: export_profile (platform, aspect, resolution, codec, loudness)
    → Loopback instructions if any gate fails

12. DISCORD RESULT
    → ACD Worker sends webhook: status, video path (or error), project location

13. HERMES/HINDSIGHT MEMORY UPDATE
    → hermes-football-memory-learning: hermes_memory_update (lessons, tool envelope, source outcomes, music decisions, clip patterns, QA problems, result status)
    → Written to MEMORY.md/USER.md (size-enforced) + full project record at projects/<id>/football_emotion/project_record.json
    → Hindsight (if local_embedded) retains full semantic recall
```

---

## 4. Memory Design

### 4.1 Hermes Built-in Memory
- **MEMORY.md** (~2,200 chars): Agent observations, reusable lessons
- **USER.md** (~1,375 chars): User preferences, style patterns
- **Session Search (SQLite+FTS5):** Full conversation history, cross-profile searchable
- **Frozen Snapshot Pattern:** System prompt gets memory snapshot at session start; mid-session writes update disk but **not** system prompt (preserves prefix cache)
- **Drift Detection:** On write, reloads under lock; refuses write if on-disk content wouldn't round-trip; creates `.bak.<ts>` snapshot
- **Threat Scanning:** `threat_patterns.py` at load time; poisoned entries → `[BLOCKED: ...]` in snapshot, kept in live state for user review

### 4.2 Football Memory Update (hermes-football-memory-learning)
**Output:** `hermes_memory_update` artifact → distilled to MEMORY.md/USER.md
```yaml
hermes_memory_update:
  project_id: string
  topic: string
  story_type: string
  short_lessons: [string]           # each ≤ MEMORY.md scale
  best_source_types: [string]
  successful_hook_pattern: string | null
  successful_audio_pattern: string | null
  clips_to_avoid_next_time: [string]
  full_project_record_path: string  # pointer to large on-disk record
```

### 4.3 Hindsight Integration (Optional, Kaggle-Compatible)
- **Mode:** `local_embedded` only (downloads ~200MB daemon, needs local LLM endpoint)
- **Config:** `$HERMES_HOME/hindsight/config.json` (profile-scoped)
- **Bank ID Template:** `hermes-{profile}` for isolation
- **Tools Exposed:** `hindsight_retain`, `hindsight_recall`, `hindsight_reflect`
- **Not Used:** Cloud mode (no internet), local_external (no persistent daemon on Kaggle)

### 4.4 Kaggle Persistence Design
```
Kaggle Kernel (ephemeral)
├── /kaggle/working/
│   ├── .hermes/              ← symlinked from ~/.hermes
│   │   ├── config.yaml
│   │   ├── .env
│   │   ├── state.db          (sessions)
│   │   ├── memories/
│   │   │   ├── MEMORY.md
│   │   │   └── USER.md
│   │   └── skills/football-emotion-video/
│   └── projects/             ← symlinked from OpenMontage PROJECTS_DIR
│       └── <project-id>/
│           ├── checkpoint_*.json
│           ├── football_emotion/
│           │   ├── brief_interpretation.json
│           │   ├── source_candidates.json
│           │   ├── clip_scores.json
│           │   ├── story_plan.json
│           │   ├── audio_music_plan.json
│           │   ├── visual_cohesion_plan.json
│           │   ├── graphics_text_plan.json
│           │   ├── assembly_plan.json
│           │   ├── rights_and_license_report.json
│           │   ├── qa_report.json
│           │   ├── hermes_memory_update.json
│           │   └── project_record.json
│           └── (OpenMontage artifacts: brief, scene_plan, asset_manifest, edit_decisions, render_report)
```
**Setup Commands (run once per kernel session):**
```bash
export HERMES_HOME=/kaggle/working/.hermes
export OPENMONTAGE_PROJECTS_DIR=/kaggle/working/projects
mkdir -p $HERMES_HOME $OPENMONTAGE_PROJECTS_DIR
ln -sfn /kaggle/working/.hermes ~/.hermes
ln -sfn /kaggle/working/projects ~/OpenMontage/projects  # if OpenMontage expects ~/OpenMontage
```

---

## 5. Failure & Resume Design

### 5.1 Checkpoint Strategy (OpenMontage `lib/checkpoint.py`)
- **Per-stage checkpoints:** `projects/<id>/checkpoint_<stage>.json` + `history/` archive
- **Gate enforcement:** `human_approval_default: true` in manifest → status `awaiting_human` required before `completed`
- **Atomic writes:** `.tmp` → `os.replace`; superseded checkpoints archived to `history/`
- **Resume:** `get_next_stage()` uses pipeline-specific stage order; tools declare `resume_support`: `NONE`/`FROM_START`/`FROM_CHECKPOINT`

### 5.2 Failure Modes & Recovery

| Failure Point | Detection | Recovery |
|---------------|-----------|----------|
| YouTube search returns no candidates | `football-source-discovery` outputs empty ranked list | Abort → Discord "no footage found" → memory lesson |
| Video download fails (blocked/removed) | `video_downloader` returns error | `football-footage-acquisition` tries next ranked candidate (max 3 retries per slot) |
| Frame extraction fails | `frame_sampler` status `UNAVAILABLE` | Fallback: `video_analyzer` deep mode (monolithic) or manual review gate |
| Scene analysis confidence low | `video_scene_analysis.verification_status: partial/unverified` | Flag `manual_review_needed: true` → human gate before timestamp extraction |
| Clip scoring yields no ≥6 candidates for required slot | `football-clip-scoring` mandatory package check fails | Loopback to `football-source-discovery` (social-edit-reasoning routes back) |
| OpenMontage pipeline stage fails | Checkpoint status `failed` | Resume from last `completed` checkpoint; re-run failed stage with revised inputs |
| Render runtime unavailable | `render_runtime` locked but provider missing | Preflight catches this; user prompted to confirm alternative (FFmpeg only) |
| Audio license verification fails | `license_verification_record.status: rejected` | `football-music-library-selector` finds alternative; loopback to audio plan |
| Discard candidate due to rights risk | `footage_rights_risk_record.recommendation: avoid` | Replace from ranked list; log lesson to memory |

### 5.3 Resumable Project State
- **Hermes:** Session ID persisted in `state.db`; `parent_session_id` links subagents
- **OpenMontage:** Checkpoint per stage + `project.json` marker
- **ACD Worker:** Tracks project ID, stage, last successful checkpoint in `state/runs/<run-id>.json`
- **Discord:** Notified on failure with resume instructions (re-run with same project ID)

---

## 6. Future Additional-Skill-System Extension Method

**Principle:** Football Emotion skills are **domain-specific**, not framework-specific. New categories (e.g., "Tech Review", "Travel Vlog") add parallel skill trees under `~/.hermes/skills/<category>/`.

### 6.1 Extension Pattern
```
~/.hermes/skills/
├── football-emotion-video/          (23 skills — this system)
├── tech-review-video/               (future: new skills)
│   ├── tech-source-discovery
│   ├── tech-spec-extraction
│   ├── tech-comparison-scripting
│   └── ...
└── travel-vlog-video/               (future)
    ├── travel-location-scouting
    ├── travel-itinerary-story
    └── ...
```

### 6.2 Shared Infrastructure (Reused)
| Component | Reused By All Categories |
|-----------|-------------------------|
| `social-edit-reasoning` | Stage router + editorial journey state machine |
| `hermes-openmontage-repo-bridge` | Repo integration (parameterized by skill category path) |
| `openmontage-edit-planning` | Edit planning (parameterized by artifact contract) |
| `openmontage-audio-operation-mapper` | Audio mapping (parameterized by audio plan schema) |
| `hermes-football-memory-learning` → `hermes-<category>-memory-learning` | Memory distillation (category-specific lessons) |
| Editorial journey references (`shared/references/editorial-journey/*`) | Professional workflow methodology |
| Verification standard, provenance standard, llm-decision-boundaries | Cross-cutting governance |

### 6.3 Category-Specific Contracts
Each category defines its own `pipeline-artifacts.md` extending the base with domain-specific artifacts (e.g., `tech_spec_comparison_table`, `travel_itinerary_map`).

### 6.4 Pipeline Selection
- Football emotion → `documentary-montage` (real footage, archive style)
- Tech review → `screen-demo` or `hybrid` (screen capture + generated inserts)
- Travel vlog → `talking-head` or `cinematic` (user footage + b-roll)
- **New pipeline manifests** added to `OpenMontage/pipeline_defs/` without core changes (manifest-first architecture)

---

## 7. Final Repository Structure

```
/home/kasun/Music/Director/acd-video-worker/
├── README.md
├── packages/
│   └── football_emotion_skill_system_v7_final_runtime.zip
├── docs/
│   ├── UPSTREAM_COMPATIBILITY_REPORT.md
│   ├── SKILL_SYSTEM_RECONCILIATION.md
│   ├── FINAL_ARCHITECTURE.md          (this file)
│   ├── IMPLEMENTATION_CONTRACT.md
│   ├── SESSION_02_BUILD_PLAN.md
│   └── upstream-lock.json
├── skills/
│   └── football-emotion-video/        (extracted from ZIP at setup)
│       ├── skills/                    (23 skill folders)
│       ├── shared/
│       ├── tools/
│       ├── evals/
│       └── implementation/
├── external/                          (cloned at setup, not in git)
│   ├── Hermes-Agent/                  (git clone NousResearch/Hermes-Agent @ 5ecc079)
│   └── OpenMontage/                   (git clone calesthio/OpenMontage @ f633b5f)
├── bootstrap/
│   ├── install_hermes.sh              (runs setup-hermes.sh, sets HERMES_HOME)
│   ├── install_openmontage.sh         (make setup, sets OPENMONTAGE_PROJECTS_DIR)
│   ├── install_skills.sh              (extracts ZIP → ~/.hermes/skills/football-emotion-video/)
│   └── validate_setup.py              (runs bridge_preflight.py + validate_skill_system.py)
├── scripts/
│   ├── acd_worker.py                  (main orchestrator entry point)
│   ├── discord_notify.py
│   └── kaggle_persistence.sh          (symlinks for /kaggle/working)
├── jobs/
│   └── football_video_job.py          (Kaggle job template)
├── state/
│   └── runs/                          (run metadata: project_id, stage, checkpoint, status)
└── outputs/                           (symlinked to /kaggle/working/outputs for delivery)
```

---

## 8. Decisions Explicitly Rejected

| Rejected Idea | Reason |
|---------------|--------|
| Modify Hermes-Agent core code | Locked: "Do not modify upstream repositories" |
| Modify OpenMontage core code | Locked: "Do not modify upstream repositories" |
| Build custom video editor | Locked: "OpenMontage is the primary editing and rendering engine" |
| Use Claude Video Editor | Locked: "Do not introduce another editor" |
| Implement proxies/CAPTCHA solving/IP rotation | Locked: "Do not implement proxies, CAPTCHA solving, stolen cookies, IP rotation or bot-protection bypass" |
| Automated license verification (scraper) | Locked: "Licensing automation is outside current target" — manual checklist only |
| Single MVP pipeline for all categories | Locked: "Future video categories will use separate skill systems" |
| Silent render runtime default | Locked: "OpenMontage treats silent defaulting as a governance violation" — user confirmation required |
| Hermes skill pipeline orchestrator built-in | Hermes has no pipeline orchestrator; skills activate by description match. Our orchestrator enforces order. |
| Hindsight Cloud on Kaggle | No outbound internet; only `local_embedded` possible |
| Browser tools on Kaggle | No background processes/daemons; Playwright blocked |
| GPU video generation on Kaggle (Wan/Hunyuan) | VRAM OOM risk on P100/T4; FFmpeg-only path chosen |
| Persistent Kaggle storage outside /kaggle/working | Not possible; symlinks to /kaggle/working is the pattern |
| Football-footage-finder as separate skill | Replaced by `football-source-discovery` + NEW `football-footage-acquisition` |
| Storing full project data in Hermes MEMORY.md | Size limits (2.2K/1.375K); use project files + pointer |
| Bypassing OpenMontage pipeline manifests | Locked: "Do not bypass pipeline_defs/ and stage director skills" |
| Writing OpenMontage artifacts outside projects/<id>/ | Locked: "Backlot and checkpoints depend on project workspace" |