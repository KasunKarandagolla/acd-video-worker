# Implementation Contract — Thin ACD Control Plane

**Status:** locked

**Authority:** `docs/FINAL_ARCHITECTURE.md`

## Required production path

The only production entrypoint is `scripts/acd_worker.py`. It must call `ThinRunController`; it must never import or invoke the retired worker creative orchestrator, manual OpenMontage stage runner, worker creative artifact generators or duplicate quality-loop router.

The controller may perform only:

1. intake and run-state persistence;
2. source manifest preparation;
3. environment/profile/skill preflight;
4. one supported Hermes job invocation or supported session resume;
5. strict final result parsing;
6. independent final media validation;
7. terminal persistence and best-effort notification.

## State contract

Allowed states are exactly `INTAKE`, `SOURCE_READY`, `AGENT_RUNNING`, `VALIDATING`, `DELIVERED`, `BLOCKED`, and `FAILED`. State writes are atomic. State stores no creative stage machine, chain-of-thought or duplicated OpenMontage artifacts.

Every blocker/error has a stable code, actionable message, phase and optional evidence. Expected missing external prerequisites map to `BLOCKED`; malformed results and unexpected execution faults map to `FAILED`.

## Hermes contract

- Use the pinned supported `-p ... chat -q ... -Q` interface.
- Use `--resume`, not invented session flags.
- Pass the Hermes root as `HERMES_HOME`; let `-p` resolve the named profile.
- Preload the bridge/router/story entry skills and instruct progressive use of every relevant Football Emotion skill.
- Run from the pinned OpenMontage root so native agent guidance is in scope.
- Capture stdout/stderr, redact secrets, enforce timeout and trust neither exit code nor prose as delivery evidence.
- A strict JSON result file inside the project workspace is mandatory.

## OpenMontage contract

- Never modify the pinned checkout.
- Hermes must read the actual guide, context, selected manifest and director skills.
- Capability discovery goes through the real ToolRegistry.
- OpenMontage owns canonical artifacts, runtime choice/routing, rendering and native review.
- If the pinned capability is unavailable, return an exact blocker; do not invent a CLI or implement the stages in the worker.
- Respect native approval gates. A missing required approval maps to `APPROVAL_REQUIRED`.

## Source contract

- Local paths and URLs may enter the source manifest.
- Discovery/ranking is a creative Hermes/skill decision.
- Download/replacement uses the worker-owned `scripts/acquire_sources.py` boundary.
- Candidates are tried sequentially and validated before acceptance.
- Every attempt and exact failure is recorded.
- Never bypass DRM, login, age/geo gates, cookies, CAPTCHA, protected playback or access controls.
- Rights status remains unverified until evidenced; transformative intent is not declared legally safe.

## Delivery contract

`DELIVERED` requires all of the following:

- Hermes result status is `delivered`;
- at least one candidate path is inside the run’s OpenMontage project workspace;
- the file exists and is non-empty;
- real ffprobe succeeds;
- schema-valid `brief`, `scene_plan`, `asset_manifest`, `edit_decisions`, `render_report`, and `final_review` exist separately under native `artifacts/`;
- `render_report`, `final_review`, renderer family and runtime agree on the delivered file;
- sampled frames contain meaningful visual detail rather than a blank/solid-colour technical canary;
- a video stream and positive duration exist;
- validation evidence is persisted.

Dry runs, fixture bytes, mocked outputs, plan JSON, self-referential or schema-invalid artifact claims, blank renders, registry discovery and process exit zero cannot satisfy delivery.

## Persistence and notification

Kaggle hydration/export copies only project state, outputs and the named Hermes profile’s durable non-secret data. `.env`, tokens and other credentials are excluded. Discord is optional, receives only macro outcomes, and can never change a run result.

## Required validation

- Python compilation.
- Focused thin-controller tests.
- Real technical media canary when ffmpeg/ffprobe exist.
- Fake media rejection.
- Production-import AST boundary test.
- Hermes argv/profile/resume/skill contract test.
- Skill-system validator with zero errors/warnings.
- Exact upstream pins and no tracked upstream modifications.
- Secret scan.
- Honest live blockers when endpoint/runtime/network requirements are unavailable.
