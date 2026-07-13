"""Thin macro-state controller delegating creative work to Hermes/OpenMontage."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .agent_contract import AgentEnvelope, load_agent_envelope
from .hermes_runner import HermesRunner
from .job_prompt import PRELOADED_SKILLS, build_job_prompt
from .media_validation import FinalMediaValidator, OpenMontageArtifactValidator
from .notifications import DiscordNotifier
from .run_state import RunProblem, RunState, RunStateStore, RunStatus, TERMINAL_STATUSES, utc_now
from .source_service import SourceService, sanitize_reference


class EnvironmentBlocker(RuntimeError):
    pass


@dataclass
class ThinControllerConfig:
    worker_root: Path
    hermes_home: Path
    hermes_profile: str
    hermes_cli: Optional[str]
    openmontage_root: Path
    projects_dir: Path
    state_dir: Path
    hermes_timeout: int = 3600
    hermes_max_turns: int = 60
    hermes_recovery_max_turns: int = 30
    hermes_headless_auto_approve: bool = True
    discord_webhook_url: str = ""
    dry_run: bool = False


class ThinRunController:
    def __init__(
        self,
        config: ThinControllerConfig,
        *,
        runner: Optional[HermesRunner] = None,
        source_service: Optional[SourceService] = None,
        notifier: Optional[DiscordNotifier] = None,
    ):
        self.config = config
        self.store = RunStateStore(config.state_dir)
        self.source_service = source_service or SourceService()
        self.notifier = notifier or DiscordNotifier(config.discord_webhook_url)
        self.runner = runner or HermesRunner(
            hermes_home=str(config.hermes_home),
            profile=config.hermes_profile,
            hermes_cli=config.hermes_cli,
            timeout=config.hermes_timeout,
            cwd=config.openmontage_root,
            max_turns=config.hermes_max_turns,
            headless_auto_approve=config.hermes_headless_auto_approve,
        )
        self.log = logging.getLogger("acd_worker.thin_controller")

    def start(self, request: str, input_references: Iterable[str] = ()) -> RunState:
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
        )
        self.store.save(state)
        self.notifier.started(state)
        return self._continue(state)

    def resume(self, run_id: str) -> RunState:
        state = self.store.load(run_id)
        if state.status in TERMINAL_STATUSES:
            return state
        return self._continue(state)

    def _continue(self, state: RunState) -> RunState:
        agent_invoked = False
        try:
            if state.status == RunStatus.INTAKE:
                self.source_service.prepare_manifest(Path(state.source_manifest_path), state.input_references)
                state.transition(RunStatus.SOURCE_READY)
                self.store.save(state)

            if state.status == RunStatus.SOURCE_READY:
                self._preflight(state)
                prompt = build_job_prompt(
                    run_id=state.run_id,
                    project_id=state.project_id,
                    request=state.request,
                    worker_root=self.config.worker_root.resolve(),
                    openmontage_root=self.config.openmontage_root.resolve(),
                    project_dir=Path(state.project_dir).resolve(),
                    source_manifest_path=Path(state.source_manifest_path).resolve(),
                    result_path=Path(state.agent_result_path).resolve(),
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
                execution = self.runner.run_session(
                    prompt=prompt,
                    session_id=state.hermes_session_id,
                    expected_skills=list(PRELOADED_SKILLS),
                )
                agent_invoked = True
                if execution.session_id:
                    state.hermes_session_id = execution.session_id
                    self.store.save(state)
                if not execution.success:
                    return self._classify_hermes_failure(state, execution)

            if state.status == RunStatus.AGENT_RUNNING:
                result_path = Path(state.agent_result_path)
                if not result_path.is_file() and not agent_invoked:
                    prompt_path = Path(state.prompt_path)
                    if not prompt_path.is_file():
                        return self._fail(state, "PROMPT_MISSING", "Cannot resume because the persisted Hermes job prompt is missing.", "agent")
                    execution = self.runner.run_session(
                        prompt=prompt_path.read_text(encoding="utf-8"),
                        session_id=state.hermes_session_id,
                        expected_skills=list(PRELOADED_SKILLS),
                    )
                    agent_invoked = True
                    if execution.session_id:
                        state.hermes_session_id = execution.session_id
                        self.store.save(state)
                    if not execution.success:
                        return self._classify_hermes_failure(state, execution)

                # Pinned Hermes exits zero after its iteration-limit summary,
                # but that final summary call has tools disabled. If the agent
                # reached that boundary before writing the required envelope,
                # give the same session one bounded continuation. This is a
                # control-plane protocol recovery, not another creative stage
                # machine: Hermes retains its history and decides how to finish
                # the native OpenMontage work (or report a blocker) itself.
                if not result_path.is_file():
                    recovery = self.runner.run_session(
                        prompt=self._result_recovery_prompt(state),
                        session_id=state.hermes_session_id,
                        expected_skills=[],
                        max_turns=self.config.hermes_recovery_max_turns,
                    )
                    if recovery.session_id:
                        state.hermes_session_id = recovery.session_id
                        self.store.save(state)
                    if not recovery.success:
                        return self._classify_hermes_failure(state, recovery)
                    if not result_path.is_file():
                        return self._fail(
                            state,
                            "HERMES_RESULT_MISSING",
                            "Hermes exited successfully twice without writing the mandatory result contract.",
                            "agent",
                            {
                                "session_id": state.hermes_session_id,
                                "continuation_attempted": True,
                                "recovery_max_turns": self.config.hermes_recovery_max_turns,
                            },
                        )
                envelope = load_agent_envelope(Path(state.agent_result_path), state.run_id)
                state.output_candidates = envelope.output_media
                state.openmontage_artifacts = envelope.openmontage_artifacts
                if envelope.status == "blocked":
                    return self._problem_from_envelope(state, envelope, blocked=True)
                if envelope.status == "failed":
                    return self._problem_from_envelope(state, envelope, blocked=False)
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
                self.store.save(state)
                if not state.artifact_validation.get("valid"):
                    return self._fail(
                        state,
                        "OPENMONTAGE_ARTIFACT_VALIDATION_FAILED",
                        "Hermes claimed delivery without schema-valid native OpenMontage artifacts and review evidence.",
                        "validation",
                        state.artifact_validation,
                    )
                validator = FinalMediaValidator(Path(state.project_dir))
                state.validation = [validator.validate(candidate) for candidate in state.output_candidates]
                self.store.save(state)
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
            return self._block(state, "RUNTIME_PREREQUISITE_MISSING", str(exc), state.status.value.lower())
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

    def _result_recovery_prompt(self, state: RunState) -> str:
        return f"""Continue the same ACD production run {state.run_id} from the existing workspace.

MANDATORY RESULT PATH: {state.agent_result_path}

Do not repeat repository, skill, pipeline, or capability discovery already completed in this session. Inspect the work and canonical artifacts already present under {state.project_dir}, then complete only the remaining native OpenMontage steps.

You have a bounded continuation of {self.config.hermes_recovery_max_turns} tool-calling turns. Reserve enough turns to write the mandatory result contract at {state.agent_result_path}. If a genuine schema-valid native render and review cannot be completed within this continuation, stop production work and write an honest `blocked` or `failed` result contract with actionable evidence. Never substitute a direct FFmpeg/helper render, never invent artifacts, and never claim delivery without the required native evidence.

Before ending, write the result JSON file. Printing JSON without writing that file is not completion.
"""

    def _classify_hermes_failure(self, state: RunState, execution) -> RunState:
        error = (execution.error or "Hermes exited without a result").lower()
        if any(token in error for token in ("api key", "credentials", "provider", "rate limit", "quota", "resourceexhausted", "workers are busy", " 503")):
            return self._block(state, "HERMES_RUNTIME_UNAVAILABLE", execution.error or "Hermes runtime unavailable", "agent", {"returncode": execution.returncode})
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
