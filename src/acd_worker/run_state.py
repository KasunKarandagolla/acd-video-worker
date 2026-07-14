"""Small, durable run state for the thin ACD control plane."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStatus(str, Enum):
    INTAKE = "INTAKE"
    SOURCE_READY = "SOURCE_READY"
    AGENT_RUNNING = "AGENT_RUNNING"
    VALIDATING = "VALIDATING"
    DELIVERED = "DELIVERED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


TERMINAL_STATUSES = {RunStatus.DELIVERED, RunStatus.BLOCKED, RunStatus.FAILED}

ALLOWED_TRANSITIONS = {
    RunStatus.INTAKE: {RunStatus.SOURCE_READY, RunStatus.BLOCKED, RunStatus.FAILED},
    RunStatus.SOURCE_READY: {RunStatus.AGENT_RUNNING, RunStatus.BLOCKED, RunStatus.FAILED},
    RunStatus.AGENT_RUNNING: {RunStatus.VALIDATING, RunStatus.BLOCKED, RunStatus.FAILED},
    RunStatus.VALIDATING: {RunStatus.DELIVERED, RunStatus.BLOCKED, RunStatus.FAILED},
    RunStatus.DELIVERED: set(),
    # BLOCKED remains terminal during ordinary resume. The controller may use
    # this single transition only for an explicit retry of a transient Hermes
    # provider blocker, preserving the same project and Hermes session.
    RunStatus.BLOCKED: {RunStatus.AGENT_RUNNING},
    RunStatus.FAILED: set(),
}


@dataclass
class RunProblem:
    code: str
    message: str
    phase: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunState:
    schema_version: str
    run_id: str
    project_id: str
    request: str
    status: RunStatus
    created_at: str
    updated_at: str
    project_dir: str
    source_manifest_path: str
    agent_result_path: str
    prompt_path: str
    input_references: list[str] = field(default_factory=list)
    hermes_profile: str = "football-emotion"
    hermes_session_id: Optional[str] = None
    output_candidates: list[dict[str, Any]] = field(default_factory=list)
    openmontage_artifacts: list[dict[str, Any]] = field(default_factory=list)
    artifact_validation: dict[str, Any] = field(default_factory=dict)
    validation: list[dict[str, Any]] = field(default_factory=list)
    blocker: Optional[RunProblem] = None
    error: Optional[RunProblem] = None
    history: list[dict[str, str]] = field(default_factory=list)
    continuations_used: int = 0
    heartbeat_at: Optional[str] = None
    heartbeat: dict[str, Any] = field(default_factory=dict)
    native_execution: dict[str, Any] = field(default_factory=dict)
    approval_policy: dict[str, Any] = field(default_factory=dict)

    def transition(self, target: RunStatus) -> None:
        if target == self.status:
            return
        if target not in ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"Invalid run transition: {self.status.value} -> {target.value}")
        previous = self.status
        self.status = target
        self.updated_at = utc_now()
        self.history.append({"from": previous.value, "to": target.value, "at": self.updated_at})

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunState":
        values = dict(data)
        values["status"] = RunStatus(values["status"])
        if values.get("blocker"):
            values["blocker"] = RunProblem(**values["blocker"])
        if values.get("error"):
            values["error"] = RunProblem(**values["error"])
        return cls(**values)


class RunStateStore:
    """Atomic JSON persistence; no creative workflow state belongs here."""

    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, run_id: str) -> Path:
        if not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_id):
            raise ValueError("Invalid run ID")
        return self.root / f"{run_id}.json"

    def save(self, state: RunState) -> Path:
        target = self.path_for(state.run_id)
        payload = json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n"
        fd, temporary = tempfile.mkstemp(prefix=f".{state.run_id}.", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return target

    def load(self, run_id: str) -> RunState:
        return RunState.from_dict(json.loads(self.path_for(run_id).read_text(encoding="utf-8")))

    @contextmanager
    def lease(self, run_id: str):
        """Hold a process-scoped exclusive lease without stale lock files.

        Kaggle/Linux releases ``flock`` automatically when a worker dies, so
        restart safety does not depend on guessing whether a timestamp is stale.
        """
        import fcntl

        lease_dir = self.root / ".leases"
        lease_dir.mkdir(parents=True, exist_ok=True)
        path = lease_dir / f"{self.path_for(run_id).stem}.lock"
        handle = path.open("a+", encoding="utf-8")
        try:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError(f"Run {run_id} is already owned by another worker") from exc
            handle.seek(0)
            handle.truncate()
            json.dump({"run_id": run_id, "pid": os.getpid(), "acquired_at": utc_now()}, handle)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
