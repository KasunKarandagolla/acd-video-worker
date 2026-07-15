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


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_journal(journal_path: Path, public_journal_path: Path, payload: dict[str, Any]) -> None:
    _atomic_json(journal_path, payload)
    _atomic_json(public_journal_path, payload)


def _delivered_result(
    command: dict[str, Any],
    render_report_path: Path,
    final_review_path: Path,
    output_path: Path,
    output_hash: str,
    *,
    reused: bool,
    recovered: bool = False,
    tool_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": "1.0",
        "status": "delivered",
        "reused": reused,
        "recovered": recovered,
        "fingerprint": command["fingerprint"],
        "output_media": [{
            "role": "primary",
            "path": str(output_path),
            "sha256": output_hash,
            "approved_silence": command.get("approved_silence") is True,
        }],
        "openmontage_artifacts": _artifact_entries(
            command, render_report_path, final_review_path
        ),
    }
    if tool_result is not None:
        payload["tool_result"] = tool_result
    return payload


def _publish_reviewed_transaction(
    command: dict[str, Any],
    project_dir: Path,
    output_path: Path,
    render_report_path: Path,
    final_review_path: Path,
    render_report: dict[str, Any],
    final_review: dict[str, Any],
    journal_path: Path,
    public_journal_path: Path,
    *,
    reused: bool,
    recovered: bool,
    tool_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_hash = str((render_report.get("metadata") or {}).get("output_sha256") or "")
    if not output_path.is_file() or not output_hash or _sha256(output_path) != output_hash:
        raise RuntimeError("reviewed native transaction output bytes no longer match its hash")
    review_metadata = final_review.get("metadata") or {}
    if (
        (render_report.get("metadata") or {}).get("acd_input_fingerprint")
        != command["fingerprint"]
        or review_metadata.get("acd_input_fingerprint") != command["fingerprint"]
        or review_metadata.get("output_sha256") != output_hash
    ):
        raise RuntimeError("reviewed native transaction identity does not match the command")
    if (
        final_review.get("status") != "pass"
        or final_review.get("recommended_action") != "present_to_user"
    ):
        raise RuntimeError("reviewed native transaction does not authorize presentation")
    validate_artifact("final_review", final_review)
    validate_artifact("render_report", render_report)
    _atomic_json(final_review_path, final_review)
    _atomic_json(render_report_path, render_report)
    write_checkpoint(
        project_dir.parent,
        project_dir.name,
        "compose",
        "completed",
        artifacts={"render_report": render_report, "final_review": final_review},
        pipeline_type=command["pipeline"],
        metadata={
            "acd_input_fingerprint": command["fingerprint"],
            "output_sha256": output_hash,
        },
    )
    _write_journal(journal_path, public_journal_path, {
        "version": "1.0",
        "fingerprint": command["fingerprint"],
        "status": "published",
        "output_path": str(output_path),
        "output_sha256": output_hash,
    })
    return _delivered_result(
        command,
        render_report_path,
        final_review_path,
        output_path,
        output_hash,
        reused=reused,
        recovered=recovered,
        tool_result=tool_result,
    )


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
    control_dir = project_dir / "football_emotion"
    public_journal_path = control_dir / "native_transaction.json"
    transaction_dir = control_dir / "native-transactions" / command["fingerprint"]
    journal_path = transaction_dir / "journal.json"
    reviewed_report_path = transaction_dir / "render_report.json"
    reviewed_review_path = transaction_dir / "final_review.json"

    existing = _existing_delivery(command, render_report_path, final_review_path, output_path)
    if existing:
        report = json.loads(render_report_path.read_text(encoding="utf-8"))
        review = json.loads(final_review_path.read_text(encoding="utf-8"))
        write_checkpoint(
            project_dir.parent,
            project_dir.name,
            "compose",
            "completed",
            artifacts={"render_report": report, "final_review": review},
            pipeline_type=command["pipeline"],
            metadata={
                "acd_input_fingerprint": command["fingerprint"],
                "output_sha256": (report.get("metadata") or {}).get("output_sha256"),
            },
        )
        _write_journal(journal_path, public_journal_path, {
            "version": "1.0",
            "fingerprint": command["fingerprint"],
            "status": "published",
            "output_path": str(output_path),
            "output_sha256": (report.get("metadata") or {}).get("output_sha256"),
            "reused": True,
        })
        return existing

    journal = _read_json(journal_path)
    if journal and journal.get("fingerprint") != command["fingerprint"]:
        return {
            "schema_version": "1.0",
            "status": "failed",
            "code": "NATIVE_TRANSACTION_CONFLICT",
            "message": "Native transaction journal belongs to a different fingerprint",
        }
    if journal and journal.get("status") == "rendered_reviewed":
        reviewed_report = _read_json(reviewed_report_path)
        reviewed_review = _read_json(reviewed_review_path)
        if reviewed_report is None or reviewed_review is None:
            return {
                "schema_version": "1.0",
                "status": "failed",
                "code": "NATIVE_REVIEWED_TRANSACTION_INCOMPLETE",
                "message": "Durable reviewed transaction is missing its native artifacts",
            }
        if (
            journal.get("render_report_sha256") != _sha256(reviewed_report_path)
            or journal.get("final_review_sha256") != _sha256(reviewed_review_path)
        ):
            return {
                "schema_version": "1.0",
                "status": "failed",
                "code": "NATIVE_REVIEWED_TRANSACTION_HASH_MISMATCH",
                "message": "Durable reviewed transaction artifacts do not match their journal hashes",
            }
        return _publish_reviewed_transaction(
            command,
            project_dir,
            output_path,
            render_report_path,
            final_review_path,
            reviewed_report,
            reviewed_review,
            journal_path,
            public_journal_path,
            reused=True,
            recovered=True,
        )
    if journal and journal.get("status") == "rendering" and output_path.is_file():
        return {
            "schema_version": "1.0",
            "status": "failed",
            "code": "NATIVE_RENDER_RECOVERY_REVIEW_REQUIRED",
            "message": (
                "A render exists after an interrupted native call but no durable native review exists. "
                "The bridge refuses to compose twice."
            ),
            "fingerprint": command["fingerprint"],
            "output_path": str(output_path),
            "output_sha256": _sha256(output_path),
        }
    if journal and journal.get("status") == "native_review_rejected":
        return {
            "schema_version": "1.0",
            "status": "failed",
            "code": "OPENMONTAGE_FINAL_REVIEW_REJECTED",
            "message": "The durable OpenMontage final review rejected delivery",
            "fingerprint": command["fingerprint"],
            "final_review": _read_json(reviewed_review_path),
        }
    if journal and journal.get("status") == "failed" and output_path.is_file():
        return {
            "schema_version": "1.0",
            "status": "failed",
            "code": "NATIVE_FAILED_TRANSACTION_HAS_OUTPUT",
            "message": "A failed native transaction left output bytes; automatic recomposition is refused",
            "fingerprint": command["fingerprint"],
            "output_path": str(output_path),
            "output_sha256": _sha256(output_path),
        }

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

    _write_journal(journal_path, public_journal_path, {
        "version": "1.0",
        "fingerprint": command["fingerprint"],
        "status": "prepared",
        "output_path": str(output_path),
    })
    registry.discover()
    tool = registry.get("video_compose")
    if tool is None:
        raise RuntimeError("OpenMontage ToolRegistry did not expose video_compose")
    _write_journal(journal_path, public_journal_path, {
        "version": "1.0",
        "fingerprint": command["fingerprint"],
        "status": "rendering",
        "output_path": str(output_path),
    })
    result = tool.execute(compose_inputs)
    if not result.success:
        _write_journal(journal_path, public_journal_path, {
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
        _atomic_json(reviewed_review_path, final_review)
        _write_journal(journal_path, public_journal_path, {
            "version": "1.0",
            "fingerprint": command["fingerprint"],
            "status": "native_review_rejected",
            "output_path": str(output_path),
            "output_sha256": _sha256(output_path),
            "final_review_path": str(reviewed_review_path),
        })
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

    # Persist the native review transaction before publishing canonical files.
    # A restart after this boundary reuses these bytes and never composes again.
    _atomic_json(reviewed_review_path, final_review)
    _atomic_json(reviewed_report_path, render_report)
    _write_journal(journal_path, public_journal_path, {
        "version": "1.0",
        "fingerprint": command["fingerprint"],
        "status": "rendered_reviewed",
        "output_path": str(output_path),
        "output_sha256": output_hash,
        "render_report_path": str(reviewed_report_path),
        "final_review_path": str(reviewed_review_path),
        "render_report_sha256": _sha256(reviewed_report_path),
        "final_review_sha256": _sha256(reviewed_review_path),
    })
    if os.environ.get("ACD_NATIVE_FAULT_AFTER", "") == "rendered_reviewed":
        raise RuntimeError("Injected failure after rendered_reviewed transaction boundary")
    return _publish_reviewed_transaction(
        command,
        project_dir,
        output_path,
        render_report_path,
        final_review_path,
        render_report,
        final_review,
        journal_path,
        public_journal_path,
        reused=False,
        recovered=False,
        tool_result={
            "duration_seconds": result.duration_seconds,
            "cost_usd": result.cost_usd,
            "artifacts": result.artifacts,
        },
    )
