"""Hermes completion contract for the thin production path."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# Hermes may author a typed creative handoff or report a problem. Delivery is
# never a model-owned status: only native execution plus worker validation can
# transition RunState to DELIVERED.
# ``delivered`` remains parseable solely so the controller can reject old
# model-authored delivery envelopes with a precise migration error. It is not
# an accepted production transition.
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
        required = {
            "schema_version",
            "run_id",
            "status",
            "output_media",
            "openmontage_artifacts",
            "source_requests",
            "blocker",
            "error",
            "summary",
        }
        missing = sorted(required - data.keys())
        if missing:
            raise ValueError(f"Agent result missing fields: {', '.join(missing)}")
        if data["schema_version"] != "1.0":
            raise ValueError(f"Unsupported agent result schema_version: {data['schema_version']!r}")
        if data["run_id"] != expected_run_id:
            raise ValueError("Agent result run_id does not match this run")
        if data["status"] not in VALID_AGENT_STATUSES:
            raise ValueError(f"Unsupported agent result status: {data['status']!r}")
        status = str(data["status"])
        output_media = data["output_media"]
        if not isinstance(output_media, list):
            raise ValueError("Agent result output_media must be a list")
        openmontage_artifacts = data["openmontage_artifacts"]
        if not isinstance(openmontage_artifacts, list):
            raise ValueError("Agent result openmontage_artifacts must be a list")
        source_requests = data["source_requests"]
        if not isinstance(source_requests, list):
            raise ValueError("Agent result source_requests must be a list")
        if not isinstance(data["summary"], str):
            raise ValueError("Agent result summary must be a string")

        blocker = data.get("blocker")
        error = data.get("error")
        for label, problem in (("blocker", blocker), ("error", error)):
            if problem is None:
                continue
            if not isinstance(problem, dict):
                raise ValueError(f"Agent result {label} must be an object or null")
            problem_missing = sorted({"code", "message", "phase", "evidence"} - problem.keys())
            if problem_missing:
                raise ValueError(f"Agent result {label} missing fields: {', '.join(problem_missing)}")
            if not all(isinstance(problem[key], str) and problem[key] for key in ("code", "message", "phase")):
                raise ValueError(f"Agent result {label} code, message and phase must be non-empty strings")
            if not isinstance(problem["evidence"], dict):
                raise ValueError(f"Agent result {label} evidence must be an object")
        envelope = cls(
            schema_version=str(data["schema_version"]),
            run_id=str(data["run_id"]),
            status=status,
            output_media=output_media,
            openmontage_artifacts=openmontage_artifacts,
            source_requests=source_requests,
            execution_request=data.get("execution_request"),
            blocker=blocker,
            error=error,
            summary=data["summary"],
        )
        if envelope.status == "ready_for_execution":
            if envelope.output_media:
                raise ValueError("Ready-for-execution result must not claim output media")
            if not isinstance(envelope.execution_request, dict):
                raise ValueError("Ready-for-execution result contains no typed execution_request")
            if envelope.blocker is not None or envelope.error is not None:
                raise ValueError("Ready-for-execution result must not contain blocker or error")
        if envelope.status == "blocked" and not envelope.blocker:
            raise ValueError("Blocked agent result contains no blocker")
        if envelope.status == "blocked" and envelope.error is not None:
            raise ValueError("Blocked agent result must not contain error")
        if envelope.status == "failed" and not envelope.error:
            raise ValueError("Failed agent result contains no error")
        if envelope.status == "failed" and envelope.blocker is not None:
            raise ValueError("Failed agent result must not contain blocker")
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
