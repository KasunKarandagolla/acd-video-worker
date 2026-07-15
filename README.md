# AI Creative Director Video Worker

This repository is the thin, free-only control plane around two pinned upstream systems:

- **Hermes-Agent** owns creative reasoning, Football Emotion skill use, reflection, memory and workflow decisions.
- **OpenMontage** owns its native production pipeline, artifacts, tools, runtime routing, rendering and native review.
- **The worker** owns only intake, source acquisition/replacement, policy, small run state, final independent validation, persistence and optional notification/packaging infrastructure.

The complete Football Emotion Skill System remains first-class under `skills/football-emotion-video/`. It teaches Hermes the project’s football-emotion storytelling, footage understanding, clip selection, cutting, pacing, audio, graphics, rights-risk and quality doctrine.

## Production flow

```text
request / mixed inputs
        ↓
thin ACD controller (7 macro states)
        ↓
Hermes + Football Emotion skills
        ↓ typed acd-openmontage toolset (no shell/file/code tools)
OpenMontage schema/checkpoint/tool adapter (creative work through edit)
        ↓
typed ready_for_execution handoff
        ↓
deterministic bridge → OpenMontage video_compose + native review
        ↓
worker native-artifact + ffprobe + visual-content validation
        ↓
DELIVERED / BLOCKED / FAILED
```

The macro states are `INTAKE`, `SOURCE_READY`, `AGENT_RUNNING`, `VALIDATING`, `DELIVERED`, `BLOCKED`, and `FAILED`. The old 19-stage Python orchestrator is legacy code and is not imported by the production entrypoint.

## Setup

Pinned commits are recorded in `docs/upstream-lock.json`:

- Hermes-Agent: `5ecc07986f46463ca3096679b03a46402eb19cee`
- OpenMontage: `f633b5f428b9be9a2afecba851dfddd101619756`

Install the pinned repositories and the complete skill system:

```bash
bash bootstrap/install_hermes.sh
bash bootstrap/install_openmontage.sh
HERMES_HOME="$HOME/.hermes" HERMES_PROFILE=football-emotion bash bootstrap/install_skills.sh
```

The OpenMontage installer keeps the exact upstream commit and applies the
tracked, hashed `cinematic-cut-props-v1` compatibility patch. Bootstrap and
runtime fail closed if any other tracked delta exists, the patch no longer
reverses cleanly, or an overlay hash differs.

Configure a free Hermes model endpoint in the named profile. Do not commit credentials.

For a Kaggle session, expose the existing `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY` secrets as environment variables, then run:

```bash
bash bootstrap/bootstrap_kaggle.sh
bash bootstrap/run_kaggle_job.sh "<video request>" --input <optional-path-or-url>
```

Set `ACD_PERSIST_SOURCE` to a mounted prior `acd-persist-export` directory to hydrate earlier non-secret state. The launcher always exports updated state to `ACD_PERSIST_EXPORT` (default `/kaggle/working/acd-persist-export`) for the notebook version/output to preserve.

## Run

```bash
PYTHONPATH=src python3 scripts/acd_worker.py \
  "Create a professional football-emotion video about an underdog comeback" \
  --input /absolute/path/to/local-clip.mp4 \
  --input https://example.com/reference \
  --approve-all-checkpoints \
  --approve-runtime-tuple cinematic,templated,cinematic-trailer,remotion
```

Use `--approve-silence` only for an intentional no-audio delivery. It is valid
only when Hermes also writes `edit_decisions.metadata.acd_silence_plan` with
`intentional: true` and a non-empty rationale. Request prose and model-authored
approval-looking JSON are never authorization.

Resume a non-terminal run:

```bash
PYTHONPATH=src python3 scripts/acd_worker.py --run-id <run-id>
```

An ordinary resume never reopens a terminal state. A transient free-provider
blocker can be retried explicitly without discarding the project or Hermes
session:

```bash
PYTHONPATH=src python3 scripts/acd_worker.py \
  --run-id <run-id> --retry-blocked --json
```

This is accepted only for the explicit retryable blocker allowlist, including
provider throttling/capacity, runtime unavailability and typed approval
blockers. Delivery, authentication/configuration errors, protocol failures,
validation failures, dry-run and other failed states remain terminal.
The generated Hermes profile caps the
effective context at 65,536 tokens by default (`ACD_HERMES_CONTEXT_LENGTH`) so
Hermes' native compression runs before large free-endpoint requests are
typically throttled.

If that provider remains unavailable, the same Hermes session can be handed to
another model already configured in the named profile. Set
`ACD_HERMES_MODEL_OVERRIDE` to the exact configured model ID before the explicit
blocked retry. The runner passes Hermes' supported global `-m` selector before
`chat`; `--resume` still restores the existing conversation, memory and native
OpenMontage work. This setting never creates a new session or fallback router.

OpenMontage pipelines can span more than one Hermes CLI tool-turn slice. When
Hermes exits cleanly without a terminal result, the controller may run one
bounded same-session checkpoint continuation by default (32 initial turns plus
24 continuation turns, each inside the same 20-minute process timeout). Configure
the slice budgets with `ACD_HERMES_MAX_TURNS`,
`ACD_HERMES_RECOVERY_MAX_TURNS`, and `ACD_HERMES_MAX_CONTINUATIONS`. Every slice
uses the same Hermes session and resumes the next incomplete native OpenMontage
checkpoint without repeating research or capability discovery. This is session
budgeting, not a worker creative stage machine, and it cannot weaken delivery
validation. Only a coherent canonical artifact plus its matching native
checkpoint counts as progress; loose files, chat/tool activity and exit zero do
not earn another slice.

A resumed `AGENT_RUNNING` run counts its first checkpoint continuation as slice
one; it does not receive an additional uncounted recovery call. Continuations
also lock already-probed non-empty media against regeneration, permit only one
corrected retry per missing asset, require immediate native asset checkpointing,
and direct Hermes to publish the typed handoff as soon as the canonical edit
prerequisites validate.

The production profile installs the `acd-openmontage` Hermes plugin. Its narrow
tools expose bounded read-only contract access, schema-validated artifact and
checkpoint publication, certified zero-cost creative tools, and the existing
worker-owned source acquisition boundary. Hermes runs from the isolated project
workspace with `coding_context: off`; production does not expose terminal,
mutable file or code-execution toolsets and does not enable `--yolo`.

When Nemotron 3 Ultra is selected, profile generation also applies NVIDIA's
required reasoning-plus-tool-call parser flags (`enable_thinking` and
`force_nonempty_content`). The setup doctor rejects an Ultra profile missing
either flag; model-emitted JSON is never reinterpreted as an executable tool
call by the worker.

For each new runtime fingerprint, the first real production provider request
is a status-only named `openmontage_native` call on this same Hermes session.
The controller requires matching normalized-response structure and a successful
real handler callback before it accepts creative work. It persists that
non-secret certificate in the run state, so bounded continuations and restored
Kaggle sessions do not repeat the handshake. No separate probe session or
second adapter is part of production.

The adapter is the only process that imports the pinned OpenMontage contracts
and calls `registry.get(name).execute(inputs)`. Hermes stops after schema-valid
planning, scene, asset and edit checkpoints and returns `ready_for_execution` as
one exact JSON object. The event adapter captures the supported Hermes
`run_conversation` return separately from diagnostic CLI output. The worker
validates and atomically publishes that terminal envelope (or reconstructs it
from complete native checkpoints), then
validates the runtime tuple, approvals, schemas and cross-artifact references
before invoking OpenMontage `video_compose` exactly once. Hermes cannot render,
review or claim delivery on the production path.

Prepare intake and the Hermes job prompt without executing production:

```bash
PYTHONPATH=src python3 scripts/acd_worker.py --dry-run "test request"
```

Dry-run always ends `BLOCKED`; it can never certify a render.

## Source acquisition boundary

Hermes may discover and rank sources, but downloads/replacements go through:

```bash
PYTHONPATH=src python3 scripts/acquire_sources.py \
  --manifest <project>/football_emotion/source_manifest.json \
  --output-dir <project>/source_media \
  --slot opening_pressure \
  --url <candidate-1> \
  --url <candidate-2>
```

The adapter tries candidates sequentially, validates acquired media and records exact failures. It never bypasses DRM or access controls.

## Validation

```bash
python3 -m compileall -q src scripts tests
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 bootstrap/validate_setup.py
```

The setup doctor emits `thin-validation.json`, `thin-validation.md`, and
`runtime-validation-certificate.json`. It returns non-zero for any required
failed or blocked gate; missing optional Discord configuration is reported but
does not block certification.

Run the exact native contract canary after bootstrap:

```bash
PYTHONPATH=src python3 scripts/run_native_contract_canary.py \
  --project-dir /tmp/acd-native-contract-canary \
  --openmontage-root "$OPENMONTAGE_ROOT"
```

This authors original local canary assets, validates native checkpoints and
typed approvals, invokes the same bridge/ToolRegistry/`video_compose`/Remotion
path as production, runs native final review, then repeats independent artifact,
ffprobe and visual-change validation. It is a runtime contract certificate,
not a substitute for Football Emotion creative review.

A run becomes `DELIVERED` only after the deterministic bridge receives a typed
creative handoff, OpenMontage publishes schema-valid native artifacts and a
passing final review, the output under `renders/` passes independent `ffprobe`,
hash lineage and sampled-frame visual-content checks. A legacy model-authored
`delivered` envelope, exit code zero, fixtures, blank/solid-colour MP4s and
ad-hoc fallback renders are insufficient.

The bridge publishes a runtime certificate only after native and independent
checks agree. The production controller remains authoritative even when Hermes
prints confident prose or exits successfully.
