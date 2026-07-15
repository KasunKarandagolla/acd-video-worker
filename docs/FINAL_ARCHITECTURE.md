# Final Architecture — AI Creative Director

**Status:** locked current source of truth

**Date:** 2026-07-12
**Upstreams:** Hermes-Agent `5ecc07986f46463ca3096679b03a46402eb19cee`; OpenMontage `f633b5f428b9be9a2afecba851dfddd101619756`

## Product

A free-only, agentic creative director for professional football-emotion videos. Inputs may be ideas, local media, social/video URLs, images, audio, reference edits or mixtures. Videos without speech must be understood through frames/vision and audio/music/emotion evidence rather than transcript dependence.

The low-resource laptop is for assembly and light checks. Kaggle or another capable environment is the production runtime. No paid API/subscription or local LLM/VLM is required.

Free cloud vision/frame analysis is allowed by default with a clear one-time disclosure recorded in durable project state.

## Ownership

### Hermes-Agent

- interprets the request;
- owns creative planning and reasoning;
- activates the Football Emotion skills;
- chooses supported tools and OpenMontage capabilities;
- owns creative reflection and loopbacks;
- owns memory and reusable project learning;
- coordinates the high-level workflow.

### Football Emotion Skill System

- provides football-emotion taste and story doctrine;
- governs visual/audio understanding, timestamps and clip selection;
- governs professional cutting, pacing, narration, music, SFX and ducking;
- governs graphics, transitions, color, retention and quality review;
- governs fact provenance, rights-risk behavior and memory-learning guidance.

It remains complete and first-class. It is installed under the named Hermes profile and is not rewritten into Python stages.

### OpenMontage

- owns its native agent pipeline and manifests;
- owns stage director skills and approval gates;
- owns canonical artifacts and schemas;
- owns ToolRegistry and native tools such as `video_compose`;
- owns render-runtime selection/routing, composition and rendering;
- owns checkpoints/Backlot artifacts and native render review.

Hermes runs in the pinned OpenMontage checkout and follows `AGENT_GUIDE.md`, `PROJECT_CONTEXT.md`, the selected manifest and stage skills. The worker does not reproduce OpenMontage stages.

### ACD worker

- starts/resumes a run;
- configures paths and environment;
- creates the user-input/source manifest;
- provides sequential source acquisition/replacement;
- enforces free-only and access/rights policy boundaries;
- stores only small run-level state;
- independently validates native artifact identity/schema/review evidence, final output with ffprobe, and sampled-frame visual content;
- hydrates/exports Kaggle state;
- sends optional non-fatal notifications;
- packages delivered output.

The worker is not a creative framework.

## Runtime

```text
User request and mixed inputs
  → thin ACD controller
  → source manifest / acquisition boundary
  → one Hermes production job with Football Emotion skills
  → Hermes authors native artifacts through edit
  → deterministic typed handoff
  → OpenMontage native compose + native review
  → independent worker native-artifact, media and visual-content validation
  → persistence + optional notification
```

Worker macro states only:

```text
INTAKE → SOURCE_READY → AGENT_RUNNING → NATIVE_EXECUTING → VALIDATING → DELIVERED
                    ↘ BLOCKED / FAILED ↙          ↘ BLOCKED / FAILED ↙
```

`NATIVE_EXECUTING` is only a durable exactly-once transaction boundary; it is
not a worker-owned creative workflow stage.

`BLOCKED` is correct for an unavailable free model endpoint, missing native render runtime, protected/unavailable sources, an unresolved native approval gate or Kaggle restriction. `FAILED` is reserved for protocol/code/unexpected execution faults. No fixture, dry run, plan JSON, self-referential artifact claim, blank render, ad-hoc fallback MP4, compose-only artifact or exit code can produce `DELIVERED`.

## Native integration facts

- Supported Hermes invocation: `hermes -p football-emotion chat -q <prompt> -Q --source tool --max-turns <n>`.
- Resume uses `--resume <session-id>`.
- Relevant skills are explicitly preloaded with repeatable `--skills`; the full nested package remains discoverable below the active profile `skills/` directory.
- Quiet Hermes stdout is the final response; stderr provides a parseable `session_id:` line.
- OpenMontage is deliberately agent-driven for creative authoring. It has no
  supported single all-stage pipeline CLI to wrap. Hermes follows its native
  contracts through edit; the deterministic bridge then calls the actual
  registry `video_compose` tool for compose/review.
- A result JSON file inside the OpenMontage project workspace is the worker/Hermes terminal contract. Native OpenMontage artifacts remain native.

## Permanent constraints

- No upstream forks or ad-hoc edits. The exact OpenMontage pin is augmented only
  by a tracked, hashed, fail-closed compatibility patch/overlay.
- No paid APIs/subscriptions.
- No local LLM/VLM requirement.
- FFmpeg/ffprobe remain permanent technical infrastructure.
- No DRM, authentication, cookie, CAPTCHA, proxy or access-control bypass.
- No silent render-runtime substitution.
- No fake success or fixture-based production certification.
- Credentials are environment/profile secrets and are never committed.
