# Thin-Orchestration Module Map

## Final ownership

| Owner | Responsibilities |
|---|---|
| Hermes | Request interpretation, creative reasoning, Football Emotion skill activation, reflection, loopbacks, memory and workflow/tool decisions |
| Football Emotion Skill System | Football-emotion taste, story, footage understanding, timestamps, clip selection, cutting/pacing, audio, graphics, rights-risk, retention and QA doctrine |
| OpenMontage | Native manifests, director skills, artifact schemas, ToolRegistry, `video_compose`, runtime routing, rendering, checkpoints/Backlot and native review |
| ACD worker | Intake, source acquisition/replacement, free-only/rights policy, seven-state run record, final validation, persistence and optional notifications/packaging |

## Classification

| Classification | Module | Evidence and destination |
|---|---|---|
| KEEP | `skills/football-emotion-video/` | Complete creative doctrine preserved as first-class; only its repository-boundary references track the deterministic handoff |
| KEEP | `src/acd_worker/source/` | Existing sequential discovery/acquisition/replacement implementation; called through the worker source boundary |
| KEEP | `bootstrap/install_*.sh` | Pinned upstream and skill installation; made path-portable |
| KEEP | `src/acd_worker/hermes_runner.py` | One supported quiet Hermes profile/session invocation; no stage sequencing or artifact bus |
| KEEP | `src/acd_worker/run_state.py` | Seven macro states and atomic run-level persistence only |
| KEEP | `src/acd_worker/thin_controller.py` | Intake → bounded Hermes creative handoff → deterministic native bridge → independent validation; contains no creative stages |
| KEEP | `src/acd_worker/source_service.py` and `scripts/acquire_sources.py` | Worker-owned source manifest and sequential replacement boundary callable by Hermes |
| KEEP | `src/acd_worker/media_validation.py` | Independent final `ffprobe` delivery gate |
| KEEP | `src/acd_worker/job_prompt.py` | Single versioned ownership/job/result contract for Hermes |
| KEEP | `bootstrap/bootstrap_kaggle.sh` and `bootstrap/run_kaggle_job.sh` | Thin setup and hydrate → run → export environment wrapper |
| KEEP | `src/acd_worker/notifications.py` | Optional started/blocked/failed/delivered notifications; never affects outcome |
| REMOVED | `src/acd_worker/orchestrator.py` | Worker-owned 19-stage creative workflow |
| REMOVED | `src/acd_worker/openmontage_runner.py` | Manually reconstructed native OpenMontage stages |
| REMOVED | `src/acd_worker/footage_requirements.py` | Worker-created creative planning artifact; Hermes/skills own it |
| REMOVED | `src/acd_worker/quality_loop.py` | Duplicate creative loopback rules; Hermes/OpenMontage own them |
| REMOVED | fixture E2E scripts and old generated reports | Evidence for the retired worker workflow |

## Verified pinned-upstream boundary

- Hermes `hermes_cli/_parser.py` defines quiet non-interactive `chat -q ... -Q`, `--resume`, `--skills`, `--max-turns`, and `--source`.
- Hermes `cli.py` prints only the final response to stdout in quiet mode and a parseable `session_id:` line to stderr.
- Hermes profile selection resolves `-p football-emotion` to the named profile; the worker supplies the Hermes root through `HERMES_HOME` to avoid nested profile paths.
- Hermes recursively discovers `SKILL.md` files below the active profile’s `skills/` directory and supports explicit preloading.
- OpenMontage `AGENT_GUIDE.md` defines an agent-driven native pipeline; `PROJECT_CONTEXT.md` identifies `tools/video/video_compose.py` as the runtime-aware composition boundary.
- OpenMontage has no single native pipeline-runner CLI that should be wrapped. Hermes operates inside the pinned checkout and authors canonical artifacts through edit; the isolated deterministic bridge then calls the real ToolRegistry `video_compose` and native review exactly once.
- The pinned cinematic Remotion handoff has an audited, hash-verified compatibility patch. Bootstrap and runtime reject any commit, overlay, patch hash or tracked modified-path set outside that exact certificate.
