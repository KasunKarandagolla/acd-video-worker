#!/usr/bin/env python3
"""Configure the named Hermes profile from free endpoint environment values."""

from __future__ import annotations

import json
import os
from pathlib import Path


def q(value: str) -> str:
    return json.dumps(value)


def main() -> int:
    root = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser().resolve()
    profile = os.environ.get("HERMES_PROFILE", "football-emotion")
    profile_home = root if root.parent.name == "profiles" else root / "profiles" / profile
    profile_home.mkdir(parents=True, exist_ok=True)
    config_path = profile_home / "config.yaml"

    base_url = os.environ.get("LLM_BASE_URL", "").strip()
    model = os.environ.get("LLM_MODEL", "").strip()
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not (base_url and model and key):
        if not config_path.exists():
            template = Path(__file__).resolve().parent.parent / "config" / "hermes-profile.template.yaml"
            config_path.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        print("Free endpoint not auto-configured: set LLM_BASE_URL, LLM_MODEL and LLM_API_KEY, or run Hermes model setup.")
        return 2

    # The key remains only in the process/Kaggle secret environment. Config
    # stores its variable name, never the credential value.
    # Free hosted endpoints commonly throttle very large repeated agent
    # contexts before the model's advertised context window is reached. Cap
    # Hermes' effective window so its native compressor runs earlier while
    # preserving the same session, memory and workflow ownership.
    context_length = int(os.environ.get("ACD_HERMES_CONTEXT_LENGTH", "65536"))
    if context_length < 32768:
        raise ValueError("ACD_HERMES_CONTEXT_LENGTH must be at least 32768")
    extra_body = ""
    if model == "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning":
        budget = int(os.environ.get("ACD_NEMOTRON_REASONING_BUDGET", "4096"))
        extra_body = f"    extra_body:\n      reasoning_budget: {budget}\n"
    elif model == "nvidia/nemotron-3-ultra-550b-a55b":
        budget = int(os.environ.get("ACD_NEMOTRON_REASONING_BUDGET", "16384"))
        extra_body = (
            "    extra_body:\n"
            "      chat_template_kwargs:\n"
            "        enable_thinking: true\n"
            f"      reasoning_budget: {budget}\n"
        )

    config = f"""# Generated free-endpoint profile; no credential value is stored here.
model:
  default: {q(model)}
  provider: custom:acd-free
  context_length: {context_length}

providers:
  acd-free:
    name: ACD Free Endpoint
    api: {q(base_url)}
    key_env: LLM_API_KEY
    default_model: {q(model)}
    transport: chat_completions
{extra_body}    discover_models: false
    models:
      {q(model)}: {{}}

toolsets: [web, memory, session_search, skills, acd-openmontage]
web:
  search_backend: ddgs
plugins:
  enabled: [acd-openmontage]
memory:
  provider: builtin
display:
  interface: cli
  tool_progress: off
skills:
  external_dirs: []
  template_vars: true
  inline_shell: false
  write_approval: false
agent:
  max_turns: 32
  coding_context: off
  max_spawn_depth: 1
  subagent_auto_approve: false
moa:
  enabled: false
"""
    config_path.write_text(config, encoding="utf-8")
    print(f"Configured Hermes profile {profile!r} for model {model!r}; API key remains in LLM_API_KEY.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
