from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sqlite3
import sys
import tempfile
import types
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
from acd_worker.run_state import RunProblem, RunState, RunStateStore, RunStatus, utc_now
from acd_worker.source_service import SourceService, sanitize_reference
from acd_worker.thin_controller import ThinControllerConfig, ThinRunController


class FakeRunner:
    def __init__(self, root: Path, behavior, *, autocertify: bool = True):
        self.profile_dir = root / "hermes" / "profiles" / "football-emotion"
        for skill in PRELOADED_SKILLS:
            target = self.profile_dir / "skills" / "football-emotion-video" / "skills" / skill
            target.mkdir(parents=True, exist_ok=True)
            (target / "SKILL.md").write_text(f"---\nname: {skill}\ndescription: test\n---\n", encoding="utf-8")
        plugin = self.profile_dir / "plugins" / "acd-openmontage"
        plugin.mkdir(parents=True, exist_ok=True)
        (plugin / "plugin.yaml").write_text("name: acd-openmontage\n", encoding="utf-8")
        (plugin / "__init__.py").write_text("def register(ctx): pass\n", encoding="utf-8")
        self.behavior = behavior
        self.autocertify = autocertify
        self.calls = []

    def find_skill(self, name):
        matches = list((self.profile_dir / "skills").rglob(f"{name}/SKILL.md"))
        return matches[0] if matches else None

    def run_session(self, **kwargs):
        self.calls.append(kwargs)
        result = self.behavior(kwargs)
        environment = kwargs.get("environment") or {}
        required = environment.get("ACD_FORCE_INITIAL_OPENMONTAGE_TOOL") == "1"
        if self.autocertify and result.success and required:
            result.metadata = dict(result.metadata or {})
            result.metadata.update({
                "event_adapter_used": True,
                "tool_contract_requested": True,
                "tool_contract_id": environment.get("ACD_HERMES_TOOL_CONTRACT_ID"),
            })
            summary = dict(result.metadata.get("event_summary") or {})
            summary.setdefault("events", {
                "tool_handshake_started": 1,
                "tool_handshake_completed": 1,
            })
            summary.setdefault("agent_contract", {
                "has_openmontage_native": True,
                "has_acd_acquire_source": True,
                "provider": "custom:acd-free",
                "model": "test-model",
            })
            request = {
                "handshake_request": True,
                "tool_count": 1,
                "tools": "openmontage_native",
                "status_only": True,
                "tool_choice_mode": "named",
                "tool_choice_name": "openmontage_native",
                "model": "test-model",
            }
            summary.setdefault("request_contract", request)
            summary.setdefault("first_request_contract", request)
            summary.setdefault("first_response_contract", {
                "tool_call_count": 1,
                "tool_call_names": "openmontage_native",
                "status_operation": True,
                "finish_reason": "tool_calls",
            })
            summary.setdefault("tool_handshake", {
                "required": True,
                "started": True,
                "completed": True,
                "failed": False,
                "result_success": True,
            })
            result.metadata["event_summary"] = summary
        return result


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
            state.hermes_tool_contract = {
                "schema_version": "1.0",
                "status": "passed",
                "contract_id": "contract-1",
            }
            store = RunStateStore(Path(tmp))
            store.save(state)
            restored = store.load("resume_1")
            self.assertEqual(restored.status, RunStatus.INTAKE)
            self.assertEqual(restored.hermes_tool_contract["contract_id"], "contract-1")

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
    def test_production_resource_defaults_match_bounded_runbook(self):
        from scripts.acd_worker import ACDConfig

        with patch.dict(os.environ, {}, clear=True):
            runtime = ACDConfig.from_env()
        self.assertEqual(runtime.hermes_timeout, 480)
        self.assertEqual(runtime.hermes_max_turns, 20)
        self.assertEqual(runtime.hermes_recovery_max_turns, 12)
        self.assertEqual(runtime.hermes_max_continuations, 1)
        self.assertEqual(runtime.native_execution_timeout, 480)

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
        self.assertIn('openmontage_native(operation="status"', prompt)
        self.assertIn('openmontage_native(operation="publish_artifact"', prompt)
        self.assertIn("acd_acquire_source", prompt)
        self.assertIn("terminal, execute_code", prompt)
        self.assertIn("do not invent, generate, analyze or probe `source.mp4`", prompt)
        self.assertIn("canonical `shared/...` paths still resolve from", prompt)
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
            for source in manifest["sources"]:
                self.assertIn("availability_status", source)
                self.assertIn("technical_verification_status", source)
                self.assertIn("rights_status", source)
                self.assertEqual(source["rights_evidence"], [])
                self.assertNotIn("status", source)

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
            self.assertNotIn("--yolo", command)
            toolsets = command[command.index("--toolsets") + 1].split(",")
            self.assertIn("acd-openmontage", toolsets)
            self.assertNotIn("terminal", toolsets)
            self.assertNotIn("file", toolsets)
            self.assertNotIn("code_execution", toolsets)
            self.assertEqual(command[command.index("--max-turns") + 1], "9")
            self.assertEqual(mocked.call_args.kwargs["env"]["HERMES_HOME"], str(root / "home"))
            self.assertEqual(result.session_id, "20260712_abc12345")

    def test_runtime_environment_is_scoped_into_plugin_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cli = root / "hermes"
            cli.write_text("#!/bin/sh\n", encoding="utf-8")
            cli.chmod(0o755)
            (root / "home" / "profiles" / "football-emotion").mkdir(parents=True)
            (root / "project").mkdir()
            completed = subprocess.CompletedProcess([], 0, stdout="", stderr="session_id: session_12345678\n")
            runner = HermesRunner(str(root / "home"), hermes_cli=str(cli), cwd=root)
            with patch("acd_worker.hermes_runner.subprocess.run", return_value=completed) as mocked:
                runner.run_session("prompt", environment={"ACD_RUN_ID": "run-1", "ACD_PROJECT_DIR": root / "project"})
            environment = mocked.call_args.kwargs["env"]
            self.assertEqual(environment["ACD_RUN_ID"], "run-1")
            self.assertEqual(environment["ACD_PROJECT_DIR"], str(root / "project"))
            self.assertEqual(mocked.call_args.kwargs["cwd"], str((root / "project").resolve()))

    def test_terminal_payload_requires_one_exact_json_object(self):
        payload = {"schema_version": "1.0", "run_id": "run-1", "status": "blocked"}
        self.assertEqual(HermesRunner._extract_terminal_payload(json.dumps(payload)), payload)
        self.assertEqual(
            HermesRunner._extract_terminal_payload(f"```json\n{json.dumps(payload)}\n```"),
            payload,
        )
        self.assertIsNone(HermesRunner._extract_terminal_payload("prose\n" + json.dumps(payload)))

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
            self.assertEqual(state.blocker.code, "HERMES_PROVIDER_TRANSIENT")

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
            self.assertEqual(state.blocker.code, "HERMES_AUTH_REQUIRED")
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
            self.assertEqual(blocked.blocker.code, "HERMES_PROVIDER_RATE_LIMITED")
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

    def test_runtime_change_blocks_old_session_until_explicit_restart(self):
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
            Path(blocked.agent_result_path).write_text(
                json.dumps({"status": "blocked", "run_id": blocked.run_id}),
                encoding="utf-8",
            )
            plugin = runner.profile_dir / "plugins" / "acd-openmontage" / "__init__.py"
            plugin.write_text("def register(ctx):\n    return 'changed'\n", encoding="utf-8")

            changed = controller.resume(blocked.run_id, retry_blocked=True)
            self.assertEqual(changed.blocker.code, "HERMES_SESSION_RUNTIME_CHANGED")
            self.assertEqual(len(runner.calls), 1)

            restarted = controller.resume(
                blocked.run_id,
                retry_blocked=True,
                restart_hermes_session=True,
            )
            self.assertEqual(restarted.blocker.code, "HERMES_PROVIDER_RATE_LIMITED")
            self.assertEqual(restarted.hermes_session_generation, 1)
            self.assertEqual(len(runner.calls), 2)
            self.assertIsNone(runner.calls[-1]["session_id"])
            self.assertFalse(Path(restarted.agent_result_path).exists())

    def test_authentication_blocker_is_not_retryable_without_configuration_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)
            runner = FakeRunner(
                root,
                lambda _: HermesSessionResult(
                    success=False,
                    session_id="session_12345678",
                    returncode=1,
                    error="HTTP 401: Unauthorized",
                ),
            )
            controller = ThinRunController(cfg, runner=runner)
            blocked = controller.start("test")
            retried = controller.resume(blocked.run_id, retry_blocked=True)
            self.assertEqual(retried.blocker.code, "HERMES_AUTH_REQUIRED")
            self.assertEqual(len(runner.calls), 1)

    def test_secret_redaction(self):
        token = "ghp" + "_abcdefghijk"
        redacted = HermesRunner._redact(f"api_key=supersecret authorization: Bearer tokenvalue {token}")
        self.assertNotIn("supersecret", redacted)
        self.assertNotIn("tokenvalue", redacted)
        self.assertNotIn(token, redacted)


class OptionalInfrastructureTests(unittest.TestCase):
    def test_event_adapter_bootstraps_named_profile_before_run_agent_import(self):
        """The live agent must load config and plugins from its named profile."""
        adapter = ROOT / "scripts" / "hermes_event_adapter.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_modules = root / "fake-modules"
            package = fake_modules / "hermes_cli"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "main.py").write_text(
                "import os, sys\n"
                "from pathlib import Path\n"
                "index = sys.argv.index('-p')\n"
                "name = sys.argv[index + 1]\n"
                "os.environ['HERMES_HOME'] = str(Path(os.environ['HERMES_HOME']) / 'profiles' / name)\n"
                "def main(): return 0\n",
                encoding="utf-8",
            )
            (fake_modules / "run_agent.py").write_text(
                "import os\n"
                "from pathlib import Path\n"
                "Path(os.environ['ACD_IMPORT_ORDER_PROBE']).write_text(os.environ.get('HERMES_HOME', ''), encoding='utf-8')\n"
                "class AIAgent:\n"
                "    def __init__(self, **kwargs): pass\n",
                encoding="utf-8",
            )
            event_file = root / "events.jsonl"
            probe = root / "profile-seen-by-run-agent.txt"
            hermes_root = root / "hermes-home"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(adapter),
                    "--event-file",
                    str(event_file),
                    "-p",
                    "football-emotion",
                    "chat",
                ],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PYTHONPATH": str(fake_modules),
                    "HERMES_HOME": str(hermes_root),
                    "ACD_IMPORT_ORDER_PROBE": str(probe),
                },
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                probe.read_text(encoding="utf-8"),
                str(hermes_root / "profiles" / "football-emotion"),
            )

    def test_hermes_event_adapter_preserves_aiagent_class_contract(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from hermes_event_adapter import instrument_run_agent

        received = {}

        class FakeAgent:
            _TOOL_CALL_ARGUMENTS_CORRUPTION_MARKER = "marker"

            @staticmethod
            def _get_tool_call_id_static(_tool_call):
                return "call-1"

            def __init__(self, **kwargs):
                received.update(kwargs)

        class Sink:
            progress = object()
            start = object()
            complete = object()
            step = object()
            status = object()
            event = object()

            def emit(self, event, **_fields):
                received["emitted"] = event

        module = SimpleNamespace(AIAgent=FakeAgent)
        original_class = module.AIAgent
        installed = instrument_run_agent(module, Sink())

        self.assertIs(installed, original_class)
        self.assertIs(module.AIAgent, original_class)
        self.assertEqual(module.AIAgent._TOOL_CALL_ARGUMENTS_CORRUPTION_MARKER, "marker")
        self.assertEqual(module.AIAgent._get_tool_call_id_static({}), "call-1")
        module.AIAgent()
        self.assertEqual(received["emitted"], "agent_created")
        for key in (
            "tool_progress_callback", "tool_start_callback", "tool_complete_callback",
            "step_callback", "status_callback", "event_callback",
        ):
            self.assertIn(key, received)

    def test_hermes_event_adapter_captures_only_exact_final_response(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from hermes_event_adapter import EventSink, instrument_run_agent

        payload = {
            "schema_version": "1.0",
            "run_id": "run-1",
            "status": "blocked",
            "output_media": [],
            "openmontage_artifacts": [],
            "source_requests": [],
            "blocker": {
                "code": "TEST_BLOCKER",
                "message": "contract test",
                "phase": "agent",
                "evidence": {},
            },
            "error": None,
            "summary": "contract test",
        }

        class FakeAgent:
            def __init__(self, **_kwargs):
                pass

            def run_conversation(self):
                return {"final_response": json.dumps(payload), "messages": ["not persisted"]}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sink = EventSink(root / "events.jsonl", root / "terminal.json")
            module = SimpleNamespace(AIAgent=FakeAgent)
            instrument_run_agent(module, sink)
            result = module.AIAgent().run_conversation()
            self.assertEqual(result["messages"], ["not persisted"])
            self.assertEqual(json.loads((root / "terminal.json").read_text(encoding="utf-8")), payload)

            (root / "terminal.json").unlink()
            sink.capture_terminal_response({"final_response": "reasoning before\n" + json.dumps(payload)})
            self.assertFalse((root / "terminal.json").exists())

    def test_hermes_event_adapter_forces_only_initial_native_tool(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from hermes_event_adapter import EventSink, instrument_run_agent

        native_tool = {
            "type": "function",
            "function": {
                "name": "openmontage_native",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["status", "read_document", "publish_artifact"],
                        }
                    },
                    "required": ["operation"],
                },
            },
        }
        web_tool = {
            "type": "function",
            "function": {"name": "web_search", "parameters": {"type": "object"}},
        }

        class FakeAgent:
            def __init__(self, **_kwargs):
                self.valid_tool_names = {"openmontage_native", "acd_acquire_source", "web_search"}

            def _build_api_kwargs(self, _messages):
                return {
                    "tools": [native_tool, web_tool],
                    "tool_choice": "auto",
                    "extra_body": {
                        "chat_template_kwargs": {
                            "enable_thinking": True,
                            "force_nonempty_content": True,
                        }
                    },
                }

            def _interruptible_api_call(self, request):
                return request

        with tempfile.TemporaryDirectory() as tmp:
            events = Path(tmp) / "events.jsonl"
            module = SimpleNamespace(AIAgent=FakeAgent)
            with patch.dict(os.environ, {"ACD_FORCE_INITIAL_OPENMONTAGE_TOOL": "1"}):
                sink = EventSink(events)
                instrument_run_agent(module, sink)
                agent = module.AIAgent()
                first = agent._build_api_kwargs([])
                agent._interruptible_api_call(first)
                self.assertEqual(
                    first["tool_choice"],
                    {"type": "function", "function": {"name": "openmontage_native"}},
                )
                self.assertEqual(len(first["tools"]), 1)
                self.assertEqual(
                    first["tools"][0]["function"]["parameters"]["properties"]["operation"]["enum"],
                    ["status"],
                )
                self.assertEqual(
                    native_tool["function"]["parameters"]["properties"]["operation"]["enum"],
                    ["status", "read_document", "publish_artifact"],
                )
                sink.start("call-1", "openmontage_native", {"operation": "status"})
                sink.complete(
                    "call-1",
                    "openmontage_native",
                    {"operation": "status"},
                    json.dumps({"success": True, "operation": "status"}),
                )
                second = agent._build_api_kwargs([])
                agent._interruptible_api_call(second)

            self.assertEqual(second["tool_choice"], "auto")
            summary = HermesRunner._event_summary(events)
            self.assertEqual(summary["agent_contract"]["tool_count"], "3")
            self.assertEqual(summary["agent_contract"]["has_openmontage_native"], "True")
            self.assertEqual(summary["request_contract"]["has_openmontage_native"], "True")
            self.assertEqual(summary["request_contract"]["handshake_request"], "True")
            self.assertEqual(summary["request_contract"]["tool_count"], "1")
            self.assertEqual(summary["request_contract"]["status_only"], "True")
            self.assertEqual(summary["request_contract"]["tool_choice_mode"], "named")
            self.assertEqual(summary["last_request_contract"]["handshake_request"], "False")
            self.assertEqual(summary["last_request_contract"]["tool_count"], "2")
            self.assertEqual(summary["tool_handshake"]["completed"], True)
            request_events = [
                json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()
                if '"event": "api_request_ready"' in line
            ]
            self.assertEqual(request_events[0]["handshake_request"], "True")
            self.assertEqual(request_events[0]["force_nonempty_content"], "True")

    def test_hermes_event_adapter_captures_normalized_response_structure_only(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from hermes_event_adapter import EventSink, instrument_run_agent

        native_tool = {
            "type": "function",
            "function": {
                "name": "openmontage_native",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string", "enum": ["status"]},
                    },
                    "required": ["operation"],
                },
            },
        }

        class FakeTransport:
            def normalize_response(self, _response, **_kwargs):
                return SimpleNamespace(
                    finish_reason="tool_calls",
                    content="must-not-be-recorded",
                    reasoning="hidden-reasoning-must-not-be-recorded",
                    provider_data={},
                    tool_calls=[SimpleNamespace(
                        name="openmontage_native",
                        arguments=json.dumps({"operation": "status"}),
                    )],
                )

        class FakeAgent:
            def __init__(self, **_kwargs):
                self.valid_tool_names = {"openmontage_native", "acd_acquire_source"}
                self.transport = FakeTransport()

            def _build_api_kwargs(self, _messages):
                return {"model": "test", "tools": [native_tool]}

            def _get_transport(self):
                return self.transport

            def _interruptible_api_call(self, request):
                return request

        with tempfile.TemporaryDirectory() as tmp:
            events = Path(tmp) / "events.jsonl"
            sink = EventSink(events)
            module = SimpleNamespace(AIAgent=FakeAgent)
            instrument_run_agent(module, sink)
            agent = module.AIAgent()
            normalized = agent._get_transport().normalize_response(object())
            self.assertEqual(normalized.finish_reason, "tool_calls")
            raw = events.read_text(encoding="utf-8")
            self.assertNotIn("must-not-be-recorded", raw)
            self.assertNotIn("hidden-reasoning-must-not-be-recorded", raw)
            summary = HermesRunner._event_summary(events)
            self.assertEqual(summary["first_response_contract"]["tool_call_count"], "1")
            self.assertEqual(
                summary["first_response_contract"]["tool_call_names"],
                "openmontage_native",
            )

    def test_hermes_event_adapter_rejects_post_build_request_mutation(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from hermes_event_adapter import EventSink, instrument_run_agent

        native_tool = {
            "type": "function",
            "function": {
                "name": "openmontage_native",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["status", "publish_artifact"],
                        }
                    },
                },
            },
        }

        class FakeAgent:
            def __init__(self, **_kwargs):
                self.valid_tool_names = {"openmontage_native", "acd_acquire_source"}

            def _build_api_kwargs(self, _messages):
                return {"model": "test", "tools": [native_tool], "tool_choice": "auto"}

            def _interruptible_api_call(self, request):
                return request

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"ACD_FORCE_INITIAL_OPENMONTAGE_TOOL": "1"}
        ):
            module = SimpleNamespace(AIAgent=FakeAgent)
            instrument_run_agent(module, EventSink(Path(tmp) / "events.jsonl"))
            agent = module.AIAgent()
            request = agent._build_api_kwargs([])
            # Simulate an LLM middleware weakening the prepared request.
            request["tool_choice"] = "auto"
            with self.assertRaisesRegex(RuntimeError, "ACD_HERMES_TOOL_REQUEST_INVALID"):
                agent._interruptible_api_call(request)

    def test_hermes_event_adapter_rejects_text_response_before_second_request(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from hermes_event_adapter import EventSink, instrument_run_agent

        native_tool = {
            "type": "function",
            "function": {
                "name": "openmontage_native",
                "parameters": {
                    "type": "object",
                    "properties": {"operation": {"type": "string", "enum": ["status"]}},
                },
            },
        }

        class FakeTransport:
            def normalize_response(self, _response, **_kwargs):
                return SimpleNamespace(
                    finish_reason="stop",
                    content="text-only refusal",
                    reasoning=None,
                    provider_data={},
                    tool_calls=[],
                )

        class FakeAgent:
            def __init__(self, **_kwargs):
                self.valid_tool_names = {"openmontage_native", "acd_acquire_source"}
                self.transport = FakeTransport()

            def _build_api_kwargs(self, _messages):
                return {"model": "test", "tools": [native_tool], "tool_choice": "auto"}

            def _get_transport(self):
                return self.transport

            def _interruptible_api_call(self, request):
                return request

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"ACD_FORCE_INITIAL_OPENMONTAGE_TOOL": "1"}
        ):
            events = Path(tmp) / "events.jsonl"
            module = SimpleNamespace(AIAgent=FakeAgent)
            instrument_run_agent(module, EventSink(events))
            agent = module.AIAgent()
            first = agent._build_api_kwargs([])
            agent._interruptible_api_call(first)
            agent._get_transport().normalize_response(object())
            with self.assertRaisesRegex(RuntimeError, "ACD_HERMES_TOOL_HANDSHAKE_FAILED"):
                agent._build_api_kwargs([])
            summary = HermesRunner._event_summary(events)
            self.assertEqual(summary["first_response_contract"]["tool_call_count"], "0")
            self.assertEqual(
                summary["tool_handshake"]["failure_code"],
                "INVALID_PROVIDER_TOOL_RESPONSE",
            )

    def test_hermes_event_adapter_fails_before_provider_without_native_tool(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from hermes_event_adapter import EventSink, instrument_run_agent

        class FakeAgent:
            def __init__(self, **_kwargs):
                self.valid_tool_names = {"acd_acquire_source"}

            def _build_api_kwargs(self, _messages):
                return {
                    "model": "test-model",
                    "tools": [{
                        "type": "function",
                        "function": {"name": "acd_acquire_source", "parameters": {}},
                    }],
                }

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"ACD_FORCE_INITIAL_OPENMONTAGE_TOOL": "1"}
        ):
            sink = EventSink(Path(tmp) / "events.jsonl")
            module = SimpleNamespace(AIAgent=FakeAgent)
            instrument_run_agent(module, sink)
            with self.assertRaisesRegex(RuntimeError, "ACD_HERMES_TOOL_UNAVAILABLE"):
                module.AIAgent()._build_api_kwargs([])

    def test_hermes_event_adapter_fails_before_ultra_request_without_flags(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from hermes_event_adapter import EventSink, instrument_run_agent

        native_tool = {
            "type": "function",
            "function": {
                "name": "openmontage_native",
                "parameters": {
                    "type": "object",
                    "properties": {"operation": {"type": "string", "enum": ["status"]}},
                },
            },
        }

        class FakeAgent:
            def __init__(self, **_kwargs):
                self.valid_tool_names = {"openmontage_native", "acd_acquire_source"}

            def _build_api_kwargs(self, _messages):
                return {
                    "model": "nvidia/nemotron-3-ultra-550b-a55b",
                    "tools": [native_tool],
                    "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
                }

            def _interruptible_api_call(self, request):
                return request

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"ACD_FORCE_INITIAL_OPENMONTAGE_TOOL": "1"}
        ):
            sink = EventSink(Path(tmp) / "events.jsonl")
            module = SimpleNamespace(AIAgent=FakeAgent)
            instrument_run_agent(module, sink)
            agent = module.AIAgent()
            request = agent._build_api_kwargs([])
            with self.assertRaisesRegex(
                RuntimeError, "ACD_HERMES_TOOL_CONTRACT_CONFIG_INVALID"
            ):
                agent._interruptible_api_call(request)

    def test_hermes_event_adapter_records_clean_system_exit_as_finished(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import hermes_event_adapter

        class FakeAgent:
            def __init__(self, **_kwargs):
                pass

        run_agent = types.ModuleType("run_agent")
        run_agent.AIAgent = FakeAgent
        hermes_cli = types.ModuleType("hermes_cli")
        hermes_cli.__path__ = []
        hermes_main = types.ModuleType("hermes_cli.main")

        def clean_exit():
            raise SystemExit(0)

        hermes_main.main = clean_exit
        with tempfile.TemporaryDirectory() as tmp:
            events = Path(tmp) / "events.jsonl"
            with (
                patch.dict(sys.modules, {"run_agent": run_agent, "hermes_cli": hermes_cli, "hermes_cli.main": hermes_main}),
                patch.object(sys, "argv", ["adapter", "--event-file", str(events)]),
            ):
                self.assertEqual(hermes_event_adapter.main(), 0)
            payloads = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(payloads[-1]["event"], "adapter_finished")
            self.assertEqual(payloads[-1]["exit_code"], "0")

    def test_profile_plugin_and_bridge_reference_mirrors_are_installed(self):
        installer = (ROOT / "bootstrap" / "install_skills.sh").read_text(encoding="utf-8")
        self.assertIn("PROFILE_PLUGINS_DIR/acd-openmontage", installer)
        self.assertIn("Bridge reference mirrors", installer)
        self.assertIn("openmontage-artifact-bridge.md", installer)

    def test_hermes_bootstrap_pins_ddgs_search_dependency(self):
        installer = (ROOT / "bootstrap" / "install_hermes.sh").read_text(encoding="utf-8")
        self.assertIn('DDGS_VERSION="${ACD_DDGS_VERSION:-9.14.4}"', installer)
        self.assertIn('"ddgs==$DDGS_VERSION"', installer)

    def test_openmontage_plugin_exposes_typed_tools_without_render(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "acd_openmontage_plugin",
            ROOT / "plugins" / "acd-openmontage" / "__init__.py",
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        registered = {}

        class Context:
            def register_tool(self, **kwargs):
                registered[kwargs["name"]] = kwargs

        module.register(Context())
        self.assertEqual(set(registered), {"openmontage_native", "acd_acquire_source"})
        operations = registered["openmontage_native"]["schema"]["parameters"]["properties"]["operation"]["enum"]
        self.assertEqual(operations, ["status", "read_document", "tool_info", "publish_artifact", "run_tool"])
        self.assertNotIn("video_compose", operations)

    def test_creative_adapter_document_and_tool_paths_are_fail_closed(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "openmontage_creative_adapter",
            ROOT / "scripts" / "openmontage_creative_adapter.py",
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            openmontage = root / "OpenMontage"
            (project / "artifacts").mkdir(parents=True)
            (openmontage / "schemas" / "artifacts").mkdir(parents=True)
            document = project / "artifacts" / "scene_plan.json"
            document.write_text("{}", encoding="utf-8")
            self.assertEqual(
                module._document_path(
                    "project", "artifacts/scene_plan.json",
                    project=project, openmontage=openmontage,
                ),
                document.resolve(),
            )
            with self.assertRaises(ValueError):
                module._document_path(
                    "openmontage", "../.env",
                    project=project, openmontage=openmontage,
                )
            info = {
                "input_schema": {"properties": {"output_path": {"type": "string"}}},
                "side_effects": ["writes output"],
            }
            with self.assertRaises(ValueError):
                module._validate_tool_paths(project, "math_animate", {}, info)
            with self.assertRaises(ValueError):
                module._validate_tool_paths(
                    project, "math_animate", {"output_path": str(root / "escape.webm")}, info,
                )

    def test_canary_font_supports_portable_environment_override(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from run_native_contract_canary import discover_canary_font

        with tempfile.TemporaryDirectory() as tmp:
            font = Path(tmp) / "Portable-Bold.ttf"
            font.write_bytes(b"font-placeholder")
            discover_canary_font.cache_clear()
            with patch.dict(__import__("os").environ, {"ACD_CANARY_FONT": str(font)}):
                self.assertEqual(discover_canary_font(), font.resolve())
            discover_canary_font.cache_clear()

            matched = Path(tmp) / "Kaggle-Installed-Bold.ttf"
            matched.write_bytes(b"fontconfig-placeholder")
            completed = SimpleNamespace(returncode=0, stdout=str(matched) + "\n", stderr="")
            environment = __import__("os").environ
            saved_override = environment.pop("ACD_CANARY_FONT", None)
            try:
                with patch("run_native_contract_canary.subprocess.run", return_value=completed):
                    self.assertEqual(discover_canary_font(), matched.resolve())
            finally:
                if saved_override is not None:
                    environment["ACD_CANARY_FONT"] = saved_override
                discover_canary_font.cache_clear()

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
            (source / ".env.local").write_text("SECRET=local", encoding="utf-8")
            (source / "link").symlink_to(source / "state.db")
            copy_tree(source, destination)
            self.assertTrue((destination / "state.db").is_file())
            self.assertFalse((destination / ".env").exists())
            self.assertFalse((destination / ".env.local").exists())
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

    def test_persistence_generations_publish_atomically_and_hydrate_current(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import kaggle_persistence

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hermes = root / "hermes" / "profiles" / "football-emotion"
            state = root / "state" / "runs"
            projects = root / "projects"
            hermes.mkdir(parents=True)
            state.mkdir(parents=True)
            projects.mkdir()
            (state / "run.json").write_text('{"status":"BLOCKED"}\n', encoding="utf-8")
            destination = root / "persist"
            environment = {
                "HERMES_HOME": str(root / "hermes"),
                "HERMES_PROFILE": "football-emotion",
                "ACD_STATE_DIR": str(state),
                "OPENMONTAGE_PROJECTS_DIR": str(projects),
            }
            with patch.dict(os.environ, environment, clear=False):
                kaggle_persistence.export(destination)
                pointer = json.loads((destination / "current.json").read_text(encoding="utf-8"))
                generation = destination / "generations" / pointer["generation_id"]
                self.assertTrue((generation / "snapshot-manifest.json").is_file())
                shutil.rmtree(root / "state")
                state.mkdir(parents=True)
                kaggle_persistence.hydrate(destination)
                self.assertEqual((state / "run.json").read_text(encoding="utf-8"), '{"status":"BLOCKED"}\n')

    def test_persistence_rejects_unmanifested_generation_file(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import kaggle_persistence

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "hermes" / "profiles" / "football-emotion"
            state = root / "state" / "runs"
            projects = root / "projects"
            profile.mkdir(parents=True)
            state.mkdir(parents=True)
            projects.mkdir()
            (state / "run.json").write_text("{}\n", encoding="utf-8")
            destination = root / "persist"
            environment = {
                "HERMES_HOME": str(root / "hermes"),
                "HERMES_PROFILE": "football-emotion",
                "ACD_STATE_DIR": str(state),
                "OPENMONTAGE_PROJECTS_DIR": str(projects),
            }
            with patch.dict(os.environ, environment, clear=False):
                kaggle_persistence.export(destination)
                pointer = json.loads((destination / "current.json").read_text(encoding="utf-8"))
                generation = destination / "generations" / pointer["generation_id"]
                (generation / "unmanifested.txt").write_text("tamper", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "file set mismatch"):
                    kaggle_persistence.hydrate(destination)

    def test_persistence_failed_generation_does_not_advance_current(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import kaggle_persistence

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "hermes" / "profiles" / "football-emotion"
            state = root / "state" / "runs"
            projects = root / "projects"
            profile.mkdir(parents=True)
            state.mkdir(parents=True)
            projects.mkdir()
            (state / "run.json").write_text("{}\n", encoding="utf-8")
            destination = root / "persist"
            environment = {
                "HERMES_HOME": str(root / "hermes"),
                "HERMES_PROFILE": "football-emotion",
                "ACD_STATE_DIR": str(state),
                "OPENMONTAGE_PROJECTS_DIR": str(projects),
            }
            with patch.dict(os.environ, environment, clear=False):
                kaggle_persistence.export(destination)
                before = (destination / "current.json").read_bytes()
                original = kaggle_persistence.copy_tree

                def fail_after_one(source, target):
                    if target.name == "acd-state":
                        raise OSError("injected snapshot failure")
                    return original(source, target)

                with patch.object(kaggle_persistence, "copy_tree", side_effect=fail_after_one):
                    with self.assertRaises(OSError):
                        kaggle_persistence.export(destination)
                self.assertEqual((destination / "current.json").read_bytes(), before)

    def test_persistence_export_refuses_active_or_starting_run_race(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import kaggle_persistence

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "hermes" / "profiles" / "football-emotion"
            state = root / "state" / "runs"
            projects = root / "projects"
            profile.mkdir(parents=True)
            state.mkdir(parents=True)
            projects.mkdir()
            destination = root / "persist"
            environment = {
                "HERMES_HOME": str(root / "hermes"),
                "HERMES_PROFILE": "football-emotion",
                "ACD_STATE_DIR": str(state),
                "OPENMONTAGE_PROJECTS_DIR": str(projects),
            }
            store = RunStateStore(state)
            with patch.dict(os.environ, environment, clear=False):
                with store.lease("active-run"):
                    with self.assertRaisesRegex(RuntimeError, "run is active"):
                        kaggle_persistence.export(destination)
            self.assertFalse((destination / "current.json").exists())

    def test_persistence_destination_cannot_overlap_runtime_roots(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import kaggle_persistence

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "hermes" / "profiles" / "football-emotion"
            state = root / "state" / "runs"
            projects = root / "projects"
            profile.mkdir(parents=True)
            state.mkdir(parents=True)
            projects.mkdir()
            environment = {
                "HERMES_HOME": str(root / "hermes"),
                "HERMES_PROFILE": "football-emotion",
                "ACD_STATE_DIR": str(state),
                "OPENMONTAGE_PROJECTS_DIR": str(projects),
            }
            with patch.dict(os.environ, environment, clear=False):
                with self.assertRaisesRegex(ValueError, "must not overlap"):
                    kaggle_persistence.export(projects / "persistence")

    def test_persistence_secret_scan_covers_large_files_and_chunk_boundaries(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import kaggle_persistence

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = root / "large-runtime-log.bin"
            with payload.open("wb") as handle:
                handle.seek(33 * 1024 * 1024 - 7)
                handle.write(b"nvapi-abcdefghijklmnopqrstuvwx")
            with self.assertRaisesRegex(ValueError, "credential-like material"):
                kaggle_persistence._reject_secrets(root)

    def test_kaggle_launchers_fail_closed_and_preserve_unknown_directories(self):
        launcher = (ROOT / "bootstrap" / "run_kaggle_job.sh").read_text(encoding="utf-8")
        master = (ROOT / "bootstrap" / "kaggle_master_init.sh").read_text(encoding="utf-8")
        self.assertIn('if [[ "$hydrate_status" -ne 0 ]]', launcher)
        self.assertIn('exit "$hydrate_status"', launcher)
        self.assertIn('if [[ "$persist_status" -ne 0 ]]', launcher)
        self.assertNotIn('rm -rf "$REPO_DIR"', master)
        self.assertIn("Refusing to replace a non-repository directory", master)

    def test_timeout_processes_are_isolated_and_killed_as_groups(self):
        native = (ROOT / "src" / "acd_worker" / "native_bridge.py").read_text(encoding="utf-8")
        hermes = (ROOT / "src" / "acd_worker" / "hermes_runner.py").read_text(encoding="utf-8")
        for source in (native, hermes):
            self.assertIn("start_new_session=True", source)
            self.assertIn("os.killpg(process.pid, signal.SIGTERM)", source)
            self.assertIn("os.killpg(process.pid, signal.SIGKILL)", source)

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
            self.assertIn("search_backend: ddgs", config)
            self.assertIn("enabled: [acd-openmontage]", config)
            self.assertIn("acd-openmontage", config)
            self.assertNotIn("terminal", next(line for line in config.splitlines() if line.startswith("toolsets:")))
            self.assertNotIn("file", next(line for line in config.splitlines() if line.startswith("toolsets:")))
            self.assertIn("coding_context: off", config)

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
            self.assertIn("force_nonempty_content: true", config)
            self.assertIn("reasoning_budget: 16384", config)

    def test_doctor_fails_closed_on_incomplete_ultra_tool_contract(self):
        from bootstrap.validate_setup import model_tool_contract_gate

        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp)
            config = profile / "config.yaml"
            config.write_text(
                "model:\n  default: nvidia/nemotron-3-ultra-550b-a55b\n"
                "chat_template_kwargs:\n  enable_thinking: true\n",
                encoding="utf-8",
            )
            missing = model_tool_contract_gate(profile)
            self.assertEqual(missing.status, "failed")
            self.assertIn("force_nonempty_content", missing.evidence)

            config.write_text(
                config.read_text(encoding="utf-8") + "  force_nonempty_content: true\n",
                encoding="utf-8",
            )
            self.assertEqual(model_tool_contract_gate(profile).status, "passed")

    def test_doctor_checks_pinned_same_path_hermes_hooks(self):
        from bootstrap.validate_setup import hermes_same_path_contract_gate

        with tempfile.TemporaryDirectory() as tmp:
            hermes = Path(tmp)
            (hermes / "agent" / "transports").mkdir(parents=True)
            (hermes / "run_agent.py").write_text(
                "class AIAgent:\n"
                "    def _build_api_kwargs(self): pass\n"
                "    def _interruptible_api_call(self): pass\n"
                "    def _interruptible_streaming_api_call(self): pass\n",
                encoding="utf-8",
            )
            (hermes / "agent" / "conversation_loop.py").write_text(
                "_cc_fr = agent._get_transport()\n"
                "_finish_result = _cc_fr.normalize_response(response)\n",
                encoding="utf-8",
            )
            executor = hermes / "agent" / "tool_executor.py"
            executor.write_text(
                "agent.tool_start_callback(x)\n"
                "agent.tool_complete_callback(x, function_result)\n",
                encoding="utf-8",
            )
            (hermes / "agent" / "transports" / "types.py").write_text(
                "class ToolCall:\n    arguments: str\nclass NormalizedResponse: pass\n",
                encoding="utf-8",
            )
            self.assertEqual(hermes_same_path_contract_gate(hermes).status, "passed")
            executor.write_text("callbacks missing\n", encoding="utf-8")
            self.assertEqual(hermes_same_path_contract_gate(hermes).status, "failed")

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
    def test_interrupted_render_without_review_is_not_automatically_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)
            now = utc_now()
            state = RunState(
                schema_version="1.0",
                run_id="manual-review-required",
                project_id="football-manual-review",
                request="test",
                status=RunStatus.BLOCKED,
                created_at=now,
                updated_at=now,
                project_dir=str(cfg.projects_dir / "football-manual-review"),
                source_manifest_path=str(root / "source_manifest.json"),
                agent_result_path=str(root / "agent_result.json"),
                prompt_path=str(root / "prompt.md"),
                blocker=RunProblem(
                    code="NATIVE_RENDER_RECOVERY_REVIEW_REQUIRED",
                    message="render bytes exist without durable review",
                    phase="native_execution",
                ),
                native_execution={"status": "rendering", "fingerprint": "fp"},
            )
            runner = FakeRunner(root, lambda _: self.fail("Hermes must not run"))
            controller = ThinRunController(cfg, runner=runner)
            controller.store.save(state)

            resumed = controller.resume(state.run_id, retry_blocked=True)

            self.assertEqual(resumed.status, RunStatus.BLOCKED)
            self.assertEqual(resumed.blocker.code, "NATIVE_RENDER_RECOVERY_REVIEW_REQUIRED")
            self.assertEqual(runner.calls, [])

    def test_successful_process_without_live_tool_contract_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)
            runner = FakeRunner(
                root,
                lambda _call: HermesSessionResult(
                    success=True,
                    session_id="session_12345678",
                    returncode=0,
                    metadata={
                        "event_adapter_used": False,
                        "tool_contract_requested": True,
                    },
                ),
                autocertify=False,
            )
            state = ThinRunController(cfg, runner=runner).start("test")
            self.assertEqual(state.status, RunStatus.BLOCKED)
            self.assertEqual(state.blocker.code, "HERMES_TOOL_HANDSHAKE_UNVERIFIED")
            self.assertEqual(len(runner.calls), 1)

    def test_real_native_status_handler_failure_is_runtime_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)
            metadata = {
                "event_adapter_used": True,
                "tool_contract_requested": True,
                "event_summary": {
                    "events": {"tool_handshake_started": 1, "tool_handshake_failed": 1},
                    "agent_contract": {
                        "has_openmontage_native": True,
                        "has_acd_acquire_source": True,
                    },
                    "first_request_contract": {
                        "handshake_request": True,
                        "tool_count": 1,
                        "tools": "openmontage_native",
                        "status_only": True,
                        "tool_choice_mode": "named",
                        "tool_choice_name": "openmontage_native",
                    },
                    "first_response_contract": {
                        "tool_call_count": 1,
                        "tool_call_names": "openmontage_native",
                        "status_operation": True,
                    },
                    "tool_handshake": {
                        "required": True,
                        "started": True,
                        "completed": False,
                        "failed": True,
                        "failure_code": "OPENMONTAGE_TOOL_BRIDGE_UNAVAILABLE",
                    },
                },
            }
            runner = FakeRunner(
                root,
                lambda _call: HermesSessionResult(
                    success=True,
                    session_id="session_12345678",
                    returncode=0,
                    metadata=metadata,
                ),
                autocertify=False,
            )
            state = ThinRunController(cfg, runner=runner).start("test")
            self.assertEqual(state.status, RunStatus.BLOCKED)
            self.assertEqual(state.blocker.code, "OPENMONTAGE_RUNTIME_UNAVAILABLE")

    def test_worker_publishes_validated_terminal_payload_from_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)

            def behavior(call):
                run_id = call["environment"]["ACD_RUN_ID"]
                return HermesSessionResult(
                    success=True,
                    session_id="session_12345678",
                    returncode=0,
                    terminal_payload={
                        "schema_version": "1.0",
                        "run_id": run_id,
                        "status": "blocked",
                        "output_media": [],
                        "openmontage_artifacts": [],
                        "source_requests": [],
                        "blocker": {
                            "code": "CREATIVE_INPUT_UNAVAILABLE",
                            "message": "Required creative input is unavailable.",
                            "phase": "research",
                            "evidence": {},
                        },
                        "error": None,
                        "summary": "Blocked honestly.",
                    },
                )

            state = ThinRunController(cfg, runner=FakeRunner(root, behavior)).start("test")
            self.assertEqual(state.status, RunStatus.BLOCKED)
            self.assertEqual(state.blocker.code, "CREATIVE_INPUT_UNAVAILABLE")
            self.assertTrue(Path(state.agent_result_path).is_file())

    def test_ready_handoff_executes_bridge_before_delivery_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)

            def behavior(call):
                prompt = call["prompt"]
                result_path = Path(next(
                    line.split(":", 1)[1].strip()
                    for line in prompt.splitlines()
                    if line.startswith("- worker-owned terminal envelope path:")
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

            def behavior(call):
                # A loose artifact without its matching native checkpoint is
                # not durable progress and must not earn another model slice.
                project = Path(call["environment"]["ACD_PROJECT_DIR"])
                artifacts = project / "artifacts"
                artifacts.mkdir(parents=True, exist_ok=True)
                (artifacts / "research_brief.json").write_text(
                    '{"version":"1.0"}', encoding="utf-8"
                )
                return HermesSessionResult(
                    success=True,
                    session_id="session_12345678",
                    returncode=0,
                    metadata={"event_summary": {"max_step": 32, "tool_calls": {"read_file": 20}}},
                )

            runner = FakeRunner(root, behavior)
            state = ThinRunController(cfg, runner=runner).start("test")
            self.assertEqual(state.status, RunStatus.BLOCKED)
            self.assertEqual(state.blocker.code, "HERMES_NO_NATIVE_PROGRESS")
            self.assertEqual(len(runner.calls), 1)
            self.assertEqual(runner.calls[0]["environment"]["ACD_RUN_ID"], state.run_id)
            self.assertEqual(runner.calls[0]["environment"]["ACD_PROJECT_DIR"], state.project_dir)
            self.assertEqual(
                runner.calls[0]["environment"]["ACD_FORCE_INITIAL_OPENMONTAGE_TOOL"],
                "1",
            )
            self.assertEqual(state.blocker.evidence["execution"]["event_summary"]["max_step"], 32)

    def test_invalid_terminal_payload_is_reported_in_no_progress_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)

            def behavior(call):
                return HermesSessionResult(
                    success=True,
                    session_id="session_12345678",
                    returncode=0,
                    terminal_payload={
                        "schema_version": "1.0",
                        "run_id": call["environment"]["ACD_RUN_ID"],
                        "status": "blocked",
                    },
                )

            state = ThinRunController(cfg, runner=FakeRunner(root, behavior)).start("test")
            self.assertEqual(state.status, RunStatus.BLOCKED)
            self.assertEqual(state.blocker.code, "HERMES_NO_NATIVE_PROGRESS")
            self.assertIn("terminal_payload_error", state.blocker.evidence["execution"])
            self.assertEqual(
                state.blocker.evidence["execution"]["terminal_payload_keys"],
                ["run_id", "schema_version", "status"],
            )

    def test_missing_result_gets_bounded_checkpoint_continuations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)

            def behavior(call):
                if len(runner.calls) == 1:
                    project = Path(call["environment"]["ACD_PROJECT_DIR"])
                    artifacts = project / "artifacts"
                    artifacts.mkdir(parents=True, exist_ok=True)
                    research = {"version": "1.0"}
                    (artifacts / "research_brief.json").write_text(json.dumps(research), encoding="utf-8")
                    (project / "checkpoint_research.json").write_text(json.dumps({
                        "stage": "research",
                        "status": "completed",
                        "artifacts": {"research_brief": research},
                    }), encoding="utf-8")
                    return HermesSessionResult(success=True, session_id="session_12345678", returncode=0)
                prompt = call["prompt"]
                self.assertIn("Do not repeat repository", prompt)
                self.assertIn("status: ready_for_execution", prompt)
                self.assertIn("Never invoke `math_animate`", prompt)
                self.assertIn("one corrected retry", prompt)
                self.assertIn("do not generate, redesign or compose anything", prompt)
                self.assertIn("CONTINUATION SLICE: 1 of 1", prompt)
                self.assertIn("final continuation slice", prompt)
                result_path = Path(next(
                    line.split(":", 1)[1].strip()
                    for line in prompt.splitlines()
                    if line.startswith("WORKER-OWNED RESULT PATH:")
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
            self.assertEqual(
                runner.calls[0]["environment"]["ACD_FORCE_INITIAL_OPENMONTAGE_TOOL"],
                "1",
            )
            self.assertEqual(
                runner.calls[1]["environment"]["ACD_FORCE_INITIAL_OPENMONTAGE_TOOL"],
                "0",
            )
            self.assertEqual(state.hermes_tool_contract["status"], "passed")
            self.assertEqual(
                state.hermes_tool_contract["contract_id"],
                runner.calls[0]["environment"]["ACD_HERMES_TOOL_CONTRACT_ID"],
            )

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
            self.assertEqual(resumed.blocker.code, "HERMES_NATIVE_PROGRESS_STALLED")
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

    def test_interrupted_native_result_resumes_without_another_hermes_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)

            def behavior(call):
                project = Path(call["environment"]["ACD_PROJECT_DIR"])
                artifacts = project / "artifacts"
                artifacts.mkdir(parents=True, exist_ok=True)
                (project / "project.json").write_text(
                    json.dumps({"pipeline_type": "cinematic"}), encoding="utf-8"
                )
                for kind in ("proposal_packet", "scene_plan", "asset_manifest", "edit_decisions"):
                    (artifacts / f"{kind}.json").write_text(
                        json.dumps({"version": "1.0"}), encoding="utf-8"
                    )
                return HermesSessionResult(success=True, session_id="session_12345678", returncode=0)

            class RecoveringBridge:
                def __init__(self):
                    self.calls = 0

                def prepare(self, request):
                    return SimpleNamespace(approved_silence=False), {"runtime": {}}, "recovery-fingerprint"

                def execute(self, request, heartbeat=None):
                    self.calls += 1
                    if self.calls == 1:
                        raise NativeExecutionError(
                            "NATIVE_RESULT_MISSING",
                            "injected crash after native adapter",
                        )
                    return SimpleNamespace(
                        fingerprint="recovery-fingerprint",
                        output_media=[{"path": str(root / "render.mp4"), "sha256": "hash"}],
                        openmontage_artifacts=[{"kind": "render_report", "path": str(root / "report.json")}],
                        compatibility={"supported": True},
                        native_result={"status": "delivered", "recovered": True},
                    )

            runner = FakeRunner(root, behavior)
            bridge = RecoveringBridge()
            controller = ThinRunController(cfg, runner=runner, native_bridge=bridge)
            blocked = controller.start("test")
            self.assertEqual(blocked.status, RunStatus.BLOCKED)
            self.assertEqual(blocked.blocker.code, "NATIVE_RESULT_MISSING")
            self.assertEqual(len(runner.calls), 1)

            with (
                patch("acd_worker.thin_controller.OpenMontageArtifactValidator.validate", return_value={"valid": True}),
                patch("acd_worker.thin_controller.FinalMediaValidator.validate", return_value={"valid": True}),
            ):
                delivered = controller.resume(blocked.run_id, retry_blocked=True)
            self.assertEqual(delivered.status, RunStatus.DELIVERED)
            self.assertEqual(bridge.calls, 2)
            self.assertEqual(len(runner.calls), 1)
            self.assertTrue(delivered.native_execution["native_result"]["recovered"])

    def test_ready_handoff_rejects_artifact_declaration_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_for(root)

            def behavior(call):
                prompt = call["prompt"]
                result_path = Path(next(line.split(":", 1)[1].strip() for line in prompt.splitlines() if line.startswith("- worker-owned terminal envelope path:")))
                run_id = next(line.split(":", 1)[1].strip() for line in prompt.splitlines() if line.startswith("RUN ID:"))
                result_path.write_text(json.dumps({
                    "schema_version": "1.0", "run_id": run_id, "status": "ready_for_execution",
                    "output_media": [], "openmontage_artifacts": [],
                    "source_requests": [], "blocker": None, "error": None,
                    "summary": "typed handoff with intentionally mismatched declarations",
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
    def test_native_transaction_recovers_after_review_without_second_compose(self):
        import importlib.util

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            artifacts = project / "artifacts"
            renders = project / "renders"
            artifacts.mkdir(parents=True)
            renders.mkdir()
            artifact_paths = {}
            for kind in ("proposal_packet", "scene_plan", "asset_manifest", "edit_decisions"):
                path = artifacts / f"{kind}.json"
                path.write_text(json.dumps({"version": "1.0"}), encoding="utf-8")
                artifact_paths[kind] = str(path)
            output = renders / "final.mp4"
            calls = []

            class Tool:
                def execute(self, inputs):
                    calls.append(inputs)
                    output.write_bytes(b"native-reviewed-render")
                    return SimpleNamespace(
                        success=True,
                        error=None,
                        data={"final_review": {
                            "version": "1.0",
                            "status": "pass",
                            "recommended_action": "present_to_user",
                            "metadata": {},
                        }},
                        duration_seconds=1.0,
                        cost_usd=0.0,
                        artifacts=[],
                    )

            registry = SimpleNamespace(discover=lambda: None, get=lambda name: Tool())
            checkpoint_module = types.ModuleType("lib.checkpoint")
            checkpoint_module.write_checkpoint = lambda *args, **kwargs: None
            schemas_module = types.ModuleType("schemas.artifacts")
            schemas_module.validate_artifact = lambda *args, **kwargs: None
            registry_module = types.ModuleType("tools.tool_registry")
            registry_module.registry = registry
            fake_modules = {
                "lib": types.ModuleType("lib"),
                "lib.checkpoint": checkpoint_module,
                "schemas": types.ModuleType("schemas"),
                "schemas.artifacts": schemas_module,
                "tools": types.ModuleType("tools"),
                "tools.tool_registry": registry_module,
            }
            spec = importlib.util.spec_from_file_location(
                "acd_native_delivery_transaction_test",
                ROOT / "patches" / "openmontage" / "overlay" / "lib" / "acd_native_delivery.py",
            )
            module = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, fake_modules):
                assert spec.loader is not None
                spec.loader.exec_module(module)
            module._probe = lambda _path: {
                "duration": 12.0,
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "video_codec": "h264",
                "audio_codec": None,
            }
            command = {
                "fingerprint": "f" * 64,
                "project_dir": str(project),
                "output_path": str(output),
                "pipeline": "cinematic",
                "artifacts": artifact_paths,
                "approved_silence": True,
            }
            with patch.dict(os.environ, {"ACD_NATIVE_FAULT_AFTER": "rendered_reviewed"}):
                with self.assertRaisesRegex(RuntimeError, "Injected failure"):
                    module.execute_delivery(command)
            self.assertEqual(len(calls), 1)
            recovered = module.execute_delivery(command)
            self.assertEqual(recovered["status"], "delivered")
            self.assertTrue(recovered["recovered"])
            self.assertEqual(len(calls), 1)

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

    def test_legacy_flat_blocker_is_rejected_instead_of_normalized(self):
        with self.assertRaisesRegex(ValueError, "Agent result missing fields"):
            AgentEnvelope.from_dict({
                "run_id": "run-1",
                "status": "blocked",
                "blocker_code": "NATIVE_PIPELINE_TURN_BUDGET_EXHAUSTED",
                "last_valid_artifact": "proposal_packet",
                "last_valid_stage": "proposal",
                "missing_native_stages": ["scene_plan", "assets", "edit"],
                "note": "Native pipeline remains incomplete.",
            }, "run-1")

    def test_delivered_envelope_remains_strict(self):
        with self.assertRaisesRegex(ValueError, "Agent result missing fields"):
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
                    if line.startswith("- worker-owned terminal envelope path:")
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

    @staticmethod
    def _detailed_frame(offset: int, size: int = 256) -> bytes:
        base = bytes(255 if (index // 4) % 2 else 0 for index in range(size))
        offset %= size
        return base[offset:] + base[:offset]

    def test_temporal_validator_rejects_detailed_static_video(self):
        frame = self._detailed_frame(0)
        evidence = FinalMediaValidator._analyze_frames([frame] * 11)
        self.assertFalse(evidence["visually_blank"])
        self.assertTrue(evidence["visually_frozen"])
        self.assertEqual(evidence["changing_intervals"], 0)

    def test_temporal_validator_rejects_intro_motion_then_freeze(self):
        frames = [self._detailed_frame(index) for index in range(4)]
        frames.extend([frames[-1]] * 7)
        evidence = FinalMediaValidator._analyze_frames(frames)
        self.assertTrue(evidence["visually_frozen"])
        self.assertFalse(all(evidence["temporal_segment_coverage"]))
        self.assertTrue(evidence["frozen_ending"])

    def test_temporal_validator_accepts_motion_across_whole_timeline(self):
        frames = [self._detailed_frame(index * 3) for index in range(11)]
        evidence = FinalMediaValidator._analyze_frames(frames)
        self.assertFalse(evidence["visually_blank"])
        self.assertFalse(evidence["visually_frozen"])
        self.assertTrue(all(evidence["temporal_segment_coverage"]))

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
