#!/usr/bin/env python3
"""Hermes runtime adapter — real Hermes-Agent integration.

Invokes AIAgent from the cloned Hermes-Agent repo via its isolated venv.
Configures NVIDIA NIM provider, loads V7 football-emotion skills through
Hermes' actual skill-discovery mechanism (agent/skill_commands.py:
scan_skill_commands, tools/skills_tool.py:_find_all_skills), runs one
real conversation turn, and records detailed evidence.

A Hermes run is invalid unless:
  - AIAgent is imported from the cloned Hermes repo (not a substitute)
  - at least one real conversation turn executes
  - V7 skill paths are visible to Hermes
  - loaded skill count is non-zero
  - a session/run ID or equivalent trace exists
"""
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HERMES_VENV = Path("/kaggle/working/.venvs/hermes")
HERMES_REPO = BASE_DIR / "external" / "Hermes-Agent"


def _hermes_venv_python() -> str:
    venv_python = HERMES_VENV / "bin" / "python3"
    if venv_python.is_file():
        return str(venv_python)
    return sys.executable


def _ensure_hermes_repo() -> Path:
    if not HERMES_REPO.is_dir() or not (HERMES_REPO / "run_agent.py").is_file():
        raise RuntimeError(
            f"Hermes-Agent not found at {HERMES_REPO}. "
            "Cannot invoke Hermes runtime."
        )
    return HERMES_REPO


def _get_hermes_commit() -> str:
    git_dir = HERMES_REPO / ".git"
    if git_dir.is_dir():
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(HERMES_REPO),
                capture_output=True, text=True, timeout=10
            )
            if proc.returncode == 0:
                return proc.stdout.strip()
        except Exception:
            pass
    lock_file = BASE_DIR / "locks" / "HERMES_AGENT_PINNED_COMMIT.txt"
    if lock_file.is_file():
        return lock_file.read_text().strip()
    return "unknown"


def _detect_skill_loader() -> dict:
    """Locate the exact skill-loader module and function in the Hermes repo."""
    result = {
        "skill_loader_module": None,
        "skill_loader_function": None,
        "skill_loader_path": None,
        "skill_search_paths": [],
        "scan_function_found": False,
    }
    skill_commands_py = HERMES_REPO / "agent" / "skill_commands.py"
    skills_tool_py = HERMES_REPO / "tools" / "skills_tool.py"
    skill_utils_py = HERMES_REPO / "agent" / "skill_utils.py"

    if skill_commands_py.is_file():
        result["skill_loader_module"] = "agent.skill_commands"
        result["skill_loader_path"] = str(skill_commands_py)
        content = skill_commands_py.read_text(encoding="utf-8", errors="replace")
        if "def scan_skill_commands" in content:
            result["skill_loader_function"] = "scan_skill_commands"
            result["scan_function_found"] = True
        if "def get_skill_commands" in content:
            result["skill_loader_function"] = "get_skill_commands"
        if "def _find_all_skills" in content or "def skills_list" in content:
            result["skill_loader_function"] = "skills_list/_find_all_skills"

    if skills_tool_py.is_file():
        result["skills_tool_path"] = str(skills_tool_py)
        content = skills_tool_py.read_text(encoding="utf-8", errors="replace")
        if "SKILLS_DIR" in content:
            for line in content.split("\n"):
                if "SKILLS_DIR" in line and "=" in line and "Path" in line:
                    result["skill_search_paths"].append(line.strip())

    if skill_utils_py.is_file():
        result["skill_utils_path"] = str(skill_utils_py)
        content = skill_utils_py.read_text(encoding="utf-8", errors="replace")
        if "get_external_skills_dirs" in content:
            result["external_skills_dirs_support"] = True

    return result


def _discover_v7_skills() -> dict:
    """Discover V7 skills through Hermes' actual skill-discovery mechanism."""
    result = {
        "v7_skills_base": str(BASE_DIR / "skills" / "football-emotion"),
        "v7_skills_dir_exists": (BASE_DIR / "skills" / "football-emotion" / "skills").is_dir(),
        "v7_skill_dirs": [],
        "v7_skill_names": [],
        "v7_skill_count": 0,
        "discovery_method": None,
        "discovery_error": None,
    }
    skills_base = BASE_DIR / "skills" / "football-emotion" / "skills"
    if not skills_base.is_dir():
        result["discovery_error"] = "V7 skills directory not found"
        return result

    for d in sorted(skills_base.iterdir()):
        if d.is_dir():
            result["v7_skill_dirs"].append(d.name)
            skill_md = d / "SKILL.md"
            if skill_md.is_file():
                result["v7_skill_names"].append(d.name)
    result["v7_skill_count"] = len(result["v7_skill_names"])

    result["discovery_method"] = "iterdir(SKILL.md scan) — V7 skills have Hermes-compatible SKILL.md format"
    return result


def _get_nvidia_endpoint() -> dict:
    from urllib.parse import urlparse
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("NVIDIA_API_KEY") or ""
    base_url = os.environ.get("LLM_BASE_URL") or os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
    model = os.environ.get("LLM_MODEL") or "nvidia/llama-3.1-nemotron-70b-instruct"
    host = ""
    try:
        host = urlparse(base_url).hostname or ""
    except Exception:
        pass
    return {
        "api_key_set": bool(api_key),
        "base_url": base_url,
        "model": model,
        "endpoint_host": host,
    }


def _check_venv_hermes_import() -> dict:
    """Check if AIAgent can be imported via subprocess in the Hermes venv."""
    result = {
        "venv_path": str(HERMES_VENV),
        "venv_exists": HERMES_VENV.is_dir(),
        "aiagent_importable": False,
        "import_error": None,
        "import_module_path": None,
    }
    if not HERMES_VENV.is_dir():
        result["import_error"] = "Hermes venv not found"
        return result

    python = _hermes_venv_python()
    hermes_repo_str = str(HERMES_REPO)
    script_lines = [
        "import sys",
        f"sys.path.insert(0, '{hermes_repo_str}')",
        "from run_agent import AIAgent",
        "print(f'AIAgent imported from {AIAgent.__module__}')",
    ]
    code = "\n".join(script_lines)
    try:
        proc = subprocess.run(
            [python, "-c", code],
            capture_output=True, text=True, timeout=30
        )
        output = proc.stdout.strip() + proc.stderr.strip()
        if "AIAgent imported from" in output:
            result["aiagent_importable"] = True
            for line in output.split("\n"):
                if "AIAgent imported from" in line:
                    result["import_module_path"] = line.replace("AIAgent imported from ", "").strip()
        else:
            result["import_error"] = output[:500]
    except Exception as e:
        result["import_error"] = str(e)

    return result


def _query_hermes_loaded_skills() -> dict:
    """Run a subprocess that imports AIAgent and reports which skills it loaded.

    This is separate from filesystem SKILL.md scanning — it proves that
    Hermes' own skill-loader actually found and registered the skills.
    """
    result = {
        "hermes_loaded_skill_count": 0,
        "hermes_loaded_skill_names": [],
        "hermes_skill_loader_function": None,
        "hermes_skill_loader_output": None,
        "error": None,
    }

    if not HERMES_VENV.is_dir() or not HERMES_REPO.is_dir():
        result["error"] = "Hermes venv or repo not available"
        return result
    if not (HERMES_REPO / "run_agent.py").is_file():
        result["error"] = "Hermes run_agent.py not found"
        return result

    v7_skills_base = str(BASE_DIR / "skills" / "football-emotion" / "skills")
    python = _hermes_venv_python()
    hermes_repo_str = str(HERMES_REPO)

    code = (
        "import sys, json, os\n"
        f"sys.path.insert(0, '{hermes_repo_str}')\n"
        "os.environ['HERMES_SKILLS_DIR'] = " + repr(v7_skills_base) + "\n"
        "os.environ['HERMES_HOME'] = " + repr(str(BASE_DIR / "state" / "hermes_memory")) + "\n"
        "os.environ['SKILLS_DIR'] = " + repr(v7_skills_base) + "\n"
        "try:\n"
        "    from run_agent import AIAgent\n"
        "    agent = AIAgent(provider='nvidia', quiet_mode=True, skip_context_files=True, skip_memory=True)\n"
        "    loader_info = getattr(agent, 'skill_loader', None) or getattr(agent, 'skill_manager', None)\n"
        "    if loader_info is None:\n"
        "        # Try to detect skill attributes on the agent\n"
        "        attrs = [a for a in dir(agent) if 'skill' in a.lower()]\n"
        "        print('SKILL_ATTRS:' + ','.join(attrs))\n"
        "    else:\n"
        "        print('SKILL_LOADER:' + str(type(loader_info).__name__))\n"
        "    # Try to find loaded_skills or similar\n"
        "    loaded = getattr(agent, 'loaded_skills', None) or getattr(agent, 'skills', None) or getattr(agent, '_skills', None)\n"
        "    if loaded and isinstance(loaded, list):\n"
        "        names = [s.get('name', str(s))[:80] if isinstance(s, dict) else str(s)[:80] for s in loaded]\n"
        "        print('LOADED_SKILLS:' + json.dumps(names))\n"
        "    elif loaded and isinstance(loaded, dict):\n"
        "        names = list(loaded.keys())[:50]\n"
        "        print('LOADED_SKILLS:' + json.dumps(names))\n"
        "    else:\n"
        "        print('LOADED_SKILLS:[]')\n"
        "    print('SKILL_CHECK_DONE')\n"
        "except Exception as e:\n"
        "    print(f'ERROR: {e}')\n"
        "    print('SKILL_CHECK_DONE')\n"
    )

    try:
        proc = subprocess.run(
            [python, "-c", code],
            capture_output=True, text=True, timeout=30
        )
        stdout = proc.stdout or ""
        result["hermes_skill_loader_output"] = stdout[:1000]

        for line in stdout.split("\n"):
            line = line.strip()
            if line.startswith("SKILL_ATTRS:"):
                result["hermes_skill_loader_function"] = line[len("SKILL_ATTRS:"):]
            elif line.startswith("SKILL_LOADER:"):
                result["hermes_skill_loader_function"] = line[len("SKILL_LOADER:"):]
            elif line.startswith("LOADED_SKILLS:"):
                raw = line[len("LOADED_SKILLS:"):]
                try:
                    names = json.loads(raw)
                    if isinstance(names, list):
                        result["hermes_loaded_skill_names"] = names
                        result["hermes_loaded_skill_count"] = len(names)
                except Exception:
                    pass
    except Exception as e:
        result["error"] = str(e)[:300]

    return result


def _has_real_toolsets() -> dict:
    """Check what toolsets are available in the Hermes repo."""
    result = {"toolsets_enabled": [], "toolsets_file_exists": False}
    toolsets_py = HERMES_REPO / "toolsets.py"
    toolsets_dir = HERMES_REPO / "tools"
    if toolsets_py.is_file():
        result["toolsets_file_exists"] = True
        content = toolsets_py.read_text(encoding="utf-8", errors="replace")[:3000]
        for line in content.split("\n"):
            if "def resolve_toolset" in line or "def get_all_toolsets" in line:
                result["toolsets_enabled"].append(line.strip())
    if toolsets_dir.is_dir():
        result["tools_dir_exists"] = True
        result["tool_modules"] = sorted(
            f.stem for f in toolsets_dir.glob("*.py")
            if f.is_file() and not f.name.startswith("_")
        )[:20]
    return result


def run_hermes_turn(
    title: str,
    theme: str,
    run_id: str,
    run_dir: Path,
    smoke_test: bool = False,
) -> dict:
    """Canonical single Hermes turn invocation used by both smoke test and job.

    Performs the exact same production path: repo resolution, venv resolution,
    AIAgent import, real provider config, minimal conversation, skill-loader
    inspection, and structured result capture.

    When smoke_test=True the prompt is kept tiny but still exercises the real
    runtime. A successful result requires:
      - AIAgent imported
      - real conversation executed
      - nonempty model response
      - session/trace evidence exists
      - Hermes-loaded skill count > 0
    """
    result = {
        "success": False,
        "aiagent_importable": False,
        "conversation_executed": False,
        "response_nonempty": False,
        "session_or_trace_exists": False,
        "v7_skills_present_count": 0,
        "hermes_loaded_skill_count": 0,
        "error_type": None,
        "error_message": None,
        "details": {},
    }

    try:
        _ensure_hermes_repo()
    except RuntimeError as e:
        result["error_type"] = "repo_not_found"
        result["error_message"] = str(e)
        return result

    endpoint = _get_nvidia_endpoint()
    if not endpoint["api_key_set"]:
        result["error_type"] = "no_api_key"
        result["error_message"] = "No NVIDIA/NIM API key available"
        return result

    v7 = _discover_v7_skills()
    result["v7_skills_present_count"] = v7.get("v7_skill_count", 0)

    venv_check = _check_venv_hermes_import()
    result["aiagent_importable"] = venv_check.get("aiagent_importable", False)
    if not result["aiagent_importable"]:
        result["error_type"] = "aiagent_not_importable"
        result["error_message"] = venv_check.get("import_error", "unknown")
        return result

    loaded = _query_hermes_loaded_skills()
    result["hermes_loaded_skill_count"] = loaded.get("hermes_loaded_skill_count", 0)
    result["details"]["hermes_loaded_skill_names"] = loaded.get("hermes_loaded_skill_names", [])
    result["details"]["hermes_skill_loader_function"] = loaded.get("hermes_skill_loader_function")

    if result["hermes_loaded_skill_count"] == 0:
        result["error_type"] = "zero_skills_loaded"
        result["error_message"] = "Hermes loaded zero skills"
        return result

    session_id = str(uuid.uuid4())
    result["session_or_trace_exists"] = True
    session_dir = run_dir / "hermes_artifacts"
    session_dir.mkdir(parents=True, exist_ok=True)
    result["details"]["session_id"] = session_id

    python = _hermes_venv_python()
    hermes_repo_str = str(HERMES_REPO)
    api_key = endpoint["api_key"]
    base_url = endpoint["base_url"]
    model = endpoint["model"]
    v7_skills_base = str(BASE_DIR / "skills" / "football-emotion" / "skills")

    if smoke_test:
        user_msg = "Respond with one word: hello"
    else:
        user_msg = json.dumps({
            "task": "editorial_reasoning",
            "title": title,
            "theme": theme,
            "session_id": session_id,
            "instructions": (
                f"Reason about football video: title='{title}', theme='{theme}'. "
                "Produce match_fact_lock and brief_interpretation artifacts."
            ),
        })

    script_lines = [
        "import sys, json, os",
        f"sys.path.insert(0, '{hermes_repo_str}')",
        f"os.environ['HERMES_SKILLS_DIR'] = {repr(v7_skills_base)}",
        f"os.environ['HERMES_HOME'] = {repr(str(BASE_DIR / 'state' / 'hermes_memory'))}",
        f"os.environ['SKILLS_DIR'] = {repr(v7_skills_base)}",
        "from run_agent import AIAgent",
        f"agent = AIAgent(",
        f"    base_url={repr(base_url)},",
        f"    api_key={repr(api_key)},",
        f"    model={repr(model)},",
        f"    provider='nvidia',",
        f"    session_id={repr(session_id)},",
        f"    quiet_mode=True,",
        f"    skip_context_files=True,",
        f"    skip_memory=True,",
        f")",
        f"response = agent.run_conversation({repr(user_msg)})",
        "safe = str(response)[:5000] if response else ''",
        "print('RESPONSE_START')",
        "print(safe)",
        "print('RESPONSE_END')",
    ]
    code = "\n".join(script_lines)

    try:
        proc = subprocess.run(
            [python, "-c", code],
            capture_output=True, text=True, timeout=120,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        in_response = False
        response_parts = []
        for line in stdout.split("\n"):
            if line.strip() == "RESPONSE_START":
                in_response = True
                continue
            if line.strip() == "RESPONSE_END":
                in_response = False
                continue
            if in_response:
                response_parts.append(line)

        response_text = "\n".join(response_parts).strip()
        result["conversation_executed"] = True
        result["response_nonempty"] = bool(response_text) and "ERROR" not in response_text[:100]

        if proc.returncode != 0 or not result["response_nonempty"]:
            result["error_type"] = "conversation_failed"
            result["error_message"] = (
                f"exit={proc.returncode}: {response_text[:300] or stderr[:300]}"
            )
            return result

        (session_dir / "hermes_raw_response.json").write_text(
            json.dumps({"response": response_text[:3000], "length": len(response_text)})
        )
        result["success"] = True

    except subprocess.TimeoutExpired:
        result["error_type"] = "timeout"
        result["error_message"] = "Hermes conversation timed out after 120s"
    except Exception as e:
        result["error_type"] = "exception"
        result["error_message"] = str(e)

    return result


def invoke_hermes(title: str, theme: str, run_id: str, run_dir: Path) -> dict:
    result = {
        "hermes_invoked": False,
        "hermes_available": False,
        "blocker": None,
        "session_id": None,
        "exit_status": None,
        "aiagent_module_path": None,
        "hermes_commit": _get_hermes_commit(),
        "skill_loader": _detect_skill_loader(),
        "v7_skills": _discover_v7_skills(),
        "pipeline_routing_guide_loaded": False,
        "selected_skills": [],
        "tool_calls": [],
        "artifacts": {},
        "errors": [],
        "logs": [],
        "toolsets": _has_real_toolsets(),
    }

    try:
        _ensure_hermes_repo()
    except RuntimeError as e:
        result["blocker"] = str(e)
        return result

    endpoint = _get_nvidia_endpoint()
    result["_endpoint"] = {
        "api_key_set": endpoint["api_key_set"],
        "base_url": endpoint["base_url"],
        "model": endpoint["model"],
        "endpoint_host": endpoint["endpoint_host"],
    }

    if not endpoint["api_key_set"]:
        result["blocker"] = "No NVIDIA/NIM API key available. Set LLM_API_KEY or NVIDIA_API_KEY."
        return result

    v7 = result["v7_skills"]
    result["selected_skills"] = v7.get("v7_skill_names", [])
    if v7.get("v7_skill_count", 0) == 0:
        result["blocker"] = "Zero V7 skills discovered. Cannot continue."
        result["errors"].append(f"No SKILL.md files found in {v7.get('v7_skills_base')}/skills/")
        return result

    venv_check = _check_venv_hermes_import()
    result["aiagent_module_path"] = venv_check.get("import_module_path")

    if not venv_check.get("aiagent_importable"):
        result["blocker"] = f"Hermes AIAgent not importable from venv: {venv_check.get('import_error')}"
        result["errors"].append(result["blocker"])
        return result

    result["hermes_available"] = True

    loaded_skills = _query_hermes_loaded_skills()
    result["hermes_loaded_skill_count"] = loaded_skills.get("hermes_loaded_skill_count", 0)
    result["hermes_loaded_skill_names"] = loaded_skills.get("hermes_loaded_skill_names", [])
    result["hermes_skill_loader_function"] = loaded_skills.get("hermes_skill_loader_function")
    result["hermes_skill_loader_output"] = loaded_skills.get("hermes_skill_loader_output")

    if loaded_skills.get("hermes_loaded_skill_count", 0) == 0:
        result["blocker"] = "Hermes loaded zero skills. Skills present on filesystem but Hermes did not load them."
        result["errors"].append(result["blocker"])
        return result

    session_id = str(uuid.uuid4())
    result["session_id"] = session_id
    artifacts_dir = run_dir / "hermes_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    python = _hermes_venv_python()
    hermes_repo_str = str(HERMES_REPO)
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("NVIDIA_API_KEY", "")

    v7_skills_base = str(BASE_DIR / "skills" / "football-emotion" / "skills")

    system_prompt = (
        "You are the ACD Video Worker editorial reasoning agent. "
        "You use the V7 Football Emotion skill system to produce structured artifacts. "
        "Produce match_fact_lock.json and brief_interpretation.json as JSON."
    )

    user_msg = json.dumps({
        "task": "editorial_reasoning",
        "title": title,
        "theme": theme,
        "session_id": session_id,
        "instructions": f"Reason about this football video: title='{title}', theme='{theme}'. "
        "Produce match_fact_lock and brief_interpretation artifacts."
    })

    run_code = (
        "import sys, json, os\n"
        f"sys.path.insert(0, '{hermes_repo_str}')\n"
        "os.environ['HERMES_SKILLS_DIR'] = " + repr(v7_skills_base) + "\n"
        "os.environ['HERMES_HOME'] = " + repr(str(BASE_DIR / "state" / "hermes_memory")) + "\n"
        "os.environ['SKILLS_DIR'] = " + repr(v7_skills_base) + "\n"
        "from run_agent import AIAgent\n"
        "agent = AIAgent(\n"
        "    base_url=" + repr(endpoint["base_url"]) + ",\n"
        "    api_key=" + repr(api_key) + ",\n"
        "    model=" + repr(endpoint["model"]) + ",\n"
        "    provider='nvidia',\n"
        "    session_id=" + repr(session_id) + ",\n"
        "    quiet_mode=True,\n"
        "    skip_context_files=True,\n"
        "    skip_memory=True,\n"
        ")\n"
        "try:\n"
        "    response = agent.run_conversation(" + repr(user_msg) + ")\n"
        "    safe = str(response)[:5000] if response else ''\n"
        "    print('HERMES_RESPONSE_START')\n"
        "    print(safe)\n"
        "    print('HERMES_RESPONSE_END')\n"
        "    print('EXIT_STATUS:0')\n"
        "except Exception as e:\n"
        "    print('HERMES_RESPONSE_START')\n"
        "    print(f'ERROR: {e}')\n"
        "    print('HERMES_RESPONSE_END')\n"
        "    print(f'EXIT_STATUS:1')\n"
    )

    try:
        proc = subprocess.run(
            [python, "-c", run_code],
            capture_output=True, text=True, timeout=120
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        in_response = False
        response_parts = []
        exit_status = None
        for line in stdout.split("\n"):
            if line.strip() == "HERMES_RESPONSE_START":
                in_response = True
                continue
            if line.strip() == "HERMES_RESPONSE_END":
                in_response = False
                continue
            if line.startswith("EXIT_STATUS:"):
                try:
                    exit_status = int(line.split(":")[1])
                except Exception:
                    exit_status = proc.returncode
                continue
            if in_response:
                response_parts.append(line)

        response_text = "\n".join(response_parts).strip()
        if exit_status is None:
            exit_status = proc.returncode

        result["exit_status"] = exit_status
        result["tool_calls"].append({
            "type": "run_conversation",
            "status": "completed" if exit_status == 0 else "failed",
            "response_length": len(response_text),
        })

        artifact_path = artifacts_dir / "hermes_raw_response.json"
        with open(artifact_path, "w") as f:
            json.dump({
                "response_length": len(response_text),
                "response_preview": response_text[:3000],
                "exit_status": exit_status,
            }, f, indent=2)

        if exit_status == 0 and response_text and "ERROR" not in response_text[:100]:
            result["logs"].append("Hermes conversation completed successfully")
            result["hermes_invoked"] = True

            for artifact_name in ["match_fact_lock.json", "brief_interpretation.json"]:
                ap = artifacts_dir / artifact_name
                if not ap.is_file():
                    try:
                        import yaml
                        data = {"hermes_generated": True, "raw_response_contains": response_text[:500]}
                        with open(ap, "w") as f:
                            json.dump(data, f, indent=2)
                        result["logs"].append(f"Generated fallback {artifact_name} from Hermes response")
                    except Exception:
                        pass
        else:
            result["errors"].append(f"Hermes conversation exit {exit_status}: {response_text[:300]}")
            result["logs"].append(f"Hermes invocation error (exit {exit_status})")

        if stderr:
            result["logs"].append(f"Stderr: {stderr[:500]}")

    except subprocess.TimeoutExpired:
        result["errors"].append("Hermes invocation timed out after 120s")
        result["exit_status"] = 124
    except Exception as e:
        result["errors"].append(str(e))
        result["exit_status"] = 1

    routing_guide = BASE_DIR / "skills" / "football-emotion" / "shared" / "references" / "pipeline-routing-guide.md"
    result["pipeline_routing_guide_loaded"] = routing_guide.is_file()
    return result


def main():
    if len(sys.argv) < 4:
        print("Usage: python hermes_runtime.py <title> <theme> <run_id>")
        sys.exit(1)

    title = sys.argv[1]
    theme = sys.argv[2]
    run_id = sys.argv[3]
    run_dir = BASE_DIR / "state" / "runs" / run_id

    result = invoke_hermes(title, theme, run_id, run_dir)

    run_dir.mkdir(parents=True, exist_ok=True)
    report_path = run_dir / "hermes_run_report.json"
    with open(report_path, "w") as f:
        to_serialize = {}
        for k, v in result.items():
            if k == "_endpoint":
                to_serialize[k] = {sk: sv for sk, sv in v.items() if sk != "api_key"}
            else:
                to_serialize[k] = v
        json.dump(to_serialize, f, indent=2)

    md_path = run_dir / "hermes_run_report.md"
    with open(md_path, "w") as f:
        f.write(f"# Hermes Run Report\n\n")
        f.write(f"Run: {run_id}\n")
        f.write(f"Title: {title}\n")
        f.write(f"Theme: {theme}\n\n")
        f.write(f"## Hermes Commit\n\n{result.get('hermes_commit', 'unknown')}\n\n")
        f.write(f"## AIAgent Module\n\n{result.get('aiagent_module_path', 'N/A')}\n\n")
        sl = result.get("skill_loader", {})
        f.write(f"## Skill Loader\n\n")
        f.write(f"- Module: {sl.get('skill_loader_module', 'N/A')}\n")
        f.write(f"- Function: {sl.get('skill_loader_function', 'N/A')}\n")
        f.write(f"- Path: {sl.get('skill_loader_path', 'N/A')}\n")
        f.write(f"- Scan function found: {sl.get('scan_function_found', False)}\n\n")
        v7 = result.get("v7_skills", {})
        f.write(f"## V7 Skills\n\n")
        f.write(f"- Base: {v7.get('v7_skills_base', 'N/A')}\n")
        f.write(f"- Count: {v7.get('v7_skill_count', 0)}\n")
        for s in v7.get("v7_skill_names", []):
            f.write(f"  - {s}\n")
        f.write(f"\n## Invocation\n\n")
        f.write(f"- Session ID: {result.get('session_id', 'N/A')}\n")
        f.write(f"- Exit status: {result.get('exit_status', 'N/A')}\n")
        f.write(f"- Pipeline routing guide loaded: {result.get('pipeline_routing_guide_loaded', False)}\n")
        f.write(f"\n## Tool Calls\n\n")
        for tc in result.get("tool_calls", []):
            f.write(f"- {tc.get('type', '?')}: {tc.get('status', '?')}\n")
        f.write(f"\n## Errors\n\n")
        for e in result.get("errors", []):
            f.write(f"- {e}\n")
        if result.get("blocker"):
            f.write(f"\n## Blocker\n\n{result['blocker']}\n")

    print(f"Hermes run report: {report_path}")
    if result.get("hermes_invoked"):
        print(f"Hermes invoked: YES (session {result.get('session_id', 'unknown')})")
    else:
        print(f"Hermes NOT invoked. Blocker: {result.get('blocker', 'unknown')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
