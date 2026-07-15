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
TRUE_VALUES = {"1", "true", "yes", "on"}
INITIAL_NATIVE_TOOL = "openmontage_native"


def _tool_names(tool_definitions) -> set[str]:
    """Extract OpenAI-compatible function names without retaining schemas."""
    names: set[str] = set()
    for definition in tool_definitions or []:
        if not isinstance(definition, dict):
            continue
        function = definition.get("function")
        if isinstance(function, dict) and function.get("name"):
            names.add(str(function["name"]))
        elif definition.get("name"):
            names.add(str(definition["name"]))
    return names


class EventSink:
    def __init__(self, path: Path, terminal_response_path: Path | None = None):
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.terminal_response_path = (
            terminal_response_path.expanduser().resolve()
            if terminal_response_path is not None
            else None
        )
        self.tool_started = False

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
        self.tool_started = True
        self.emit("tool_start", call_id=args[0] if args else None, tool=args[1] if len(args) > 1 else None)

    def complete(self, *args, **_kwargs):
        self.emit("tool_complete", call_id=args[0] if args else None, tool=args[1] if len(args) > 1 else None)

    def step(self, *args, **_kwargs):
        self.emit("agent_step", step=args[0] if args else None)

    def status(self, *args, **_kwargs):
        self.emit("agent_status", category=args[0] if args else None)

    def event(self, *args, **_kwargs):
        self.emit("agent_event", name=args[0] if args else None)

    @staticmethod
    def _exact_json_object(value):
        if not isinstance(value, str):
            return value if isinstance(value, dict) else None
        text = value.strip()
        if text.startswith("```json") and text.endswith("```"):
            text = text[7:-3].strip()
        elif text.startswith("```") and text.endswith("```"):
            text = text[3:-3].strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def capture_terminal_response(self, result) -> None:
        """Persist only the exact final response returned by Hermes itself.

        CLI stdout contains reasoning/progress rendering even in quiet mode,
        so it is not a trustworthy result bus.  The wrapped supported
        run_conversation return value is authoritative for which text was the
        terminal assistant response; envelope validation remains in the worker.
        """
        if self.terminal_response_path is None:
            return
        candidates = []
        if isinstance(result, dict):
            candidates.extend(
                result.get(key)
                for key in ("final_response", "response", "output")
                if result.get(key) is not None
            )
        else:
            candidates.append(result)
        payload = next(
            (parsed for value in candidates if (parsed := self._exact_json_object(value)) is not None),
            None,
        )
        if payload is None:
            return
        target = self.terminal_response_path
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)


def instrument_run_agent(run_agent_module, sink: EventSink):
    """Add callbacks without replacing Hermes' AIAgent class object.

    Hermes runtime helpers lazily access class constants and static methods as
    ``run_agent.AIAgent.<member>``. Replacing that class with a factory
    function breaks the supported conversation loop before the first tool
    call. Wrapping ``__init__`` keeps class identity and every class/static
    member intact while remaining isolated to this adapter subprocess.
    """
    agent_class = run_agent_module.AIAgent
    original_init = agent_class.__init__
    original_run_conversation = getattr(agent_class, "run_conversation", None)

    def instrumented_init(agent_self, *agent_args, **agent_kwargs):
        agent_kwargs.update({
            "tool_progress_callback": sink.progress,
            "tool_start_callback": sink.start,
            "tool_complete_callback": sink.complete,
            "step_callback": sink.step,
            "status_callback": sink.status,
            "event_callback": sink.event,
        })
        original_init(agent_self, *agent_args, **agent_kwargs)
        installed_tools = {
            str(name) for name in (getattr(agent_self, "valid_tool_names", None) or set())
        }
        sink.emit(
            "agent_created",
            tool_count=len(installed_tools),
            has_openmontage_native=INITIAL_NATIVE_TOOL in installed_tools,
            has_acd_acquire_source="acd_acquire_source" in installed_tools,
        )

        # The production contract requires the first action in every Hermes
        # slice to be openmontage_native(status). Prompt-only compliance is not
        # a reliable protocol boundary: an OpenAI-compatible endpoint may
        # legally choose a text response when tool_choice remains "auto".
        # Force only that first named tool; after any real tool starts, Hermes
        # regains normal autonomous tool selection for the creative workflow.
        original_build_api_kwargs = getattr(agent_self, "_build_api_kwargs", None)
        force_initial_native = (
            os.environ.get("ACD_FORCE_INITIAL_OPENMONTAGE_TOOL", "").strip().lower()
            in TRUE_VALUES
        )
        if callable(original_build_api_kwargs):
            def instrumented_build_api_kwargs(api_messages):
                request = original_build_api_kwargs(api_messages)
                if not isinstance(request, dict):
                    return request
                request_tools = _tool_names(request.get("tools"))
                force_applied = (
                    force_initial_native
                    and not getattr(sink, "tool_started", False)
                    and INITIAL_NATIVE_TOOL in request_tools
                )
                if force_applied:
                    request["tool_choice"] = {
                        "type": "function",
                        "function": {"name": INITIAL_NATIVE_TOOL},
                    }
                extra_body = request.get("extra_body")
                chat_template = (
                    extra_body.get("chat_template_kwargs", {})
                    if isinstance(extra_body, dict)
                    else {}
                )
                sink.emit(
                    "api_request_ready",
                    tool_count=len(request_tools),
                    has_openmontage_native=INITIAL_NATIVE_TOOL in request_tools,
                    forced_initial_native=force_applied,
                    enable_thinking=chat_template.get("enable_thinking"),
                    force_nonempty_content=chat_template.get("force_nonempty_content"),
                )
                return request

            agent_self._build_api_kwargs = instrumented_build_api_kwargs

    agent_class.__init__ = instrumented_init
    if callable(original_run_conversation):
        def instrumented_run_conversation(agent_self, *run_args, **run_kwargs):
            result = original_run_conversation(agent_self, *run_args, **run_kwargs)
            sink.capture_terminal_response(result)
            return result

        agent_class.run_conversation = instrumented_run_conversation
    return agent_class


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--event-file", type=Path, required=True)
    parser.add_argument("--terminal-response-file", type=Path)
    args, hermes_args = parser.parse_known_args()
    sink = EventSink(args.event_file, args.terminal_response_file)

    import run_agent
    instrument_run_agent(run_agent, sink)
    sink.emit("adapter_started")
    sys.argv = ["hermes", *hermes_args]
    try:
        from hermes_cli.main import main as hermes_main

        result = hermes_main()
        sink.emit("adapter_finished", return_value=result)
        return int(result or 0)
    except SystemExit as exc:
        # Hermes' supported CLI uses SystemExit for normal command
        # completion as well as errors.  Preserve the real exit code instead
        # of recording every clean max-turn/session exit as adapter failure.
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        if code == 0:
            sink.emit("adapter_finished", exit_code=code)
        else:
            sink.emit("adapter_failed", error_type="SystemExit", exit_code=code)
        return code
    except BaseException as exc:
        sink.emit("adapter_failed", error_type=type(exc).__name__)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
