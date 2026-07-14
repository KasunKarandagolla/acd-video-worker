#!/usr/bin/env python3
"""Instrument pinned Hermes callbacks while preserving its supported CLI flow."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


SECRET_RE = re.compile(r"(?i)(?:sk-|ghp_|github_pat_|bearer\s+)[A-Za-z0-9_.-]{8,}")


class EventSink:
    def __init__(self, path: Path):
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **fields) -> None:
        safe = {"at": datetime.now(timezone.utc).isoformat(), "event": event}
        for key, value in fields.items():
            if value is None:
                continue
            text = SECRET_RE.sub("[REDACTED]", str(value))[:300]
            safe[key] = text
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def progress(self, *args, **_kwargs):
        self.emit("tool_progress", signal=args[0] if args else None, tool=args[1] if len(args) > 1 else None)

    def start(self, *args, **_kwargs):
        self.emit("tool_start", call_id=args[0] if args else None, tool=args[1] if len(args) > 1 else None)

    def complete(self, *args, **_kwargs):
        self.emit("tool_complete", call_id=args[0] if args else None, tool=args[1] if len(args) > 1 else None)

    def step(self, *args, **_kwargs):
        self.emit("agent_step", step=args[0] if args else None)

    def status(self, *args, **_kwargs):
        self.emit("agent_status", category=args[0] if args else None)

    def event(self, *args, **_kwargs):
        self.emit("agent_event", name=args[0] if args else None)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--event-file", type=Path, required=True)
    args, hermes_args = parser.parse_known_args()
    sink = EventSink(args.event_file)

    import run_agent

    original = run_agent.AIAgent

    def instrumented_agent(*agent_args, **agent_kwargs):
        agent_kwargs.update({
            "tool_progress_callback": sink.progress,
            "tool_start_callback": sink.start,
            "tool_complete_callback": sink.complete,
            "step_callback": sink.step,
            "status_callback": sink.status,
            "event_callback": sink.event,
        })
        agent = original(*agent_args, **agent_kwargs)
        sink.emit("agent_created")
        return agent

    run_agent.AIAgent = instrumented_agent
    sink.emit("adapter_started")
    sys.argv = ["hermes", *hermes_args]
    try:
        from hermes_cli.main import main as hermes_main

        result = hermes_main()
        sink.emit("adapter_finished", return_value=result)
        return int(result or 0)
    except BaseException as exc:
        sink.emit("adapter_failed", error_type=type(exc).__name__)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
