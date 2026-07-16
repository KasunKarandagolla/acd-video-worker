#!/usr/bin/env python3
"""Instrument pinned Hermes callbacks while preserving its supported CLI flow."""

from __future__ import annotations

import argparse
import copy
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


def _tool_name(definition) -> str:
    if not isinstance(definition, dict):
        return ""
    function = definition.get("function")
    if isinstance(function, dict) and function.get("name"):
        return str(function["name"])
    return str(definition.get("name") or "")


def _status_only_tool(definition) -> dict:
    """Copy the native tool schema and permit only the harmless status call."""
    if _tool_name(definition) != INITIAL_NATIVE_TOOL:
        raise ValueError("tool definition is not openmontage_native")
    restricted = copy.deepcopy(definition)
    function = restricted.get("function")
    parameters = function.get("parameters") if isinstance(function, dict) else None
    properties = parameters.get("properties") if isinstance(parameters, dict) else None
    operation = properties.get("operation") if isinstance(properties, dict) else None
    if not isinstance(operation, dict):
        raise ValueError("openmontage_native has no operation schema")
    operation["enum"] = ["status"]
    required = list(parameters.get("required") or [])
    if "operation" not in required:
        required.append("operation")
    parameters["required"] = required
    return restricted


def _parse_json_object(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _tool_choice_shape(value) -> tuple[str, str]:
    if isinstance(value, dict):
        function = value.get("function")
        if isinstance(function, dict):
            return "named", str(function.get("name") or "")
        return "object", ""
    if value is None:
        return "omitted", ""
    return str(value), ""


class EventSink:
    def __init__(self, path: Path, terminal_response_path: Path | None = None):
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.terminal_response_path = (
            terminal_response_path.expanduser().resolve()
            if terminal_response_path is not None
            else None
        )
        self.request_count = 0
        self.response_count = 0
        self.handshake_required = (
            os.environ.get("ACD_FORCE_INITIAL_OPENMONTAGE_TOOL", "").strip().lower()
            in TRUE_VALUES
        )
        self.handshake_attempted = False
        self.handshake_completed = False
        self.handshake_error = ""

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
        call_id = args[0] if args else None
        tool = args[1] if len(args) > 1 else None
        tool_args = args[2] if len(args) > 2 and isinstance(args[2], dict) else {}
        operation = tool_args.get("operation")
        self.emit("tool_start", call_id=call_id, tool=tool, operation=operation)
        if self.handshake_required and not self.handshake_completed:
            self.handshake_attempted = True
            if tool == INITIAL_NATIVE_TOOL and operation == "status":
                self.emit(
                    "tool_handshake_started",
                    call_id=call_id,
                    tool=tool,
                    operation=operation,
                )
            else:
                self.handshake_error = "unexpected initial tool or operation"
                self.emit(
                    "tool_handshake_failed",
                    code="UNEXPECTED_INITIAL_TOOL",
                    tool=tool,
                    operation=operation,
                )

    def complete(self, *args, **_kwargs):
        call_id = args[0] if args else None
        tool = args[1] if len(args) > 1 else None
        tool_args = args[2] if len(args) > 2 and isinstance(args[2], dict) else {}
        raw_result = args[3] if len(args) > 3 else None
        result = _parse_json_object(raw_result)
        operation = tool_args.get("operation")
        self.emit(
            "tool_complete",
            call_id=call_id,
            tool=tool,
            operation=operation,
            result_success=result.get("success"),
            result_code=result.get("code"),
        )
        if self.handshake_required and not self.handshake_completed:
            success = (
                tool == INITIAL_NATIVE_TOOL
                and operation == "status"
                and result.get("success") is True
            )
            if success:
                self.handshake_completed = True
                self.handshake_error = ""
                self.emit(
                    "tool_handshake_completed",
                    call_id=call_id,
                    tool=tool,
                    operation=operation,
                    result_success=True,
                    result_code=result.get("code"),
                )
            else:
                self.handshake_error = str(
                    result.get("code") or "native status handler did not succeed"
                )
                self.emit(
                    "tool_handshake_failed",
                    code=result.get("code") or "NATIVE_STATUS_FAILED",
                    tool=tool,
                    operation=operation,
                    result_success=result.get("success"),
                )

    def step(self, *args, **_kwargs):
        self.emit("agent_step", step=args[0] if args else None)

    def status(self, *args, **_kwargs):
        self.emit("agent_status", category=args[0] if args else None)

    def event(self, *args, **_kwargs):
        self.emit("agent_event", name=args[0] if args else None)

    def response(self, normalized) -> None:
        """Record normalized response structure, never response text or reasoning."""
        self.response_count += 1
        tool_calls = list(getattr(normalized, "tool_calls", None) or [])
        names = [str(getattr(item, "name", "") or "") for item in tool_calls]
        status_operation = (
            len(tool_calls) == 1
            and names == [INITIAL_NATIVE_TOOL]
            and _parse_json_object(getattr(tool_calls[0], "arguments", None)).get("operation")
            == "status"
        )
        provider_data = getattr(normalized, "provider_data", None)
        reasoning_present = bool(getattr(normalized, "reasoning", None))
        if isinstance(provider_data, dict):
            reasoning_present = reasoning_present or bool(
                provider_data.get("reasoning_content")
                or provider_data.get("reasoning_details")
            )
        content = getattr(normalized, "content", None)
        self.emit(
            "api_response_normalized",
            response_index=self.response_count,
            finish_reason=getattr(normalized, "finish_reason", None),
            content_present=bool(isinstance(content, str) and content.strip()),
            reasoning_present=reasoning_present,
            tool_call_count=len(tool_calls),
            tool_call_names=",".join(name for name in names if name),
            status_operation=status_operation,
        )
        if self.handshake_required and self.response_count == 1 and not status_operation:
            self.handshake_attempted = True
            self.handshake_error = "provider did not return one executable native status call"
            self.emit(
                "tool_handshake_failed",
                code="INVALID_PROVIDER_TOOL_RESPONSE",
                tool_call_count=len(tool_calls),
                tool_call_names=",".join(name for name in names if name),
                status_operation=False,
            )

    def dispatched_request(self, request, *, model: str = "") -> None:
        """Validate and record the final kwargs passed to the provider call."""
        if not isinstance(request, dict):
            raise RuntimeError("ACD_HERMES_TOOL_REQUEST_INVALID: provider request is not a dict")
        self.request_count += 1
        final_tools = list(request.get("tools") or [])
        final_tool_names = _tool_names(final_tools)
        choice_mode, choice_name = _tool_choice_shape(request.get("tool_choice"))
        operation = None
        if len(final_tools) == 1 and _tool_name(final_tools[0]) == INITIAL_NATIVE_TOOL:
            function = final_tools[0].get("function") or {}
            parameters = function.get("parameters") or {}
            properties = parameters.get("properties") or {}
            operation = properties.get("operation") or {}
        status_only = isinstance(operation, dict) and operation.get("enum") == ["status"]
        handshake_request = self.handshake_required and not self.handshake_completed
        extra_body = request.get("extra_body")
        chat_template = (
            extra_body.get("chat_template_kwargs", {})
            if isinstance(extra_body, dict)
            else {}
        )
        active_model = str(request.get("model") or model or "")
        self.emit(
            "api_request_ready",
            request_index=self.request_count,
            handshake_request=handshake_request,
            tool_count=len(final_tools),
            tools=",".join(sorted(final_tool_names)),
            has_openmontage_native=INITIAL_NATIVE_TOOL in final_tool_names,
            status_only=status_only,
            tool_choice_mode=choice_mode,
            tool_choice_name=choice_name,
            enable_thinking=chat_template.get("enable_thinking"),
            force_nonempty_content=chat_template.get("force_nonempty_content"),
            model=active_model,
        )
        if not handshake_request:
            return
        valid = (
            len(final_tools) == 1
            and final_tool_names == {INITIAL_NATIVE_TOOL}
            and status_only
            and choice_mode == "named"
            and choice_name == INITIAL_NATIVE_TOOL
        )
        if not valid:
            self.handshake_attempted = True
            self.handshake_error = "final provider request did not preserve native status restriction"
            self.emit("tool_handshake_failed", code="INVALID_FINAL_PROVIDER_REQUEST")
            raise RuntimeError(
                "ACD_HERMES_TOOL_REQUEST_INVALID: final provider request did not preserve "
                "the named status-only openmontage_native contract"
            )
        if (
            "nemotron-3-ultra-550b-a55b" in active_model.lower()
            and (
                chat_template.get("enable_thinking") is not True
                or chat_template.get("force_nonempty_content") is not True
            )
        ):
            self.handshake_attempted = True
            self.handshake_error = "Nemotron Ultra tool flags missing from final provider request"
            self.emit(
                "tool_handshake_failed",
                code="NEMOTRON_TOOL_FLAGS_MISSING",
                enable_thinking=chat_template.get("enable_thinking"),
                force_nonempty_content=chat_template.get("force_nonempty_content"),
            )
            raise RuntimeError(
                "ACD_HERMES_TOOL_CONTRACT_CONFIG_INVALID: Nemotron Ultra requires "
                "enable_thinking=true and force_nonempty_content=true"
            )

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
            tools=",".join(sorted(installed_tools)),
            has_openmontage_native=INITIAL_NATIVE_TOOL in installed_tools,
            has_acd_acquire_source="acd_acquire_source" in installed_tools,
            provider=getattr(agent_self, "provider", None),
            model=getattr(agent_self, "model", None),
            api_mode=getattr(agent_self, "api_mode", None),
        )

        # The production contract requires the first provider action for an
        # uncertified run to be openmontage_native(status). Prompt-only
        # compliance is not a reliable protocol boundary: an OpenAI-compatible
        # endpoint may legally choose text when tool_choice remains "auto".
        # Force only that first named tool. Full tools are restored only after
        # the real status handler reports success, and the controller persists
        # that certificate across continuation slices and kernel restarts.
        original_build_api_kwargs = getattr(agent_self, "_build_api_kwargs", None)
        force_initial_native = bool(getattr(sink, "handshake_required", False))
        if force_initial_native:
            sink.emit(
                "tool_handshake_required",
                contract_id=os.environ.get("ACD_HERMES_TOOL_CONTRACT_ID", ""),
                tool=INITIAL_NATIVE_TOOL,
                operation="status",
            )
        if callable(original_build_api_kwargs):
            def instrumented_build_api_kwargs(api_messages):
                request = original_build_api_kwargs(api_messages)
                if not isinstance(request, dict):
                    return request
                original_tools = list(request.get("tools") or [])
                force_applied = (
                    force_initial_native
                    and not sink.handshake_completed
                )
                if force_applied:
                    if sink.handshake_attempted:
                        raise RuntimeError(
                            "ACD_HERMES_TOOL_HANDSHAKE_FAILED: "
                            f"{sink.handshake_error or 'initial status call did not complete'}"
                        )
                    matches = [
                        definition for definition in original_tools
                        if _tool_name(definition) == INITIAL_NATIVE_TOOL
                    ]
                    if len(matches) != 1:
                        sink.emit(
                            "tool_handshake_failed",
                            code="NATIVE_TOOL_UNAVAILABLE",
                            native_tool_matches=len(matches),
                        )
                        raise RuntimeError(
                            "ACD_HERMES_TOOL_UNAVAILABLE: expected exactly one "
                            "openmontage_native tool in the live AIAgent"
                        )
                    request["tools"] = [_status_only_tool(matches[0])]
                    request["tool_choice"] = {
                        "type": "function",
                        "function": {"name": INITIAL_NATIVE_TOOL},
                    }
                return request

            agent_self._build_api_kwargs = instrumented_build_api_kwargs

        def instrument_dispatch(method_name):
            original = getattr(agent_self, method_name, None)
            if not callable(original):
                return

            def instrumented(api_kwargs, *call_args, **call_kwargs):
                sink.dispatched_request(
                    api_kwargs,
                    model=str(getattr(agent_self, "model", "") or ""),
                )
                return original(api_kwargs, *call_args, **call_kwargs)

            setattr(agent_self, method_name, instrumented)

        instrument_dispatch("_interruptible_streaming_api_call")
        instrument_dispatch("_interruptible_api_call")

        original_get_transport = getattr(agent_self, "_get_transport", None)
        if callable(original_get_transport):
            def instrumented_get_transport():
                transport = original_get_transport()
                if getattr(transport, "_acd_response_instrumented", False):
                    return transport
                original_normalize = getattr(transport, "normalize_response", None)
                if callable(original_normalize):
                    def instrumented_normalize(response, **kwargs):
                        normalized = original_normalize(response, **kwargs)
                        sink.response(normalized)
                        return normalized

                    transport.normalize_response = instrumented_normalize
                    transport._acd_response_instrumented = True
                return transport

            agent_self._get_transport = instrumented_get_transport

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

    # Pinned Hermes applies -p/--profile while importing hermes_cli.main and
    # requires that to happen before run_agent or cli cache profile-scoped
    # configuration. Importing run_agent first makes an isolated plugin probe
    # pass while the real AIAgent silently uses the root profile and omits the
    # named profile's tools.
    sys.argv = ["hermes", *hermes_args]
    from hermes_cli import main as hermes_main_module

    import run_agent

    instrument_run_agent(run_agent, sink)
    sink.emit("adapter_started")
    try:
        result = hermes_main_module.main()
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
