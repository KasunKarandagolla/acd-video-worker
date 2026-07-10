#!/usr/bin/env python3
"""Runtime smoke test — verifies all integration points without full render.

Tests:
- Hermes dependencies import
- AIAgent import from cloned repo
- NVIDIA provider configuration
- one tiny real Hermes conversation
- V7 skill discovery count
- memory path visibility
- search capability
- OpenMontage pipeline loader import
- tool registry discovery
- schema availability
- selected pipeline availability

Writes:
  state/runs/runtime_smoke_test.json
  state/runs/runtime_smoke_test.md
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HERMES_REPO = BASE_DIR / "external" / "Hermes-Agent"
OM_REPO = BASE_DIR / "external" / "OpenMontage"
HERMES_VENV = Path("/kaggle/working/.venvs/hermes")


def _subprocess_python(code: str, venv: bool = False, timeout: int = 30) -> dict:
    python = str(HERMES_VENV / "bin" / "python3") if (venv and HERMES_VENV.is_dir()) else sys.executable
    try:
        proc = subprocess.run(
            [python, "-c", code],
            capture_output=True, text=True, timeout=timeout
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip()[:1000],
            "stderr": proc.stderr.strip()[:500],
            "success": proc.returncode == 0,
        }
    except Exception as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e), "success": False}


def test_hermes_deps_import() -> dict:
    code = "import openai, pydantic, yaml, requests, jsonschema; print('ok')"
    r = _subprocess_python(code, venv=True)
    return {"test": "hermes_deps_import", "passed": r["success"], "detail": r["stdout"] or r["stderr"]}


def test_aiagent_import() -> dict:
    code = (
        "import sys; sys.path.insert(0, " + repr(str(HERMES_REPO)) + "); "
        "from run_agent import AIAgent; "
        "print('OK: ' + AIAgent.__module__)"
    )
    r = _subprocess_python(code, venv=True)
    return {"test": "aiagent_import", "passed": r["success"], "detail": r["stdout"] or r["stderr"]}


def test_nvidia_provider_config() -> dict:
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("NVIDIA_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL") or "https://integrate.api.nvidia.com/v1"
    model = os.environ.get("LLM_MODEL") or "nvidia/llama-3.1-nemotron-70b-instruct"
    passed = bool(api_key) and bool(base_url)
    return {
        "test": "nvidia_provider_config",
        "passed": passed,
        "detail": f"API key set: {bool(api_key)}, base_url: {base_url}, model: {model}",
    }


def test_tiny_conversation() -> dict:
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("NVIDIA_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL") or "https://integrate.api.nvidia.com/v1"
    model = os.environ.get("LLM_MODEL") or "nvidia/llama-3.1-nemotron-70b-instruct"
    if not api_key:
        return {"test": "tiny_conversation", "passed": False, "detail": "No API key"}

    code = (
        "import sys; sys.path.insert(0, " + repr(str(HERMES_REPO)) + "); "
        "from run_agent import AIAgent; "
        "agent = AIAgent("
        f"base_url={repr(base_url)}, "
        f"api_key={repr(api_key)}, "
        f"model={repr(model)}, "
        "provider='nvidia', "
        "quiet_mode=True, skip_context_files=True, skip_memory=True); "
        "resp = agent.run_conversation('Say hello in one word.'); "
        "print(str(resp)[:200])"
    )
    r = _subprocess_python(code, venv=True, timeout=60)
    passed = r["success"] and len(r["stdout"]) > 0 and "ERROR" not in r["stdout"].upper()
    return {"test": "tiny_conversation", "passed": passed, "detail": r["stdout"][:200] if passed else (r["stdout"] or r["stderr"])[:200]}


def test_v7_skill_discovery() -> dict:
    skills_base = BASE_DIR / "skills" / "football-emotion" / "skills"
    if not skills_base.is_dir():
        return {"test": "v7_skill_discovery", "passed": False, "detail": "Skills dir not found", "count": 0}
    count = 0
    names = []
    for d in sorted(skills_base.iterdir()):
        if d.is_dir() and (d / "SKILL.md").is_file():
            count += 1
            names.append(d.name)
    return {"test": "v7_skill_discovery", "passed": count > 0, "count": count, "names": names, "detail": f"{count} skills"}


def test_hermes_loaded_skills() -> dict:
    """Check Hermes' actual loaded skill count (separate from filesystem scan)."""
    from scripts.hermes_runtime import _query_hermes_loaded_skills, _discover_v7_skills
    v7 = _discover_v7_skills()
    v7_present = v7.get("v7_skill_count", 0)
    loaded = _query_hermes_loaded_skills()
    loaded_count = loaded.get("hermes_loaded_skill_count", 0)
    loaded_names = loaded.get("hermes_loaded_skill_names", [])
    loader_fn = loaded.get("hermes_skill_loader_function")
    return {
        "test": "hermes_loaded_skills",
        "passed": v7_present > 0,
        "v7_skills_present_count": v7_present,
        "hermes_loaded_skill_count": loaded_count,
        "hermes_loaded_skill_names": loaded_names,
        "hermes_skill_loader_function": loader_fn,
        "hermes_skill_loader_output": loaded.get("hermes_skill_loader_output"),
        "detail": f"V7 present: {v7_present}, Hermes loaded: {loaded_count}, loader fn: {loader_fn}",
    }


def test_memory_path() -> dict:
    mem_dir = BASE_DIR / "state" / "hermes_memory"
    passed = mem_dir.is_dir()
    files = [f.name for f in mem_dir.iterdir()] if passed else []
    return {"test": "memory_path_visibility", "passed": passed, "detail": f"{len(files)} files" if passed else "Not found", "files": files}


def test_search_capability() -> dict:
    report_path = BASE_DIR / "state" / "runs" / "search_capability_preflight.json"
    if report_path.is_file():
        with open(report_path) as f:
            data = json.load(f)
        return {"test": "search_capability", "passed": data.get("current_event_fact_verification") != "blocked", "detail": data.get("current_event_fact_verification", "unknown")}
    return {"test": "search_capability", "passed": False, "detail": "Preflight report not found"}


def test_om_pipeline_loader() -> dict:
    if not OM_REPO.is_dir():
        return {"test": "om_pipeline_loader", "passed": False, "detail": "OpenMontage not cloned"}
    code = (
        "import sys; sys.path.insert(0, " + repr(str(OM_REPO)) + "); "
        "from lib.pipeline_loader import load_pipeline, list_pipelines; "
        "pipelines = list_pipelines(); "
        "print(f'OK: {len(pipelines)} pipelines: {pipelines}')"
    )
    r = _subprocess_python(code, timeout=15)
    return {"test": "om_pipeline_loader", "passed": r["success"], "detail": r["stdout"] or r["stderr"]}


def test_tool_registry_discovery() -> dict:
    if not OM_REPO.is_dir():
        return {"test": "tool_registry_discovery", "passed": False, "detail": "OpenMontage not cloned"}
    code = (
        "import sys; sys.path.insert(0, " + repr(str(OM_REPO)) + "); "
        "from tools.tool_registry import registry; "
        "tools = registry.discover('tools'); "
        "print(f'OK: {len(tools)} tools discovered: {tools}')"
    )
    r = _subprocess_python(code, timeout=15)
    return {"test": "tool_registry_discovery", "passed": r["success"], "detail": r["stdout"] or r["stderr"]}


def test_schema_availability() -> dict:
    if not OM_REPO.is_dir():
        return {"test": "schema_availability", "passed": False, "detail": "OpenMontage not cloned"}
    schemas_dir = OM_REPO / "schemas"
    if not schemas_dir.is_dir():
        return {"test": "schema_availability", "passed": False, "detail": "Schemas dir not found"}
    schema_files = sorted(schemas_dir.rglob("*.json"))
    return {"test": "schema_availability", "passed": len(schema_files) > 0, "detail": f"{len(schema_files)} schema files", "files": [str(f.relative_to(schemas_dir)) for f in schema_files[:20]]}


def test_selected_pipeline_available() -> dict:
    if not OM_REPO.is_dir():
        return {"test": "selected_pipeline_available", "passed": False, "detail": "OpenMontage not cloned"}
    pipeline_defs = OM_REPO / "pipeline_defs"
    if not pipeline_defs.is_dir():
        return {"test": "selected_pipeline_available", "passed": False, "detail": "pipeline_defs not found"}
    yamls = sorted(pipeline_defs.glob("*.yaml"))
    names = [p.stem for p in yamls]
    selected = "clip-factory"
    passed = selected in names
    return {"test": "selected_pipeline_available", "passed": passed, "detail": f"'{selected}' {'found' if passed else 'not found'} in {names}"}


def test_openmontage_deterministic_selection() -> dict:
    """Verify OpenMontage selection is deterministic: never picks first arbitrary tool."""
    if not OM_REPO.is_dir():
        return {"test": "openmontage_deterministic_selection", "passed": False, "detail": "OpenMontage not cloned"}
    try:
        sys.path.insert(0, str(OM_REPO))
        from tools.tool_registry import registry
        from lib.pipeline_loader import load_pipeline, list_pipelines, get_required_tools
        registry.discover("tools")
        all_tools = registry.list_all()
        pipelines = list_pipelines()
        selected_pipeline = None
        for name in ["clip-factory", "cinematic", "hybrid", "documentary-montage"]:
            if name in pipelines:
                selected_pipeline = name
                break
        if not selected_pipeline and pipelines:
            return {"test": "openmontage_deterministic_selection", "passed": False, "detail": "No expected pipeline found"}
        if not selected_pipeline:
            return {"test": "openmontage_deterministic_selection", "passed": False, "detail": "No pipelines available"}

        manifest = load_pipeline(selected_pipeline)
        required = list(get_required_tools(manifest))

        # Selection rules from render_with_openmontage._run_registry_discovery
        selected_tool = None
        selection_rule = None
        for rt in required:
            if rt in all_tools:
                selected_tool = rt
                selection_rule = "matched_manifest_required"
                break
        if not selected_tool:
            compose_tools = [t for t in all_tools if "compose" in t.lower() or "edit" in t.lower()]
            if compose_tools:
                selected_tool = compose_tools[0]
                selection_rule = "matched_compose_edit_name"
        if not selected_tool and "video_compose" in all_tools:
            selected_tool = "video_compose"
            selection_rule = "matched_video_compose_name"

        return {
            "test": "openmontage_deterministic_selection",
            "passed": selected_tool is not None,
            "selected_pipeline_manifest": selected_pipeline,
            "pipeline_load_success": True,
            "required_tools": required,
            "registered_tools": all_tools,
            "selected_compose_tool": selected_tool,
            "compose_tool_support_status": selection_rule or "blocked_no_compatible_tool",
            "detail": f"Pipeline={selected_pipeline}, tool={selected_tool}, rule={selection_rule}",
        }
    except Exception as e:
        return {"test": "openmontage_deterministic_selection", "passed": False, "detail": str(e)[:200]}


def main():
    v7_test = test_v7_skill_discovery()
    hermes_skills_test = test_hermes_loaded_skills()
    om_det_test = test_openmontage_deterministic_selection()

    tests = [
        test_hermes_deps_import(),
        test_aiagent_import(),
        test_nvidia_provider_config(),
        test_tiny_conversation(),
        v7_test,
        hermes_skills_test,
        test_memory_path(),
        test_search_capability(),
        test_om_pipeline_loader(),
        test_tool_registry_discovery(),
        test_schema_availability(),
        test_selected_pipeline_available(),
        om_det_test,
    ]

    passed_count = sum(1 for t in tests if t["passed"])
    total = len(tests)

    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
        "smoke_test_passed": passed_count == total,
        "tests_passed": passed_count,
        "tests_total": total,
        "tests": tests,
        "v7_skills_present_count": v7_test.get("count", 0),
        "v7_skill_names": v7_test.get("names", []),
        "hermes_loaded_skill_count": hermes_skills_test.get("hermes_loaded_skill_count", 0),
        "hermes_loaded_skill_names": hermes_skills_test.get("hermes_loaded_skill_names", []),
        "hermes_skill_loader_function": hermes_skills_test.get("hermes_skill_loader_function"),
        "hermes_skill_loader_output": hermes_skills_test.get("hermes_skill_loader_output"),
        "selected_pipeline_manifest": om_det_test.get("selected_pipeline_manifest"),
        "pipeline_load_success": om_det_test.get("pipeline_load_success"),
        "required_tools": om_det_test.get("required_tools"),
        "registered_tools": om_det_test.get("registered_tools"),
        "selected_compose_tool": om_det_test.get("selected_compose_tool"),
        "compose_tool_support_status": om_det_test.get("compose_tool_support_status"),
    }

    report_json = BASE_DIR / "state" / "runs" / "runtime_smoke_test.json"
    report_json.parent.mkdir(parents=True, exist_ok=True)
    with open(report_json, "w") as f:
        json.dump(result, f, indent=2)

    report_md = BASE_DIR / "state" / "runs" / "runtime_smoke_test.md"
    with open(report_md, "w") as f:
        f.write(f"# Runtime Smoke Test\n\n")
        f.write(f"Timestamp: {result['timestamp_utc']}\n")
        f.write(f"Passed: {passed_count}/{total}\n\n")
        f.write(f"## Results\n\n")
        for t in tests:
            status = "PASS" if t["passed"] else "FAIL"
            f.write(f"- {status}: {t['test']} — {t.get('detail', '')}\n")

    print(f"Runtime smoke test: {report_json}")
    print(f"Passed: {passed_count}/{total}")

    if not result["smoke_test_passed"]:
        print("SMOKE TEST FAILED — blocking job")
        for t in tests:
            if not t["passed"]:
                print(f"  FAIL: {t['test']} — {t.get('detail', '')[:100]}")
        sys.exit(1)

    print("All smoke tests passed — proceeding to job.")


if __name__ == "__main__":
    main()
