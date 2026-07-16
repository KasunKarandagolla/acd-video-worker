"""Thin macro-state controller delegating creative work to Hermes/OpenMontage."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .agent_contract import AgentEnvelope, load_agent_envelope
from .compatibility import COMPATIBILITY_MARKER, PINNED_OPENMONTAGE_COMMIT
from .hermes_runner import HermesRunner
from .job_prompt import PRELOADED_SKILLS, build_job_prompt
from .media_validation import FinalMediaValidator, OpenMontageArtifactValidator
from .native_bridge import NativeExecutionBridge, NativeExecutionError
from .notifications import DiscordNotifier
from .run_state import RunProblem, RunState, RunStateStore, RunStatus, TERMINAL_STATUSES, utc_now
from .source_service import SourceService, sanitize_reference


CANONICAL_CREATIVE_ARTIFACTS = {
    "research": "research_brief",
    "proposal": "proposal_packet",
    "idea": "brief",
    "script": "script",
    "scene_plan": "scene_plan",
    "assets": "asset_manifest",
    "edit": "edit_decisions",
}

PINNED_HERMES_COMMIT = "5ecc07986f46463ca3096679b03a46402eb19cee"
HERMES_TOOL_CONTRACT_VERSION = "same-path-status-v1"


class EnvironmentBlocker(RuntimeError):
    def __init__(self, message: str, *, code: str = "RUNTIME_PREREQUISITE_MISSING", evidence: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.evidence = evidence or {}


@dataclass
class ThinControllerConfig:
    worker_root: Path
    hermes_home: Path
    hermes_profile: str
    hermes_cli: Optional[str]
    openmontage_root: Path
    projects_dir: Path
    state_dir: Path
    hermes_timeout: int = 480
    hermes_max_turns: int = 20
    hermes_recovery_max_turns: int = 12
    hermes_max_continuations: int = 1
    hermes_headless_auto_approve: bool = False
    hermes_model_override: Optional[str] = None
    discord_webhook_url: str = ""
    dry_run: bool = False
    native_execution_timeout: int = 480


class ThinRunController:
    def __init__(
        self,
        config: ThinControllerConfig,
        *,
        runner: Optional[HermesRunner] = None,
        source_service: Optional[SourceService] = None,
        notifier: Optional[DiscordNotifier] = None,
        native_bridge: Optional[NativeExecutionBridge] = None,
    ):
        self.config = config
        self.store = RunStateStore(config.state_dir)
        self.source_service = source_service or SourceService()
        self.notifier = notifier or DiscordNotifier(config.discord_webhook_url)
        self.native_bridge = native_bridge
        self.runner = runner or HermesRunner(
            hermes_home=str(config.hermes_home),
            profile=config.hermes_profile,
            hermes_cli=config.hermes_cli,
            timeout=config.hermes_timeout,
            cwd=config.openmontage_root,
            max_turns=config.hermes_max_turns,
            headless_auto_approve=config.hermes_headless_auto_approve,
            model_override=config.hermes_model_override,
        )
        self.log = logging.getLogger("acd_worker.thin_controller")

    def start(self, request: str, input_references: Iterable[str] = (), approval_policy: Optional[dict] = None) -> RunState:
        run_id = uuid.uuid4().hex
        project_id = f"football-{run_id[:12]}"
        project_dir = self.config.projects_dir.expanduser().resolve() / project_id
        football_dir = project_dir / "football_emotion"
        football_dir.mkdir(parents=True, exist_ok=False)
        now = utc_now()
        state = RunState(
            schema_version="1.0",
            run_id=run_id,
            project_id=project_id,
            request=request,
            status=RunStatus.INTAKE,
            created_at=now,
            updated_at=now,
            project_dir=str(project_dir),
            source_manifest_path=str(football_dir / "source_manifest.json"),
            agent_result_path=str(football_dir / "acd_agent_result.json"),
            prompt_path=str(football_dir / "hermes_job_prompt.md"),
            input_references=[sanitize_reference(str(item)) for item in input_references],
            hermes_profile=self.config.hermes_profile,
            approval_policy=dict(approval_policy or {}),
        )
        self.store.save(state)
        self.notifier.started(state)
        with self.store.lease(state.run_id):
            return self._continue(state)

    def resume(
        self,
        run_id: str,
        *,
        retry_blocked: bool = False,
        approval_policy: Optional[dict] = None,
        restart_hermes_session: bool = False,
    ) -> RunState:
        state = self.store.load(run_id)
        if approval_policy is not None:
            state.approval_policy = dict(approval_policy)
            self.store.save(state)
        hermes_resumable = state.status in {RunStatus.SOURCE_READY, RunStatus.AGENT_RUNNING} or (
            state.status == RunStatus.BLOCKED
            and state.blocker is not None
            and state.blocker.phase in {"agent", "agent_contract", "agent_preflight"}
        )
        if hermes_resumable:
            runtime = self._current_hermes_runtime_identity()
            previous = state.hermes_runtime_identity or {}
            changed = bool(previous and previous.get("identity") != runtime["identity"])
            if changed and not restart_hermes_session:
                return self._block(
                    state,
                    "HERMES_SESSION_RUNTIME_CHANGED",
                    "The persisted Hermes session belongs to a different model/profile/plugin/skill runtime. Resume is blocked until a fresh Hermes session is explicitly authorized.",
                    "agent_contract",
                    {"previous": previous, "current": runtime},
                )
            if restart_hermes_session:
                state.hermes_session_id = None
                state.hermes_tool_contract = {}
                state.hermes_runtime_identity = runtime
                state.hermes_session_generation += 1
                state.continuations_used = 0
                # The terminal envelope is worker-owned transport state, not a
                # creative artifact. A fresh Hermes generation must not consume
                # an old session's blocked/malformed handoff. Native artifacts
                # and checkpoints remain untouched.
                Path(state.agent_result_path).unlink(missing_ok=True)
                if state.status == RunStatus.BLOCKED:
                    state.blocker = None
                    state.transition(RunStatus.AGENT_RUNNING)
                self.store.save(state)
        if state.status == RunStatus.BLOCKED and retry_blocked:
            retryable = {
                # Backward compatibility for runs persisted by pre-split builds.
                "HERMES_RUNTIME_UNAVAILABLE",
                "HERMES_PROVIDER_RATE_LIMITED",
                "HERMES_PROVIDER_TRANSIENT",
                "OPENMONTAGE_RUNTIME_UNAVAILABLE",
                "OPENMONTAGE_COMPATIBILITY_PATCH_MISSING",
                "NATIVE_EXECUTION_TIMEOUT",
                "NATIVE_RESULT_MISSING",
                "NATIVE_REVIEWED_TRANSACTION_INCOMPLETE",
                "UNAPPROVED_RUNTIME_TUPLE",
                "UNAPPROVED_SILENCE_PLAN",
                "UNAPPROVED_CHECKPOINT",
                "CHECKPOINT_APPROVAL_MISSING",
                "APPROVAL_REQUIRED",
                "HERMES_NO_NATIVE_PROGRESS",
                "HERMES_NATIVE_PROGRESS_STALLED",
                "CREATIVE_HANDOFF_INCOMPLETE",
            }
            if not state.blocker or state.blocker.code not in retryable:
                return state
            state.blocker = None
            resume_target = (
                RunStatus.NATIVE_EXECUTING
                if state.native_execution.get("status") in {
                    "prepared", "rendering", "rendered_reviewed", "published"
                }
                else RunStatus.AGENT_RUNNING
            )
            state.transition(resume_target)
            self.store.save(state)
            with self.store.lease(state.run_id):
                return self._continue(state)
        if state.status in TERMINAL_STATUSES:
            return state
        with self.store.lease(state.run_id):
            return self._continue(state)

    def _continue(self, state: RunState) -> RunState:
        agent_invoked = False
        last_execution_metadata: dict = {}
        try:
            if state.status == RunStatus.INTAKE:
                self.source_service.prepare_manifest(Path(state.source_manifest_path), state.input_references)
                state.transition(RunStatus.SOURCE_READY)
                self.store.save(state)

            if state.status == RunStatus.SOURCE_READY:
                self._preflight(state)
                self._bind_hermes_runtime_identity(state)
                prompt = build_job_prompt(
                    run_id=state.run_id,
                    project_id=state.project_id,
                    request=state.request,
                    worker_root=self.config.worker_root.resolve(),
                    openmontage_root=self.config.openmontage_root.resolve(),
                    project_dir=Path(state.project_dir).resolve(),
                    source_manifest_path=Path(state.source_manifest_path).resolve(),
                    result_path=Path(state.agent_result_path).resolve(),
                    football_skill_root=(self.runner.profile_dir / "skills" / "football-emotion-video").resolve(),
                    approval_policy=state.approval_policy,
                )
                Path(state.prompt_path).write_text(prompt, encoding="utf-8")
                if self.config.dry_run:
                    return self._block(
                        state,
                        "DRY_RUN_ONLY",
                        "Prompt prepared; dry-run mode never claims delivery.",
                        "agent_preflight",
                        {"prompt_path": state.prompt_path},
                    )
                state.transition(RunStatus.AGENT_RUNNING)
                self.store.save(state)
                progress_before = self._native_progress_signature(state)
                execution = self.runner.run_session(
                    prompt=prompt,
                    session_id=state.hermes_session_id,
                    expected_skills=list(PRELOADED_SKILLS),
                    progress_callback=lambda event: self._heartbeat(state, event),
                    environment=self._hermes_environment(state),
                )
                agent_invoked = True
                last_execution_metadata = dict(execution.metadata or {})
                if execution.session_id:
                    state.hermes_session_id = execution.session_id
                    self.store.save(state)
                if not execution.success:
                    return self._classify_hermes_failure(state, execution)
                contract_problem = self._validate_hermes_tool_contract(state, execution)
                if contract_problem is not None:
                    return contract_problem
                self._capture_terminal_payload(state, execution)
                last_execution_metadata = dict(execution.metadata or {})
                if (
                    not Path(state.agent_result_path).is_file()
                    and self._reconcile_execution_handoff(state) is None
                    and self._native_progress_signature(state) == progress_before
                ):
                    return self._block(
                        state,
                        "HERMES_NO_NATIVE_PROGRESS",
                        "Hermes completed its bounded creative slice without publishing any native OpenMontage artifact or checkpoint.",
                        "agent",
                        {
                            "session_id": state.hermes_session_id,
                            "max_turns": self.config.hermes_max_turns,
                            "execution": last_execution_metadata,
                            **self._native_progress_evidence(state),
                        },
                    )

            if state.status == RunStatus.NATIVE_EXECUTING:
                reconciled = self._reconcile_execution_handoff(state)
                if reconciled is None:
                    return self._fail(
                        state,
                        "NATIVE_RECOVERY_INPUT_MISSING",
                        "A native transaction was interrupted but its canonical creative handoff can no longer be reconstructed.",
                        "native_execution",
                        {"native_execution": state.native_execution},
                    )
                execution_request, declared_artifacts = reconciled
                self._publish_controller_handoff(state, execution_request, declared_artifacts)
                state.openmontage_artifacts = declared_artifacts
                native_result = self._execute_native(state, execution_request)
                self._accept_native_result(state, native_result)

            if state.status == RunStatus.AGENT_RUNNING:
                result_path = Path(state.agent_result_path)
                approval = self._pending_native_approval(state)
                if approval is not None:
                    return self._block(
                        state,
                        "APPROVAL_REQUIRED",
                        f"OpenMontage checkpoint {approval['stage']!r} requires typed user approval.",
                        approval["stage"],
                        approval,
                    )
                # A resumed session is continued by the bounded loop below. Do
                # not run an extra uncounted recovery slice before that loop.
                # A missing session ID is the only case that must replay the
                # original job prompt to establish a supported Hermes session.
                if not result_path.is_file() and not agent_invoked and not state.hermes_session_id:
                    prompt_path = Path(state.prompt_path)
                    if not prompt_path.is_file():
                        return self._fail(state, "PROMPT_MISSING", "Cannot resume because the persisted Hermes job prompt is missing.", "agent")
                    execution = self.runner.run_session(
                        prompt=prompt_path.read_text(encoding="utf-8"),
                        session_id=state.hermes_session_id,
                        expected_skills=list(PRELOADED_SKILLS),
                        progress_callback=lambda event: self._heartbeat(state, event),
                        environment=self._hermes_environment(state),
                    )
                    agent_invoked = True
                    last_execution_metadata = dict(execution.metadata or {})
                    if execution.session_id:
                        state.hermes_session_id = execution.session_id
                        self.store.save(state)
                    if not execution.success:
                        return self._classify_hermes_failure(state, execution)
                    contract_problem = self._validate_hermes_tool_contract(state, execution)
                    if contract_problem is not None:
                        return contract_problem
                    self._capture_terminal_payload(state, execution)
                    last_execution_metadata = dict(execution.metadata or {})

                # OpenMontage deliberately makes the agent its control plane and
                # persists progress as native checkpoints. A production pipeline
                # can legitimately exceed one Hermes CLI turn slice, so continue
                # the same session from those checkpoints without introducing a
                # worker-side stage machine or repeating research/discovery.
                while (
                    not result_path.is_file()
                    and self._reconcile_execution_handoff(state) is None
                    and state.continuations_used < self.config.hermes_max_continuations
                ):
                    state.continuations_used += 1
                    self.store.save(state)
                    progress_before = self._native_progress_signature(state)
                    recovery = self.runner.run_session(
                        prompt=self._checkpoint_continuation_prompt(
                            state,
                            continuation=state.continuations_used,
                            final=state.continuations_used == self.config.hermes_max_continuations,
                        ),
                        session_id=state.hermes_session_id,
                        expected_skills=[],
                        max_turns=self.config.hermes_recovery_max_turns,
                        progress_callback=lambda event: self._heartbeat(state, event),
                        environment=self._hermes_environment(state),
                    )
                    last_execution_metadata = dict(recovery.metadata or {})
                    if recovery.session_id:
                        state.hermes_session_id = recovery.session_id
                        self.store.save(state)
                    if not recovery.success:
                        return self._classify_hermes_failure(state, recovery)
                    contract_problem = self._validate_hermes_tool_contract(state, recovery)
                    if contract_problem is not None:
                        return contract_problem
                    self._capture_terminal_payload(state, recovery)
                    last_execution_metadata = dict(recovery.metadata or {})
                    approval = self._pending_native_approval(state)
                    if approval is not None:
                        return self._block(
                            state,
                            "APPROVAL_REQUIRED",
                            f"OpenMontage checkpoint {approval['stage']!r} requires typed user approval.",
                            approval["stage"],
                            approval,
                        )
                    if (
                        not result_path.is_file()
                        and self._reconcile_execution_handoff(state) is None
                        and self._native_progress_signature(state) == progress_before
                    ):
                        return self._block(
                            state,
                            "HERMES_NATIVE_PROGRESS_STALLED",
                            "Hermes used a continuation slice without advancing any native OpenMontage artifact or checkpoint.",
                            "agent",
                            {
                                "session_id": state.hermes_session_id,
                                "continuations_attempted": state.continuations_used,
                                "continuation_max_turns": self.config.hermes_recovery_max_turns,
                                "execution": last_execution_metadata,
                                **self._native_progress_evidence(state),
                            },
                        )
                envelope = None
                protocol_error = None
                if result_path.is_file():
                    try:
                        envelope = load_agent_envelope(Path(state.agent_result_path), state.run_id)
                    except ValueError as exc:
                        protocol_error = str(exc)
                if envelope is None:
                    reconciled = self._reconcile_execution_handoff(state)
                    if reconciled is None:
                        if protocol_error is not None:
                            return self._fail(
                                state,
                                "AGENT_CONTRACT_INVALID",
                                "Hermes published a terminal envelope that violates the worker-owned handoff contract.",
                                "agent_contract",
                                {"agent_protocol_error": protocol_error},
                            )
                        return self._block(
                            state,
                            "CREATIVE_HANDOFF_INCOMPLETE",
                            "Hermes exited without a usable terminal handoff and the native creative artifacts are incomplete.",
                            "agent",
                            {
                                "session_id": state.hermes_session_id,
                                "continuations_attempted": state.continuations_used,
                                "continuation_max_turns": self.config.hermes_recovery_max_turns,
                                "agent_protocol_error": protocol_error,
                                "execution": last_execution_metadata,
                                **self._native_progress_evidence(state),
                            },
                        )
                    execution_request, declared_artifacts = reconciled
                    self._publish_controller_handoff(state, execution_request, declared_artifacts)
                    state.output_candidates = []
                    state.openmontage_artifacts = declared_artifacts
                    native_result = self._execute_native(state, execution_request)
                    self._accept_native_result(state, native_result)
                    envelope = None
                else:
                    state.output_candidates = envelope.output_media
                    state.openmontage_artifacts = envelope.openmontage_artifacts
                if envelope is None:
                    # Deterministic checkpoint reconciliation already produced
                    # and executed the native handoff above.
                    pass
                elif envelope.status == "blocked":
                    return self._problem_from_envelope(state, envelope, blocked=True)
                elif envelope.status == "failed":
                    return self._problem_from_envelope(state, envelope, blocked=False)
                elif envelope.status == "delivered":
                    return self._fail(
                        state,
                        "LEGACY_DELIVERY_UNSUPPORTED",
                        "Hermes cannot claim delivery; only the deterministic native transaction and worker validator may deliver.",
                        "agent_contract",
                        {"reported_outputs": len(envelope.output_media)},
                    )
                elif envelope.status == "ready_for_execution":
                    self._validate_handoff_declarations(envelope)
                    try:
                        native_result = self._execute_native(state, envelope.execution_request or {})
                    except NativeExecutionError as exc:
                        runtime_blockers = {
                            "OPENMONTAGE_PIN_MISMATCH",
                            "OPENMONTAGE_RUNTIME_UNAVAILABLE",
                            "OPENMONTAGE_COMPATIBILITY_PATCH_MISSING",
                            "UNSUPPORTED_RUNTIME_TUPLE",
                            "UNAPPROVED_RUNTIME_TUPLE",
                            "UNAPPROVED_SILENCE_PLAN",
                            "UNAPPROVED_CHECKPOINT",
                            "CHECKPOINT_APPROVAL_MISSING",
                            "NATIVE_ADAPTER_MISSING",
                            "NATIVE_EXECUTION_TIMEOUT",
                            "NATIVE_RESULT_MISSING",
                            "NATIVE_REVIEWED_TRANSACTION_INCOMPLETE",
                            "NATIVE_RENDER_RECOVERY_REVIEW_REQUIRED",
                            "NATIVE_FAILED_TRANSACTION_HAS_OUTPUT",
                        }
                        if exc.code in runtime_blockers:
                            return self._block(state, exc.code, str(exc), "native_execution", exc.evidence)
                        return self._fail(state, exc.code, str(exc), "native_execution", exc.evidence)
                    self._accept_native_result(state, native_result)
                if state.status == RunStatus.AGENT_RUNNING:
                    state.transition(RunStatus.VALIDATING)
                    self.store.save(state)

            if state.status == RunStatus.VALIDATING:
                artifact_validator = OpenMontageArtifactValidator(
                    Path(state.project_dir),
                    self.config.openmontage_root,
                    Path(state.agent_result_path),
                )
                state.artifact_validation = artifact_validator.validate(
                    state.openmontage_artifacts,
                    state.output_candidates,
                )
                validator = FinalMediaValidator(Path(state.project_dir))
                state.validation = [validator.validate(candidate) for candidate in state.output_candidates]
                self.store.save(state)
                if not state.artifact_validation.get("valid"):
                    return self._fail(
                        state,
                        "OPENMONTAGE_ARTIFACT_VALIDATION_FAILED",
                        "Hermes claimed delivery without schema-valid native OpenMontage artifacts and review evidence.",
                        "validation",
                        {
                            "artifact_validation": state.artifact_validation,
                            "media_validation": state.validation,
                        },
                    )
                valid = [evidence for evidence in state.validation if evidence.get("valid")]
                if not valid:
                    if any(e.get("blocker_code") == "FFPROBE_UNAVAILABLE" for e in state.validation):
                        return self._block(state, "FFPROBE_UNAVAILABLE", "ffprobe is required for final delivery validation.", "validation", {"results": state.validation})
                    return self._fail(state, "OUTPUT_VALIDATION_FAILED", "Hermes claimed delivery but no candidate passed independent media validation.", "validation", {"results": state.validation})
                state.transition(RunStatus.DELIVERED)
                self.store.save(state)
                self.notifier.terminal(state)
            return state
        except EnvironmentBlocker as exc:
            return self._block(state, exc.code, str(exc), state.status.value.lower(), exc.evidence)
        except NativeExecutionError as exc:
            runtime_blockers = {
                "OPENMONTAGE_PIN_MISMATCH",
                "OPENMONTAGE_RUNTIME_UNAVAILABLE",
                "OPENMONTAGE_COMPATIBILITY_PATCH_MISSING",
                "UNSUPPORTED_RUNTIME_TUPLE",
                "UNAPPROVED_RUNTIME_TUPLE",
                "UNAPPROVED_SILENCE_PLAN",
                "UNAPPROVED_CHECKPOINT",
                "CHECKPOINT_APPROVAL_MISSING",
                "NATIVE_ADAPTER_MISSING",
                "NATIVE_EXECUTION_TIMEOUT",
                "NATIVE_RESULT_MISSING",
                "NATIVE_REVIEWED_TRANSACTION_INCOMPLETE",
                "NATIVE_RENDER_RECOVERY_REVIEW_REQUIRED",
                "NATIVE_FAILED_TRANSACTION_HAS_OUTPUT",
            }
            if exc.code in runtime_blockers:
                return self._block(state, exc.code, str(exc), "native_execution", exc.evidence)
            return self._fail(state, exc.code, str(exc), "native_execution", exc.evidence)
        except (ValueError, json.JSONDecodeError) as exc:
            return self._fail(state, "PROTOCOL_ERROR", str(exc), state.status.value.lower())
        except Exception as exc:  # terminal boundary: persist an honest failure
            self.log.exception("Thin controller failed")
            return self._fail(state, "UNEXPECTED_ERROR", str(exc), state.status.value.lower())

    def _preflight(self, state: RunState) -> None:
        if not self.config.openmontage_root.is_dir():
            raise EnvironmentBlocker(f"Pinned OpenMontage checkout is missing: {self.config.openmontage_root}")
        if not (self.config.openmontage_root / "AGENT_GUIDE.md").is_file():
            raise EnvironmentBlocker("OpenMontage AGENT_GUIDE.md is missing")
        if not self.runner.profile_dir.is_dir():
            raise EnvironmentBlocker(f"Hermes profile is missing: {self.runner.profile_dir}")
        missing = [skill for skill in PRELOADED_SKILLS if not self.runner.find_skill(skill)]
        if missing:
            raise EnvironmentBlocker(f"Required Football Emotion skills are not installed: {', '.join(missing)}")
        plugin = self.runner.profile_dir / "plugins" / "acd-openmontage"
        if not (plugin / "plugin.yaml").is_file() or not (plugin / "__init__.py").is_file():
            raise EnvironmentBlocker(f"Required Hermes OpenMontage plugin is not installed: {plugin}")
        if not (self.config.worker_root / "scripts" / "openmontage_creative_adapter.py").is_file():
            raise EnvironmentBlocker("OpenMontage creative adapter is missing")
        if not Path(state.source_manifest_path).is_file():
            raise EnvironmentBlocker("Worker source manifest is missing before Hermes startup")

    @staticmethod
    def _tree_digest(root: Path) -> str:
        """Hash one installed contract tree without timestamps or cache files."""
        root = Path(root).expanduser().resolve()
        digest = hashlib.sha256()
        if not root.is_dir():
            return "missing"
        for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
            if (
                not path.is_file()
                or path.is_symlink()
                or "__pycache__" in path.parts
                or path.suffix in {".pyc", ".pyo"}
            ):
                continue
            relative = str(path.relative_to(root))
            digest.update(relative.encode())
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        return digest.hexdigest()

    def _current_hermes_runtime_identity(self) -> dict[str, str]:
        profile = self.runner.profile_dir
        plugin_root = profile / "plugins" / "acd-openmontage"
        skill_root = profile / "skills" / "football-emotion-video"
        config_path = profile / "config.yaml"
        payload = {
            "schema_version": "1.0",
            "hermes_commit": PINNED_HERMES_COMMIT,
            "profile": self.config.hermes_profile,
            "model_override": self.config.hermes_model_override or "",
            "profile_config_sha256": (
                hashlib.sha256(config_path.read_bytes()).hexdigest()
                if config_path.is_file()
                else "missing"
            ),
            "plugin_sha256": self._tree_digest(plugin_root),
            "football_skill_sha256": self._tree_digest(skill_root),
            "tool_contract_version": HERMES_TOOL_CONTRACT_VERSION,
        }
        identity = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {**payload, "identity": identity}

    def _bind_hermes_runtime_identity(self, state: RunState) -> None:
        current = self._current_hermes_runtime_identity()
        previous = state.hermes_runtime_identity or {}
        if previous and previous.get("identity") != current["identity"]:
            raise EnvironmentBlocker(
                "The Hermes runtime changed after this run was created; continuing the old session would mix incompatible model/profile/plugin/skill state.",
                code="HERMES_SESSION_RUNTIME_CHANGED",
                evidence={"previous": previous, "current": current},
            )
        if not previous:
            state.hermes_runtime_identity = current
            self.store.save(state)

    def _hermes_environment(self, state: RunState) -> dict[str, str]:
        """Bind plugin tools to exactly this run and typed user policy."""
        contract_id = self._hermes_tool_contract_id()
        certificate = state.hermes_tool_contract or {}
        contract_required = not (
            certificate.get("status") == "passed"
            and certificate.get("contract_id") == contract_id
        )
        return {
            "ACD_WORKER_ROOT": str(self.config.worker_root.resolve()),
            "ACD_WORKER_PYTHON": sys.executable,
            "ACD_PROJECT_DIR": str(Path(state.project_dir).resolve()),
            "ACD_RUN_ID": state.run_id,
            "ACD_SOURCE_MANIFEST": str(Path(state.source_manifest_path).resolve()),
            "ACD_FOOTBALL_SKILL_ROOT": str(
                (self.runner.profile_dir / "skills" / "football-emotion-video").resolve()
            ),
            "ACD_APPROVAL_POLICY_JSON": json.dumps(state.approval_policy, sort_keys=True),
            # The first request of an uncertified run is the live status-only
            # handshake. Once its real handler succeeds, the persisted
            # certificate prevents repetition on continuation/restart.
            "ACD_FORCE_INITIAL_OPENMONTAGE_TOOL": "1" if contract_required else "0",
            "ACD_HERMES_TOOL_CONTRACT_ID": contract_id,
            "OPENMONTAGE_ROOT": str(self.config.openmontage_root.resolve()),
            "OPENMONTAGE_PROJECTS_DIR": str(self.config.projects_dir.resolve()),
            "OPENMONTAGE_PYTHON": os.environ.get(
                "OPENMONTAGE_PYTHON",
                str(self.config.openmontage_root.resolve() / ".venv" / "bin" / "python"),
            ),
        }

    def _hermes_tool_contract_id(self) -> str:
        """Fingerprint the non-secret runtime surface certified by the handshake."""
        profile = self.runner.profile_dir
        adapter = Path(
            getattr(
                self.runner,
                "event_adapter",
                self.config.worker_root / "scripts" / "hermes_event_adapter.py",
            )
        )
        files = {
            "profile_config": profile / "config.yaml",
            "plugin_manifest": profile / "plugins" / "acd-openmontage" / "plugin.yaml",
            "plugin_code": profile / "plugins" / "acd-openmontage" / "__init__.py",
            "event_adapter": adapter,
            "creative_adapter": self.config.worker_root / "scripts" / "openmontage_creative_adapter.py",
            "openmontage_compatibility": self.config.openmontage_root / COMPATIBILITY_MARKER,
        }
        file_hashes = {}
        for label, path in files.items():
            resolved = Path(path).expanduser().resolve()
            try:
                file_hashes[label] = hashlib.sha256(resolved.read_bytes()).hexdigest()
            except OSError:
                file_hashes[label] = "missing"
        payload = {
            "version": HERMES_TOOL_CONTRACT_VERSION,
            "hermes_commit": PINNED_HERMES_COMMIT,
            "openmontage_commit": PINNED_OPENMONTAGE_COMMIT,
            "profile": self.config.hermes_profile,
            "model_override": self.config.hermes_model_override or "",
            "football_skill_sha256": self._tree_digest(
                profile / "skills" / "football-emotion-video"
            ),
            "files": file_hashes,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @staticmethod
    def _event_truth(value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    def _validate_hermes_tool_contract(self, state: RunState, execution) -> Optional[RunState]:
        """Certify the exact production request/response/tool path or block it."""
        metadata = dict(execution.metadata or {})
        if not metadata.get("tool_contract_requested"):
            return None
        summary = metadata.get("event_summary")
        evidence = {
            "contract_id": metadata.get("tool_contract_id"),
            "session_id": execution.session_id or state.hermes_session_id,
            "event_adapter_used": metadata.get("event_adapter_used") is True,
        }
        if not isinstance(summary, dict):
            return self._block(
                state,
                "HERMES_TOOL_HANDSHAKE_UNVERIFIED",
                "The production Hermes adapter returned no structural tool-contract evidence.",
                "agent_contract",
                evidence,
            )
        agent = summary.get("agent_contract") or {}
        request = summary.get("first_request_contract") or summary.get("request_contract") or {}
        response = summary.get("first_response_contract") or {}
        handshake = summary.get("tool_handshake") or {}
        counts = summary.get("events") or {}
        evidence.update({
            "agent_contract": agent,
            "first_request_contract": request,
            "first_response_contract": response,
            "tool_handshake": handshake,
            "handshake_started_events": counts.get("tool_handshake_started", 0),
            "handshake_completed_events": counts.get("tool_handshake_completed", 0),
            "handshake_failed_events": counts.get("tool_handshake_failed", 0),
        })
        if metadata.get("event_adapter_used") is not True:
            return self._block(
                state,
                "HERMES_TOOL_HANDSHAKE_UNVERIFIED",
                "The pinned Hermes event adapter was unavailable for the required live handshake.",
                "agent_contract",
                evidence,
            )
        if not self._event_truth(agent.get("has_openmontage_native")):
            return self._block(
                state,
                "HERMES_TOOL_UNAVAILABLE",
                "The live Hermes AIAgent did not expose openmontage_native.",
                "agent_contract",
                evidence,
            )
        if not self._event_truth(agent.get("has_acd_acquire_source")):
            return self._block(
                state,
                "HERMES_SOURCE_TOOL_UNAVAILABLE",
                "The live Hermes AIAgent did not expose the worker-owned source acquisition tool.",
                "agent_contract",
                evidence,
            )
        request_valid = (
            self._event_truth(request.get("handshake_request"))
            and str(request.get("tool_count")) == "1"
            and request.get("tools") == "openmontage_native"
            and self._event_truth(request.get("status_only"))
            and request.get("tool_choice_mode") == "named"
            and request.get("tool_choice_name") == "openmontage_native"
        )
        if not request_valid:
            return self._block(
                state,
                "HERMES_TOOL_REQUEST_INVALID",
                "The first production provider request did not enforce the status-only native handshake.",
                "agent_contract",
                evidence,
            )
        model = str(request.get("model") or agent.get("model") or "").lower()
        if "nemotron-3-ultra-550b-a55b" in model and not (
            self._event_truth(request.get("enable_thinking"))
            and self._event_truth(request.get("force_nonempty_content"))
        ):
            return self._block(
                state,
                "HERMES_TOOL_CONTRACT_CONFIG_INVALID",
                "Nemotron Ultra tool parsing flags were absent from the live production request.",
                "agent_contract",
                evidence,
            )
        response_valid = (
            str(response.get("tool_call_count")) == "1"
            and response.get("tool_call_names") == "openmontage_native"
            and self._event_truth(response.get("status_operation"))
        )
        completed = (
            self._event_truth(handshake.get("required"))
            and self._event_truth(handshake.get("started"))
            and self._event_truth(handshake.get("completed"))
            and not self._event_truth(handshake.get("failed"))
            and self._event_truth(handshake.get("result_success"))
            and str(counts.get("tool_handshake_started", 0)) == "1"
            and str(counts.get("tool_handshake_completed", 0)) == "1"
        )
        handler_failure = str(handshake.get("failure_code") or "")
        if response_valid and self._event_truth(handshake.get("failed")) and handler_failure not in {
            "INVALID_PROVIDER_TOOL_RESPONSE",
            "UNEXPECTED_INITIAL_TOOL",
        }:
            return self._block(
                state,
                "OPENMONTAGE_RUNTIME_UNAVAILABLE",
                "The real openmontage_native status handler did not complete successfully.",
                "agent_contract",
                evidence,
            )
        if not response_valid or not completed:
            return self._block(
                state,
                "HERMES_TOOL_PROTOCOL_UNSUPPORTED",
                "The provider did not return one executable native status call through the pinned Hermes path.",
                "agent_contract",
                evidence,
            )
        state.hermes_tool_contract = {
            "schema_version": "1.0",
            "status": "passed",
            "contract_id": metadata.get("tool_contract_id") or self._hermes_tool_contract_id(),
            "certified_at": utc_now(),
            "session_id": execution.session_id or state.hermes_session_id,
            "provider": agent.get("provider"),
            "model": request.get("model") or agent.get("model"),
            "tool": "openmontage_native",
            "operation": "status",
        }
        self.store.save(state)
        return None

    def _checkpoint_continuation_prompt(self, state: RunState, *, continuation: int, final: bool) -> str:
        final_instruction = (
            "This is the final continuation slice. Reserve the last five tool calls for schema validation, "
            "the typed execution handoff and the exact final JSON response. If a valid handoff remains impossible, "
            "return a canonical blocked or failed object before the slice ends."
            if final else
            "This is not the final continuation slice. Continue native production from the next incomplete "
            "checkpoint. Do not emit NATIVE_PIPELINE_TURN_BUDGET_EXHAUSTED merely because this CLI slice ends; "
            "the controller will resume this same Hermes session again."
        )
        return f"""Continue the same ACD production run {state.run_id} from the existing OpenMontage checkpoints.

WORKER-OWNED RESULT PATH: {state.agent_result_path}
CONTINUATION SLICE: {continuation} of {self.config.hermes_max_continuations}

Do not repeat repository, skill, pipeline, capability discovery, provider menus or web research already completed in this session. Call `openmontage_native(operation="status")` once to receive the bounded durable checkpoint/artifact status, then resume exactly the next incomplete native stage. Built-in terminal, file and code-execution tools are intentionally unavailable. Read only a necessary unchanged contract with `openmontage_native(operation="read_document", ...)`.

Treat every successful tool output reported by status/the durable tool journal as completed. Never invoke `math_animate`, another generator or a downloader again for the same completed output path. `openmontage_native(operation="run_tool")` enforces one corrected retry for a genuinely missing or invalid output; after that, return an actionable blocker instead of looping. Immediately after successful asset generation, publish `asset_manifest` through `openmontage_native(operation="publish_artifact")` before any other tool call. Raw asset files without the updated manifest/checkpoint are not stage completion.

If `scene_plan`, `asset_manifest`, `edit_decisions` and every media path they reference are already schema-valid, do not generate, redesign or compose anything. Return `status: ready_for_execution` with the typed `execution_request` from the original job contract. The deterministic bridge—not this conversation—will invoke `video_compose`, native final review and candidate validation exactly once.

{final_instruction}

Continue authoring each missing artifact with the already-selected native stage director and publish it only through `openmontage_native(operation="publish_artifact")`. Stop after the schema-valid edit checkpoint and return the typed ready-for-execution handoff.

You have {self.config.hermes_recovery_max_turns} tool-calling turns in this slice. Never substitute a direct FFmpeg/helper render, invent artifacts, or claim delivery without native evidence. A genuine external blocker may be reported at any time, but use the complete canonical envelope below:

{{
  "schema_version": "1.0",
  "run_id": "{state.run_id}",
  "status": "blocked",
  "output_media": [],
  "openmontage_artifacts": [],
  "source_requests": [],
  "blocker": {{"code": "STABLE_CODE", "message": "actionable message", "phase": "native stage", "evidence": {{}}}},
  "error": null,
  "summary": "short factual summary"
}}

Return this JSON object as the final response. The worker—not Hermes—validates and writes the terminal envelope.
"""

    def _execute_native(self, state: RunState, request: dict) -> object:
        # Bind the model-authored handoff to user-owned run policy. Any value
        # Hermes placed under this key is overwritten deterministically.
        request = dict(request)
        request["approved_checkpoints"] = sorted(set(state.approval_policy.get("approved_checkpoints") or []))
        bridge = self.native_bridge or NativeExecutionBridge(
            self.config.worker_root,
            self.config.openmontage_root,
            Path(state.project_dir),
            timeout=self.config.native_execution_timeout,
        )
        prepared, compatibility, fingerprint = bridge.prepare(request)
        runtime = compatibility.get("runtime") or {}
        locked = state.approval_policy.get("runtime_tuple")
        if locked and any(str(runtime.get(key) or "") != str(locked.get(key) or "") for key in ("pipeline", "composition_mode", "renderer_family", "render_runtime")):
            raise NativeExecutionError(
                "UNAPPROVED_RUNTIME_TUPLE",
                "Hermes selected a runtime tuple different from the typed approval policy.",
                {"approved": locked, "selected": runtime},
            )
        if getattr(prepared, "approved_silence", False) and state.approval_policy.get("approved_silence") is not True:
            raise NativeExecutionError(
                "UNAPPROVED_SILENCE_PLAN",
                "The execution request claims approved silence, but the typed approval policy does not.",
            )
        previous = state.native_execution or {}
        if previous.get("status") == "published" and previous.get("fingerprint") != fingerprint:
            raise NativeExecutionError(
                "NATIVE_FINGERPRINT_CONFLICT",
                "A different native transaction was already published for this run.",
                {"existing": previous.get("fingerprint"), "requested": fingerprint},
            )
        if state.status == RunStatus.AGENT_RUNNING:
            state.transition(RunStatus.NATIVE_EXECUTING)
        state.native_execution = {
            "status": "prepared",
            "fingerprint": fingerprint,
            "runtime": compatibility.get("runtime"),
            "prepared_at": utc_now(),
        }
        self.store.save(state)
        result = bridge.execute(request, heartbeat=lambda event: self._heartbeat(state, event))
        state.native_execution = {
            **state.native_execution,
            "status": "published",
            "published_at": utc_now(),
            "compatibility": result.compatibility,
            "native_result": result.native_result,
        }
        self.store.save(state)
        return result

    def _accept_native_result(self, state: RunState, native_result) -> None:
        """Persist native evidence before exposing the validation phase."""
        state.output_candidates = list(native_result.output_media)
        state.openmontage_artifacts = list(native_result.openmontage_artifacts)
        state.native_execution = {
            **state.native_execution,
            "status": "published",
            "fingerprint": getattr(
                native_result,
                "fingerprint",
                state.native_execution.get("fingerprint"),
            ),
            "native_result": dict(native_result.native_result or {}),
        }
        if state.status == RunStatus.NATIVE_EXECUTING:
            state.transition(RunStatus.VALIDATING)
        self.store.save(state)

    def _publish_controller_handoff(
        self,
        state: RunState,
        execution_request: dict,
        declared_artifacts: list[dict],
    ) -> None:
        """Write the deterministic terminal handoff from native evidence.

        Hermes owns every creative artifact byte. The worker owns the terminal
        envelope, so a missing/malformed final model response cannot discard a
        complete edit checkpoint or force another model turn.
        """
        payload = {
            "schema_version": "1.0",
            "run_id": state.run_id,
            "status": "ready_for_execution",
            "output_media": [],
            "openmontage_artifacts": declared_artifacts,
            "source_requests": [],
            "execution_request": execution_request,
            "blocker": None,
            "error": None,
            "summary": "Controller reconciled a complete schema-valid OpenMontage edit handoff.",
        }
        AgentEnvelope.from_dict(payload, state.run_id)
        target = Path(state.agent_result_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def _reconcile_execution_handoff(self, state: RunState) -> Optional[tuple[dict, list[dict]]]:
        """Derive a typed handoff from completed native artifacts.

        This does not author or choose creative content. It only recognizes the
        fixed OpenMontage contract after Hermes has already published all
        creative inputs through edit. This is the fail-safe for a missing or
        malformed model-authored result envelope.
        """
        project = Path(state.project_dir).resolve()
        artifacts_dir = project / "artifacts"
        required = ("scene_plan", "asset_manifest", "edit_decisions")
        paths = {kind: artifacts_dir / f"{kind}.json" for kind in required}
        planning = [kind for kind in ("proposal_packet", "brief") if (artifacts_dir / f"{kind}.json").is_file()]
        if len(planning) != 1 or any(not path.is_file() for path in paths.values()):
            return None
        planning_kind = planning[0]
        paths[planning_kind] = artifacts_dir / f"{planning_kind}.json"

        marker = project / "project.json"
        try:
            marker_payload = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        pipeline = str(marker_payload.get("pipeline_type") or "").strip()
        if not pipeline:
            return None
        try:
            edit_payload = json.loads(paths["edit_decisions"].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        edit_metadata = edit_payload.get("metadata") if isinstance(edit_payload.get("metadata"), dict) else {}
        output_profile = edit_payload.get("output_profile") or edit_metadata.get("output_profile")
        request = {
            "pipeline": pipeline,
            "artifacts": {kind: str(path) for kind, path in paths.items()},
            "output_path": str(project / "renders" / "final.mp4"),
            # Preserve an already-authored native output-profile choice. The
            # reconciler never selects or invents a profile itself.
            "output_profile": str(output_profile) if output_profile else None,
            "approved_silence": state.approval_policy.get("approved_silence") is True,
        }
        declared = [{"kind": kind, "path": str(path)} for kind, path in paths.items()]
        return request, declared

    def _validate_handoff_declarations(self, envelope: AgentEnvelope) -> None:
        requested = {
            (str(kind), str(Path(path).expanduser().resolve()))
            for kind, path in (envelope.execution_request or {}).get("artifacts", {}).items()
            if isinstance(path, str)
        }
        declared = {
            (str(item.get("kind") or ""), str(Path(str(item.get("path") or "")).expanduser().resolve()))
            for item in envelope.openmontage_artifacts
            if isinstance(item, dict)
        }
        if requested != declared:
            raise NativeExecutionError(
                "HANDOFF_ARTIFACT_MISMATCH",
                "The result envelope and typed execution request declare different native artifacts.",
                {"requested": sorted(requested), "declared": sorted(declared)},
            )

    def _native_progress_evidence(self, state: RunState) -> dict:
        project = Path(state.project_dir).resolve()
        artifacts_dir = project / "artifacts"
        kinds = ("research_brief", "brief", "proposal_packet", "script", "scene_plan", "asset_manifest", "edit_decisions")
        present = [kind for kind in kinds if (artifacts_dir / f"{kind}.json").is_file()]
        checkpoints = sorted(path.stem for path in project.glob("checkpoint_*.json") if path.is_file())
        return {"native_artifacts_present": present, "native_checkpoints_present": checkpoints}

    def _native_progress_signature(self, state: RunState) -> tuple:
        """Track only coherent native checkpoint/artifact progress.

        A loose JSON file is not durable pipeline progress. The typed bridge
        publishes the canonical artifact and its checkpoint as one operation,
        so a continuation is earned only by a checkpoint whose embedded
        canonical payload matches the corresponding on-disk artifact.
        """
        project = Path(state.project_dir).resolve()
        signature = []
        for checkpoint in sorted(project.glob("checkpoint_*.json"), key=lambda item: item.name):
            if not checkpoint.is_file():
                continue
            try:
                payload = json.loads(checkpoint.read_text(encoding="utf-8"))
                stage = str(payload.get("stage") or "")
                status = str(payload.get("status") or "")
                kind = CANONICAL_CREATIVE_ARTIFACTS[stage]
                embedded = (payload.get("artifacts") or {}).get(kind)
                artifact = project / "artifacts" / f"{kind}.json"
                on_disk = json.loads(artifact.read_text(encoding="utf-8"))
            except (KeyError, OSError, json.JSONDecodeError, TypeError):
                continue
            if status not in {"completed", "awaiting_human"}:
                continue
            if not isinstance(embedded, dict) or embedded != on_disk:
                continue
            checkpoint_stat = checkpoint.stat()
            artifact_stat = artifact.stat()
            signature.append((
                stage,
                status,
                checkpoint_stat.st_size,
                checkpoint_stat.st_mtime_ns,
                artifact_stat.st_size,
                artifact_stat.st_mtime_ns,
            ))
        return tuple(signature)

    def _pending_native_approval(self, state: RunState) -> Optional[dict]:
        """Return the first native gate still awaiting typed user approval."""
        approved = {str(item) for item in state.approval_policy.get("approved_checkpoints") or []}
        project = Path(state.project_dir).resolve()
        for path in sorted(project.glob("checkpoint_*.json"), key=lambda item: item.name):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            stage = str(payload.get("stage") or "")
            if payload.get("status") == "awaiting_human" and stage not in approved:
                return {
                    "stage": stage,
                    "checkpoint_path": str(path),
                    "human_approval_required": payload.get("human_approval_required") is True,
                }
        return None

    def _capture_terminal_payload(self, state: RunState, execution) -> None:
        """Validate Hermes' final JSON and let the worker publish the envelope."""
        target = Path(state.agent_result_path)
        payload = getattr(execution, "terminal_payload", None)
        if target.is_file() or not isinstance(payload, dict):
            return
        try:
            AgentEnvelope.from_dict(payload, state.run_id)
        except ValueError as exc:
            execution.metadata = dict(execution.metadata or {})
            execution.metadata["terminal_payload_error"] = str(exc)
            # Bounded key names are structural evidence, not hidden reasoning
            # or model prose. They distinguish a malformed envelope from a
            # provider surfacing function-call arguments as assistant JSON.
            execution.metadata["terminal_payload_keys"] = sorted(
                str(key)[:120] for key in payload.keys()
            )[:40]
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def _heartbeat(self, state: RunState, event: dict) -> None:
        state.heartbeat_at = utc_now()
        state.heartbeat = dict(event or {})
        self.store.save(state)

    def _classify_hermes_failure(self, state: RunState, execution) -> RunState:
        error = (execution.error or "Hermes exited without a result").lower()
        evidence = {
            "returncode": execution.returncode,
            "execution": dict(execution.metadata or {}),
        }
        event_summary = evidence["execution"].get("event_summary") or {}
        handshake = event_summary.get("tool_handshake") or {}
        handshake_code = str(handshake.get("failure_code") or "")
        if handshake_code == "NATIVE_TOOL_UNAVAILABLE":
            return self._block(
                state,
                "HERMES_TOOL_UNAVAILABLE",
                "The live Hermes AIAgent did not expose openmontage_native.",
                "agent_contract",
                evidence,
            )
        if handshake_code == "NEMOTRON_TOOL_FLAGS_MISSING":
            return self._block(
                state,
                "HERMES_TOOL_CONTRACT_CONFIG_INVALID",
                "The final provider request is missing required model tool-parsing configuration.",
                "agent_contract",
                evidence,
            )
        if handshake_code == "INVALID_FINAL_PROVIDER_REQUEST":
            return self._block(
                state,
                "HERMES_TOOL_REQUEST_INVALID",
                "The final provider request did not preserve the named status-only native contract.",
                "agent_contract",
                evidence,
            )
        if handshake_code in {"INVALID_PROVIDER_TOOL_RESPONSE", "UNEXPECTED_INITIAL_TOOL"}:
            return self._block(
                state,
                "HERMES_TOOL_PROTOCOL_UNSUPPORTED",
                "The provider did not return one executable native status call.",
                "agent_contract",
                evidence,
            )
        if handshake_code:
            return self._block(
                state,
                "OPENMONTAGE_RUNTIME_UNAVAILABLE",
                "The real openmontage_native status handler did not complete successfully.",
                "agent_contract",
                evidence,
            )
        if any(token in error for token in (
            "api key", "credentials", "unauthorized", "authentication failed", " 401",
            " 403", "forbidden",
            "unknown provider", "provider not configured",
        )):
            return self._block(
                state,
                "HERMES_AUTH_REQUIRED",
                execution.error or "Hermes provider authentication is unavailable.",
                "agent",
                evidence,
            )
        if any(token in error for token in (
            "provider unavailable", "workers are busy", "timed out", "timeout", " 503",
        )):
            return self._block(
                state,
                "HERMES_PROVIDER_TRANSIENT",
                execution.error or "Hermes provider is temporarily unavailable.",
                "agent",
                evidence,
            )
        if any(token in error for token in (
            "rate limit", "too many requests", "quota", "resourceexhausted", " 429",
        )):
            return self._block(
                state,
                "HERMES_PROVIDER_RATE_LIMITED",
                execution.error or "Hermes provider rate limit is active.",
                "agent",
                evidence,
            )
        if "acd_hermes_tool_unavailable" in error:
            return self._block(
                state,
                "HERMES_TOOL_UNAVAILABLE",
                "The live Hermes AIAgent did not expose openmontage_native.",
                "agent_contract",
                evidence,
            )
        if "acd_hermes_tool_contract_config_invalid" in error:
            return self._block(
                state,
                "HERMES_TOOL_CONTRACT_CONFIG_INVALID",
                "The live provider request is missing required model tool-parsing configuration.",
                "agent_contract",
                evidence,
            )
        if "acd_hermes_tool_request_invalid" in error:
            return self._block(
                state,
                "HERMES_TOOL_REQUEST_INVALID",
                "The final provider request did not preserve the named status-only native contract.",
                "agent_contract",
                evidence,
            )
        if "acd_hermes_tool_handshake_failed" in error:
            return self._block(
                state,
                "HERMES_TOOL_PROTOCOL_UNSUPPORTED",
                "The required native status handshake failed in the pinned Hermes path.",
                "agent_contract",
                evidence,
            )
        return self._fail(state, "HERMES_EXECUTION_FAILED", execution.error or "Hermes execution failed", "agent", {"returncode": execution.returncode})

    def _problem_from_envelope(self, state: RunState, envelope: AgentEnvelope, blocked: bool) -> RunState:
        raw = envelope.blocker if blocked else envelope.error
        raw = raw or {}
        if blocked:
            return self._block(state, str(raw.get("code") or "AGENT_BLOCKED"), str(raw.get("message") or envelope.summary), str(raw.get("phase") or "agent"), raw.get("evidence") or {})
        return self._fail(state, str(raw.get("code") or "AGENT_FAILED"), str(raw.get("message") or envelope.summary), str(raw.get("phase") or "agent"), raw.get("evidence") or {})

    def _block(self, state: RunState, code: str, message: str, phase: str, evidence: Optional[dict] = None) -> RunState:
        state.blocker = RunProblem(code=code, message=message, phase=phase, evidence=evidence or {})
        if state.status not in TERMINAL_STATUSES:
            state.transition(RunStatus.BLOCKED)
        self.store.save(state)
        self.notifier.terminal(state)
        return state

    def _fail(self, state: RunState, code: str, message: str, phase: str, evidence: Optional[dict] = None) -> RunState:
        state.error = RunProblem(code=code, message=message, phase=phase, evidence=evidence or {})
        if state.status not in TERMINAL_STATUSES:
            state.transition(RunStatus.FAILED)
        self.store.save(state)
        self.notifier.terminal(state)
        return state
