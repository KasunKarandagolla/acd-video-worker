# Implementation Contract — Thin ACD Control Plane

**Status:** locked, root-cause recovery revision

**Authority:** `docs/FINAL_ARCHITECTURE.md`

## Required production path

The only production entrypoint is `scripts/acd_worker.py`. It must call `ThinRunController`; it must never import or invoke the retired worker creative orchestrator, manual OpenMontage stage runner, worker creative artifact generators or duplicate quality-loop router.

The controller may perform only:

1. intake and run-state persistence;
2. source manifest preparation;
3. environment/profile/skill preflight;
4. one supported Hermes job invocation or supported session resume, plus a
   small configured number of bounded same-session checkpoint continuations
   only when Hermes exits zero after publishing a coherent native
   checkpoint/artifact pair;
5. strict creative-handoff parsing and deterministic reconciliation of an
   already-complete native edit checkpoint;
6. compatibility, approval, schema and cross-artifact validation followed by
   one isolated OpenMontage native compose/review transaction;
7. independent final artifact/media/visual validation;
8. generation-atomic terminal persistence and best-effort notification.

## State contract

Allowed states are exactly `INTAKE`, `SOURCE_READY`, `AGENT_RUNNING`,
`NATIVE_EXECUTING`, `VALIDATING`, `DELIVERED`, `BLOCKED`, and `FAILED`.
`NATIVE_EXECUTING` records only the deterministic transaction boundary. State
writes are atomic. State stores no creative stage machine, chain-of-thought or
duplicated OpenMontage artifacts.

Every blocker/error has a stable code, actionable message, phase and optional evidence. Expected missing external prerequisites map to `BLOCKED`; malformed results and unexpected execution faults map to `FAILED`.

Terminal states are immutable during ordinary resume. An explicit
`--retry-blocked` may reopen only the controller's fixed retryable blocker
allowlist (provider/runtime availability, typed approval, and bounded native
progress blockers). An interrupted render with no durable native review is not
retryable because a second compose would violate exactly-once execution. It must reuse the same project and, when one exists, the
supported Hermes `--resume` session. Failed and delivered states never reopen.
If the persisted profile/model/plugin/Football-skill identity changes, reuse of
that conversation is forbidden. Explicit `--restart-hermes-session` authority
may start a clean Hermes conversation while preserving valid native project
checkpoints.

## Hermes contract

- Use the pinned supported `-p ... chat -q ... -Q` interface.
- The runner uses Hermes' supported global `-m` selector before `chat` for the
  configured model. A model/profile/plugin/skill identity change requires an
  explicit clean Hermes session; it cannot be injected into an old session.
- Use `--resume`, not invented session flags.
- Pass the Hermes root as `HERMES_HOME`; let `-p` resolve the named profile.
- Preload the six core bridge/story/cutting/audio/quality entry skills and
  instruct progressive use of every relevant Football Emotion skill. The full
  system remains installed and first-class.
- Run from the isolated per-run project directory with `coding_context: off`.
  Never run the production conversation from either source checkout.
- Enable the installed `acd-openmontage` plugin/toolset. Do not expose terminal,
  mutable file or code-execution toolsets and do not enable headless `--yolo`.
- For `nvidia/nemotron-3-ultra-550b-a55b`, the generated provider request must
  include both `chat_template_kwargs.enable_thinking=true` and NVIDIA's required
  `chat_template_kwargs.force_nonempty_content=true`. Bootstrap must fail closed
  if this reasoning-plus-tool parsing contract is absent.
- Capture stdout/stderr for diagnostics, redact secrets and enforce timeout.
  Isolate the adapter in its own process group and terminate all descendants on
  timeout or heartbeat failure.
  Capture the supported `run_conversation` return value separately because
  quiet CLI stdout can still contain reasoning/progress rendering; never scan
  general stdout for a convenient JSON substring.
- Hermes returns exactly one strict JSON terminal object. The worker validates
  and atomically publishes it; Hermes has no direct file-write authority. No
  missing field is normalized and no prose is parsed as a result.
- A bounded same-session continuation is allowed only after a checkpoint with
  `completed`/`awaiting_human` status embeds the same canonical artifact JSON
  that exists on disk. Loose files, event activity and exit zero are not
  progress. A slice with no new coherent checkpoint blocks immediately.

## Deterministic native bridge contract

- Keep the exact pinned OpenMontage commit. Apply only the tracked, hashed
  compatibility patch/overlay; bootstrap and execution must reject any other
  tracked delta or hash mismatch.
- Hermes reads bounded allowlisted regions of the actual guide, context,
  selected manifest/director skills and Football references through
  `openmontage_native(operation=read_document)`.
- The plugin's isolated adapter imports the pinned OpenMontage checkout,
  initializes the native project and discovers the real ToolRegistry. Hermes
  never imports OpenMontage or guesses a CLI/module function.
- Hermes authors canonical creative payloads; `publish_artifact` validates each
  against the pinned schema, enforces native stage order, writes it atomically
  and calls the native checkpoint writer. Approval is derived only from typed
  run policy.
- `run_tool` may invoke only the audited zero-cost creative allowlist and calls
  `registry.get(name).execute(inputs)` under the pinned OpenMontage interpreter.
  Source/publish tiers, `video_compose`, paid calls, unsafe code and paths
  outside the run project are rejected.
- Hermes authors through the native edit checkpoint, then returns
  `ready_for_execution`. The worker owns publication of the terminal envelope.
- The worker overwrites any model-supplied approval fields with run-state policy,
  validates native checkpoint gates through pinned OpenMontage, and invokes the
  isolated native adapter exactly once per input fingerprint.
- OpenMontage owns runtime choice/routing, `video_compose`, rendering and native review.
- If the pinned capability is unavailable, return an exact blocker; do not invent a CLI or implement the stages in the worker.
- Respect native approval gates. `human_approved` is accepted only when the
  same stage appears in the typed user policy. Missing approval is a structured
  retryable blocker; a suppressed manifest gate is a failure.
- Legacy Hermes `delivered` envelopes are parsed only to return
  `LEGACY_DELIVERY_UNSUPPORTED`; they cannot enter validation or delivery.
- Native publication is a crash-safe `prepared → rendering →
  rendered_reviewed → published` journal. Recovery after `rendered_reviewed`
  must reuse the reviewed bytes and must not call `video_compose` twice.
- The native input fingerprint binds the complete typed request, approvals,
  source manifest, canonical artifacts, referenced media, Football skills,
  pinned commits, compatibility marker, and installed adapter/overlay bytes.

## Source contract

- Local paths and URLs may enter the source manifest.
- Discovery/ranking is a creative Hermes/skill decision.
- Download/replacement uses the worker-owned `scripts/acquire_sources.py` boundary.
- Candidates are tried sequentially and validated before acceptance.
- Every attempt and exact failure is recorded.
- Never bypass DRM, login, age/geo gates, cookies, CAPTCHA, protected playback or access controls.
- Rights status remains unverified until evidenced; transformative intent is not declared legally safe.
- Availability, technical validation, provenance, license and rights evidence
  are separate fields. A successful download or ffprobe result is never rights
  verification.

## Delivery contract

`DELIVERED` requires all of the following:

- Hermes produced or the controller deterministically reconciled a typed
  `ready_for_execution` handoff from already-authored native artifacts;
- at least one candidate path is inside the run’s OpenMontage project workspace;
- the file exists and is non-empty;
- real ffprobe succeeds;
- exactly one schema-valid planning artifact (`proposal_packet` or `brief`),
  plus `scene_plan`, `asset_manifest`, `edit_decisions`, `render_report`, and
  `final_review` exist separately under native `artifacts/`;
- `render_report`, `final_review`, renderer family and runtime agree on the delivered file;
- eleven uniformly sampled frames contain meaningful detail and distributed
  temporal change across the beginning, middle and ending; one changing frame,
  an animated intro followed by a freeze, or a frozen ending cannot pass;
- a video stream and positive duration exist;
- validation evidence is persisted.

Dry runs, fixture bytes, mocked outputs, plan JSON, self-referential or schema-invalid artifact claims, blank renders, registry discovery and process exit zero cannot satisfy delivery.

## Persistence and notification

Kaggle hydration/export copies only project state, outputs and the named Hermes
profile’s durable non-secret data. It requires either an explicit fresh start
or a hash-verified committed generation, refuses active run leases, uses SQLite
backup, scans for secrets, publishes an immutable generation, then atomically
advances `current.json`. `.env`, tokens and credentials are excluded. Discord
is optional, receives only macro outcomes, and can never change a run result.

## Required validation

- Python compilation.
- Focused thin-controller tests.
- Real technical media canary when ffmpeg/ffprobe exist.
- Fake media rejection.
- Production-import AST boundary test.
- Hermes argv/profile/resume/skill contract test.
- Skill-system validator with zero errors/warnings.
- Exact upstream pins and exactly the audited hashed OpenMontage compatibility delta.
- Secret scan.
- Honest live blockers when endpoint/runtime/network requirements are unavailable.
