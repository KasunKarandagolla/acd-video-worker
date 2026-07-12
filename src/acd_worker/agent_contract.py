"""Hermes completion contract for the thin production path."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


VALID_AGENT_STATUSES = {"delivered", "blocked", "failed"}


@dataclass
class AgentEnvelope:
    schema_version: str
    run_id: str
    status: str
    output_media: list[dict[str, Any]] = field(default_factory=list)
    openmontage_artifacts: list[dict[str, Any]] = field(default_factory=list)
    source_requests: list[dict[str, Any]] = field(default_factory=list)
    blocker: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None
    summary: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], expected_run_id: str) -> "AgentEnvelope":
        required = {"schema_version", "run_id", "status", "output_media"}
        missing = sorted(required - data.keys())
        if missing:
            raise ValueError(f"Agent result missing fields: {', '.join(missing)}")
        if data["run_id"] != expected_run_id:
            raise ValueError("Agent result run_id does not match this run")
        if data["status"] not in VALID_AGENT_STATUSES:
            raise ValueError(f"Unsupported agent result status: {data['status']!r}")
        if not isinstance(data["output_media"], list):
            raise ValueError("Agent result output_media must be a list")
        envelope = cls(
            schema_version=str(data["schema_version"]),
            run_id=str(data["run_id"]),
            status=str(data["status"]),
            output_media=data["output_media"],
            openmontage_artifacts=data.get("openmontage_artifacts") or [],
            source_requests=data.get("source_requests") or [],
            blocker=data.get("blocker"),
            error=data.get("error"),
            summary=str(data.get("summary") or ""),
        )
        if envelope.status == "delivered" and not envelope.output_media:
            raise ValueError("Delivered agent result contains no output media")
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
