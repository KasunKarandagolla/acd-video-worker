"""Hermes completion contract for the thin production path."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


VALID_AGENT_STATUSES = {"ready_for_execution", "delivered", "blocked", "failed"}


@dataclass
class AgentEnvelope:
    schema_version: str
    run_id: str
    status: str
    output_media: list[dict[str, Any]] = field(default_factory=list)
    openmontage_artifacts: list[dict[str, Any]] = field(default_factory=list)
    source_requests: list[dict[str, Any]] = field(default_factory=list)
    execution_request: Optional[dict[str, Any]] = None
    blocker: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None
    summary: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], expected_run_id: str) -> "AgentEnvelope":
        required = {"run_id", "status"}
        missing = sorted(required - data.keys())
        if missing:
            raise ValueError(f"Agent result missing fields: {', '.join(missing)}")
        if data["run_id"] != expected_run_id:
            raise ValueError("Agent result run_id does not match this run")
        if data["status"] not in VALID_AGENT_STATUSES:
            raise ValueError(f"Unsupported agent result status: {data['status']!r}")
        status = str(data["status"])
        if status in {"ready_for_execution", "delivered"}:
            delivered_missing = sorted({"schema_version", "output_media"} - data.keys())
            if delivered_missing:
                label = "Delivered agent result" if status == "delivered" else "Ready agent result"
                raise ValueError(f"{label} missing fields: {', '.join(delivered_missing)}")
        output_media = data.get("output_media", [])
        if not isinstance(output_media, list):
            raise ValueError("Agent result output_media must be a list")

        blocker = data.get("blocker")
        if status == "blocked" and not blocker and data.get("blocker_code"):
            evidence_keys = {
                "last_valid_artifact", "last_valid_stage", "missing_native_stages",
                "artifacts_present", "checkpoints_written",
            }
            blocker = {
                "code": str(data["blocker_code"]),
                "message": str(data.get("note") or data.get("summary") or "Hermes reported a native pipeline blocker."),
                "phase": str(data.get("last_valid_stage") or "agent"),
                "evidence": {key: data[key] for key in evidence_keys if key in data},
            }

        error = data.get("error")
        if status == "failed" and not error and data.get("error_code"):
            error = {
                "code": str(data["error_code"]),
                "message": str(data.get("note") or data.get("summary") or "Hermes reported a native pipeline failure."),
                "phase": str(data.get("last_valid_stage") or "agent"),
                "evidence": data.get("evidence") or {},
            }
        envelope = cls(
            schema_version=str(data.get("schema_version") or "1.0"),
            run_id=str(data["run_id"]),
            status=status,
            output_media=output_media,
            openmontage_artifacts=data.get("openmontage_artifacts") or [],
            source_requests=data.get("source_requests") or [],
            execution_request=data.get("execution_request"),
            blocker=blocker,
            error=error,
            summary=str(data.get("summary") or data.get("note") or ""),
        )
        if envelope.status == "delivered" and not envelope.output_media:
            raise ValueError("Delivered agent result contains no output media")
        if envelope.status == "ready_for_execution":
            if envelope.output_media:
                raise ValueError("Ready-for-execution result must not claim output media")
            if not isinstance(envelope.execution_request, dict):
                raise ValueError("Ready-for-execution result contains no typed execution_request")
        if envelope.status == "blocked" and not envelope.blocker:
            raise ValueError("Blocked agent result contains no blocker")
        if envelope.status == "failed" and not envelope.error:
            raise ValueError("Failed agent result contains no error")
        return envelope


def load_agent_envelope(path: Path, expected_run_id: str) -> AgentEnvelope:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Hermes did not create its result file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Hermes result is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Hermes result must be a JSON object")
    return AgentEnvelope.from_dict(data, expected_run_id)
