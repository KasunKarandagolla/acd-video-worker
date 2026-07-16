"""Hermes-facing tools for one typed ACD/OpenMontage production run.

The plugin is intentionally small.  It does not choose a pipeline, author
creative content, route stages, or render.  Hermes supplies every creative
artifact/tool input; the isolated OpenMontage interpreter validates and
executes those explicit requests against the pinned native contracts.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


OPENMONTAGE_SCHEMA = {
    "name": "openmontage_native",
    "description": (
        "Use the pinned OpenMontage runtime without shell commands or ad-hoc Python. "
        "Call operation=status first. Use read_document for bounded read-only "
        "OpenMontage/project/Football references. Use publish_artifact for each Hermes-authored "
        "canonical artifact/checkpoint and run_tool for a chosen native OpenMontage "
        "tool. video_compose and source-tier tools are deliberately unavailable here: "
        "the ACD deterministic bridge renders after the edit handoff, and "
        "acd_acquire_source owns downloads."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "status", "read_document", "tool_info",
                    "publish_artifact", "run_tool",
                ],
            },
            "pipeline": {"type": "string"},
            "title": {"type": "string"},
            "kind": {"type": "string"},
            "artifact": {"type": "object", "additionalProperties": True},
            "tool_name": {"type": "string"},
            "inputs": {"type": "object", "additionalProperties": True},
            "scope": {
                "type": "string",
                "enum": ["openmontage", "project", "football"],
            },
            "path": {"type": "string"},
            "start_line": {"type": "integer", "minimum": 1},
            "line_count": {"type": "integer", "minimum": 1, "maximum": 240},
        },
        "required": ["operation"],
        "additionalProperties": False,
    },
}


ACQUIRE_SCHEMA = {
    "name": "acd_acquire_source",
    "description": (
        "Acquire one story slot through the worker-owned free-only/rights-aware source "
        "boundary. Candidates are tried in ranked order and the run source manifest is "
        "updated. Never call an OpenMontage source-tier tool or shell downloader instead."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "slot": {
                "type": "string",
                "pattern": "^[A-Za-z0-9_-]{1,80}$",
            },
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
        },
        "required": ["slot", "urls"],
        "additionalProperties": False,
    },
}


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _required_path(name: str) -> Path:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not configured for this production run")
    return Path(value).expanduser().resolve()


def _openmontage_command() -> list[str]:
    worker = _required_path("ACD_WORKER_ROOT")
    openmontage = _required_path("OPENMONTAGE_ROOT")
    python = Path(
        os.environ.get("OPENMONTAGE_PYTHON", str(openmontage / ".venv" / "bin" / "python"))
    ).expanduser().resolve()
    adapter = worker / "scripts" / "openmontage_creative_adapter.py"
    if not python.is_file():
        raise RuntimeError(f"Pinned OpenMontage Python is unavailable: {python}")
    if not adapter.is_file():
        raise RuntimeError(f"OpenMontage creative adapter is unavailable: {adapter}")
    return [str(python), str(adapter)]


def _invoke_adapter(args: dict[str, Any]) -> str:
    try:
        openmontage = _required_path("OPENMONTAGE_ROOT")
        completed = subprocess.run(
            _openmontage_command(),
            input=json.dumps(args),
            capture_output=True,
            text=True,
            timeout=420,
            cwd=str(openmontage),
            env=os.environ.copy(),
            check=False,
        )
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        return _json({"success": False, "code": "OPENMONTAGE_TOOL_BRIDGE_UNAVAILABLE", "error": str(exc)})
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return _json({
            "success": False,
            "code": "OPENMONTAGE_TOOL_BRIDGE_PROTOCOL_ERROR",
            "error": (completed.stderr or completed.stdout or "adapter returned no JSON")[-3000:],
            "returncode": completed.returncode,
        })
    if completed.returncode != 0:
        payload.setdefault("success", False)
        payload.setdefault("returncode", completed.returncode)
    return _json(payload)


def handle_openmontage(args: dict[str, Any], **_kwargs) -> str:
    return _invoke_adapter(dict(args or {}))


def handle_acquire(args: dict[str, Any], **_kwargs) -> str:
    try:
        worker = _required_path("ACD_WORKER_ROOT")
        manifest = _required_path("ACD_SOURCE_MANIFEST")
        project = _required_path("ACD_PROJECT_DIR")
        python = Path(os.environ.get("ACD_WORKER_PYTHON", sys.executable)).expanduser().resolve()
        command = [
            str(python), str(worker / "scripts" / "acquire_sources.py"),
            "--manifest", str(manifest),
            "--output-dir", str(project / "source_media"),
            "--slot", str(args.get("slot") or ""),
        ]
        for url in args.get("urls") or []:
            command.extend(["--url", str(url)])
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=900,
            cwd=str(worker),
            env=os.environ.copy(),
            check=False,
        )
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        return _json({"status": "blocked", "code": "ACQUISITION_BOUNDARY_UNAVAILABLE", "message": str(exc)})
    try:
        return _json(json.loads(completed.stdout))
    except json.JSONDecodeError:
        return _json({
            "status": "failed",
            "code": "ACQUISITION_PROTOCOL_ERROR",
            "message": (completed.stderr or completed.stdout or "acquisition returned no JSON")[-3000:],
            "returncode": completed.returncode,
        })


def check_runtime() -> bool:
    try:
        worker = _required_path("ACD_WORKER_ROOT")
        openmontage = _required_path("OPENMONTAGE_ROOT")
        project = _required_path("ACD_PROJECT_DIR")
        source_manifest = _required_path("ACD_SOURCE_MANIFEST")
        command = _openmontage_command()
        return all((
            worker.is_dir(),
            (worker / "scripts" / "acd_worker.py").is_file(),
            openmontage.is_dir(),
            (openmontage / "AGENT_GUIDE.md").is_file(),
            project.is_dir(),
            source_manifest.is_file(),
            _required_path("ACD_FOOTBALL_SKILL_ROOT").is_dir(),
            Path(command[0]).is_file(),
            Path(command[1]).is_file(),
        ))
    except RuntimeError:
        return False


def register(ctx) -> None:
    ctx.register_tool(
        name="openmontage_native",
        toolset="acd-openmontage",
        schema=OPENMONTAGE_SCHEMA,
        handler=handle_openmontage,
        check_fn=check_runtime,
        description=OPENMONTAGE_SCHEMA["description"],
        emoji="🎬",
    )
    ctx.register_tool(
        name="acd_acquire_source",
        toolset="acd-openmontage",
        schema=ACQUIRE_SCHEMA,
        handler=handle_acquire,
        check_fn=check_runtime,
        description=ACQUIRE_SCHEMA["description"],
        emoji="🛡️",
    )
