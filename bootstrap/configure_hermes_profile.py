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
    config = f"""# Generated free-endpoint profile; no credential value is stored here.
model:
  default: {q(model)}
  provider: custom:acd-free

providers:
  acd-free:
    name: ACD Free Endpoint
    api: {q(base_url)}
    key_env: LLM_API_KEY
    default_model: {q(model)}
    transport: chat_completions
    discover_models: false
    models:
      {q(model)}: {{}}

toolsets: [file, terminal, web, memory, session_search, skills]
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
  max_turns: 60
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
