from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acd_worker.hermes_runner import HermesRunner, HermesSessionResult
from acd_worker.compatibility import (
    CINEMATIC_PROPS_PATCH,
    PINNED_OPENMONTAGE_COMMIT,
    OpenMontageCompatibilityRegistry,
    RuntimeTuple,
)
from acd_worker.agent_contract import AgentEnvelope
from acd_worker.job_prompt import PRELOADED_SKILLS, build_job_prompt
from acd_worker.media_validation import FinalMediaValidator, OpenMontageArtifactValidator, REQUIRED_OPENMONTAGE_ARTIFACTS
from acd_worker.notifications import DiscordNotifier
from acd_worker.native_bridge import NativeExecutionBridge, NativeExecutionError, NativeExecutionRequest
from acd_worker.run_state import RunState, RunStateStore, RunStatus, utc_now
from acd_worker.source_service import SourceService, sanitize_reference
from acd_worker.thin_controller import ThinControllerConfig, ThinRunController


class FakeRunner:
    def __init__(self, root: Path, behavior):
        self.profile_dir = root / "hermes" / "profiles" / "football-emotion"
        for skill in PRELOADED_SKILLS:
            target = self.profile_dir / "skills" / "football-emotion-video" / "skills" / skill
            target.mkdir(parents=True, exist_ok=True)
            (target / "SKILL.md").write_text(f"---\nname: {skill}\ndescription: test\n---\n", encoding="utf-8")
        self.behavior = behavior
        self.calls = []

    def find_skill(self, name):
        matches = list((self.profile_dir / "skills").rglob(f"{name}/SKILL.md"))
        return matches[0] if matches else None

    def run_session(self, **kwargs):
        self.calls.append(kwargs)
        return self.behavior(kwargs)


def config_for(root: Path, dry_run: bool = False) -> ThinControllerConfig:
    om = root / "OpenMontage"
    om.mkdir(exist_ok=True)
    (om / "AGENT_GUIDE.md").write_text("native agent contract", encoding="utf-8")
    return ThinControllerConfig(
        worker_root=ROOT,
        hermes_home=root / "hermes",
        hermes_profile="football-emotion",
        hermes_cli=None,
        openmontage_root=om,
        projects_dir=om / "projects",
        state_dir=root / "state",
        dry_run=dry_run,
    )


class RunStateTests(unittest.TestCase):
    def test_macro_transitions_and_terminal_state(self):
        now = utc_now()
        state = RunState("1.0", "r1", "p1", "request", RunStatus.INTAKE, now, now, "/p", "/s", "/a", "/j")
        state.transition(RunStatus.SOURCE_READY)
        state.transition(RunStatus.AGENT_RUNNING)
        state.transition(RunStatus.FAILED)
        with self.assertRaises(ValueError):
            state.transition(RunStatus.INTAKE)

    def test_blocked_can_only_reenter_agent_running_transition(self):
        now = utc_now()
        state = RunState("1.0", "r1", "p1", "request", RunStatus.BLOCKED, now, now, "/p", "/s", "/a", "/j")
        state.transition(RunStatus.AGENT_RUNNING)
        with self.assertRaises(ValueError):
            state.transition(RunStatus.INTAKE)

    def test_store_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = utc_now()
            state = RunState("1.0", "resume_1", "p1", "request", RunStatus.INTAKE, now, now, "/p", "/s", "/a", "/j")
            store = RunStateStore(Path(tmp))
            store.save(state)
            self.assertEqual(store.load("resume_1").status, RunStatus.INTAKE)

    def test_store_lease_prevents_concurrent_run_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStateStore(Path(tmp))
            with store.lease("run-1"):
                with self.assertRaisesRegex(RuntimeError, "already owned"):
                    with store.lease("run-1"):
                        self.fail("second lease must not be acquired")


class CompatibilityTests(unittest.TestCase):
    def test_cinematic_remotion_requires_audited_patch(self):
        registry = OpenMontageCompatibilityRegistry(ROOT / "external" / "OpenMontage")
        runtime = RuntimeTuple("cinematic", "templated", "cinematic-trailer", "remotion")
        with (
            patch.object(registry, "_commit", return_value=PINNED_OPENMONTAGE_COMMIT),
            patch.object(registry, "_missing_runtime_capabilities", return_value=()),
            patch.object(registry, "_patches", return_value=set()),
        ):
            rejected = registry.evaluate(runtime)
        self.assertFalse(rejected.supported)
        self.assertEqual(rejected.required_patch, CINEMATIC_PROPS_PATCH)

        with (
            patch.object(registry, "_commit", return_value=PINNED_OPENMONTAGE_COMMIT),
            patch.object(registry, "_missing_runtime_capabilities", return_value=()),
            patch.object(registry, "_patches", return_value={CINEMATIC_PROPS_PATCH}),
        ):
            accepted = registry.evaluate(runtime)
        self.assertTrue(accepted.supported)


class PromptAndBoundaryTests(unittest.TestCase):
    def test_prompt_delegates_creative_and_native_pipeline(self):
        prompt = build_job_prompt(
            run_id="r1", project_id="p1", request="football emotion",
            worker_root=ROOT, openmontage_root=ROOT / "external" / "OpenMontage",
            project_dir=ROOT / "project", source_manifest_path=ROOT / "project" / "source.json",
            result_path=ROOT / "project" / "result.json",
            football_skill_root=ROOT / "skills" / "football-emotion-video",
        )
        for skill in ("Football Emotion Skill System", "hermes-football-memory-learning", "video_compose"):
            self.assertIn(skill, prompt)
        self.assertIn("Never invent a command or rebuild OpenMontage stages", prompt)
        self.assertIn("A technically valid fallback MP4 is not delivery", prompt)
        self.assertIn('"kind": "proposal_packet"', prompt)
        self.assertNotIn('"kind": "brief or proposal_packet according to selected pipeline"', prompt)
        self.assertIn('"status": "ready_for_execution|blocked|failed"', prompt)
        self.assertIn('"execution_request":', prompt)
        self.assertIn("Do not call `video_compose` yourself", prompt)
        self.assertIn("ToolResult` exposes `.success`, `.data`, `.artifacts`, `.error`", prompt)
        self.assertIn("do not invent, generate, analyze or probe `source.mp4`", prompt)
        self.assertIn("shared/...` inside any Football Emotion skill resolve from", prompt)
        self.assertNotIn("from tools.video.video_compose import video_compose", prompt)

    def test_production_entrypoint_has_no_legacy_orchestrator_import(self):
        tree = ast.parse((ROOT / "scripts" / "acd_worker.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
        joined = " ".join(imports)
        self.assertNotIn("acd_worker.orchestrator", joined)
        self.assertNotIn("openmontage_runner", joined)

    def test_source_manifest_keeps_mixed_inputs_and_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "clip.mp4"
            local.write_bytes(b"not claimed as valid media")
            path = root / "manifest.json"
            manifest = SourceService().prepare_manifest(path, [str(local), "https://example.com/video"])
            self.assertTrue(manifest["policy"]["free_only"])
            self.assertEqual([s["kind"] for s in manifest["sources"]], ["local_file", "url"])

    def test_source_reference_strips_credentials_but_keeps_video_id(self):
        cleaned = sanitize_reference("https://user:pass@example.com/watch?v=abc123&access_token=secret#fragment")
        self.assertEqual(cleaned, "https://example.com/watch?v=abc123")


class HermesRunnerTests(unittest.TestCase):
    def test_supported_profile_resume_and_skill_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cli = root / "hermes"
            cli.write_text("#!/bin/sh\n", encoding="utf-8")
            cli.chmod(0o755)
            profile = root / "home" / "profiles" / "football-emotion" / "skills" / "x"
            profile.mkdir(parents=True)
            completed = subprocess.CompletedProcess([], 0, stdout='{"status":"blocked"}\n', stderr="\nsession_id: 20260712_abc12345\n")
            runner = HermesRunner(str(root / "home"), hermes_cli=str(cli), cwd=root, max_turns=17)
            with patch("acd_worker.hermes_runner.subprocess.run", return_value=completed) as mocked:
                result = runner.run_session("prompt", session_id="old_session", expected_skills=["skill-a"], max_turns=9)
            command = mocked.call_args.args[0]
            self.assertEqual(command[:4], [str(cli), "-p", "football-emotion", "chat"])
            self.assertIn("--resume", command)
            self.assertIn("--skills", command)
            self.assertIn("--yolo", command)
            self.assertEqual(command[command.index("--max-turns") + 1], "9")
            self.assertEqual(mocked.call_args.kwargs["env"]["HERMES_HOME"], str(root / "home"))
            self.assertEqual(result.session_id, "20260712_abc12345")

    def test_explicit_model_override_precedes_chat_on_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cli = root / "hermes"
            cli.write_text("#!/bin/sh\n", encoding="utf-8")
            cli.chmod(0o755)
            (root / "home" / "profiles" / "football-emotion").mkdir(parents=True)
            completed = subprocess.CompletedProcess([], 0, stdout="", stderr="session_id: session_12345678\n")
            runner = HermesRunner(
                str(root / "home"),
                hermes_cli=str(cli),
                cwd=root,
                model_override="nvidia/nemotron-3-ultra-550b-a55b",
            )
            with patch("acd_worker.hermes_runner.subprocess.run", return_value=completed) as mocked:
                runner.run_session("continue", session_id="session_12345678")
            command = mocked.call_args.args[0]
            self.assertEqual(
                command[:6],
                [
                    str(cli), "-p", "football-emotion", "-m",
                    "nvidia/nemotron-3-ultra-550b-a55b", "chat",
                ],
            )
            self.assertEqual(command[command.index("--resume") + 1], "session_12345678")

    def test_session_log_diagnostic_surfaces_provider_capacity_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cli = root / "hermes"
            cli.write_text("#!/bin/sh\n", encoding="utf-8")
            cli.chmod(0o755)
            logs = root / "home" / "profiles" / "football-emotion" / "logs"
            logs.mkdir(parents=True)
            (logs / "errors.log").write_text(
                "ERROR [session_12345678] API call failed: ResourceExhausted: All workers are busy HTTP 503\n",
                encoding="utf-8",
            )
            completed = subprocess.CompletedProcess([], 1, stdout="", stderr="session_id: session_12345678\n")
            runner = HermesRunner(str(root / "home"), hermes_cli=str(cli), cwd=root)
            with patch("acd_worker.hermes_runner.subprocess.run", return_value=completed):
                result = runner.run_session("prompt")
            self.assertIn("ResourceExhausted", result.error)

    def test_provider_capacity_failure_is_structured_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)
            runner = FakeRunner(
                root,
                lambda _: HermesSessionResult(
                    success=False,
                    session_id="session_12345678",
                    returncode=1,
                    error="HTTP 503: ResourceExhausted: All workers are busy",
                ),
            )
            state = ThinRunController(cfg, runner=runner).start("test")
            self.assertEqual(state.status, RunStatus.BLOCKED)
            self.assertEqual(state.blocker.code, "HERMES_RUNTIME_UNAVAILABLE")

    def test_provider_authentication_failure_is_structured_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)
            runner = FakeRunner(
                root,
                lambda _: HermesSessionResult(
                    success=False,
                    session_id="session_12345678",
                    returncode=1,
                    error=(
                        "Error code: 401 - {'status': 401, 'title': 'Unauthorized', "
                        "'detail': 'Authentication failed'}"
                    ),
                ),
            )
            state = ThinRunController(cfg, runner=runner).start("test")
            self.assertEqual(state.status, RunStatus.BLOCKED)
            self.assertEqual(state.blocker.code, "HERMES_RUNTIME_UNAVAILABLE")
            self.assertIsNone(state.error)

    def test_transient_provider_blocker_requires_explicit_same_session_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)

            runner = FakeRunner(
                root,
                lambda _: HermesSessionResult(
                    success=False,
                    session_id="session_12345678",
                    returncode=1,
                    error="HTTP 429: Too Many Requests",
                ),
            )
            controller = ThinRunController(cfg, runner=runner)
            blocked = controller.start("test")
            self.assertEqual(blocked.status, RunStatus.BLOCKED)
            self.assertEqual(len(runner.calls), 1)

            unchanged = controller.resume(blocked.run_id)
            self.assertEqual(unchanged.status, RunStatus.BLOCKED)
            self.assertEqual(len(runner.calls), 1)

            retried = controller.resume(blocked.run_id, retry_blocked=True)
            self.assertEqual(retried.status, RunStatus.BLOCKED)
            self.assertEqual(len(runner.calls), 2)
            self.assertEqual(runner.calls[1]["session_id"], "session_12345678")
            self.assertIn("existing OpenMontage checkpoints", runner.calls[1]["prompt"])
            self.assertNotIn("USER REQUEST:", runner.calls[1]["prompt"])
            self.assertIn(
                {"from": "BLOCKED", "to": "AGENT_RUNNING"},
                [{"from": item["from"], "to": item["to"]} for item in retried.history],
            )

    def test_secret_redaction(self):
        token = "ghp" + "_abcdefghijk"
        redacted = HermesRunner._redact(f"api_key=supersecret authorization: Bearer tokenvalue {token}")
        self.assertNotIn("supersecret", redacted)
        self.assertNotIn("tokenvalue", redacted)
        self.assertNotIn(token, redacted)


class OptionalInfrastructureTests(unittest.TestCase):
    def test_discord_failure_is_non_fatal(self):
        notifier = DiscordNotifier("https://example.invalid/webhook", timeout=1)
        with patch("acd_worker.notifications.urllib.request.urlopen", side_effect=OSError("offline")):
            notifier._send("title", "description", 0)

    def test_fresh_hermes_install_tolerates_only_completed_postinstall_failure(self):
        installer = (ROOT / "bootstrap" / "install_hermes.sh").read_text(encoding="utf-8")
        self.assertIn('elif [[ -x "$HOME/.local/bin/hermes" ]]', installer)
        self.assertIn('exit 1', installer)

    def test_persistence_excludes_env_and_symlinks(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from kaggle_persistence import copy_tree

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            (source / "state.db").write_text("durable", encoding="utf-8")
            (source / ".env").write_text("SECRET=value", encoding="utf-8")
            (source / "link").symlink_to(source / "state.db")
            copy_tree(source, destination)
            self.assertTrue((destination / "state.db").is_file())
            self.assertFalse((destination / ".env").exists())
            self.assertFalse((destination / "link").exists())

    def test_persistence_uses_sqlite_backup_for_live_database(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from kaggle_persistence import copy_tree

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            database = source / "state.db"
            connection = sqlite3.connect(database)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE events(value TEXT)")
            connection.execute("INSERT INTO events VALUES ('durable')")
            connection.commit()
            copy_tree(source, destination)
            with sqlite3.connect(destination / "state.db") as snapshot:
                self.assertEqual(snapshot.execute("SELECT value FROM events").fetchone()[0], "durable")
            connection.close()

    def test_profile_configuration_never_writes_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "test-secret-value"
            environment = {
                **__import__("os").environ,
                "HERMES_HOME": str(root / "hermes"),
                "HERMES_PROFILE": "football-emotion",
                "LLM_BASE_URL": "https://free.example/v1",
                "LLM_MODEL": "free-model",
                "LLM_API_KEY": secret,
            }
            result = subprocess.run(
                [sys.executable, str(ROOT / "bootstrap" / "configure_hermes_profile.py")],
                env=environment, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0)
            config = (root / "hermes" / "profiles" / "football-emotion" / "config.yaml").read_text(encoding="utf-8")
            self.assertNotIn(secret, config)
            self.assertIn("key_env: LLM_API_KEY", config)
            self.assertIn("context_length: 65536", config)

    def test_ultra_profile_enables_native_thinking_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            environment = {
                **__import__("os").environ,
                "HERMES_HOME": str(root / "hermes"),
                "HERMES_PROFILE": "football-emotion",
                "LLM_BASE_URL": "https://integrate.api.nvidia.com/v1",
                "LLM_MODEL": "nvidia/nemotron-3-ultra-550b-a55b",
                "LLM_API_KEY": "test-secret-value",
            }
            result = subprocess.run(
                [sys.executable, str(ROOT / "bootstrap" / "configure_hermes_profile.py")],
                env=environment, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0)
            config = (root / "hermes" / "profiles" / "football-emotion" / "config.yaml").read_text(encoding="utf-8")
            self.assertIn("enable_thinking: true", config)
            self.assertIn("reasoning_budget: 16384", config)

    def test_candidate_validator_rejects_missing_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = subprocess.run([
                sys.executable,
                str(ROOT / "scripts" / "validate_delivery_candidate.py"),
                "--project-dir", str(root / "project"),
                "--openmontage-root", str(root / "OpenMontage"),
                "--result", str(root / "missing.json"),
                "--run-id", "run-1",
            ], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)["valid"])


class ControllerTests(unittest.TestCase):
    def test_ready_handoff_executes_bridge_before_delivery_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)

            def behavior(call):
                prompt = call["prompt"]
                result_path = Path(next(
                    line.split(":", 1)[1].strip()
                    for line in prompt.splitlines()
                    if line.startswith("- mandatory final result file:")
                ))
                run_id = next(line.split(":", 1)[1].strip() for line in prompt.splitlines() if line.startswith("RUN ID:"))
                result_path.write_text(json.dumps({
                    "schema_version": "1.0",
                    "run_id": run_id,
                    "status": "ready_for_execution",
                    "output_media": [],
                    "openmontage_artifacts": [],
                    "execution_request": {"pipeline": "cinematic", "artifacts": {}, "output_path": "unused"},
                    "source_requests": [],
                    "blocker": None,
                    "error": None,
                    "summary": "creative artifacts ready",
                }), encoding="utf-8")
                return HermesSessionResult(success=True, session_id="session_12345678", returncode=0)

            class FakeBridge:
                def prepare(self, request):
                    return request, {"runtime": {"renderer_family": "cinematic-trailer"}}, "fingerprint-1"

                def execute(self, request, heartbeat=None):
                    if heartbeat:
                        heartbeat({"event": "native_test"})
                    return SimpleNamespace(
                        output_media=[{"path": str(root / "render.mp4"), "sha256": "hash", "approved_silence": True}],
                        openmontage_artifacts=[{"kind": "render_report", "path": str(root / "render_report.json")}],
                        compatibility={"supported": True},
                        native_result={"status": "delivered"},
                    )

            controller = ThinRunController(cfg, runner=FakeRunner(root, behavior), native_bridge=FakeBridge())
            with (
                patch("acd_worker.thin_controller.OpenMontageArtifactValidator.validate", return_value={"valid": True}),
                patch("acd_worker.thin_controller.FinalMediaValidator.validate", return_value={"valid": True, "path": str(root / "render.mp4")}),
            ):
                state = controller.start("test")
            self.assertEqual(state.status, RunStatus.DELIVERED)
            self.assertEqual(state.native_execution["status"], "published")
            self.assertEqual(state.native_execution["fingerprint"], "fingerprint-1")
            self.assertEqual(state.heartbeat["event"], "native_test")

    def test_dry_run_is_blocked_not_delivered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root, dry_run=True)
            runner = FakeRunner(root, lambda _: self.fail("Hermes must not run in dry-run"))
            state = ThinRunController(cfg, runner=runner).start("test")
            self.assertEqual(state.status, RunStatus.BLOCKED)
            self.assertEqual(state.blocker.code, "DRY_RUN_ONLY")

    def test_zero_exit_without_result_file_reports_incomplete_native_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)
            runner = FakeRunner(root, lambda _: HermesSessionResult(success=True, session_id="session_12345678", returncode=0))
            state = ThinRunController(cfg, runner=runner).start("test")
            self.assertEqual(state.status, RunStatus.BLOCKED)
            self.assertEqual(state.blocker.code, "CREATIVE_HANDOFF_INCOMPLETE")
            self.assertEqual(len(runner.calls), 2)
            self.assertEqual(runner.calls[1]["session_id"], "session_12345678")
            self.assertEqual(runner.calls[1]["max_turns"], 60)
            self.assertIn("CONTINUATION SLICE: 1 of 1", runner.calls[1]["prompt"])

    def test_missing_result_gets_bounded_checkpoint_continuations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)

            def behavior(call):
                if len(runner.calls) == 1:
                    return HermesSessionResult(success=True, session_id="session_12345678", returncode=0)
                prompt = call["prompt"]
                self.assertIn("Do not repeat repository", prompt)
                self.assertIn("status: ready_for_execution", prompt)
                self.assertIn("Never invoke `math_animate`", prompt)
                self.assertIn("at most one corrected retry", prompt)
                self.assertIn("do not generate, redesign or compose anything", prompt)
                self.assertIn("CONTINUATION SLICE: 1 of 1", prompt)
                self.assertIn("final continuation slice", prompt)
                result_path = Path(next(
                    line.split(":", 1)[1].strip()
                    for line in prompt.splitlines()
                    if line.startswith("MANDATORY RESULT PATH:")
                ))
                result_path.write_text(json.dumps({
                    "schema_version": "1.0",
                    "run_id": next(line.split()[6] for line in prompt.splitlines() if line.startswith("Continue the same ACD production run")),
                    "status": "blocked",
                    "output_media": [],
                    "openmontage_artifacts": [],
                    "source_requests": [],
                    "blocker": {
                        "code": "NATIVE_PIPELINE_INCOMPLETE",
                        "message": "Bounded continuation could not finish the native render.",
                        "phase": "render",
                        "evidence": {},
                    },
                    "error": None,
                    "summary": "Honest bounded stop.",
                }), encoding="utf-8")
                return HermesSessionResult(success=True, session_id="session_12345678", returncode=0)

            runner = FakeRunner(root, behavior)
            state = ThinRunController(cfg, runner=runner).start("test")
            self.assertEqual(state.status, RunStatus.BLOCKED)
            self.assertEqual(state.blocker.code, "NATIVE_PIPELINE_INCOMPLETE")
            self.assertEqual(len(runner.calls), 2)

    def test_resume_counts_only_bounded_continuation_slices(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)
            now = utc_now()
            project = cfg.projects_dir / "football-resume"
            football = project / "football_emotion"
            football.mkdir(parents=True)
            prompt_path = football / "hermes_job_prompt.md"
            prompt_path.write_text("original prompt", encoding="utf-8")
            state = RunState(
                schema_version="1.0",
                run_id="resume-count",
                project_id="football-resume",
                request="test",
                status=RunStatus.AGENT_RUNNING,
                created_at=now,
                updated_at=now,
                project_dir=str(project),
                source_manifest_path=str(football / "source_manifest.json"),
                agent_result_path=str(football / "acd_agent_result.json"),
                prompt_path=str(prompt_path),
                hermes_session_id="session_12345678",
            )
            runner = FakeRunner(
                root,
                lambda _: HermesSessionResult(
                    success=True,
                    session_id="session_12345678",
                    returncode=0,
                ),
            )
            controller = ThinRunController(cfg, runner=runner)
            controller.store.save(state)

            resumed = controller.resume(state.run_id)

            self.assertEqual(resumed.status, RunStatus.BLOCKED)
            self.assertEqual(resumed.blocker.code, "CREATIVE_HANDOFF_INCOMPLETE")
            self.assertEqual(len(runner.calls), 1)
            self.assertIn("CONTINUATION SLICE: 1 of 1", runner.calls[0]["prompt"])
            self.assertNotEqual(runner.calls[0]["prompt"], "original prompt")

    def test_controller_reconciles_complete_native_artifacts_without_agent_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)

            def behavior(call):
                if "PROJECT ID:" in call["prompt"]:
                    project = cfg.projects_dir / next(
                        line.split(":", 1)[1].strip()
                        for line in call["prompt"].splitlines()
                        if line.startswith("PROJECT ID:")
                    )
                    artifacts = project / "artifacts"
                    artifacts.mkdir(parents=True, exist_ok=True)
                    (project / "project.json").write_text(json.dumps({"pipeline_type": "cinematic"}), encoding="utf-8")
                    for kind in ("proposal_packet", "scene_plan", "asset_manifest", "edit_decisions"):
                        payload = {"version": "1.0"}
                        if kind == "edit_decisions":
                            payload["metadata"] = {"output_profile": "generic_720p"}
                        (artifacts / f"{kind}.json").write_text(json.dumps(payload), encoding="utf-8")
                return HermesSessionResult(success=True, session_id="session_12345678", returncode=0)

            class FakeBridge:
                def prepare(self, request):
                    self.request = request
                    return SimpleNamespace(approved_silence=False), {"runtime": {}}, "fingerprint-reconciled"

                def execute(self, request, heartbeat=None):
                    return SimpleNamespace(
                        output_media=[{"path": str(root / "render.mp4"), "sha256": "hash", "approved_silence": False}],
                        openmontage_artifacts=[{"kind": "render_report", "path": str(root / "render_report.json")}],
                        compatibility={"supported": True},
                        native_result={"status": "delivered"},
                    )

            bridge = FakeBridge()
            controller = ThinRunController(cfg, runner=FakeRunner(root, behavior), native_bridge=bridge)
            with (
                patch("acd_worker.thin_controller.OpenMontageArtifactValidator.validate", return_value={"valid": True}),
                patch("acd_worker.thin_controller.FinalMediaValidator.validate", return_value={"valid": True}),
            ):
                state = controller.start("test")
            self.assertEqual(state.status, RunStatus.DELIVERED)
            self.assertEqual(bridge.request["pipeline"], "cinematic")
            self.assertEqual(bridge.request["output_profile"], "generic_720p")
            self.assertEqual(set(bridge.request["artifacts"]), {"proposal_packet", "scene_plan", "asset_manifest", "edit_decisions"})

    def test_ready_handoff_rejects_artifact_declaration_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)

            def behavior(call):
                prompt = call["prompt"]
                result_path = Path(next(line.split(":", 1)[1].strip() for line in prompt.splitlines() if line.startswith("- mandatory final result file:")))
                run_id = next(line.split(":", 1)[1].strip() for line in prompt.splitlines() if line.startswith("RUN ID:"))
                result_path.write_text(json.dumps({
                    "schema_version": "1.0", "run_id": run_id, "status": "ready_for_execution",
                    "output_media": [], "openmontage_artifacts": [],
                    "execution_request": {
                        "pipeline": "cinematic",
                        "artifacts": {"scene_plan": str(root / "scene_plan.json")},
                        "output_path": str(root / "renders" / "final.mp4"),
                    },
                }), encoding="utf-8")
                return HermesSessionResult(success=True, session_id="session_12345678", returncode=0)

            state = ThinRunController(cfg, runner=FakeRunner(root, behavior)).start("test")
            self.assertEqual(state.status, RunStatus.FAILED)
            self.assertEqual(state.error.code, "HANDOFF_ARTIFACT_MISMATCH")


class NativeBridgeContractTests(unittest.TestCase):
    def test_native_fingerprint_binds_media_bytes_not_only_manifest_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            artifacts = project / "artifacts"
            media = project / "assets" / "clip.mp4"
            artifacts.mkdir(parents=True)
            media.parent.mkdir(parents=True)
            media.write_bytes(b"first-media-version")
            manifest = artifacts / "asset_manifest.json"
            edit = artifacts / "edit_decisions.json"
            manifest.write_text(json.dumps({"assets": [{"id": "clip", "path": str(media)}]}), encoding="utf-8")
            edit.write_text(json.dumps({"cuts": [{"id": "c1", "source": "clip"}]}), encoding="utf-8")
            planning = artifacts / "proposal_packet.json"
            scene_plan = artifacts / "scene_plan.json"
            planning.write_text("{}", encoding="utf-8")
            scene_plan.write_text("{}", encoding="utf-8")
            request = NativeExecutionRequest.from_dict({
                "pipeline": "cinematic",
                "artifacts": {
                    "proposal_packet": str(planning),
                    "scene_plan": str(scene_plan),
                    "asset_manifest": str(manifest),
                    "edit_decisions": str(edit),
                },
                "output_path": str(project / "renders" / "final.mp4"),
            })
            paths = {
                "proposal_packet": planning,
                "scene_plan": scene_plan,
                "asset_manifest": manifest,
                "edit_decisions": edit,
            }
            bridge = NativeExecutionBridge(ROOT, ROOT / "external" / "OpenMontage", project)
            first = bridge._fingerprint(request, paths)
            media.write_bytes(b"second-media-version")
            second = bridge._fingerprint(request, paths)
            self.assertNotEqual(first, second)

    def test_checkpoint_approval_cannot_be_claimed_by_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge = NativeExecutionBridge(ROOT, ROOT / "external" / "OpenMontage", root / "project")
            request = NativeExecutionRequest.from_dict({
                "pipeline": "cinematic",
                "artifacts": {
                    "proposal_packet": str(root / "project/artifacts/proposal_packet.json"),
                    "scene_plan": str(root / "project/artifacts/scene_plan.json"),
                    "asset_manifest": str(root / "project/artifacts/asset_manifest.json"),
                    "edit_decisions": str(root / "project/artifacts/edit_decisions.json"),
                },
                "output_path": str(root / "project/renders/final.mp4"),
                "approved_checkpoints": [],
            })
            evidence = [{
                "stage": "proposal",
                "path": str(root / "project/checkpoint_proposal.json"),
                "status": "completed",
                "manifest_requires_approval": True,
                "human_approval_required": True,
                "human_approved": True,
            }]
            completed = SimpleNamespace(returncode=0, stdout=json.dumps(evidence), stderr="")
            with patch("acd_worker.native_bridge.subprocess.run", return_value=completed):
                with self.assertRaises(NativeExecutionError) as raised:
                    bridge._validate_checkpoint_contract(request, {
                        "proposal_packet": root / "project/artifacts/proposal_packet.json",
                    })
            self.assertEqual(raised.exception.code, "UNAPPROVED_CHECKPOINT")

    def test_checkpoint_manifest_gate_cannot_be_suppressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge = NativeExecutionBridge(ROOT, ROOT / "external" / "OpenMontage", root / "project")
            request = NativeExecutionRequest.from_dict({
                "pipeline": "cinematic",
                "artifacts": {
                    "proposal_packet": "proposal_packet.json",
                    "scene_plan": "scene_plan.json",
                    "asset_manifest": "asset_manifest.json",
                    "edit_decisions": "edit_decisions.json",
                },
                "output_path": str(root / "project/renders/final.mp4"),
                "approved_checkpoints": ["proposal"],
            })
            evidence = [{
                "stage": "proposal", "status": "completed",
                "manifest_requires_approval": True,
                "human_approval_required": False,
                "human_approved": True,
            }]
            completed = SimpleNamespace(returncode=0, stdout=json.dumps(evidence), stderr="")
            with patch("acd_worker.native_bridge.subprocess.run", return_value=completed):
                with self.assertRaises(NativeExecutionError) as raised:
                    bridge._validate_checkpoint_contract(request, {"proposal_packet": Path("proposal_packet.json")})
            self.assertEqual(raised.exception.code, "NATIVE_CHECKPOINT_INVALID")

    def test_silent_edit_requires_typed_plan_before_runtime_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            artifacts = project / "artifacts"
            artifacts.mkdir(parents=True)
            for kind in ("proposal_packet", "scene_plan", "asset_manifest"):
                (artifacts / f"{kind}.json").write_text(json.dumps({"version": "1.0"}), encoding="utf-8")
            edit = artifacts / "edit_decisions.json"
            edit.write_text(json.dumps({"version": "1.0", "cuts": [], "render_runtime": "remotion"}), encoding="utf-8")
            request = {
                "pipeline": "cinematic",
                "artifacts": {kind: str(artifacts / f"{kind}.json") for kind in ("proposal_packet", "scene_plan", "asset_manifest", "edit_decisions")},
                "output_path": str(project / "renders" / "final.mp4"),
                "approved_silence": False,
            }
            bridge = NativeExecutionBridge(ROOT, ROOT / "external" / "OpenMontage", project)
            with self.assertRaises(NativeExecutionError) as raised:
                bridge.prepare(request)
            self.assertEqual(raised.exception.code, "UNAPPROVED_SILENCE_PLAN")

    def test_legacy_flat_blocker_is_safely_normalized(self):
        envelope = AgentEnvelope.from_dict({
            "run_id": "run-1",
            "status": "blocked",
            "blocker_code": "NATIVE_PIPELINE_TURN_BUDGET_EXHAUSTED",
            "last_valid_artifact": "proposal_packet",
            "last_valid_stage": "proposal",
            "missing_native_stages": ["scene_plan", "assets", "edit"],
            "note": "Native pipeline remains incomplete.",
        }, "run-1")
        self.assertEqual(envelope.schema_version, "1.0")
        self.assertEqual(envelope.output_media, [])
        self.assertEqual(envelope.blocker["code"], "NATIVE_PIPELINE_TURN_BUDGET_EXHAUSTED")
        self.assertEqual(envelope.blocker["phase"], "proposal")
        self.assertEqual(
            envelope.blocker["evidence"]["missing_native_stages"],
            ["scene_plan", "assets", "edit"],
        )

    def test_delivered_envelope_remains_strict(self):
        with self.assertRaisesRegex(ValueError, "Delivered agent result missing fields"):
            AgentEnvelope.from_dict({
                "run_id": "run-1",
                "status": "delivered",
            }, "run-1")

    def test_legacy_agent_delivery_cannot_bypass_native_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)

            def behavior(call):
                result_path = Path(next(
                    line.split(":", 1)[1].strip()
                    for line in call["prompt"].splitlines()
                    if line.startswith("- mandatory final result file:")
                ))
                output = result_path.parent.parent / "renders" / "final.mp4"
                output.parent.mkdir(parents=True)
                output.write_bytes(b"candidate")
                run_id = next(
                    line.split(":", 1)[1].strip()
                    for line in call["prompt"].splitlines()
                    if line.startswith("RUN ID:")
                )
                result_path.write_text(json.dumps({
                    "schema_version": "1.0",
                    "run_id": run_id,
                    "status": "delivered",
                    "output_media": [{"path": str(output), "role": "primary"}],
                    "openmontage_artifacts": [],
                    "source_requests": [],
                    "blocker": None,
                    "error": None,
                    "summary": "candidate",
                }), encoding="utf-8")
                return HermesSessionResult(success=True, session_id="session_12345678", returncode=0)

            runner = FakeRunner(root, behavior)
            state = ThinRunController(cfg, runner=runner).start("test")
            self.assertEqual(state.status, RunStatus.FAILED)
            self.assertEqual(state.error.code, "LEGACY_DELIVERY_UNSUPPORTED")
            self.assertEqual(state.validation, [])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required")
    def test_real_ffprobe_media_passes_independent_validator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "renders" / "final.mp4"
            output.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=1",
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output),
            ], capture_output=True, check=True)
            evidence = FinalMediaValidator(root).validate({
                "path": str(output),
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "approved_silence": True,
            })
            self.assertTrue(evidence["valid"])

    def test_fake_mp4_bytes_cannot_deliver(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            fake = project / "final.mp4"
            fake.write_bytes(b"fake mp4 fixture")
            evidence = FinalMediaValidator(project).validate({"path": str(fake)})
            self.assertFalse(evidence["valid"])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required")
    def test_solid_colour_video_is_not_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            output = project / "blank.mp4"
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=darkblue:s=320x180:d=1",
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output),
            ], capture_output=True, check=True)
            evidence = FinalMediaValidator(project).validate({
                "path": str(output),
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "approved_silence": True,
            })
            self.assertFalse(evidence["valid"])
            self.assertTrue(evidence["visually_blank"])


class NativeArtifactValidationTests(unittest.TestCase):
    def test_agent_result_cannot_impersonate_as_render_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            result = project / "agent_result.json"
            result.write_text("{}", encoding="utf-8")
            evidence = OpenMontageArtifactValidator(project, root / "OpenMontage", result).validate(
                [{"kind": "render_report", "path": str(result)}],
                [{"path": str(project / "renders" / "final.mp4")}],
            )
            self.assertFalse(evidence["valid"])
            self.assertIn("worker agent result", evidence["artifacts"][0]["error"])

    def test_schema_valid_native_artifact_chain_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            artifacts_dir = project / "artifacts"
            renders = project / "renders"
            schemas = root / "OpenMontage" / "schemas" / "artifacts"
            artifacts_dir.mkdir(parents=True)
            renders.mkdir(parents=True)
            schemas.mkdir(parents=True)
            output = renders / "final.mp4"
            output.write_bytes(b"media is validated separately")
            output_hash = hashlib.sha256(output.read_bytes()).hexdigest()
            result_path = project / "football_emotion" / "agent_result.json"

            payloads = {kind: {"version": "1.0"} for kind in REQUIRED_OPENMONTAGE_ARTIFACTS}
            payloads["brief"] = {"version": "1.0"}
            payloads["render_report"] = {
                "version": "1.0",
                "outputs": [{"path": str(output)}],
                "final_review_ref": str(artifacts_dir / "final_review.json"),
                "render_grammar": "documentary-montage",
                "metadata": {"output_sha256": output_hash},
            }
            payloads["edit_decisions"] = {
                "version": "1.0",
                "render_runtime": "remotion",
                "renderer_family": "documentary-montage",
            }
            payloads["final_review"] = {
                "version": "1.0",
                "output_path": str(output),
                "status": "pass",
                "recommended_action": "present_to_user",
                "checks": {
                    "visual_spotcheck": {
                        "frames_sampled": 4,
                        "black_frames_detected": False,
                        "broken_overlays": False,
                        "missing_assets": False,
                        "unreadable_text": False,
                    },
                    "promise_preservation": {
                        "delivery_promise_honored": True,
                        "render_runtime_used": "remotion",
                        "runtime_swap_detected": False,
                        "silent_downgrade_detected": False,
                    },
                },
                "metadata": {"output_sha256": output_hash},
            }
            declared = []
            for kind, payload in payloads.items():
                path = artifacts_dir / f"{kind}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                (schemas / f"{kind}.schema.json").write_text(json.dumps({"type": "object"}), encoding="utf-8")
                declared.append({"kind": kind, "path": str(path)})

            validator = OpenMontageArtifactValidator(project, root / "OpenMontage", result_path)
            with patch.object(validator, "_schema_error", return_value=""):
                evidence = validator.validate(declared, [{"path": str(output), "sha256": output_hash}])
            self.assertTrue(evidence["valid"], evidence)

    def test_cross_artifact_missing_asset_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            artifacts = project / "artifacts"
            assets = project / "assets"
            artifacts.mkdir(parents=True)
            assets.mkdir()
            present = assets / "present.webm"
            present.write_bytes(b"valid-media-placeholder")
            manifest_path = artifacts / "asset_manifest.json"
            manifest_path.write_text(json.dumps({
                "version": "1.0",
                "assets": [{"id": "present", "path": "assets/present.webm"}],
            }), encoding="utf-8")
            edit_path = artifacts / "edit_decisions.json"
            edit_path.write_text(json.dumps({
                "version": "1.0",
                "render_runtime": "remotion",
                "cuts": [
                    {"id": "c1", "source": "present", "in_seconds": 0, "out_seconds": 1},
                    {"id": "c2", "source": "deleted-background", "in_seconds": 1, "out_seconds": 2},
                ],
            }), encoding="utf-8")
            validator = OpenMontageArtifactValidator(
                project,
                root / "OpenMontage",
                project / "football_emotion" / "agent_result.json",
            )

            errors = validator._cross_artifact_errors({
                "asset_manifest": manifest_path,
                "edit_decisions": edit_path,
            })

            self.assertEqual(len(errors), 1)
            self.assertIn("deleted-background", errors[0])

    def test_cross_artifact_existing_manifest_reference_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            artifacts = project / "artifacts"
            assets = project / "assets"
            artifacts.mkdir(parents=True)
            assets.mkdir()
            present = assets / "present.webm"
            present.write_bytes(b"valid-media-placeholder")
            manifest_path = artifacts / "asset_manifest.json"
            manifest_path.write_text(json.dumps({
                "version": "1.0",
                "assets": [{"id": "present", "path": "assets/present.webm"}],
            }), encoding="utf-8")
            edit_path = artifacts / "edit_decisions.json"
            edit_path.write_text(json.dumps({
                "version": "1.0",
                "render_runtime": "remotion",
                "cuts": [{"id": "c1", "source": "present", "in_seconds": 0, "out_seconds": 1}],
            }), encoding="utf-8")
            validator = OpenMontageArtifactValidator(
                project,
                root / "OpenMontage",
                project / "football_emotion" / "agent_result.json",
            )

            errors = validator._cross_artifact_errors({
                "asset_manifest": manifest_path,
                "edit_decisions": edit_path,
            })

            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
