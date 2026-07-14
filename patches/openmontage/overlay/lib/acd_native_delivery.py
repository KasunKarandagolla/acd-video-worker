"""ACD compatibility extension: one native compose/review transaction.

This module is installed into the pinned OpenMontage checkout by an explicit,
hashed compatibility overlay. It owns the OpenMontage ToolResult-to-artifact
handoff so the ACD worker never fabricates native render or review artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from lib.checkpoint import write_checkpoint
from schemas.artifacts import validate_artifact
from tools.tool_registry import registry


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("ffprobe rejected the native render")
    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if not video:
        raise RuntimeError("native render has no video stream")
    rate = str(video.get("avg_frame_rate") or "0/1").split("/", 1)
    fps = float(rate[0]) / max(float(rate[1]), 1.0)
    return {
        "duration": float((payload.get("format") or {}).get("duration") or 0),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": fps,
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None,
    }


def _artifact_entries(command: dict[str, Any], render_report: Path, final_review: Path) -> list[dict[str, str]]:
    entries = [{"kind": kind, "path": str(Path(path).resolve())} for kind, path in command["artifacts"].items()]
    entries.extend((
        {"kind": "render_report", "path": str(render_report)},
        {"kind": "final_review", "path": str(final_review)},
    ))
    return entries


def _existing_delivery(command: dict[str, Any], render_report_path: Path, final_review_path: Path, output_path: Path) -> dict[str, Any] | None:
    try:
        report = json.loads(render_report_path.read_text(encoding="utf-8"))
        review = json.loads(final_review_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    metadata = report.get("metadata") or {}
    if metadata.get("acd_input_fingerprint") != command["fingerprint"] or not output_path.is_file():
        return None
    if metadata.get("output_sha256") != _sha256(output_path):
        return None
    review_metadata = review.get("metadata") or {}
    if review_metadata.get("acd_input_fingerprint") != command["fingerprint"]:
        return None
    if review_metadata.get("output_sha256") != metadata.get("output_sha256"):
        return None
    validate_artifact("render_report", report)
    validate_artifact("final_review", review)
    if review.get("status") != "pass" or review.get("recommended_action") != "present_to_user":
        return None
    return {
        "schema_version": "1.0",
        "status": "delivered",
        "reused": True,
        "fingerprint": command["fingerprint"],
        "output_media": [{
            "role": "primary", "path": str(output_path), "sha256": metadata["output_sha256"],
            "approved_silence": command.get("approved_silence") is True,
        }],
        "openmontage_artifacts": _artifact_entries(command, render_report_path, final_review_path),
    }


def execute_delivery(command: dict[str, Any]) -> dict[str, Any]:
    project_dir = Path(command["project_dir"]).expanduser().resolve()
    output_path = Path(command["output_path"]).expanduser().resolve()
    artifacts_dir = project_dir / "artifacts"
    render_report_path = artifacts_dir / "render_report.json"
    final_review_path = artifacts_dir / "final_review.json"
    journal_path = project_dir / "football_emotion" / "native_transaction.json"

    existing = _existing_delivery(command, render_report_path, final_review_path, output_path)
    if existing:
        return existing

    payloads = {
        kind: json.loads(Path(path).read_text(encoding="utf-8"))
        for kind, path in command["artifacts"].items()
    }
    for kind, payload in payloads.items():
        validate_artifact(kind, payload)

    edit = payloads["edit_decisions"]
    compose_inputs: dict[str, Any] = {
        "operation": "render",
        "edit_decisions": edit,
        "asset_manifest": payloads["asset_manifest"],
        # The public video_compose input accepts the scene list here even
        # though the canonical artifact itself is an object wrapper.
        "scene_plan": payloads["scene_plan"].get("scenes") or [],
        "output_path": str(output_path),
        "approved_silence": command.get("approved_silence") is True,
    }
    if "proposal_packet" in payloads:
        compose_inputs["proposal_packet"] = payloads["proposal_packet"]
    if command.get("output_profile"):
        compose_inputs["output_profile"] = command["output_profile"]
    if command.get("remotion_timeout_ms"):
        compose_inputs["remotion_timeout_ms"] = command["remotion_timeout_ms"]

    _atomic_json(journal_path, {
        "version": "1.0",
        "fingerprint": command["fingerprint"],
        "status": "prepared",
        "output_path": str(output_path),
    })
    registry.discover()
    tool = registry.get("video_compose")
    if tool is None:
        raise RuntimeError("OpenMontage ToolRegistry did not expose video_compose")
    result = tool.execute(compose_inputs)
    if not result.success:
        _atomic_json(journal_path, {
            "version": "1.0",
            "fingerprint": command["fingerprint"],
            "status": "failed",
            "error": str(result.error or "native video_compose failed")[-4000:],
        })
        return {
            "schema_version": "1.0",
            "status": "failed",
            "code": "OPENMONTAGE_VIDEO_COMPOSE_FAILED",
            "message": str(result.error or "native video_compose failed"),
        }
    if not output_path.is_file():
        raise RuntimeError("video_compose returned success without the declared output")

    final_review = (result.data or {}).get("final_review")
    if not isinstance(final_review, dict):
        raise RuntimeError("video_compose did not return its native final_review artifact")
    if final_review.get("status") != "pass" or final_review.get("recommended_action") != "present_to_user":
        return {
            "schema_version": "1.0",
            "status": "failed",
            "code": "OPENMONTAGE_FINAL_REVIEW_REJECTED",
            "message": "OpenMontage native final_review did not approve delivery",
            "final_review": final_review,
        }

    probe = _probe(output_path)
    output_hash = _sha256(output_path)
    final_review.setdefault("metadata", {})["output_sha256"] = output_hash
    final_review["metadata"]["acd_input_fingerprint"] = command["fingerprint"]
    render_report = {
        "version": "1.0",
        "outputs": [{
            "path": str(output_path),
            "format": "mp4",
            "codec": probe["video_codec"] or "unknown",
            **({"audio_codec": probe["audio_codec"]} if probe["audio_codec"] else {}),
            "resolution": f"{probe['width']}x{probe['height']}",
            "fps": probe["fps"],
            "duration_seconds": probe["duration"],
            "file_size_bytes": output_path.stat().st_size,
        }],
        "render_time_seconds": float(result.duration_seconds or 0),
        "render_grammar": edit.get("renderer_family"),
        "final_review_ref": str(final_review_path),
        "metadata": {
            "acd_input_fingerprint": command["fingerprint"],
            "output_sha256": output_hash,
            "native_tool": "video_compose",
        },
    }
    validate_artifact("final_review", final_review)
    validate_artifact("render_report", render_report)

    # Publish artifacts first and the native checkpoint last. A rerun with the
    # same fingerprint reconciles a crash between these replacements.
    _atomic_json(final_review_path, final_review)
    _atomic_json(render_report_path, render_report)
    write_checkpoint(
        project_dir.parent,
        project_dir.name,
        "compose",
        "completed",
        artifacts={"render_report": render_report, "final_review": final_review},
        pipeline_type=command["pipeline"],
        metadata={"acd_input_fingerprint": command["fingerprint"], "output_sha256": output_hash},
    )
    _atomic_json(journal_path, {
        "version": "1.0",
        "fingerprint": command["fingerprint"],
        "status": "published",
        "output_path": str(output_path),
        "output_sha256": output_hash,
    })
    return {
        "schema_version": "1.0",
        "status": "delivered",
        "reused": False,
        "fingerprint": command["fingerprint"],
        "output_media": [{
            "role": "primary", "path": str(output_path), "sha256": output_hash,
            "approved_silence": command.get("approved_silence") is True,
        }],
        "openmontage_artifacts": _artifact_entries(command, render_report_path, final_review_path),
        "tool_result": {
            "duration_seconds": result.duration_seconds,
            "cost_usd": result.cost_usd,
            "artifacts": result.artifacts,
        },
    }
