#!/usr/bin/env python3
"""Run the real Hermes/provider/plugin/OpenMontage status contract once.

Static configuration checks cannot prove that the selected provider returns an
executable tool call. This bounded gate uses the same HermesRunner, profile,
event adapter, named plugin and pinned OpenMontage interpreter as production,
but permits only the harmless native status operation and never renders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from acd_worker.hermes_runner import HermesRunner


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _file_digest(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tree_digest(root: Path) -> str:
    if not root.is_dir():
        return "missing"
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
        if not path.is_file() or path.is_symlink() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        digest.update(str(path.relative_to(root)).encode())
        digest.update(_file_digest(path).encode())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Certify the live Hermes native tool path")
    parser.add_argument("--worker-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("/kaggle/working/acd-runtime-validation/runtime-certificate.json"))
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    worker = args.worker_root.expanduser().resolve()
    hermes_home = Path(os.environ.get("HERMES_HOME", "/kaggle/working/.hermes")).expanduser().resolve()
    profile = os.environ.get("HERMES_PROFILE", "football-emotion")
    profile_dir = hermes_home / "profiles" / profile
    openmontage = Path(os.environ.get("OPENMONTAGE_ROOT", worker / "external" / "OpenMontage")).expanduser().resolve()
    openmontage_python = Path(os.environ.get("OPENMONTAGE_PYTHON", openmontage / ".venv" / "bin" / "python")).expanduser().resolve()
    model = os.environ.get("ACD_HERMES_MODEL_OVERRIDE") or os.environ.get("LLM_MODEL") or ""
    runtime_identity = {
        "profile": profile,
        "model": model,
        "profile_config_sha256": _file_digest(profile_dir / "config.yaml"),
        "plugin_sha256": _tree_digest(profile_dir / "plugins" / "acd-openmontage"),
        "football_skill_sha256": _tree_digest(profile_dir / "skills" / "football-emotion-video"),
        "worker_adapter_sha256": _file_digest(worker / "scripts" / "hermes_event_adapter.py"),
        "openmontage_marker_sha256": _file_digest(openmontage / ".acd-compatibility-patches.json"),
    }
    contract_seed = json.dumps(runtime_identity, sort_keys=True).encode()
    contract_id = hashlib.sha256(contract_seed).hexdigest()

    with tempfile.TemporaryDirectory(prefix="acd-hermes-live-gate-") as tmp:
        project = Path(tmp).resolve()
        control = project / "football_emotion"
        control.mkdir(parents=True)
        source_manifest = control / "source_manifest.json"
        source_manifest.write_text(
            json.dumps({"schema_version": "1.0", "policy": {"free_only": True}, "sources": []}) + "\n",
            encoding="utf-8",
        )
        runner = HermesRunner(
            str(hermes_home),
            profile=profile,
            timeout=args.timeout,
            cwd=project,
            max_turns=3,
            model_override=model or None,
        )
        execution = runner.run_session(
            prompt=(
                "This is a bounded production compatibility gate. Execute the forced "
                "openmontage_native status call. After it succeeds, reply exactly ACD_NATIVE_GATE_READY. "
                "Do not call any other tool and do not create or render media."
            ),
            expected_skills=[],
            max_turns=3,
            environment={
                "ACD_WORKER_ROOT": str(worker),
                "OPENMONTAGE_ROOT": str(openmontage),
                "OPENMONTAGE_PYTHON": str(openmontage_python),
                "ACD_PROJECT_DIR": str(project),
                "ACD_SOURCE_MANIFEST": str(source_manifest),
                "ACD_FOOTBALL_SKILL_ROOT": str(profile_dir / "skills" / "football-emotion-video"),
                "ACD_RUN_ID": "live-tool-contract-gate",
                "ACD_FORCE_INITIAL_OPENMONTAGE_TOOL": "1",
                "ACD_HERMES_TOOL_CONTRACT_ID": contract_id,
                "ACD_APPROVAL_POLICY_JSON": json.dumps({
                    "approved_checkpoints": [],
                    "approved_silence": False,
                    "runtime_tuple": {
                        "pipeline": "cinematic",
                        "composition_mode": "templated",
                        "renderer_family": "cinematic-trailer",
                        "render_runtime": "remotion",
                    },
                }, sort_keys=True),
                "ACD_APPROVED_CHECKPOINTS": "[]",
                "ACD_APPROVED_RUNTIME_TUPLE": "{}",
                "ACD_APPROVED_SILENCE": "false",
            },
        )

    summary = (execution.metadata or {}).get("event_summary") or {}
    handshake = summary.get("tool_handshake") or {}
    agent = summary.get("agent_contract") or {}
    first_request = summary.get("first_request_contract") or {}
    first_response = summary.get("first_response_contract") or {}
    live_valid = all((
        execution.success,
        agent.get("has_openmontage_native") in {True, "True", "true"},
        handshake.get("required") is True,
        handshake.get("completed") is True,
        handshake.get("failed") is not True,
        first_request.get("status_only") in {True, "True", "true"},
        first_request.get("tool_choice_name") == "openmontage_native",
        first_response.get("status_operation") in {True, "True", "true"},
    ))
    static_path = args.output.expanduser().resolve().parent / "thin-validation.json"
    try:
        static_validation = json.loads(static_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        static_validation = None
    static_valid = bool(
        isinstance(static_validation, dict)
        and static_validation.get("production_path_complete") is True
    )
    valid = live_valid and static_valid
    certificate = {
        "schema_version": "1.0",
        "valid": valid,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "model": model,
        "contract_id": contract_id,
        "runtime_identity": runtime_identity,
        "static_validation": {
            "valid": static_valid,
            "path": str(static_path),
            "sha256": _file_digest(static_path),
            "summary": (static_validation or {}).get("summary") if isinstance(static_validation, dict) else None,
            "runtime_identity": (static_validation or {}).get("runtime_identity") if isinstance(static_validation, dict) else None,
        },
        "live_tool_contract_valid": live_valid,
        "session_id": execution.session_id,
        "returncode": execution.returncode,
        "event_summary": summary,
        "error": execution.error if not execution.success else None,
    }
    _atomic_json(args.output.expanduser().resolve(), certificate)
    print(json.dumps(certificate, indent=2, sort_keys=True))
    return 0 if valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
