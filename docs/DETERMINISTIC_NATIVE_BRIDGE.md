# Deterministic Native Bridge

**Status:** implemented; recovery revision failure-injection certified. Rerun
the full native canary after Kaggle bootstrap to certify the installed runtime.

## Why it exists

The earlier worker duplicated orchestration around Hermes and OpenMontage,
while later thin attempts asked Hermes to complete an entire native production
inside one conversational turn budget. That produced repeated discovery,
partial checkpoints, missing result envelopes, model-invented artifact shapes
and, in one case, a technically valid but visually empty delivery.

The bridge removes the unstable boundary. Hermes remains the creative control
plane and the full Football Emotion Skill System remains its methodology.
Hermes authors the selected OpenMontage pipeline through the edit checkpoint.
Rendering and review are a deterministic native transaction after that point.

## Ownership boundary

| Owner | Responsibilities |
|---|---|
| Hermes | Request interpretation, skill activation, creative reasoning, pipeline selection, creative artifacts, reflection and memory |
| Football Emotion Skill System | Football story, emotion, footage, clip selection, cutting, pacing, audio, graphics and quality doctrine |
| OpenMontage | Native manifests/directors, schemas, checkpoints, ToolRegistry, runtime routing, `video_compose`, Remotion and native final review |
| ACD worker | Intake/source policy, typed approvals, run lease/state, compatibility gate, deterministic native invocation, independent validation, persistence and optional notification |

The worker never authors a scene, cut, title, pacing decision or audio choice.
Checkpoint reconciliation recognizes existing canonical files; it does not fill
or transform their creative contents.

Hermes is given a typed `acd-openmontage` plugin instead of being asked to
discover or import OpenMontage through a general shell. The plugin launches a
small adapter under the pinned OpenMontage interpreter for bounded contract
reads, schema/checkpoint publication and a certified zero-cost creative-tool
allowlist. It cannot invoke `video_compose`; the deterministic bridge below is
the sole render/review owner.

Hermes progress events are observed in an isolated CLI adapter that wraps the
pinned `AIAgent.__init__` callback injection point without replacing the class.
This preserves Hermes' class constants/static helpers and supported profile,
model, session and tool behavior.

The adapter sets the real Hermes argv and imports `hermes_cli.main` before
`run_agent`. This ordering is required by pinned Hermes: the supported
`-p/--profile` bootstrap changes `HERMES_HOME` at import time before agent and
CLI modules cache profile-scoped configuration. Reversing that order makes an
isolated plugin discovery probe pass while the live AIAgent uses the root
profile and omits `openmontage_native` and `acd_acquire_source`.

An uncertified production run has one deterministic protocol entry on the same
Hermes request path used by the creative session. The existing event adapter
restricts the live `openmontage_native` schema to `operation=status`, sends only
that tool with an OpenAI-compatible named `tool_choice`, and observes the
pinned transport's normalized response. It revalidates the final kwargs at the
actual interruptible provider-call boundary after Hermes LLM middleware, so a
middleware mutation cannot weaken the restriction. Full tools are restored
only after the model returned exactly one native call and Hermes' real
tool-completion callback reported `success: true` from the status handler.
Prompt text, a synthetic gate,
an exit-zero process, or a tool-start event cannot certify the boundary.

The controller validates the request, response and handler evidence and then
persists a non-secret contract certificate in the structured run state. Its
fingerprint covers the pinned Hermes commit, selected model/profile config,
plugin code/manifest and event adapter. Continuations and kernel-restored runs
reuse a matching certificate, so they do not spend another provider turn on a
redundant handshake; a changed runtime surface is recertified automatically.
Hermes still owns all subsequent creative reasoning, skill use and workflow
decisions. Bounded events record only structural facts—tool names/counts,
choice mode, response tool-call shape, handler success and required NVIDIA
flags—never prompts, schemas, reasoning text, response text or credentials.

## Transaction

1. Hermes authors exactly one planning payload (`proposal_packet` or `brief`),
   then `scene_plan`, `asset_manifest` and `edit_decisions`. The typed plugin
   validates and atomically publishes each payload with its native checkpoint.
2. Hermes returns `status: ready_for_execution` with canonical paths and the
   selected runtime tuple. The worker validates and publishes the envelope. If
   it is missing but all required native files already exist, the worker may
   reconcile the same typed handoff.
3. The worker replaces any model-supplied approvals with the immutable typed
   run policy.
4. The bridge checks the exact OpenMontage commit, compatibility patch and
   overlay hashes, required runtime binaries, approved runtime tuple, structured
   silence plan, native schemas, manifest checkpoint gates and cross-artifact
   media references. Every checkpoint's project, stage and embedded artifact
   content must match the canonical project file exactly.
5. A SHA-256 fingerprint covers the typed request, approvals, canonical
   creative artifacts and every referenced media file's bytes. A replaced
   asset or different request cannot reuse a published transaction.
6. An isolated OpenMontage Python process invokes
   `registry.get("video_compose").execute(...)` once. OpenMontage publishes
   `render_report`, `final_review`, the compose checkpoint and output hash.
7. Before canonical publication, the bridge persists the reviewed output hash,
   `render_report`, `final_review`, and a `rendered_reviewed` journal. Recovery
   publishes those exact bytes without another compose call. An ambiguous
   post-render/pre-review crash blocks instead of guessing or rerendering.
8. The worker independently revalidates artifact identity/schema/hash lineage,
   ffprobe evidence, eleven-frame detail and whole-timeline temporal-change
   distribution before `DELIVERED`.

## Audited OpenMontage compatibility

The repository stays at OpenMontage
`f633b5f428b9be9a2afecba851dfddd101619756`. Bootstrap applies
`patches/openmontage/f633b5f-cinematic-cut-props-v1.patch` plus the hashed
`lib/acd_native_delivery.py` overlay. The patch provides only mechanical
compatibility required by the pinned native path:

- canonical cuts/asset manifest to `CinematicRenderer` props;
- project `--public-dir` media handoff instead of unsupported `file://` video;
- offline deterministic font stacks for the statically imported compositions;
- a resource-bounded native `generic_720p` profile;
- the Atelier scaffold path correction;
- structured approved-silence propagation into native final review.

The installer is idempotent and refuses an unknown source state. The setup
doctor and runtime independently verify the pin, patch hash, reverse-apply
check, expected modified-path set and overlay hashes.

## Failure semantics

- Missing/invalid live native tool registration is `HERMES_TOOL_UNAVAILABLE`.
- A text-only or malformed first provider response is
  `HERMES_TOOL_PROTOCOL_UNSUPPORTED`; no production workflow begins.
- Missing live structural evidence is `HERMES_TOOL_HANDSHAKE_UNVERIFIED`.
- Missing Nemotron Ultra parser flags is
  `HERMES_TOOL_CONTRACT_CONFIG_INVALID` before the provider call.
- A successful provider tool call whose real native status handler fails is
  `OPENMONTAGE_RUNTIME_UNAVAILABLE`, preserving the handler's evidence.
- Provider authentication is `HERMES_AUTH_REQUIRED`; throttling and temporary
  capacity are separately retryable as `HERMES_PROVIDER_RATE_LIMITED` and
  `HERMES_PROVIDER_TRANSIENT`.
- Missing native runtime is `BLOCKED`.
- Typed runtime, checkpoint or silence approvals are `BLOCKED` and may be
  supplied on an explicit retry of the same project/session.
- Schema, checkpoint tampering, artifact integrity, fingerprint conflicts,
  native review rejection and independent validation failures cannot deliver.
- A model-authored legacy `delivered` envelope always fails with
  `LEGACY_DELIVERY_UNSUPPORTED`.
- Discord failure never changes the run result.
- A changed Hermes profile/model/plugin/Football-skill identity cannot resume
  an old conversation without explicit `--restart-hermes-session` authority.
- Missing/partial persistence generations never hydrate; export never advances
  its current pointer until every non-secret file and manifest hash is durable.
- Hydration failure stops production, persistence export holds a global run
  barrier, and any export failure makes the launcher fail regardless of the
  worker's terminal status. Persistence roots and export destinations may not
  overlap.
- Adapter timeouts kill the complete process group. A render left without a
  durable native review is never an automatic-retry state; it requires explicit
  recovery evidence rather than a second compose.

## Certification

`scripts/run_native_contract_canary.py` generates original local moving assets,
writes canonical artifacts/checkpoints, enters the exact bridge, performs a
real Remotion render and native review, then runs the independent worker
validators. A valid certificate requires schema-valid native artifacts, a
passing review, matching SHA-256 lineage, meaningful sampled-frame detail and
temporal change. The canary certifies the runtime contract; it does not replace
Football Emotion taste review for a user production.

Canary typography discovers a local bold font through fontconfig and portable
Linux font-directory fallbacks. `ACD_CANARY_FONT` may explicitly select a local
TTF/OTF file; no particular distribution font package is assumed.

The earlier full native canary was verified on 2026-07-14 against the exact
pinned commit and audited patch. The crash-safe transaction revision must earn
a fresh Kaggle canary certificate before production promotion. In the earlier
ChatGPT build sandbox only, Node required a
temporary `os.networkInterfaces()` loopback shim because that container's
libuv interface lookup fails before Remotion starts. The shim is not part of
this repository or the Kaggle/production design; all render, artifact, review,
hash-lineage and independent media checks used the real native path.

Historical native evidence (not a certificate for the new transaction overlay):

| Evidence | Value |
|---|---|
| Native input/media fingerprint | `a6b7ab01bd1d01f5cf9d0ca57907efaf4a97420767f7057d3b60e70499597ecd` |
| Output SHA-256 | `40cc923d002d27e0606994639bbf4c9e06624d17110ca84ff538a70d3513f76e` |
| Media | 12.053333 s, H.264, 1280x720, 1,337,104 bytes |
| Sampled-frame validation | Historical canary value; current contract uses 11 frames plus segment/distribution/frozen-ending checks |
| Native artifacts | proposal, scene plan, asset manifest, edit, render report and final review all valid |
| Review/lineage | `pass`, `present_to_user`; checkpoint content, review fingerprint and output hash matched |
