# Hermes–OpenMontage Typed Tool Bridge

**Status:** implemented against pinned Hermes `5ecc07986f46463ca3096679b03a46402eb19cee` and OpenMontage `f633b5f428b9be9a2afecba851dfddd101619756`

## Root cause, not the latest symptom

The failed Kaggle sessions did not reveal a sequence of unrelated schema and
render bugs. They exposed one missing architectural seam: Hermes was told to
operate OpenMontage, but OpenMontage was not registered as a Hermes toolset.
Hermes therefore improvised with terminal commands, ad-hoc Python imports,
repository searches and provider discovery. The production conversation also
ran with the OpenMontage checkout as its working directory, which activated a
coding-agent posture instructing it to inspect and edit a repository. That
directly contradicted the creative-production prompt.

The strongest incident reached two 60-turn slices, roughly 120 model/API calls
and about 1.25 million input tokens without publishing a single native artifact
or checkpoint. Other runs stopped after proposal, emitted incomplete terminal
JSON, produced schema-shaped but invalid artifacts, retried failing asset tools,
or rendered a technically valid blue/empty video. Increasing the model size or
turn budget did not repair the missing tool boundary; it only made failure more
expensive and slower.

The deterministic post-edit bridge is not the root problem. Its Kaggle canary
already produced a real 12.054-second 1280×720 H.264 MP4 with schema-valid
native artifacts/review and independent non-blank/non-frozen validation. The
repair therefore preserves that bridge and changes only how Hermes reaches the
native creative contracts.

## Production boundary

| Component | Authority |
|---|---|
| Hermes | Creative reasoning, workflow choices, reflection, memory and skill activation |
| Football Emotion Skill System | First-class football story, emotion, selection, cutting, pacing, audio and quality doctrine |
| `acd-openmontage` plugin | Narrow typed transport; no creative defaults, stage loop or renderer |
| OpenMontage adapter | Pinned schemas, native stage order/checkpoints and certified native creative tools |
| Deterministic native bridge | One post-edit `video_compose`, Remotion render and native final review transaction |
| ACD worker | Source/rights policy, typed approvals, run lease/state, final validation, persistence and optional Discord |

Production Hermes runs from the isolated project directory with
`coding_context: off`. The selected toolsets are `web`, `memory`,
`session_search`, `skills` and `acd-openmontage`. Terminal, mutable file and
code-execution toolsets are absent, and `--yolo` is off.

## Tool surface

- `openmontage_native(status)` initializes the exact project and returns native
  stages, durable progress, schema locations, stage contracts, source manifest
  and a small relevant tool summary.
- `read_document` gives bounded, allowlisted, read-only access to pinned
  OpenMontage and Football references and current project contracts.
- `publish_artifact` accepts a Hermes-authored canonical JSON payload, validates
  it against the pinned native schema, enforces native stage order, writes it
  atomically and publishes its native checkpoint. Model-authored approval fields
  never authorize a gate.
- `tool_info` and `run_tool` expose only the audited zero-cost creative
  allowlist. Paid tools, source/publish tiers, unsafe Manim execution, URLs that
  bypass acquisition, out-of-project paths, and repeated failed outputs are
  rejected.
- `acd_acquire_source` is the only download/replacement path and retains the
  worker's free-only, rights-aware manifest and validation policy.

`video_compose` is intentionally absent. It remains owned by the already
certified deterministic post-edit bridge.

## Termination and progress rules

The default budget is 20 initial turns and at most one 12-turn same-session
continuation, each inside the eight-minute Hermes process timeout. A continuation
is allowed only after a native checkpoint in `completed` or `awaiting_human`
state embeds the exact canonical artifact also present on disk. Loose JSON,
tool activity, a heartbeat and process exit zero are not progress. A slice with
no coherent checkpoint blocks immediately with bounded evidence.

Hermes returns one exact JSON terminal object. It cannot write the worker result
file. Pinned Hermes quiet-mode stdout can contain rendered reasoning and progress,
so the event adapter captures only the actual supported `run_conversation`
return value; the worker never searches arbitrary logs for a JSON-looking
substring. The worker strictly validates and atomically publishes that object,
or reconstructs a ready handoff only when the complete native edit prerequisites
already validate. Rendering and delivery claims remain worker/OpenMontage
decisions.

## Predicted failure classes and guards

| Failure class | Guard |
|---|---|
| Upstream schema/stage drift | Exact commits, hashed compatibility delta, native schema validation and doctor gate |
| Model skips/reorders stages | Native stage-order enforcement in `publish_artifact` |
| Self-approved checkpoints | Approval derived only from typed run policy |
| Shell/import/CLI improvisation | No terminal/file/code toolsets; isolated cwd; typed plugin only |
| Path escape or source-policy bypass | Canonical resolution, project containment and URL rejection in tool inputs |
| Paid or unavailable tool invocation | Certified allowlist, registry status and zero-cost estimate/result checks |
| Repeated asset regeneration | Output journal, reuse of valid non-empty output and one corrected retry |
| Search dependency missing | Exact `ddgs==9.14.4` installed and verified in the Hermes venv |
| Provider 401/429/503 | Structured retryable blocker; explicit same-session retry/model override |
| Nemotron Ultra emits tool JSON as assistant text | Generated profile supplies NVIDIA's required `enable_thinking` + `force_nonempty_content` tool-parsing flags; setup doctor fails closed on drift |
| Prose or malformed terminal result | Exact-object parser and strict envelope validation |
| Blank/frozen or lineage-mismatched render | Native review plus independent ffprobe, hash and sampled-frame checks |
| Restart/concurrent ownership | Atomic run state, lease, Kaggle hydration/export and resumable native checkpoints |

## Verification and rollout

The plugin was discovered successfully by the exact pinned Hermes plugin
registry, resolving `openmontage_native` and `acd_acquire_source`. The adapter
was run under an isolated interpreter against the exact pinned OpenMontage
checkout; native cinematic initialization, stage order, schema discovery,
stage contracts, source-manifest transport and registry discovery passed.

After bootstrap, run the setup doctor and the existing native contract canary.
Then start a **fresh** production run. Do not resume the pre-fix Hermes sessions:
their history contains the contradictory coding posture and repeated failed
tool strategies, while their run directories have no trustworthy typed creative
handoff to preserve.

The 2026-07-15 first typed-bridge production probe proved every local boundary
but exited after two model steps with zero registered tool calls. NVIDIA's
[Ultra API contract](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-ultra-550b-a55b)
requires `chat_template_kwargs.enable_thinking=true` together with
`chat_template_kwargs.force_nonempty_content=true` when reasoning and tool calls
are combined. The original generated profile omitted the second flag. That is a
verified provider-contract violation and is consistent with the observed
JSON-shaped terminal response plus zero parsed tool calls; the prior trace did
not preserve the response keys needed to claim more than that. Profile
generation and the doctor now enforce the complete contract, and future
malformed-envelope evidence records bounded key names. No prose-to-tool shim or
additional retry loop was introduced.
