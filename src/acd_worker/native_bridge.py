"""Typed, deterministic execution of an already-authored OpenMontage plan."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .compatibility import (
    COMPATIBILITY_MARKER,
    PINNED_OPENMONTAGE_COMMIT,
    OpenMontageCompatibilityRegistry,
    RuntimeTuple,
)
from .media_validation import OpenMontageArtifactValidator


def _terminate_process_group(process: subprocess.Popen, grace_seconds: float = 10) -> None:
    """Stop the adapter and every renderer it spawned."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass
    # The parent may have exited while a Chromium/ffmpeg child ignored TERM.
    # Kill the process group even when wait() already returned.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if process.poll() is None:
        process.wait()


class NativeExecutionError(RuntimeError):
    def __init__(self, code: str, message: str, evidence: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.evidence = evidence or {}


@dataclass(frozen=True)
class NativeExecutionRequest:
    pipeline: str
    artifacts: dict[str, str]
    output_path: str
    output_profile: Optional[str] = None
    remotion_timeout_ms: Optional[int] = None
    approved_silence: bool = False
    # Injected by the worker from CLI/run-state policy. Hermes is never
    # trusted to grant its own checkpoint approvals.
    approved_checkpoints: tuple[str, ...] = ()

    REQUIRED_INPUTS = ("scene_plan", "asset_manifest", "edit_decisions")
    PLANNING_INPUTS = ("proposal_packet", "brief")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NativeExecutionRequest":
        if not isinstance(payload, dict):
            raise NativeExecutionError("INVALID_EXECUTION_REQUEST", "execution_request must be an object")
        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, dict):
            raise NativeExecutionError("INVALID_EXECUTION_REQUEST", "execution_request.artifacts must be an object")
        missing = [name for name in cls.REQUIRED_INPUTS if not isinstance(artifacts.get(name), str)]
        if missing:
            raise NativeExecutionError("INVALID_EXECUTION_REQUEST", "Missing native execution artifacts: " + ", ".join(missing))
        if sum(isinstance(artifacts.get(name), str) for name in cls.PLANNING_INPUTS) != 1:
            raise NativeExecutionError("INVALID_EXECUTION_REQUEST", "Declare exactly one planning artifact: proposal_packet or brief")
        output = payload.get("output_path")
        if not isinstance(output, str) or not output.strip():
            raise NativeExecutionError("INVALID_EXECUTION_REQUEST", "execution_request.output_path is required")
        return cls(
            pipeline=str(payload.get("pipeline") or "").strip(),
            artifacts={str(key): str(value) for key, value in artifacts.items()},
            output_path=output,
            output_profile=str(payload["output_profile"]) if payload.get("output_profile") else None,
            remotion_timeout_ms=int(payload["remotion_timeout_ms"]) if payload.get("remotion_timeout_ms") else None,
            approved_silence=payload.get("approved_silence") is True,
            approved_checkpoints=tuple(sorted({
                str(stage).strip()
                for stage in (payload.get("approved_checkpoints") or [])
                if str(stage).strip()
            })),
        )


@dataclass
class NativeExecutionResult:
    success: bool
    code: str
    message: str
    fingerprint: str
    output_media: list[dict[str, Any]] = field(default_factory=list)
    openmontage_artifacts: list[dict[str, Any]] = field(default_factory=list)
    native_result: dict[str, Any] = field(default_factory=dict)
    compatibility: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NativeExecutionBridge:
    """Execute one OpenMontage delivery transaction without creative decisions.

    Hermes owns the contents of the canonical input artifacts. This bridge
    validates their declared runtime tuple and asks the pinned OpenMontage
    compatibility layer to execute exactly one native compose/review
    transaction. It has no stage router and no football-specific branches.
    """

    CONTRACT_VERSION = "acd-native-transaction-v2"

    def __init__(
        self,
        worker_root: Path,
        openmontage_root: Path,
        project_root: Path,
        *,
        timeout: int = 480,
        heartbeat_interval: float = 1.0,
    ):
        self.worker_root = Path(worker_root).expanduser().resolve()
        self.openmontage_root = Path(openmontage_root).expanduser().resolve()
        self.project_root = Path(project_root).expanduser().resolve()
        self.timeout = timeout
        self.heartbeat_interval = heartbeat_interval

    def prepare(self, payload: dict[str, Any]) -> tuple[NativeExecutionRequest, dict[str, Any], str]:
        request = NativeExecutionRequest.from_dict(payload)
        paths = self._validated_paths(request)
        edit = json.loads(paths["edit_decisions"].read_text(encoding="utf-8"))
        silence_plan = (edit.get("metadata") or {}).get("acd_silence_plan")
        audio = edit.get("audio") or {}
        declares_audio = bool(
            (audio.get("narration") or {}).get("segments")
            or audio.get("music")
            or audio.get("sfx")
            or edit.get("music")
        )
        if request.approved_silence:
            if not isinstance(silence_plan, dict) or silence_plan.get("intentional") is not True or not str(silence_plan.get("rationale") or "").strip():
                raise NativeExecutionError(
                    "UNAPPROVED_SILENCE_PLAN",
                    "Approved silence requires edit_decisions.metadata.acd_silence_plan with intentional=true and a rationale.",
                )
        elif not declares_audio:
            raise NativeExecutionError(
                "UNAPPROVED_SILENCE_PLAN",
                "The edit declares no narration, music or SFX and no typed silence approval was supplied.",
            )
        runtime = RuntimeTuple.from_edit_decisions(request.pipeline, edit)
        decision = OpenMontageCompatibilityRegistry(self.openmontage_root, self.worker_root).evaluate(runtime)
        if not decision.supported:
            raise NativeExecutionError(decision.code, decision.reason, decision.to_dict())
        self._validate_native_schemas(paths)
        self._validate_checkpoint_contract(request, paths)
        cross_errors = OpenMontageArtifactValidator(
            self.project_root,
            self.openmontage_root,
            self.project_root / "football_emotion" / "acd_agent_result.json",
        ).cross_artifact_errors(paths)
        if cross_errors:
            raise NativeExecutionError(
                "NATIVE_INPUT_INTEGRITY_INVALID",
                "Native artifacts are schema-valid but their media references are not executable.",
                {"errors": cross_errors},
            )
        fingerprint = self._fingerprint(request, paths)
        return request, decision.to_dict(), fingerprint

    def execute(
        self,
        payload: dict[str, Any],
        *,
        heartbeat: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> NativeExecutionResult:
        request, compatibility, fingerprint = self.prepare(payload)
        control_dir = self.project_root / "football_emotion"
        control_dir.mkdir(parents=True, exist_ok=True)
        command_path = control_dir / f"native-command-{fingerprint[:16]}.json"
        result_path = control_dir / f"native-result-{fingerprint[:16]}.json"
        command = {
            "schema_version": "1.0",
            "fingerprint": fingerprint,
            "project_dir": str(self.project_root),
            **asdict(request),
        }
        self._atomic_json(command_path, command)

        python = Path(os.environ.get("OPENMONTAGE_PYTHON", self.openmontage_root / ".venv" / "bin" / "python")).expanduser().absolute()
        adapter = self.worker_root / "scripts" / "openmontage_native_adapter.py"
        if not adapter.is_file():
            raise NativeExecutionError("NATIVE_ADAPTER_MISSING", f"Native adapter is missing: {adapter}")
        stdout_path = control_dir / f"native-stdout-{fingerprint[:16]}.log"
        stderr_path = control_dir / f"native-stderr-{fingerprint[:16]}.log"
        started = time.monotonic()
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                [str(python), str(adapter), "--openmontage-root", str(self.openmontage_root), "--command", str(command_path), "--result", str(result_path)],
                cwd=str(self.openmontage_root),
                stdout=stdout,
                stderr=stderr,
                env=os.environ.copy(),
                start_new_session=True,
            )
            try:
                while process.poll() is None:
                    elapsed = time.monotonic() - started
                    if elapsed > self.timeout:
                        _terminate_process_group(process)
                        raise NativeExecutionError("NATIVE_EXECUTION_TIMEOUT", f"OpenMontage execution exceeded {self.timeout}s", {"fingerprint": fingerprint})
                    if heartbeat:
                        heartbeat({"phase": "native_execution", "fingerprint": fingerprint, "elapsed_seconds": round(elapsed, 1)})
                    time.sleep(self.heartbeat_interval)
            except BaseException:
                if process.poll() is None:
                    _terminate_process_group(process)
                raise

        try:
            native = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:] if stderr_path.is_file() else ""
            raise NativeExecutionError(
                "NATIVE_RESULT_MISSING",
                f"OpenMontage adapter did not publish a valid result: {exc}",
                {"returncode": process.returncode, "stderr_tail": tail},
            ) from exc
        if process.returncode != 0 or native.get("status") != "delivered":
            raise NativeExecutionError(
                str(native.get("code") or "NATIVE_EXECUTION_FAILED"),
                str(native.get("message") or "OpenMontage native delivery failed"),
                {"returncode": process.returncode, "native_result": native, "fingerprint": fingerprint},
            )
        return NativeExecutionResult(
            True,
            "DELIVERED_CANDIDATE",
            "OpenMontage published a native render and review candidate.",
            fingerprint,
            output_media=native.get("output_media") or [],
            openmontage_artifacts=native.get("openmontage_artifacts") or [],
            native_result=native,
            compatibility=compatibility,
        )

    def _validated_paths(self, request: NativeExecutionRequest) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        artifacts_dir = (self.project_root / "artifacts").resolve()
        for kind, raw in request.artifacts.items():
            path = Path(raw).expanduser().resolve()
            try:
                path.relative_to(artifacts_dir)
            except ValueError as exc:
                raise NativeExecutionError("INVALID_ARTIFACT_PATH", f"{kind} must be under project artifacts/: {path}") from exc
            if path.name != f"{kind}.json":
                raise NativeExecutionError("INVALID_ARTIFACT_PATH", f"{kind} must use canonical filename {kind}.json")
            if not path.is_file():
                raise NativeExecutionError("NATIVE_ARTIFACT_MISSING", f"Missing native artifact: {path}")
            paths[kind] = path
        output = Path(request.output_path).expanduser().resolve()
        try:
            relative = output.relative_to(self.project_root)
        except ValueError as exc:
            raise NativeExecutionError("INVALID_OUTPUT_PATH", "Native output must stay inside the OpenMontage project") from exc
        if not relative.parts or relative.parts[0] != "renders" or output.suffix.lower() != ".mp4":
            raise NativeExecutionError("INVALID_OUTPUT_PATH", "Native output must be an MP4 under project renders/")
        return paths

    def _validate_native_schemas(self, paths: dict[str, Path]) -> None:
        python = Path(os.environ.get("OPENMONTAGE_PYTHON", self.openmontage_root / ".venv" / "bin" / "python")).expanduser().absolute()
        for kind, path in paths.items():
            script = "import json,sys; from schemas.artifacts import validate_artifact; validate_artifact(sys.argv[1], json.load(open(sys.argv[2], encoding='utf-8')))"
            result = subprocess.run(
                [str(python), "-c", script, kind, str(path)],
                cwd=str(self.openmontage_root),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "native validation failed")[-2000:]
                raise NativeExecutionError("NATIVE_INPUT_SCHEMA_INVALID", f"{kind} failed native schema validation", {"kind": kind, "detail": detail})

    def _validate_checkpoint_contract(self, request: NativeExecutionRequest, paths: dict[str, Path]) -> None:
        """Verify OpenMontage checkpoints and bind approvals to run policy."""
        python = Path(os.environ.get("OPENMONTAGE_PYTHON", self.openmontage_root / ".venv" / "bin" / "python")).expanduser().absolute()
        stage_by_artifact = {
            "proposal_packet": "proposal",
            "brief": "idea",
            "scene_plan": "scene_plan",
            "asset_manifest": "assets",
            "edit_decisions": "edit",
        }
        declared = {stage_by_artifact[kind]: kind for kind in paths if kind in stage_by_artifact}
        script = r'''import json,sys
from pathlib import Path
from lib.checkpoint import validate_checkpoint
from lib.pipeline_loader import get_stage_human_approval_default, load_pipeline_readonly
project=Path(sys.argv[1]); pipeline=sys.argv[2]; declared=json.loads(sys.argv[3])
manifest=load_pipeline_readonly(pipeline)
evidence=[]
for stage,kind in declared.items():
    path=project / ("checkpoint_" + stage + ".json")
    checkpoint=json.loads(path.read_text(encoding="utf-8"))
    validate_checkpoint(checkpoint)
    if checkpoint.get("project_id") != project.name:
        raise ValueError(f"{path.name} project does not match {project.name!r}")
    if checkpoint.get("stage") != stage:
        raise ValueError(f"{path.name} declares stage {checkpoint.get('stage')!r}")
    if checkpoint.get("pipeline_type") != pipeline:
        raise ValueError(f"{path.name} pipeline does not match {pipeline!r}")
    checkpoint_artifacts=checkpoint.get("artifacts") or {}
    if kind not in checkpoint_artifacts:
        raise ValueError(f"{path.name} does not carry canonical artifact {kind!r}")
    canonical=json.loads((project / "artifacts" / (kind + ".json")).read_text(encoding="utf-8"))
    if checkpoint_artifacts[kind] != canonical:
        raise ValueError(f"{path.name} carries stale or different content for {kind!r}")
    evidence.append({
        "stage": stage,
        "path": str(path),
        "status": checkpoint.get("status"),
        "manifest_requires_approval": bool(get_stage_human_approval_default(manifest, stage)),
        "human_approval_required": checkpoint.get("human_approval_required") is True,
        "human_approved": checkpoint.get("human_approved") is True,
    })
print(json.dumps(evidence, sort_keys=True))
'''
        result = subprocess.run(
            [str(python), "-c", script, str(self.project_root), request.pipeline, json.dumps(declared, sort_keys=True)],
            cwd=str(self.openmontage_root),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "checkpoint validation failed")[-3000:]
            raise NativeExecutionError(
                "NATIVE_CHECKPOINT_INVALID",
                "Native checkpoint evidence is missing or invalid.",
                {"detail": detail, "declared_stages": sorted(declared)},
            )
        try:
            evidence = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise NativeExecutionError(
                "NATIVE_CHECKPOINT_INVALID",
                "OpenMontage checkpoint validation returned malformed evidence.",
                {"stdout": result.stdout[-2000:]},
            ) from exc
        typed = set(request.approved_checkpoints)
        for item in evidence:
            stage = str(item.get("stage") or "")
            if item.get("status") != "completed":
                code = "CHECKPOINT_APPROVAL_MISSING" if item.get("status") == "awaiting_human" else "NATIVE_CHECKPOINT_INVALID"
                raise NativeExecutionError(code, f"Native checkpoint {stage!r} is not completed.", item)
            manifest_gate = item.get("manifest_requires_approval") is True
            checkpoint_gate = item.get("human_approval_required") is True
            if manifest_gate and not checkpoint_gate:
                raise NativeExecutionError(
                    "NATIVE_CHECKPOINT_INVALID",
                    f"Native checkpoint {stage!r} suppresses a manifest-required approval gate.",
                    item,
                )
            if (manifest_gate or checkpoint_gate) and item.get("human_approved") is not True:
                raise NativeExecutionError(
                    "CHECKPOINT_APPROVAL_MISSING",
                    f"Native checkpoint {stage!r} still requires user approval.",
                    item,
                )
            if item.get("human_approved") is True and stage not in typed:
                raise NativeExecutionError(
                    "UNAPPROVED_CHECKPOINT",
                    f"Native checkpoint {stage!r} claims approval not present in the typed run policy.",
                    {**item, "typed_approvals": sorted(typed)},
                )

    def _fingerprint(self, request: NativeExecutionRequest, paths: dict[str, Path]) -> str:
        identity = {
            "contract_version": self.CONTRACT_VERSION,
            "openmontage_commit": PINNED_OPENMONTAGE_COMMIT,
            "request": asdict(request),
            "compatibility_marker_sha256": self._file_digest(
                self.openmontage_root / COMPATIBILITY_MARKER
            ),
            "installed_delivery_overlay_sha256": self._file_digest(
                self.openmontage_root / "lib" / "acd_native_delivery.py"
            ),
            "worker_native_adapter_sha256": self._file_digest(
                self.worker_root / "scripts" / "openmontage_native_adapter.py"
            ),
            "worker_delivery_overlay_sha256": self._file_digest(
                self.worker_root / "patches" / "openmontage" / "overlay" / "lib" / "acd_native_delivery.py"
            ),
            "football_skill_sha256": self._tree_digest(
                Path(
                    os.environ.get(
                        "ACD_FOOTBALL_SKILL_ROOT",
                        self.worker_root / "skills" / "football-emotion-video",
                    )
                )
            ),
            "source_manifest_sha256": self._file_digest(
                self.project_root / "football_emotion" / "source_manifest.json"
            ),
        }
        digest = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        )
        for kind in sorted(paths):
            digest.update(kind.encode())
            digest.update(paths[kind].read_bytes())
        # Artifact JSON alone is not immutable lineage: an asset can be
        # replaced at the same path after its manifest/checkpoint was written.
        # Bind every manifest asset and every direct edit reference into the
        # transaction fingerprint so such a replacement forces a new native
        # compose/review transaction.
        for media in self._media_input_paths(paths):
            digest.update(str(media.relative_to(self.project_root)).encode())
            with media.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _file_digest(path: Path) -> str:
        path = Path(path).expanduser().resolve()
        if not path.is_file() or path.is_symlink():
            return "missing"
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def _tree_digest(cls, root: Path) -> str:
        root = Path(root).expanduser().resolve()
        if not root.is_dir():
            return "missing"
        digest = hashlib.sha256()
        for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
            if (
                not path.is_file()
                or path.is_symlink()
                or "__pycache__" in path.parts
                or path.suffix in {".pyc", ".pyo"}
            ):
                continue
            digest.update(str(path.relative_to(root)).encode())
            digest.update(cls._file_digest(path).encode())
        return digest.hexdigest()

    def _media_input_paths(self, paths: dict[str, Path]) -> list[Path]:
        manifest_path = paths["asset_manifest"]
        edit_path = paths["edit_decisions"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        edit = json.loads(edit_path.read_text(encoding="utf-8"))
        validator = OpenMontageArtifactValidator(
            self.project_root,
            self.openmontage_root,
            self.project_root / "football_emotion" / "acd_agent_result.json",
        )
        assets: dict[str, Path] = {}
        media: set[Path] = set()
        for item in manifest.get("assets") or []:
            resolved = validator._resolve_artifact_reference(item.get("path"), manifest_path)
            assets[str(item.get("id") or "")] = resolved
            media.add(resolved)

        references: list[str] = []
        references.extend(str(item.get("source") or "") for item in edit.get("cuts") or [])
        references.extend(str(item.get("asset_id") or "") for item in edit.get("overlays") or [])
        audio = edit.get("audio") or {}
        references.extend(str(item.get("asset_id") or "") for item in (audio.get("narration") or {}).get("segments") or [])
        music = audio.get("music") or edit.get("music") or {}
        if music.get("asset_id"):
            references.append(str(music["asset_id"]))
        references.extend(str(item.get("asset_id") or "") for item in audio.get("sfx") or [] if item.get("asset_id"))
        subtitles = edit.get("subtitles") or {}
        if subtitles.get("enabled") and subtitles.get("source"):
            references.append(str(subtitles["source"]))
        for reference in references:
            if reference and reference not in assets:
                media.add(validator._resolve_artifact_reference(reference, edit_path))
        return sorted(media, key=lambda item: str(item))

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
