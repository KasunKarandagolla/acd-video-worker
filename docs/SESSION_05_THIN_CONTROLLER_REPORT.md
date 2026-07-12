# Session 5 — Thin Controller Implementation Report

## Baseline

- Branch inspected: `opencode-session-4.6-repair-v2`
- Starting commit: `831aa12d97231981d488af6f23ab207ffde6fe5a`
- Interrupted Session 4.6.2 was not present on any pushed branch and was intentionally excluded by user direction.
- Implementation branch: `codex/thin-orchestration`

## Result

The default production entrypoint no longer imports the worker-owned 19-stage orchestrator or manual OpenMontage stage runner. It now uses seven macro states and makes one supported Hermes job invocation. Hermes receives the complete Football Emotion system as authoritative doctrine and works inside pinned OpenMontage through its native agent contract.

## Real upstream evidence

- Hermes pinned commit `5ecc079...`: supported `hermes -p football-emotion chat -q <prompt> -Q`, `--resume`, `--skills`, `--source`, and `--max-turns` behavior verified in `hermes_cli/_parser.py`, `hermes_cli/main.py`, and `cli.py`.
- Quiet stdout contains the final response; `session_id:` is emitted to stderr for automation.
- OpenMontage pinned commit `f633b5f...`: `AGENT_GUIDE.md`, `PROJECT_CONTEXT.md`, pipeline manifests, director skills, ToolRegistry, and runtime-aware `video_compose` are the native agent boundary. No supported all-stages pipeline CLI exists to wrap.

## Implemented

- Seven-state atomic run record and resume path.
- Single high-quality Hermes job prompt and strict JSON result file.
- Explicit Football Emotion entry-skill preloading plus progressive full-system use.
- Supported Hermes profile and session-resume invocation.
- Worker-owned mixed-input source manifest and sequential acquisition/replacement command.
- Structured `DELIVERED`, `BLOCKED`, and `FAILED` outcomes.
- Independent path-contained `ffprobe` final-media validation.
- Production CLI replacement.
- Portable upstream/skill install roots and correct named-profile skill installation.
- Focused tests, including a real generated technical canary and rejection of fake MP4 bytes.

## Legacy production removal proof

`scripts/acd_worker.py` imports `ThinRunController` and `RunStatus` only from the ACD package. It does not import `acd_worker.orchestrator`, `OpenMontageRunner`, footage-planning modules, or worker quality-loop modules. An AST regression test enforces this.

## Validation

Run before commit:

```bash
python3 -m compileall -q src scripts tests
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Live Hermes and a real OpenMontage content render require a configured free endpoint and installed native runtime. Missing runtime requirements must be reported as `BLOCKED`; they are not replaced by fixtures.

Final local results:

- Focused suite: **15 passed, 0 failed**.
- Football Emotion validator: **230 checks passed, 0 warnings, 0 errors**.
- Thin environment doctor: **8 passed, 0 failed, 8 blocked** in the ChatGPT build container.
- Real technical MP4 canary: passed ffmpeg creation and independent ffprobe delivery validation.
- Live gates honestly blocked here: Hermes CLI/profile/free endpoint, installed OpenMontage registry/Remotion runtime, yt-dlp and optional Discord. Kaggle bootstrap installs the code dependencies; endpoint and Discord values remain user-supplied secrets.

## Final hardening completed

- Kaggle bootstrap and the `hydrate → one production command → export` launcher are implemented.
- Persistence excludes `.env`, credential/token files and symlinks.
- Optional Discord sends only started/blocked/failed/delivered states and is non-fatal.
- The old orchestrator, manual OpenMontage runner, duplicate quality loop, worker creative planner and fixture E2E path are removed.
- The environment doctor verifies pins, production imports, tests, skills, endpoint readiness, native OpenMontage capability, ffmpeg, source acquisition and optional Discord.
- A real local technical MP4 canary passes worker validation; fake MP4 bytes fail.
- Live Hermes and native OpenMontage content certification remain honest environment gates when no endpoint/runtime is configured. They require runtime execution, not another coding session.
