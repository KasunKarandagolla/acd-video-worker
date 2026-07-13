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
        ↓
OpenMontage native agent pipeline + render review
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

Install the pinned repositories and the unchanged skill system:

```bash
bash bootstrap/install_hermes.sh
bash bootstrap/install_openmontage.sh
HERMES_HOME="$HOME/.hermes" HERMES_PROFILE=football-emotion bash bootstrap/install_skills.sh
```

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
  --input https://example.com/reference
```

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

This is accepted only when the persisted blocker is
`HERMES_RUNTIME_UNAVAILABLE`; delivery, validation, dry-run, approval and other
blocked/failed states remain terminal. The generated Hermes profile caps the
effective context at 65,536 tokens by default (`ACD_HERMES_CONTEXT_LENGTH`) so
Hermes' native compression runs before large free-endpoint requests are
typically throttled.

If that provider remains unavailable, the same Hermes session can be handed to
another model already configured in the named profile. Set
`ACD_HERMES_MODEL_OVERRIDE` to the exact configured model ID before the explicit
blocked retry. The runner passes Hermes' supported global `-m` selector before
`chat`; `--resume` still restores the existing conversation, memory and native
OpenMontage work. This setting never creates a new session or fallback router.

Hermes gets one bounded same-session continuation when it exits cleanly before
writing the mandatory result contract (for example, after reaching its
tool-iteration ceiling). Configure the initial and recovery budgets with
`ACD_HERMES_MAX_TURNS` (default `60`) and
`ACD_HERMES_RECOVERY_MAX_TURNS` (default `30`). The continuation reuses Hermes
history and existing OpenMontage work; it may finish the native pipeline or
write an honest blocker, but it cannot weaken delivery validation.

The production prompt binds Hermes to the pinned OpenMontage execution surface:
`tools.tool_registry.registry.get(name).execute(inputs)`. It also records the
actual Football Emotion package root for `shared/...` references, forbids
invented source media, bounds one-time research/discovery and reserves turns
for compose/review/result writing. Protocol recovery is not a second full
pipeline run: unless all compose prerequisites already exist, it must write an
honest `NATIVE_PIPELINE_TURN_BUDGET_EXHAUSTED` blocker immediately.

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
```

A run becomes `DELIVERED` only after schema-valid native OpenMontage artifacts and final-review evidence exist separately under the project `artifacts/` directory, the output under `renders/` passes independent `ffprobe`, and sampled frames contain meaningful visual detail. Exit code zero, self-declared result JSON, fixtures, blank/solid-colour MP4s and ad-hoc fallback renders are insufficient.

Hermes runs `scripts/validate_delivery_candidate.py` before ending a delivered
claim. This exposes the same worker-owned artifact/media checks while the
Hermes session can still correct its OpenMontage work. The production
controller always repeats those checks independently and remains authoritative.
