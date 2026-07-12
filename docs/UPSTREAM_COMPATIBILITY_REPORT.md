> **Historical inspection snapshot. Use the current pinned-boundary evidence in `THIN_ORCHESTRATION_MODULE_MAP.md` for implementation decisions.**

# Upstream Compatibility Report

**Inspection Date:** 2026-07-11  
**Inspector:** Automated audit via OpenCode

---

## 1. Inspected Repositories

### Hermes-Agent (NousResearch/Hermes-Agent)

| Field | Value |
|-------|-------|
| Repository | https://github.com/NousResearch/Hermes-Agent |
| Commit | `5ecc07986f46463ca3096679b03a46402eb19cee` |
| Branch | `main` |
| Inspection Date | 2026-07-11 |
| Local Path (expected) | `/home/kasun/Music/Director/Hermes-Agent` |

### OpenMontage (calesthio/OpenMontage)

| Field | Value |
|-------|-------|
| Repository | https://github.com/calesthio/OpenMontage |
| Commit | `f633b5f428b9be9a2afecba851dfddd101619756` |
| Branch | `main` |
| Inspection Date | 2026-07-11 |
| Local Path (expected) | `/home/kasun/Music/Director/OpenMontage` |

---

## 2. Hermes-Agent — Real Capabilities (Verified in Code)

### 2.1 Installation & Startup
- **Bootstrap script:** `setup-hermes.sh` — detects Termux/desktop, installs `uv`, creates Python 3.11 venv, `uv sync`, installs ripgrep, seeds `.env`, symlinks `hermes` to `~/.local/bin`, runs `tools/skills_sync.py`
- **Package install:** `pip install -e .[all]` with curated extras (`modal`, `daytona`, `messaging`, `matrix`, `cron`, `cli`, `dev`, `tts-premium`, `slack`, `pty`, `honcho`, `mcp`, `homeassistant`, `sms`, `acp`, `voice`, `dingtalk`, `feishu`, `google`, `bedrock`, `web`, `youtube`)
- **CLI entry:** `hermes_cli/main.py` → `hermes` command
- **ACP server:** `hermes acp` for VS Code/Cursor integration
- **Docker:** s6-overlay, `docker/stage2-hook.sh` seeds config, skills, Playwright Chromium

### 2.2 Configuration System
- **Primary:** `~/.hermes/config.yaml` (YAML, layered: CLI flags > env vars > config.yaml > defaults)
- **Secrets:** `~/.hermes/.env` (600 perms, `load_hermes_dotenv()`)
- **Auth tokens:** `~/.hermes/auth.json` (OAuth refresh tokens)
- **Config cache:** Thread-safe `_LOAD_CONFIG_CACHE` keyed by `(path, mtime_ns, size)` + managed-scope config + env snapshot
- **Corrupt config handling:** Snapshots broken file to `config.yaml.corrupt.<ts>.bak`, falls back to defaults
- **Env writer denylist:** Blocks `LD_PRELOAD`, `PYTHONPATH`, `PATH`, `EDITOR`, `HERMES_HOME`, `HERMES_PROFILE`, etc.

### 2.3 Project/Profile Isolation
- **Profiles:** Each profile = independent `HERMES_HOME` under `~/.hermes/profiles/<name>/` (config, .env, state.db, memories/, skills/, sessions/, cron/, logs/, workspace/, home/, pairing/, platforms/)
- **Default profile:** `~/.hermes` (backward compatible)
- **Commands:** `hermes profile create <name> [--clone|--clone-all]`, `hermes profile use <name>`, `hermes profile delete <name>`, `hermes -p <name> chat`
- **Wrapper aliases:** Creates `~/.local/bin/<name>` → `hermes -p <name> $@`
- **Clone modes:** `--clone` copies config.yaml, .env, SOUL.md, memories/; `--clone-all` deep-copies minus history/backups/infrastructure
- **Projects:** First-class SQLite DB at `$HERMES_HOME/projects.db` (WAL mode); desktop session grouping by cwd longest-prefix match; kanban board binding

### 2.4 Skill Discovery & External Skill Directories
- **Skills Hub:** `tools/skills_hub.py` + `hermes_cli/skills_hub.py`
- **Sources:**
  - Bundled: `skills/` (builtin), `optional-skills/` (trusted) → synced to `~/.hermes/skills/` at install
  - GitHub taps: `hermes skills tap add <user/repo>` → Contents API, 1hr cache
  - URL install: `hermes skills install https://.../SKILL.md` → fetches, validates, quarantines
  - Local drop: `~/.hermes/skills/<category>/<name>/SKILL.md` → auto-discovered
- **Skill structure:** `SKILL.md` (required, YAML frontmatter), `DESCRIPTION.md`, `references/`, `templates/`, `assets/`, `scripts/`
- **Frontmatter:** `name`, `description`, `platforms[]`, `environments[]`, `tags[]`
- **Discovery:** Walks `~/.hermes/skills/`, parses frontmatter, filters `.git`, `.hub`, `.venv`, `node_modules`, `__pycache__`, `references/`, `templates/`, `assets/`, `scripts/`
- **Security:** `tools/skills_guard.py` AST-based static analysis, secret detection, network/eval/exec detection; trust levels: `builtin`/`trusted`/`community`

### 2.5 Tool Registration
- **Registry:** `tools/registry.py` → singleton `ToolRegistry` with thread-safe lock + generation counter
- **Self-registration:** Each tool module calls `registry.register(...)` at import time
- **Discovery:** `discover_builtin_tools()` imports all `tools/*.py` with top-level `registry.register(...)` (AST-verified)
- **Plugin toolsets:** `hermes_cli/plugins.py` discovers plugins in `plugins/` or `~/.hermes/plugins/`
- **ToolEntry schema:** `name`, `toolset`, `schema` (OpenAI function), `handler` (sync/async), `check_fn` (availability gate), `requires_env[]`, `is_async`, `description`, `emoji`, `max_result_size_chars`, `dynamic_schema_overrides`
- **Availability gating:** `check_fn` TTL cache 30s, grace window 60s after last success; `invalidate_check_fn_cache()` on enable/disable
- **Toolset composition:** 30+ built-in toolsets; `_DEFAULT_OFF_TOOLSETS` for opt-in only; platform restrictions (e.g., `discord` only on `discord` platform)

### 2.6 Browser Tools
- **Backends:** Local `agent-browser` (Node/Chromium via Playwright), Browserbase (cloud), Browser Use (cloud), Firecrawl (cloud), Camofox (local anti-detection)
- **Session isolation:** Per `task_id` browser context
- **Features:** Accessibility tree snapshots, element interaction via ref selectors (`@e1`, `@e2`...), task-aware LLM content extraction, auto-cleanup
- **Security:** Subprocess env scrubs all Hermes secrets, passes only `_BROWSER_PASSTHROUGH_KEYS`
- **Safety gates:** `tools/url_safety.py` + `tools/website_policy.py` — fail-closed URL blocking
- **Timeouts:** Configurable (`browser.command_timeout`, default 30s, min 60s for `open`, 120s for first open)
- **PATH resolution:** Prepends Hermes-managed Node, Homebrew node, system paths
- **Docker:** Playwright Chromium pre-installed; `stage2-hook.sh` exports `AGENT_BROWSER_EXECUTABLE_PATH`

### 2.7 Programmatic Control
| Interface | Entry Point | Use Case |
|-----------|-------------|----------|
| CLI (fire-based) | `run_agent.py` → `AIAgent` | `python -m run_agent "prompt"` |
| Library API | `from run_agent import AIAgent` | Embed in Python apps |
| ACP Server | `hermes acp` / `hermes_cli/subcommands/acp.py` | VS Code/Cursor integration |
| Gateway (HTTP) | `hermes gateway` / `hermes_cli/gateway.py` | Multi-user, multi-platform (Telegram, Discord, Slack, WhatsApp, Matrix) |
| Web Dashboard | `hermes dashboard` / `hermes_cli/web_server.py` | React/Vite SPA at `localhost:8080` |
| Cron/Scheduler | `hermes cron` / `hermes_cli/cron.py` | Scheduled runs with attached skills |
| Subagent/Delegation | `delegate_task` tool | Spawn child agent with inherited context, isolated memory (`skip_memory=True`) |

**AIAgent constructor:** 60+ parameters including callbacks (`tool_start`, `tool_complete`, `thinking`, `reasoning`, `clarify`, `read_terminal`, `step`, `stream_delta`, `interim_assistant`, `tool_gen`)

### 2.8 Event/Run Tracking
- **Session DB:** `hermes_state.py` (SQLite WAL) — tables: `sessions` (id, title, source, model, started_at, last_active, message_count, parent_session_id), `messages` (id, session_id, role, content, tool_calls, tool_name, tool_call_id, timestamp)
- **FTS5 Search:** `tools/session_search_tool.py` — BM25 search, modes: discovery (query), scroll (session_id + around_message_id), browse (recent); lineage-aware dedup; cron demotion, subagent/tool session hiding
- **MoA Traces:** Opt-in (`moa.save_traces: true`) → JSONL at `~/.hermes/moa-traces/<session_id>.jsonl`
- **HF Upload:** `hermes trace upload <session_id>` → exports Claude Code JSONL to private `hermes-traces` dataset; redacts secrets via `agent/redact.py`
- **Conversation Logging:** Structured JSONL to `~/.hermes/logs/agent.log`, `errors.log`
- **Kanban Events:** Task lifecycle, worktree creation, dispatcher heartbeats
- **Gateway Events:** Service state, message delivery, cron triggers
- **Run ID:** UUID (timestamp + random hex); subagents get new session_id with `parent_session_id` link; cron tagged `source: cron`; delegation tagged `source: subagent`

### 2.9 Built-in Memory
- **Memory Tool:** `tools/memory_tool.py` — two stores: `MEMORY.md` (agent observations), `USER.md` (user preferences)
- **Location:** `$HERMES_HOME/memories/` (profile-scoped)
- **Format:** §-delimited entries (`\n§\n`)
- **Limits:** 2,200 chars (MEMORY), 1,375 chars (USER) — character-based, model-independent
- **Frozen snapshot:** System prompt gets snapshot at session start; mid-session writes update disk but NOT system prompt (prefix cache preservation)
- **Drift detection:** On write, reloads file under lock; if on-disk content wouldn't round-trip through parser, refuses write, creates `.bak.<ts>`, returns remediation instructions
- **Threat scanning:** `tools/threat_patterns.py` strict scope at load — poisoned entries replaced with `[BLOCKED: ...]` in snapshot, kept in live state for user inspection
- **File locking:** `fcntl` (Unix) / `msvcrt` (Windows) on `.lock` companion files

### 2.10 Session Search
- **Tool:** `tools/session_search_tool.py` — single tool, three inferred modes (discovery, scroll, browse)
- **Lineage-aware dedup:** Walks `parent_session_id` to root; only root sessions returned
- **Source demotion:** `cron` ranked below interactive; `subagent`/`tool` hidden entirely
- **Cross-profile:** `profile` param opens another profile's `state.db` read-only; `_locate_session_db` scans all profiles for session_id
- **Zero LLM cost:** Pure SQL + FTS5, no summarization calls
- **Message shaping:** Returns slim dicts (id, role, content, timestamp, tool_name, tool_calls, tool_call_id, anchor flag)

### 2.11 Hindsight Integration
- **Plugin:** `plugins/memory/hindsight/__init__.py` — `HindsightMemoryProvider` implements `MemoryProvider` ABC
- **Modes:**
  - `cloud`: Hindsight Cloud API (vectorize.io) — needs `hindsight-client>=0.6.1`, `HINDSIGHT_API_KEY`
  - `local_embedded`: Embedded daemon (~200MB download) — needs `hindsight-all`, local LLM (OpenAI-compatible)
  - `local_external`: Connect to existing instance — needs `hindsight-client`, `HINDSIGHT_API_URL`
- **Config sources (priority):** `$HERMES_HOME/hindsight/config.json` (profile-scoped) > `~/.hindsight/config.json` (legacy shared) > env vars
- **Key config:** `mode`, `apiKey`, `api_url`, `bank_id`, `budget`, `bank_id_template` (e.g., `hermes-{profile}`), `llm_provider`, `llm_model`, `llm_api_key`, `memory_mode` (hybrid/context/tools), `recall_prefetch_method`, `retain_tags`, `observation_scopes`, `auto_recall`, `auto_retain`, `retain_every_n_turns`, `recall_types`, `recall_max_tokens`, `timeout`, `idle_timeout`
- **Tools exposed:** `hindsight_retain(content, context, tags)`, `hindsight_recall(query)`, `hindsight_reflect(query)`
- **Architecture:** Single-writer thread for `retain` (queue + sentinel shutdown); shared asyncio event loop on background thread; API capability probe checks `/version` for `update_mode=append` support (≥0.5.0); embedded daemon health grace timeout configurable

### 2.12 Persistence Locations

| Data | Path | Notes |
|------|------|-------|
| Config | `~/.hermes/config.yaml` | YAML, atomic write |
| Secrets | `~/.hermes/.env` | 600 perms |
| Auth tokens | `~/.hermes/auth.json` | OAuth refresh tokens |
| Sessions | `~/.hermes/state.db` | SQLite WAL |
| Response cache | `~/.hermes/response_store.db` | LLM response caching |
| Memory | `~/.hermes/memories/MEMORY.md`, `USER.md` | §-delimited, file-locked |
| Skills | `~/.hermes/skills/` | User-installed + synced bundled |
| Bundled skills (source) | `skills/`, `optional-skills/` | Git-tracked |
| Skill hub state | `~/.hermes/skills/.hub/` | `lock.json`, `taps.json`, `index-cache/`, `quarantine/`, `audit.log` |
| Projects | `~/.hermes/projects.db` | SQLite, per-profile |
| Kanban | `~/.hermes/kanban.db` | Root-anchored (shared across profiles) |
| Cron | `~/.hermes/cron/jobs.json` | Per-profile |
| Gateway state | `~/.hermes/gateway_state.json` | Supervised service state |
| Logs | `~/.hermes/logs/` | `agent.log`, `errors.log`, `gateways/` |
| MoA traces | `~/.hermes/moa-traces/<session_id>.jsonl` | Opt-in |
| Backups | `~/.hermes/backups/` | `hermes backup` archives |
| Checkpoints | `~/.hermes/checkpoints/` | Session checkpoints |
| State snapshots | `~/.hermes/state-snapshots/` | Quick-backup snapshots |
| Pairing | `~/.hermes/platforms/pairing/` | Device pairing approvals |
| Lazy packages | `~/.hermes/lazy-packages/` | Pip installs for optional backends (appended to sys.path) |
| Hindsight local | `~/.hindsight/` / `$HERMES_HOME/hindsight/` | Legacy shared / profile-scoped |
| Node/Chromium | `~/.hermes/node/`, `~/.hermes/.playwright/` | Hermes-managed runtimes |
| **Docker** | `/opt/data/` (mount) | All above under `/opt/data/`; image keeps immutable `/opt/hermes/` |

### 2.13 Kaggle Compatibility Risks
| Risk Area | Finding | Impact |
|-----------|---------|--------|
| No Kaggle runtime detection | No `KAGGLE_KERNEL_RUN_TYPE`, `KAGGLE_URL_BASE`, `KAGGLE_KERNEL_ID` env checks in `hermes_constants.is_container()` or platform detection | Won't auto-adapt to read-only `/kaggle/working`, no internet, ephemeral FS |
| HERMES_HOME persistence | Defaults to `~/.hermes` (POSIX) / `%LOCALAPPDATA%\hermes` (Windows) | Kaggle's `~` is ephemeral; config/skills/sessions lost on kernel restart unless `HERMES_HOME=/kaggle/working/.hermes` set |
| Network-dependent features | Browser tools (Playwright), cloud providers (Browserbase, Hindsight Cloud), gateway, web dashboard, OAuth flows | Kaggle kernels have **no outbound internet** (unless "Internet on" enabled) — all cloud backends fail |
| Subprocess/daemon restrictions | `agent-browser` (Node), Hindsight embedded daemon, s6-overlay, Docker socket, terminal tool (Docker/Modal) | Kaggle blocks background processes, daemon sockets, Docker |
| File locking | `fcntl`/`msvcrt` locks on memory files, SQLite WAL | May work but NFS/ephemeral FS semantics uncertain |
| GPU/accelerator assumptions | Skills reference CUDA, vLLM, TensorRT | Kaggle provides T4/P100/A100 but no persistent driver setup |
| Long-running processes | Gateway, cron, kanban dispatcher, MoA | Kernel timeout (typically 1-6h) kills background work |
| Secret management | `.env`, `auth.json`, credential pool | Kaggle Secrets UI injects env vars — compatible if user sets `HERMES_HOME` and exports keys to env |

**Recommendations for Kaggle:**
1. Set `HERMES_HOME=/kaggle/working/.hermes` in kernel init cell
2. Use only local providers (Ollama, local_embedded Hindsight, local browser via Camofox if binary present)
3. Disable gateway, cron, dashboard, auto-update
4. Pre-bundle skills (`hermes skills install` offline) or copy `skills/` to `/kaggle/working/.hermes/skills/`
5. Use `hermes chat -q "prompt"` for one-shot runs (no interactive REPL)

---

## 3. OpenMontage — Real Capabilities (Verified in Code)

### 3.1 Setup & Startup
- **Bootstrap:** `make setup` — Python venv, pip install, Remotion `npm install`, Piper TTS, HyperFrames npx cache-warm, `.env` creation
- **Install variants:** `make install` / `make install-dev` / `make install-gpu`
- **Demo renderer:** `python render_demo.py` — zero-key demo using Remotion components only
- **Env loader:** `lib/env_loader.py` loads `.env` into `os.environ`
- **Config:** `lib/config_model.py` — Pydantic `OpenMontageConfig` with `LLMConfig`, `BudgetConfig`, `CheckpointConfig`, `OutputConfig`, `PathsConfig`
- **Paths:** `lib/paths.py` — `REPO_ROOT`, `PROJECTS_DIR` (overridable via `OPENMONTAGE_PROJECTS_DIR`)

### 3.2 Pipeline Stages
**Canonical 8-stage flow** (used by most production pipelines):
```
research → proposal → script → scene_plan → assets → edit → compose → publish
```

**Pipeline Categories & Examples:**
| Pipeline | Category | Stages |
|----------|----------|--------|
| `animated-explainer` | generated | All 8 + `proposal.sample` sub-stage |
| `cinematic` | cinematic | All 8 + `proposal.sample` sub-stage |
| `talking-head` | talking_head | All 8 (`idea` replaces `research`) |
| `documentary-montage` | documentary | `idea → scene_plan → assets → edit → compose` (5 stages) |
| `clip-factory` | custom | `idea → script → scene_plan → assets → edit → compose → publish` (7) |
| `avatar-spokesperson` | talking_head | 8 stages |
| `character-animation` | animation | 8 stages |
| `hybrid` | hybrid | 8 stages |
| `screen-demo` | screen_recording | 8 stages |
| `podcast-repurpose` | hybrid | 8 stages |
| `localization-dub` | custom | 8 stages |
| `animation` | animation | 8 stages |

**Sub-stages (conditional):** `proposal.sample` — 10-15s preview for reference-driven productions (activated when `video_analysis_brief_exists`)

### 3.3 Pipeline Definitions
- **Location:** `pipeline_defs/*.yaml` (12 manifests)
- **Schema:** `schemas/pipelines/pipeline_manifest.schema.json` (validated via `jsonschema` on load)
- **Key manifest fields:**
  - `name`, `version`, `description`, `category`, `stability`
  - `reference_input`: `{ supported: bool, analysis_depth: transcript_only\|standard\|deep, analysis_tools: [...] }`
  - `orchestration`: EP config (skill, budget, revision limits)
  - `extensions`: `{ custom_scripts, custom_playbooks, custom_skills, custom_tools }` — enforced by `check_extension_permitted()`
  - `required_skills`: List of skill paths (stage-director + meta skills)
  - `compatible_playbooks`: Recommended/also-works/custom_allowed
  - `stages[]`: Each declares `skill`, `produces`, `required_artifacts_in`, `optional_artifacts_in`, `required_tools`, `optional_tools`, `tools_available`, `checkpoint_required`, `human_approval_default`, `review_focus[]`, `success_criteria[]`, `sub_stages[]`

**Loaders:** `lib/pipeline_loader.py` — `load_pipeline()`, `list_pipelines()`, `get_stage_order()`, `get_required_tools()`, `get_stage_sub_stages()`, `get_reference_input_config()`, `check_extension_permitted()`

### 3.4 Local-Footage Input Path
- **Entry point:** `lib/source_media_review.py::review_source_media(files, context, tool_registry)`
- **Trigger:** Required by reviewer skill when user-supplied media exists. Enforced by:
  - `SUPPLEMENTARY_ARTIFACTS = {"source_media_review"}` in `lib/checkpoint.py`
  - Stage `optional_artifacts_in: [source_media_review]` in pipelines accepting footage
  - Reviewer gate: "If user media exists but no `source_media_review`: CRITICAL"
- **Processing:**
  1. Detect media type by extension (video/audio/image)
  2. Probe with `audio_probe` (ffprobe wrapper) → technical metadata
  3. Sample frames via `frame_sampler` (4 evenly-spaced timestamps)
  4. Transcribe via `transcriber` (Whisper) if audio present
  5. Assess quality risks (resolution, mono audio, duration)
  6. Infer usability (`hero footage`, `b-roll`, `narration source`, etc.)
- **Output Artifact:** `source_media_review` (schema: `schemas/artifacts/source_media_review.schema.json`)
  - `files[]`: `{ path, media_type, reviewed: true, technical_probe, content_summary, transcript_summary, representative_frames[], quality_risks[], usable_for[] }`
  - `summary`: Human-readable description
  - `planning_implications[]`: Actionable constraints for proposal/script/scene planning

**Pipelines Using It:** `talking-head`, `cinematic`, `hybrid`, `clip-factory`, `screen-demo`, `podcast-repurpose`, `localization-dub`

### 3.5 Artifact Schemas
- **Location:** `schemas/artifacts/*.schema.json` (15 schemas)
- **Loader:** `schemas/artifacts/__init__.py` — `load_schema()`, `validate_artifact()`, `ARTIFACT_NAMES`

**Core Artifacts & Producing Stages:**
| Artifact | Schema | Produced By Stage |
|----------|--------|-------------------|
| `research_brief` | ✅ | research |
| `proposal_packet` | ✅ | proposal |
| `brief` | ✅ | idea (doc-led pipelines) |
| `script` | ✅ | script |
| `scene_plan` | ✅ | scene_plan |
| `asset_manifest` | ✅ | assets |
| `edit_decisions` | ✅ | edit |
| `render_report` | ✅ | compose |
| `publish_log` | ✅ | publish |
| `video_analysis_brief` | ✅ | (reference input analysis) |
| `source_media_review` | ✅ | (source footage inspection) |
| `decision_log` | ✅ | proposal, assets, etc. |
| `final_review` | ✅ | compose |
| `character_design`, `rig_plan`, `pose_library` | ✅ | (character animation) |

**Key Schema Features:**
- Strict `additionalProperties: false`
- Enum-constrained fields (e.g., `scene.type`, `render_runtime: [remotion, hyperframes, ffmpeg]`)
- Governance fields: `renderer_family`, `render_runtime`, `composition_mode` locked at proposal, enforced at compose

### 3.6 Tool Registry
- **Core:** `tools/tool_registry.py::ToolRegistry` (singleton `registry`)
- **Discovery:** `discover("tools")` walks `pkgutil.walk_packages()`, imports modules, registers concrete `BaseTool` subclasses via `inspect.getmembers()`

**Tool Contract (`BaseTool` in `tools/base_tool.py`):**
- Identity: `name`, `version`, `tier` (CORE/VOICE/ENHANCE/GENERATE/SOURCE/ANALYZE/PUBLISH), `capability`, `provider`
- Dependencies: `dependencies[]` — `cmd:ffmpeg`, `env:API_KEY`, `python:module`
- Runtime: `LOCAL`, `LOCAL_GPU`, `API`, `HYBRID`
- Status: `get_status()` → `AVAILABLE`/`UNAVAILABLE`/`DEGRADED` (checks dependencies)
- Cost: `estimate_cost(inputs)`, `estimate_runtime(inputs)`
- Resume: `resume_support` (NONE/FROM_START/FROM_CHECKPOINT), `idempotency_key_fields`
- Schema: `input_schema`, `output_schema`, `artifact_schema`
- Execution: `execute(inputs) -> ToolResult` (instrumented for Backlot events)
- Fallback: `fallback`, `fallback_tools[]` — `find_fallback()` resolves chain

**Registry Queries:**
- `get_by_tier()`, `get_by_capability()`, `get_by_provider()`, `get_by_status()`, `get_available()`
- `support_envelope()` — full contract report
- `capability_catalog()`, `provider_catalog()` — grouped views
- `provider_menu_summary()` — compact preflight report (configured/total, setup offers, runtime warnings)
- `gpu_required_tools()`, `network_required_tools()`

**Tier Distribution (from code):**
- CORE: analysis, video_post, enhancement, subtitle, capture, character, etc.
- VOICE: TTS providers (elevenlabs, openai, google, piper, doubao, dashscope)
- GENERATE: image/video/music generation (flux, grok, imagen, veo, kling, music_gen, suno, etc.)
- SOURCE: stock media (pexels, pixabay, archive.org, NASA, etc.)
- ANALYZE: transcriber, scene_detect, frame_sampler, video_analyzer, audio_energy

### 3.7 Video Analysis Tools

#### `video_analyzer` (`tools/analysis/video_analyzer.py`)
**Orchestrates:** download (yt-dlp) → transcript (youtube-transcript-api/Whisper) → scene detection (PySceneDetect/FFmpeg) → frame sampling (FFmpeg) → motion classification (OpenCV optical flow) → audio energy (FFmpeg ebur128)

**Depths:**
- `transcript_only`: metadata + transcript
- `standard`: + scenes + keyframes + audio energy
- `deep`: + intra-scene sampling + detailed style extraction

**Output:** `video_analysis_brief` artifact with:
- `source`: type, URL/path, duration, resolution, platform metadata
- `content_analysis`: summary, topics, tone, hook, CTA
- `structure_analysis`: scenes[], pacing_profile (avg/shortest/longest scene, cuts/min, pacing_style)
- `style_profile`: color_palette, typography, transitions, music_style, narration_style, production_quality
- `narration_transcript`: segments with timestamps
- `keyframes[]`: timestamp, scene_index, path, description
- `replication_guidance`: suggested_pipeline, playbook, motion_required, complexity, differentiation seeds

#### `scene_detect` (`tools/analysis/scene_detect.py`)
**Methods:** `content` (PySceneDetect ContentDetector), `threshold`, `adaptive`  
**Fallback:** FFmpeg `select='gt(scene,threshold)'` via lavfi or `showinfo` parsing  
**Safety:** `_escape_lavfi_movie_path()` prevents filter injection (escapes `\:,[];`)

#### `frame_sampler` (`tools/analysis/frame_sampler.py`)
**Strategies:**
- `interval`: `fps=1/N`
- `count`: N frames evenly spaced
- `timestamps`: explicit list
- `scene_guided`: first frame of each scene + midpoint for scenes >3s (bounded by `max_frames`)

### 3.8 Audio Analysis

#### `audio_energy` (`tools/analysis/audio_energy.py`)
**Uses:** FFmpeg `ebur128` filter → momentary loudness (M:) every 100ms
**Outputs:**
- `energy_profile[]`: per-second `{ time_seconds, loudness_lufs, active }`
- `recommended_offset_seconds`: first active second (threshold default -40 LUFS)
- `best_window`: highest average loudness window for `video_duration_seconds`
- `needs_loop`: bool + shortfall info

#### `audio_probe` (`tools/analysis/audio_probe.py`)
**FFprobe wrapper** — duration, format, streams, codec, sample_rate, channels, bitrate

### 3.9 Timeline/Edit Creation

**Artifact:** `edit_decisions` (schema validates)
- `cuts[]`: `{ id, source, in_seconds, out_seconds, speed, layer, transform, transition_in/out, transition_duration, reason }`
- `overlays[]`: `{ asset_id, start/end, position, animation, opacity }`
- `audio`: `narration.segments[]`, `music` (asset_id, volume, ducking params), `sfx[]`
- `subtitles`: enabled, style, source, font, colors, position
- **Governance locks (must match proposal):**
  - `renderer_family`: enum of 8 families
  - `render_runtime`: `remotion` \| `hyperframes` \| `ffmpeg`
  - `composition_mode`: `templated` \| `atelier` (requires `bespoke` block)

**Tools:**
- `video_trimmer`: cut, speed, concat
- `silence_cutter`: auto jump cuts on silent segments
- `video_stitch`: multi-clip with transitions (cut/crossfade/fadeblack), spatial layouts
- `auto_reframe`: aspect conversion with face tracking

### 3.10 Rendering Paths

**Three Runtimes** (locked at proposal, enforced at compose):
| Runtime | Tool | Use Case |
|---------|------|----------|
| `remotion` | `video_compose` (operation=`remotion_render`) | React components, animated text/charts, cinematic renders |
| `hyperframes` | `hyperframes_compose` | HTML/CSS/GSAP, kinetic typography, product promos |
| `ffmpeg` | `video_compose` (operation=`compose`) | Pure video concat/trim, talking-head |

**`video_compose`** (`tools/video/video_compose.py`):
- `compose`: FFmpeg segment re-encode → concat → subtitle burn → audio mux
- `render`: High-level — resolves asset IDs, auto-routes to Remotion for images/animations or FFmpeg for video-only
- `remotion_render`: Direct `npx remotion render` with composition ID mapping from `RENDERER_FAMILY_MAP`
- Handles silent-audio clips (injects `anullsrc`), normalizes to 30fps/yuv420p, letterbox/pad or cover crop

**`hyperframes_compose`** (`tools/video/hyperframes_compose.py`):
- Operation `compose`: Writes project JSON → `npx hyperframes render`
- Operation `doctor`: Runtime check (Node ≥22, FFmpeg, npx, hyperframes npm package)

**Governance:** Silent runtime swap forbidden. `final_review` compares `proposal_packet.production_plan.render_runtime` vs `edit_decisions.render_runtime` — mismatch = `runtime_swap_detected` blocker.

### 3.11 Checkpoint/Resume Support
- **Storage:** `PROJECTS_DIR/<project_id>/checkpoint_<stage>.json` + `history/` archive
- **Schema:** `schemas/checkpoints/checkpoint.schema.json`
  - `version`, `project_id`, `pipeline_type`, `stage`, `status` (completed/failed/awaiting_human/in_progress)
  - `checkpoint_policy`, `human_approval_required`, `human_approved`
  - `artifacts`: `{ artifact_name: data_or_path }`
  - `review`, `cost_snapshot`, `error`, `metadata`
- **Key Functions** (`lib/checkpoint.py`):
  - `init_project()` — creates workspace + `project.json` marker
  - `write_checkpoint()` — validates canonical artifact present, enforces gates, archives superseded to `history/`, atomic write via `.tmp` + `os.replace`
  - `read_checkpoint()`, `get_latest_checkpoint()`, `get_completed_stages()`, `get_next_stage()`
  - `_stage_requires_approval()` — reads `human_approval_default` from manifest (fail-closed on unknown pipeline)
- **Gate Enforcement:**
  - Manifest `human_approval_default: true` → status `awaiting_human` required before `completed`
  - Caller must pass `human_approved=True` to write `completed`
  - `checkpoint_policy: manual_all` forces all stages to gate
- **Resume:**
  - `get_next_stage()` uses pipeline-specific stage order
  - Tools declare `resume_support`: `NONE` (default), `FROM_START`, `FROM_CHECKPOINT`
  - Cost tracker (`tools/cost_tracker.py`) persists `cost_log.json` with estimate/reserve/reconcile

### 3.12 Testing & Contract Validation

**Test Structure:**
```
tests/
├── contracts/
│   ├── test_phase0_contracts.py  # Config, schemas, checkpoints, pipeline manifests, BaseTool, ToolRegistry, CostTracker
│   ├── test_phase1_contracts.py  # Phase 1 tools (transcriber, trimmer, subtitle, frame_sampler, audio_mixer, video_compose)
│   ├── test_phase2_contracts.py  # Phase 2 tools (face_enhance, scene_detect, color_grade, audio_enhance, image_selector, code_snippet, diagram_gen)
│   ├── test_phase3_contracts.py  # TTS/music/video gen tools, animated-explainer manifest, playbooks, skills, Remotion scaffold
│   ├── test_phase2_comparison.py
│   ├── test_backlot_contract.py
│   ├── test_runtime_presentation_contract.py
│   ├── test_phase1_golden.py
│   └── test_taste_governance_contracts.py
├── qa/
│   ├── test_08_end_to_end.py     # Full 8-stage synthetic run with real compose
│   ├── test_04_audio_mix.py
│   ├── test_05_video_compose.py
│   ├── test_06_video_stitch.py
│   ├── test_07_playbook_intelligence.py
│   └── test_09_hyperframes_compose.py
├── eval/
│   ├── bench_runner.py
│   ├── replay_harness/harness.py
│   └── golden_scenarios/
├── backlot/
├── lib/
└── tools/
```

**Contract Test Patterns:**
- Every tool: inherits `BaseTool`, has `name/version/tier/capabilities`, `get_info()`, `execute()`, `dry_run()`
- Status reporting: `get_status()` reflects dependency availability
- Schema validation: `validate_artifact(name, data)` against JSON Schema
- Checkpoint round-trip: write → read → validate
- Pipeline manifest: loads, validates, stage order correct, skills present
- Registry: discovers tools, capability/provider catalogs work

**QA End-to-End:** `test_08_end_to_end.py` runs full `animated-explainer` pipeline with synthetic artifacts, real `audio_mixer` + `video_compose` execution, validates all 8 checkpoints and final video output.

### 3.13 Kaggle Compatibility Risks

**GPU-Dependent Tools (Require `LOCAL_GPU` runtime, significant VRAM):**
| Tool | VRAM Requirement | Runtime |
|------|------------------|---------|
| `wan_video` | 8 GB (14B FP8) | LOCAL_GPU |
| `hunyuan_video` | 14 GB | LOCAL_GPU |
| `ltx_video_local` | 12 GB | LOCAL_GPU |
| `cogvideo_video` | 6 GB | LOCAL_GPU |
| `comfyui_video` | 8-16 GB (bundled WAN 2.2 14B FP8) | LOCAL_GPU |
| `face_restore` (CodeFormer/GFPGAN) | 2 GB | LOCAL_GPU |
| `upscale` (Real-ESRGAN) | 2 GB | LOCAL_GPU |
| `green_screen_composite` (rembg GPU) | GPU optional | LOCAL/LOCAL_GPU |

**Kaggle-Specific Risks:**
1. **VRAM Limits:** Kaggle P100 (16 GB) / T4 (16 GB) / A100 (40/80 GB) — Wan/Hunyuan/LTX may OOM on P100/T4 with other processes
2. **No Persistent Storage:** `/kaggle/working` is ephemeral; checkpoints in `projects/` lost between sessions unless symlinked to `/kaggle/working` or saved as dataset
3. **No Internet in Inference:** Many tools require network (`network_required: true`) — API providers (Veo, Kling, Runway, HeyGen, Minimax, Sora, ElevenLabs, OpenAI, Google TTS/Music/Imagen/Veo, etc.) will fail
4. **Subprocess/Daemon Restrictions:** `agent-browser` (Node), Hindsight embedded daemon, s6-overlay, Docker socket, terminal tool (Docker/Modal) — Kaggle blocks background processes, daemon sockets, Docker
5. **File Locking:** `fcntl`/`msvcrt` locks on memory files, SQLite WAL — may work but NFS/ephemeral FS semantics uncertain
6. **GPU/Accelerator Assumptions:** Skills reference CUDA, vLLM, TensorRT — Kaggle provides T4/P100 but no persistent driver setup
7. **Long-Running Processes:** Gateway, cron, kanban dispatcher, MoA — kernel timeout (typically 1-6h) kills background work
8. **Secret Management:** `.env`, `auth.json`, credential pool — Kaggle Secrets UI injects env vars — compatible if user sets `HERMES_HOME` and exports keys to env

**Recommendation for Kaggle:**
- Use `OPENMONTAGE_PROJECTS_DIR=/kaggle/working/projects` for checkpoint persistence
- Stick to `render_runtime: ffmpeg` pipelines (`talking-head`, `clip-factory`)
- Avoid `animated-explainer` with `remotion` (needs Node + browser render)
- Pre-generate assets locally or use API-based generation if network allowed
- Set `budget.mode: observe` (no CAP enforcement without API keys)

---

## 4. Compatibility Verdict

### Hermes-Agent: **COMPATIBLE WITH CONDITIONS**
✅ **Supported:** Skill system (agentskills.io standard), memory (MEMORY.md/USER.md + pluggable providers), session search (FTS5), Hindsight integration (3 modes), profile/project isolation, tool registry, browser tools (multiple backends), programmatic control (CLI, library, ACP, gateway, cron, dashboard), checkpoint/persistence, Kaggle-compatible with `HERMES_HOME` override and local-only providers.

⚠️ **Conditions:**
- Must set `HERMES_HOME=/kaggle/working/.hermes` for persistence
- Must use local providers only (no cloud browser, no cloud Hindsight, no gateway)
- Must pre-bundle skills or install offline
- No native Kaggle detection — manual env setup required

### OpenMontage: **COMPATIBLE WITH CONDITIONS**
✅ **Supported:** Pipeline-driven architecture, 12 production pipelines, 57+ tools with capability discovery, 15 artifact schemas with strict validation, checkpoint/resume with human gates, three rendering runtimes with governance, local-footage input path (`source_media_review`), FFmpeg-based tools work on CPU, comprehensive contract test suite.

⚠️ **Conditions:**
- Must set `OPENMONTAGE_PROJECTS_DIR=/kaggle/working/projects` for checkpoint persistence
- Must use `render_runtime: ffmpeg` pipelines only (no Remotion/HyperFrames without Node+browser)
- Must avoid GPU-dependent tools (Wan, Hunyuan, LTX, CogVideo, ComfyUI, face_restore, upscale)
- Must avoid network-dependent tools (all cloud APIs) unless Kaggle internet enabled
- `documentary-montage` pipeline is the best fit for football emotion (real-footage, archive-style) but requires custom clip acquisition (YouTube) not in its stock corpus tools

### Evidence Paths (from repos)

**Hermes-Agent:**
- `setup-hermes.sh`, `pyproject.toml`, `cli.py`, `hermes_cli/main.py`, `hermes_cli/config.py`, `hermes_cli/profiles.py`, `hermes_cli/projects_db.py`, `tools/skills_hub.py`, `hermes_cli/skills_hub.py`, `tools/skills_guard.py`, `tools/registry.py`, `hermes_cli/tools_config.py`, `tools/browser_tool.py`, `tools/url_safety.py`, `tools/website_policy.py`, `run_agent.py`, `agent/agent_init.py`, `hermes_state.py`, `tools/session_search_tool.py`, `agent/moa_trace.py`, `agent/trace_upload.py`, `hermes_logging.py`, `hermes_cli/kanban_db.py`, `tools/memory_tool.py`, `agent/memory_manager.py`, `agent/memory_provider.py`, `plugins/memory/hindsight/__init__.py`, `hermes_cli/subcommands/acp.py`, `hermes_cli/gateway.py`, `hermes_cli/web_server.py`, `hermes_cli/cron.py`, `docker/stage2-hook.sh`

**OpenMontage:**
- `Makefile`, `lib/env_loader.py`, `lib/config_model.py`, `lib/paths.py`, `pipeline_defs/*.yaml`, `lib/pipeline_loader.py`, `lib/source_media_review.py`, `schemas/artifacts/*.schema.json`, `schemas/artifacts/__init__.py`, `tools/tool_registry.py`, `tools/base_tool.py`, `tools/analysis/video_analyzer.py`, `tools/analysis/scene_detect.py`, `tools/analysis/frame_sampler.py`, `tools/analysis/audio_energy.py`, `tools/analysis/audio_probe.py`, `tools/video/video_compose.py`, `tools/video/hyperframes_compose.py`, `lib/checkpoint.py`, `schemas/checkpoints/checkpoint.schema.json`, `tools/cost_tracker.py`, `tests/contracts/*.py`, `tests/qa/test_08_end_to_end.py`
