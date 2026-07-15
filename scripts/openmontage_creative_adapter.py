#!/usr/bin/env python3
"""Isolated typed authoring/tool boundary for Hermes and pinned OpenMontage.

Hermes remains the author and workflow decision maker.  This adapter only
initializes the exact project workspace, validates/publishes one supplied
canonical artifact, or invokes one explicitly selected native tool.  It has no
creative defaults, stage loop, renderer, or fallback path.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


STAGE_BY_ARTIFACT = {
    "research_brief": "research",
    "proposal_packet": "proposal",
    "brief": "idea",
    "script": "script",
    "scene_plan": "scene_plan",
    "asset_manifest": "assets",
    "edit_decisions": "edit",
}
FORBIDDEN_TIERS = {"source", "publish"}
FORBIDDEN_TOOLS = {"video_compose"}
CERTIFIED_CREATIVE_TOOLS = {
    "audio_enhance",
    "audio_mixer",
    "color_grade",
    "math_animate",
    "subtitle_gen",
    "video_analyzer",
}
SCHEMA_KINDS = tuple(STAGE_BY_ARTIFACT)
READABLE_SUFFIXES = {".json", ".md", ".txt", ".yaml", ".yml"}


def _emit(payload: dict[str, Any], status: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
    return status


def _error(code: str, message: str, *, evidence: dict[str, Any] | None = None, status: int = 1) -> int:
    return _emit({"success": False, "code": code, "error": message, "evidence": evidence or {}}, status)


def _required_path(name: str) -> Path:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is not configured")
    return Path(value).expanduser().resolve()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


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


def _policy() -> dict[str, Any]:
    try:
        payload = json.loads(os.environ.get("ACD_APPROVAL_POLICY_JSON", "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("ACD_APPROVAL_POLICY_JSON is invalid") from exc
    return payload if isinstance(payload, dict) else {}


def _locked_pipeline(requested: str | None) -> str:
    runtime = _policy().get("runtime_tuple") or {}
    locked = str(runtime.get("pipeline") or "").strip()
    selected = str(requested or locked or "").strip()
    if not selected:
        raise ValueError("pipeline must be selected by Hermes or locked by typed run policy")
    if locked and selected != locked:
        raise ValueError(f"pipeline {selected!r} differs from typed approved pipeline {locked!r}")
    return selected


def _load_native(openmontage: Path) -> None:
    if str(openmontage) not in sys.path:
        sys.path.insert(0, str(openmontage))


def _source_manifest() -> dict[str, Any]:
    path = _required_path("ACD_SOURCE_MANIFEST")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"worker source manifest is unavailable: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("worker source manifest must be a JSON object")
    return value


def _document_path(
    scope: str,
    relative: str,
    *,
    project: Path,
    openmontage: Path,
) -> Path:
    """Resolve one allowlisted read-only production document."""
    raw = Path(str(relative or ""))
    if not relative or raw.is_absolute() or ".." in raw.parts:
        raise ValueError("read_document.path must be a safe relative path")
    if scope == "openmontage":
        root = openmontage
        parts = raw.parts
        allowed = (
            str(raw) in {"AGENT_GUIDE.md", "PROJECT_CONTEXT.md"}
            or parts[:1] == ("pipeline_defs",)
            or parts[:2] == ("schemas", "artifacts")
            or parts[:2] == ("skills", "pipelines")
            or parts[:2] == ("skills", "meta")
            or parts[:2] == (".agents", "skills")
        )
    elif scope == "project":
        root = project
        parts = raw.parts
        allowed = (
            str(raw) == "project.json"
            or (len(parts) == 1 and parts[0].startswith("checkpoint_") and raw.suffix == ".json")
            or (len(parts) == 2 and parts[0] == "artifacts" and raw.suffix == ".json")
            or str(raw) == "football_emotion/source_manifest.json"
        )
    elif scope == "football":
        root = _required_path("ACD_FOOTBALL_SKILL_ROOT")
        parts = raw.parts
        allowed = (
            (len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md")
            or parts[:2] == ("shared", "references")
            or parts[:2] == ("shared", "contracts")
        )
    else:
        raise ValueError(f"unsupported read_document scope: {scope!r}")
    path = (root / raw).resolve()
    if not allowed or not _inside(path, root):
        raise ValueError(f"document is outside the {scope} read allowlist: {relative}")
    if path.suffix.lower() not in READABLE_SUFFIXES or not path.is_file():
        raise ValueError(f"readable document is unavailable: {path}")
    if path.stat().st_size > 1_000_000:
        raise ValueError(f"document exceeds the bounded read limit: {path}")
    return path


def _read_document(project: Path, openmontage: Path, args: dict[str, Any]) -> dict[str, Any]:
    scope = str(args.get("scope") or "").strip()
    relative = str(args.get("path") or "").strip()
    start = int(args.get("start_line") or 1)
    count = int(args.get("line_count") or 160)
    if start < 1 or not 1 <= count <= 240:
        raise ValueError("read_document requires start_line >= 1 and line_count between 1 and 240")
    path = _document_path(scope, relative, project=project, openmontage=openmontage)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    selected = lines[start - 1 : start - 1 + count]
    return {
        "success": True,
        "operation": "read_document",
        "scope": scope,
        "path": relative,
        "start_line": start,
        "end_line": start + len(selected) - 1 if selected else start - 1,
        "total_lines": len(lines),
        "truncated": start - 1 + len(selected) < len(lines),
        "content": "\n".join(selected),
    }


def _project_status(project: Path, openmontage: Path, args: dict[str, Any]) -> dict[str, Any]:
    _load_native(openmontage)
    from lib.checkpoint import CANONICAL_STAGE_ARTIFACTS, get_pipeline_stages, init_project
    from lib.pipeline_loader import load_pipeline_readonly
    from schemas.artifacts import load_schema, validate_artifact
    from tools.tool_registry import registry

    pipeline = _locked_pipeline(args.get("pipeline"))
    title = str(args.get("title") or project.name).strip()[:200]
    initialized = init_project(
        project.name,
        title=title,
        pipeline_type=pipeline,
        pipeline_dir=project.parent,
    )
    if initialized.resolve() != project:
        raise ValueError(f"OpenMontage initialized an unexpected project path: {initialized}")

    stages = get_pipeline_stages(pipeline)
    manifest = load_pipeline_readonly(pipeline)
    progress: list[dict[str, Any]] = []
    for stage in stages:
        kind = CANONICAL_STAGE_ARTIFACTS.get(stage)
        artifact_path = project / "artifacts" / f"{kind}.json" if kind else None
        checkpoint_path = project / f"checkpoint_{stage}.json"
        artifact_valid = False
        if artifact_path and artifact_path.is_file():
            try:
                validate_artifact(kind, json.loads(artifact_path.read_text(encoding="utf-8")))
                artifact_valid = True
            except Exception:
                artifact_valid = False
        checkpoint_status = None
        if checkpoint_path.is_file():
            try:
                checkpoint_status = json.loads(checkpoint_path.read_text(encoding="utf-8")).get("status")
            except (OSError, json.JSONDecodeError):
                checkpoint_status = "invalid"
        progress.append({
            "stage": stage,
            "artifact_kind": kind,
            "artifact_valid": artifact_valid,
            "checkpoint_status": checkpoint_status,
        })

    schemas = {}
    for kind in SCHEMA_KINDS:
        schema = load_schema(kind)
        schemas[kind] = {
            "required": schema.get("required") or [],
            "path": str(openmontage / "schemas" / "artifacts" / f"{kind}.schema.json"),
        }

    registry.discover()
    suggested_names = (
        "math_animate", "video_analyzer", "audio_mixer", "audio_enhance",
        "subtitle_gen", "color_grade",
    )
    tools = []
    for name in suggested_names:
        tool = registry.get(name)
        if tool is None:
            continue
        info = tool.get_info()
        tools.append({
            "name": name,
            "status": info.get("status"),
            "tier": info.get("tier"),
            "runtime": info.get("runtime"),
            "provider": info.get("provider"),
        })
    stage_contracts = []
    for item in manifest.get("stages") or []:
        if item.get("name") in {"compose", "publish"}:
            continue
        stage_contracts.append({
            key: item.get(key)
            for key in (
                "name", "skill", "required_artifacts_in", "optional_artifacts_in",
                "produces", "required_tools", "optional_tools", "tools_available",
                "human_approval_default", "review_focus", "success_criteria",
            )
            if item.get(key) not in (None, [], {})
        })
    return {
        "success": True,
        "operation": "status",
        "project_dir": str(project),
        "pipeline": pipeline,
        "stages": stages,
        "progress": progress,
        "artifact_schemas": schemas,
        "stage_contracts": stage_contracts,
        "source_manifest": _source_manifest(),
        "suggested_tools": tools,
        "rules": {
            "publish_with": "openmontage_native(operation=publish_artifact)",
            "run_tools_with": "openmontage_native(operation=run_tool)",
            "render_owner": "ACD deterministic bridge after edit handoff",
            "source_owner": "acd_acquire_source",
            "read_owner": "openmontage_native(operation=read_document)",
        },
    }


def _publish_artifact(project: Path, openmontage: Path, args: dict[str, Any]) -> dict[str, Any]:
    _load_native(openmontage)
    from lib.checkpoint import (
        CANONICAL_STAGE_ARTIFACTS,
        get_pipeline_stages,
        validate_checkpoint,
        write_checkpoint,
    )
    from lib.pipeline_loader import get_stage_human_approval_default, load_pipeline_readonly
    from schemas.artifacts import validate_artifact

    kind = str(args.get("kind") or "").strip()
    artifact = args.get("artifact")
    if kind not in STAGE_BY_ARTIFACT:
        raise ValueError(f"unsupported creative artifact kind: {kind!r}")
    if not isinstance(artifact, dict):
        raise ValueError("artifact must be a JSON object")
    validate_artifact(kind, artifact)

    marker_path = project / "project.json"
    if not marker_path.is_file():
        raise ValueError("call openmontage_native operation=status before publishing artifacts")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    pipeline = _locked_pipeline(str(marker.get("pipeline_type") or ""))
    stage = STAGE_BY_ARTIFACT[kind]
    stages = get_pipeline_stages(pipeline)
    if stage not in stages:
        raise ValueError(f"artifact {kind!r} does not belong to pipeline {pipeline!r}")

    # OpenMontage owns the ordered pipeline.  Enforce that order mechanically
    # so a malformed model call cannot publish a later stage over missing or
    # awaiting prerequisites.
    for prior_stage in stages[: stages.index(stage)]:
        prior_kind = CANONICAL_STAGE_ARTIFACTS.get(prior_stage)
        prior_checkpoint = project / f"checkpoint_{prior_stage}.json"
        prior_artifact = project / "artifacts" / f"{prior_kind}.json" if prior_kind else None
        try:
            checkpoint_payload = json.loads(prior_checkpoint.read_text(encoding="utf-8"))
            validate_checkpoint(checkpoint_payload)
        except Exception as exc:
            raise ValueError(
                f"cannot publish {stage!r} before schema-valid checkpoint {prior_stage!r}: {exc}"
            ) from exc
        if checkpoint_payload.get("status") != "completed":
            raise ValueError(
                f"cannot publish {stage!r}; prior checkpoint {prior_stage!r} "
                f"is {checkpoint_payload.get('status')!r}"
            )
        if prior_artifact and not prior_artifact.is_file():
            raise ValueError(f"prior canonical artifact is missing: {prior_artifact}")

    manifest = load_pipeline_readonly(pipeline)
    requires_approval = bool(get_stage_human_approval_default(manifest, stage))
    typed_approvals = {
        str(item) for item in (_policy().get("approved_checkpoints") or [])
    }
    approved = stage in typed_approvals
    status = "completed" if not requires_approval or approved else "awaiting_human"
    artifact_path = project / "artifacts" / f"{kind}.json"
    checkpoint_existing = project / f"checkpoint_{stage}.json"
    if artifact_path.is_file() and checkpoint_existing.is_file():
        try:
            existing_artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            existing_checkpoint = json.loads(checkpoint_existing.read_text(encoding="utf-8"))
            validate_checkpoint(existing_checkpoint)
        except Exception:
            existing_artifact = existing_checkpoint = None
        if (
            existing_artifact == artifact
            and isinstance(existing_checkpoint, dict)
            and (existing_checkpoint.get("artifacts") or {}).get(kind) == artifact
            and existing_checkpoint.get("status") == status
        ):
            return {
                "success": True,
                "operation": "publish_artifact",
                "kind": kind,
                "stage": stage,
                "status": status,
                "reused": True,
                "artifact_path": str(artifact_path),
                "checkpoint_path": str(checkpoint_existing),
                **({
                    "blocker": {
                        "code": "APPROVAL_REQUIRED",
                        "message": f"Typed approval for checkpoint {stage!r} is required.",
                    },
                } if status == "awaiting_human" else {}),
            }

    artifact_sha = hashlib.sha256(
        json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    previous_artifact = artifact_path.read_bytes() if artifact_path.is_file() else None
    _atomic_json(artifact_path, artifact)
    try:
        checkpoint_path = write_checkpoint(
            project.parent,
            project.name,
            stage,
            status,
            artifacts={kind: artifact},
            pipeline_type=pipeline,
            human_approval_required=requires_approval,
            human_approved=approved,
            metadata={
                "acd_authored_by": "hermes",
                "acd_run_id": os.environ.get("ACD_RUN_ID", ""),
                "acd_artifact_sha256": artifact_sha,
            },
        )
    except Exception:
        if previous_artifact is None:
            artifact_path.unlink(missing_ok=True)
        else:
            fd, temporary = tempfile.mkstemp(prefix=f".{artifact_path.name}.", dir=artifact_path.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(previous_artifact)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, artifact_path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        raise
    return {
        "success": True,
        "operation": "publish_artifact",
        "kind": kind,
        "stage": stage,
        "status": status,
        "artifact_path": str(artifact_path),
        "checkpoint_path": str(checkpoint_path),
        **({
            "blocker": {
                "code": "APPROVAL_REQUIRED",
                "message": f"Typed approval for checkpoint {stage!r} is required.",
            },
        } if status == "awaiting_human" else {}),
    }


def _tool_info(openmontage: Path, args: dict[str, Any]) -> dict[str, Any]:
    _load_native(openmontage)
    from tools.tool_registry import registry

    name = str(args.get("tool_name") or "").strip()
    if not name:
        raise ValueError("tool_name is required")
    if name not in CERTIFIED_CREATIVE_TOOLS:
        raise ValueError(
            f"OpenMontage tool {name!r} is outside the certified creative bridge: "
            f"{sorted(CERTIFIED_CREATIVE_TOOLS)}"
        )
    registry.discover()
    tool = registry.get(name)
    if tool is None:
        raise ValueError(f"OpenMontage ToolRegistry has no tool named {name!r}")
    info = tool.get_info()
    return {
        "success": True,
        "operation": "tool_info",
        "tool": {
            key: info.get(key)
            for key in (
                "name", "tier", "capability", "provider", "status", "runtime",
                "stability", "input_schema", "agent_skills", "best_for", "not_good_for",
                "side_effects", "resource_profile", "retry_policy",
            )
        },
    }


def _journal_path(project: Path) -> Path:
    return project / "football_emotion" / "creative_tool_journal.json"


def _read_journal(project: Path) -> dict[str, Any]:
    path = _journal_path(project)
    if not path.is_file():
        return {"version": "1.0", "outputs": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        value = {}
    return value if isinstance(value, dict) else {"version": "1.0", "outputs": {}}


def _output_path(inputs: dict[str, Any]) -> Path | None:
    for key in ("output_path", "output_dir", "video_output_path"):
        raw = inputs.get(key)
        if raw:
            return Path(str(raw)).expanduser().resolve()
    return None


def _output_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    return 0


def _validate_tool_paths(project: Path, name: str, inputs: dict[str, Any], info: dict[str, Any]) -> None:
    """Keep native creative tool I/O inside the run workspace."""
    schema = info.get("input_schema") if isinstance(info.get("input_schema"), dict) else {}
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    output_fields = {
        key for key in properties
        if key in {"output_path", "output_dir", "video_output_path", "metadata_path"}
    }
    if info.get("side_effects") and output_fields and not any(inputs.get(key) for key in output_fields):
        raise ValueError(
            f"OpenMontage tool {name!r} must declare one project-contained output field: "
            f"{sorted(output_fields)}"
        )

    def visit(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                visit(child, str(child_key))
            return
        if isinstance(value, list):
            for child in value:
                visit(child, key)
            return
        if not isinstance(value, str) or key not in {
            "path", "source", "input_path", "output_path", "output_dir",
            "video_output_path", "metadata_path",
        }:
            return
        if value.startswith(("http://", "https://", "www.")):
            raise ValueError(
                f"URL input in {key!r} bypasses the worker source boundary; use acd_acquire_source"
            )
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            raise ValueError(f"tool path field {key!r} must be an absolute project path")
        if not _inside(candidate, project):
            raise ValueError(f"tool path field {key!r} must stay inside the project: {candidate}")

    visit(inputs)


def _run_tool(project: Path, openmontage: Path, args: dict[str, Any]) -> dict[str, Any]:
    _load_native(openmontage)
    from tools.tool_registry import registry

    name = str(args.get("tool_name") or "").strip()
    inputs = args.get("inputs")
    if not name or not isinstance(inputs, dict):
        raise ValueError("tool_name and inputs object are required")
    if name in FORBIDDEN_TOOLS:
        raise ValueError(f"{name} is reserved for the deterministic post-edit bridge")
    if name not in CERTIFIED_CREATIVE_TOOLS:
        raise ValueError(
            f"OpenMontage tool {name!r} is outside the certified creative bridge: "
            f"{sorted(CERTIFIED_CREATIVE_TOOLS)}"
        )

    registry.discover()
    tool = registry.get(name)
    if tool is None:
        raise ValueError(f"OpenMontage ToolRegistry has no tool named {name!r}")
    info = tool.get_info()
    if str(info.get("tier") or "") in FORBIDDEN_TIERS:
        raise ValueError(
            f"OpenMontage {info.get('tier')} tool {name!r} is outside this bridge; "
            "use acd_acquire_source for sources and the deterministic bridge for publishing"
        )
    if info.get("status") != "available":
        raise ValueError(f"OpenMontage tool {name!r} is not available: {info.get('status')}")
    _validate_tool_paths(project, name, inputs, info)
    estimated = float(tool.estimate_cost(inputs) or 0.0)
    if estimated > 0:
        raise ValueError(f"OpenMontage tool {name!r} estimates ${estimated:.4f}; this run is strictly zero-cost")

    output = _output_path(inputs)
    if output and not _inside(output, project):
        raise ValueError(f"tool output_path must stay inside the project workspace: {output}")
    if name == "math_animate":
        inputs = dict(inputs)
        inputs["allow_unsafe_code"] = False

    journal = _read_journal(project)
    outputs = journal.setdefault("outputs", {})
    output_key = str(output) if output else ""
    entry = outputs.get(output_key) if output_key else None
    if output and _output_size(output) > 0 and isinstance(entry, dict) and entry.get("success") is True:
        return {
            "success": True,
            "operation": "run_tool",
            "tool_name": name,
            "reused": True,
            "output_path": str(output),
            "size_bytes": _output_size(output),
        }
    attempts = int((entry or {}).get("attempts") or 0) if output_key else 0
    if output_key and attempts >= 2:
        raise ValueError(f"corrected retry budget exhausted for output {output}; author a blocker instead of looping")

    input_hash = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    if output_key:
        outputs[output_key] = {
            "tool_name": name,
            "attempts": attempts + 1,
            "success": False,
            "input_sha256": input_hash,
        }
        _atomic_json(_journal_path(project), journal)
    result = tool.execute(inputs)
    if output_key:
        outputs[output_key].update({
            "success": bool(result.success),
            "error": str(result.error or "")[-2000:],
            "cost_usd": float(result.cost_usd or 0.0),
        })
        _atomic_json(_journal_path(project), journal)
    if float(result.cost_usd or 0.0) > 0:
        raise ValueError(f"OpenMontage tool {name!r} reported non-zero cost after execution")
    return {
        "success": bool(result.success),
        "operation": "run_tool",
        "tool_name": name,
        "data": result.data,
        "artifacts": result.artifacts,
        "error": result.error,
        "duration_seconds": result.duration_seconds,
        "cost_usd": result.cost_usd,
        **({"output_path": str(output)} if output else {}),
    }


def main() -> int:
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object")
        worker = _required_path("ACD_WORKER_ROOT")
        openmontage = _required_path("OPENMONTAGE_ROOT")
        project = _required_path("ACD_PROJECT_DIR")
        if not (worker / "scripts" / "acd_worker.py").is_file():
            raise ValueError(f"ACD worker root is invalid: {worker}")
        if not (openmontage / "AGENT_GUIDE.md").is_file():
            raise ValueError(f"pinned OpenMontage root is invalid: {openmontage}")
        projects_root = _required_path("OPENMONTAGE_PROJECTS_DIR")
        if not _inside(project, projects_root):
            raise ValueError(f"project is outside OPENMONTAGE_PROJECTS_DIR: {project}")

        operation = str(request.get("operation") or "").strip()
        if operation == "status":
            payload = _project_status(project, openmontage, request)
        elif operation == "read_document":
            payload = _read_document(project, openmontage, request)
        elif operation == "tool_info":
            payload = _tool_info(openmontage, request)
        elif operation == "publish_artifact":
            payload = _publish_artifact(project, openmontage, request)
        elif operation == "run_tool":
            payload = _run_tool(project, openmontage, request)
        else:
            raise ValueError(f"unsupported operation: {operation!r}")
        return _emit(payload)
    except ValueError as exc:
        return _error("OPENMONTAGE_CONTRACT_REJECTED", str(exc))
    except Exception as exc:
        name = type(exc).__name__
        code = (
            "OPENMONTAGE_ARTIFACT_INVALID"
            if name in {"ValidationError", "CheckpointValidationError"}
            else "OPENMONTAGE_ADAPTER_FAILED"
        )
        return _error(code, str(exc), evidence={"error_type": name})


if __name__ == "__main__":
    raise SystemExit(main())
