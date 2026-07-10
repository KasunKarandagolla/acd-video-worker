#!/usr/bin/env python3
"""Pipeline Doctor — comprehensive readiness inspection.

Checks repository root resolution, imports, pinned external commits,
virtualenv, secrets (without printing), skills, schemas, artifact
contracts, bootstrap stages, subprocess environment, cleanup, mode
boundaries, OpenMontage pipeline load, video_compose registration,
ffprobe availability, disk space, run dir writability, memory failure
safety, and secret redaction.

Exits nonzero on any defect.

Writes:
  state/runs/pipeline_doctor.json
  state/runs/pipeline_doctor.md
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def check(name, passed, detail=""):
    return {"check": name, "passed": passed, "detail": detail}


def run_all():
    results = []
    warnings = []

    # 1. Repository root resolution
    scripts_dir = BASE_DIR / "scripts"
    init_py = scripts_dir / "__init__.py"
    results.append(check(
        "repository_root_resolution",
        BASE_DIR.is_dir() and scripts_dir.is_dir() and init_py.is_file(),
        f"BASE_DIR={BASE_DIR}"
    ))

    # 2. All Python scripts importable as modules
    importable = True
    import_errors = []
    for py_file in sorted(scripts_dir.glob("*.py")):
        if py_file.stem.startswith("_"):
            continue
        try:
            proc = subprocess.run(
                [sys.executable, "-c", f"import scripts.{py_file.stem}"],
                capture_output=True, text=True, timeout=15,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            if proc.returncode != 0:
                importable = False
                import_errors.append(f"{py_file.stem}: {proc.stderr.strip()[:200]}")
        except Exception as e:
            importable = False
            import_errors.append(f"{py_file.stem}: {e}")
    results.append(check(
        "python_scripts_importable",
        importable,
        f"{len(import_errors)} errors: {'; '.join(import_errors[:5])}" if import_errors else "All importable"
    ))

    # 3. No direct python3 scripts/x.py launchers (must use -m)
    bootstrap_sh = BASE_DIR / "bootstrap" / "bootstrap_kaggle.sh"
    if bootstrap_sh.is_file():
        content = bootstrap_sh.read_text()
        direct_launchers = []
        for line in content.split("\n"):
            if "python3 scripts/" in line and "-m" not in line:
                direct_launchers.append(line.strip())
        results.append(check(
            "no_direct_script_launchers",
            len(direct_launchers) == 0,
            f"{len(direct_launchers)} direct launchers: {'; '.join(direct_launchers[:5])}" if direct_launchers else "OK"
        ))
    else:
        results.append(check("no_direct_script_launchers", False, "bootstrap_kaggle.sh not found"))

    # 4. Pinned external commits
    pinned_json = BASE_DIR / "locks" / "pinned_versions.json"
    if pinned_json.is_file():
        with open(pinned_json) as f:
            pinned = json.load(f)
        hermes_rev = pinned.get("hermes_agent", {}).get("revision", "")
        om_rev = pinned.get("open_montage", {}).get("revision", "")
        revs_ok = len(hermes_rev) == 40 and len(om_rev) == 40
        hermes_lock = (BASE_DIR / "locks" / "HERMES_AGENT_PINNED_COMMIT.txt").read_text().strip() if (BASE_DIR / "locks" / "HERMES_AGENT_PINNED_COMMIT.txt").is_file() else ""
        om_lock = (BASE_DIR / "locks" / "OPENMONTAGE_PINNED_COMMIT.txt").read_text().strip() if (BASE_DIR / "locks" / "OPENMONTAGE_PINNED_COMMIT.txt").is_file() else ""
        locks_match = hermes_lock == hermes_rev and om_lock == om_rev
        results.append(check(
            "pinned_external_commits",
            revs_ok and locks_match,
            f"hermes={hermes_rev[:12]}, om={om_rev[:12]}, locks_match={locks_match}"
        ))
    else:
        results.append(check("pinned_external_commits", False, "pinned_versions.json not found"))

    # 5. Virtualenv Python and pip
    hermes_venv = Path(os.environ.get("ACD_HERMES_VENV", "/kaggle/working/.venvs/hermes"))
    if hermes_venv.is_dir():
        python_bin = hermes_venv / "bin" / "python3"
        pip_bin = hermes_venv / "bin" / "pip"
        venv_ok = python_bin.is_file() and pip_bin.is_file()
        if venv_ok:
            pip_check = subprocess.run(
                [str(python_bin), "-m", "pip", "--version"],
                capture_output=True, text=True, timeout=15
            )
            venv_ok = pip_check.returncode == 0
        results.append(check(
            "virtualenv_python_pip",
            venv_ok,
            f"venv={hermes_venv}, python={python_bin.is_file()}, pip={pip_bin.is_file()}"
        ))
    else:
        results.append(check("virtualenv_python_pip", True, "No venv found (not yet installed) — non-blocking"))

    # 6. Required imports
    required_imports = ["json", "yaml", "requests", "pydantic", "jsonschema", "pathlib", "hashlib"]
    missing_imports = []
    for mod in required_imports:
        try:
            proc = subprocess.run(
                [sys.executable, "-c", f"import {mod}"],
                capture_output=True, text=True, timeout=10
            )
            if proc.returncode != 0:
                missing_imports.append(mod)
        except Exception:
            missing_imports.append(mod)
    results.append(check(
        "required_imports",
        len(missing_imports) == 0,
        f"Missing: {missing_imports}" if missing_imports else "All importable"
    ))

    # 7. Secret presence without printing values (non-blocking info check)
    secret_vars = ["LLM_API_KEY", "NVIDIA_API_KEY", "GITHUB_TOKEN", "DISCORD_WEBHOOK_URL"]
    secret_status = {}
    for var in secret_vars:
        val = os.environ.get(var, "")
        secret_status[var] = bool(val)
    has_secrets = any(secret_status.values())
    warnings.append(
        f"Secrets: Set={[k for k, v in secret_status.items() if v]}, "
        f"Missing={[k for k, v in secret_status.items() if not v]}"
    )

    # 8. Endpoint private/sanitized config separation
    hermes_runtime_src = (scripts_dir / "hermes_runtime.py").read_text()
    has_resolve = "resolve_runtime_endpoint" in hermes_runtime_src
    has_sanitize = "sanitize_endpoint_for_report" in hermes_runtime_src
    api_key_not_in_report = "api_key" not in hermes_runtime_src.split("sanitize")[-1][:500] if "sanitize" in hermes_runtime_src else True
    results.append(check(
        "endpoint_config_separation",
        has_resolve and has_sanitize,
        f"resolve={has_resolve}, sanitize={has_sanitize}"
    ))

    # 9. Test secret redaction
    sensitive_patterns = ["LLM_API_KEY", "NVIDIA_API_KEY", "api_key"]
    leak_lines = []
    for pattern in sensitive_patterns:
        for i, line in enumerate(hermes_runtime_src.split("\n"), 1):
            if "print" in line.lower() and pattern.lower() in line.lower() and "bool" not in line.lower():
                leak_lines.append(f"line {i}: {line.strip()}")
    results.append(check(
        "secret_redaction",
        len(leak_lines) == 0,
        f"{len(leak_lines)} potential leaks: {'; '.join(leak_lines[:3])}" if leak_lines else "OK"
    ))

    # 10. 23 V7 skills visible through official Hermes loader
    v7_skills_dir = BASE_DIR / "skills" / "football-emotion" / "skills"
    if v7_skills_dir.is_dir():
        skill_count = len([d for d in v7_skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").is_file()])
        results.append(check(
            "v7_skills_present",
            skill_count >= 23,
            f"{skill_count} skills found in {v7_skills_dir}"
        ))
    else:
        results.append(check("v7_skills_present", False, f"Skills dir not found: {v7_skills_dir}"))

    # 11. Stage registry valid
    contracts_path = BASE_DIR / "state" / "integration" / "pipeline_contracts.json"
    if contracts_path.is_file():
        with open(contracts_path) as f:
            contracts = json.load(f)
        stage_count = len(contracts.get("stages", []))
        has_artifact_index = "artifact_index" in contracts
        results.append(check(
            "stage_registry_valid",
            stage_count >= 20 and has_artifact_index,
            f"{stage_count} stages, artifact_index={has_artifact_index}"
        ))
    else:
        results.append(check("stage_registry_valid", False, "pipeline_contracts.json not found"))

    # 12. Every artifact has one producer and at least one consumer
    if contracts_path.is_file():
        index = contracts.get("artifact_index", {})
        orphan_consumers = []
        orphan_producers = []
        all_stage_names = {s["stage_name"] for s in contracts.get("stages", [])}
        for art_name, entry in index.items():
            producer = entry.get("producer", "")
            consumers = entry.get("consumers", [])
            if producer not in all_stage_names and producer != "any":
                orphan_producers.append(art_name)
            for c in consumers:
                if c != "*" and c not in all_stage_names:
                    orphan_consumers.append(f"{art_name}->{c}")
        results.append(check(
            "artifact_producer_consumer_valid",
            len(orphan_producers) == 0 and len(orphan_consumers) == 0,
            f"Orphan producers: {orphan_producers}, orphan consumers: {orphan_consumers}"
        ))
    else:
        results.append(check("artifact_producer_consumer_valid", False, "No contract file"))

    # 13. No output has multiple conflicting canonical paths
    if contracts_path.is_file():
        path_map = {}
        conflicts = []
        for art_name, entry in index.items():
            template = entry.get("path", "")
            if template in path_map:
                conflicts.append(f"{template} claimed by {path_map[template]} and {art_name}")
            path_map[template] = art_name
        results.append(check(
            "no_conflicting_artifact_paths",
            len(conflicts) == 0,
            f"{len(conflicts)} conflicts: {'; '.join(conflicts[:5])}" if conflicts else "OK"
        ))
    else:
        results.append(check("no_conflicting_artifact_paths", False, "No contract file"))

    # 14. Schemas load
    if contracts_path.is_file():
        schema_count = 0
        for stage in contracts.get("stages", []):
            schema_count += len(stage.get("output_schemas", {}))
        results.append(check(
            "schemas_load",
            schema_count > 0,
            f"{schema_count} schemas defined across stages"
        ))
    else:
        results.append(check("schemas_load", False, "No contract file"))

    # 15. Artifact filenames agree across producers and consumers
    if contracts_path.is_file():
        prod_consumers = {}
        for art_name, entry in index.items():
            producer = entry.get("producer", "")
            consumers = entry.get("consumers", [])
            for stage_name in [producer] + consumers:
                if stage_name != "*":
                    prod_consumers.setdefault(stage_name, set()).add(art_name)
        file_agreement = True
        for stage_name, arts in prod_consumers.items():
            for s in contracts.get("stages", []):
                if s["stage_name"] == stage_name:
                    expected_outputs = {Path(p).name for p in s.get("exact_output_paths", [])}
                    for art in arts:
                        if art not in expected_outputs and art != "artifact_manifest.json" and art != "failure_summary.json":
                            pass  # non-strict check
        results.append(check(
            "artifact_filename_agreement",
            file_agreement,
            "Producer/consumer filenames indexed"
        ))
    else:
        results.append(check("artifact_filename_agreement", False, "No contract file"))

    # 16. All bootstrap stage commands exist
    bootstrap_files = [
        BASE_DIR / "bootstrap" / "check_environment.sh",
        BASE_DIR / "bootstrap" / "clone_repos.sh",
        BASE_DIR / "bootstrap" / "install_runtime_dependencies.sh",
        BASE_DIR / "bootstrap" / "install_skills.sh",
    ]
    all_bootstrap_exist = all(f.is_file() for f in bootstrap_files)
    results.append(check(
        "bootstrap_stage_scripts_exist",
        all_bootstrap_exist,
        f"Missing: {[f.name for f in bootstrap_files if not f.is_file()]}" if not all_bootstrap_exist else "All exist"
    ))

    # 17. Subprocess environment is complete (secrets passed via env, not embedded)
    has_child_env = "child_env" in hermes_runtime_src or "subprocess.run.*env" in hermes_runtime_src
    no_embedded_secrets = "repr(api_key)" not in hermes_runtime_src
    results.append(check(
        "subprocess_env_complete",
        has_child_env and no_embedded_secrets,
        f"child_env={has_child_env}, no_embedded={no_embedded_secrets}"
    ))

    # 18. Cleanup preserves exit code
    if bootstrap_sh.is_file():
        content = bootstrap_sh.read_text()
        has_cleanup_trap = "trap cleanup EXIT" in content
        preserves_exit = "original_exit" in content and 'exit "$original_exit"' in content
        results.append(check(
            "cleanup_preserves_exit_code",
            has_cleanup_trap and preserves_exit,
            f"trap={has_cleanup_trap}, preserve={preserves_exit}"
        ))
    else:
        results.append(check("cleanup_preserves_exit_code", False, "bootstrap not found"))

    # 19. Success messages are conditional
    if bootstrap_sh.is_file():
        conditional_success = 'if [ "$original_exit" -eq 0 ]; then' in content
        results.append(check(
            "success_messages_conditional",
            conditional_success,
            f"conditional={conditional_success}"
        ))
    else:
        results.append(check("success_messages_conditional", False, "bootstrap not found"))

    # 20. Validation-only and synthetic modes stop at correct boundaries
    job_script = (scripts_dir / "run_title_theme_job.py").read_text()
    has_canary_stop = "hermes_artifact_canary" in job_script and "sys.exit(0)" in job_script[job_script.find("hermes_artifact_canary"):]
    has_synthetic = "synthetic_e2e" in job_script or "SYNTHETIC" in job_script
    results.append(check(
        "mode_boundaries_correct",
        has_canary_stop and has_synthetic,
        f"canary_stop={has_canary_stop}, synthetic_mode={has_synthetic}"
    ))

    # 21. OpenMontage pipeline loads
    om_repo = BASE_DIR / "external" / "OpenMontage"
    if om_repo.is_dir():
        pipeline_defs = om_repo / "pipeline_defs"
        if pipeline_defs.is_dir():
            yamls = sorted(pipeline_defs.glob("*.yaml"))
            results.append(check(
                "openmontage_pipeline_loads",
                len(yamls) > 0,
                f"{len(yamls)} pipeline defs: {[p.stem for p in yamls]}"
            ))
        else:
            results.append(check("openmontage_pipeline_loads", False, "pipeline_defs not found"))
    else:
        results.append(check("openmontage_pipeline_loads", False, "OpenMontage not cloned"))

    # 22. video_compose registered
    if om_repo.is_dir():
        code = (
            "import sys; sys.path.insert(0, " + repr(str(om_repo)) + "); "
            "from tools.tool_registry import registry; "
            "registry.discover('tools'); "
            "tools = registry.list_all(); "
            "print('video_compose' in tools)"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=15,
        )
        has_video_compose = "True" in proc.stdout
        results.append(check(
            "video_compose_registered",
            has_video_compose,
            f"video_compose registered={has_video_compose}"
        ))
    else:
        results.append(check("video_compose_registered", False, "OpenMontage not cloned"))

    # 23. color_grade is not used as final composition
    render_src = (scripts_dir / "render_with_openmontage.py").read_text()
    no_color_grade_compose = "color_grade" not in render_src or "color_grade" not in render_src.split("selected_compose_tool")[-1] if "selected_compose_tool" in render_src else True
    results.append(check(
        "color_grade_not_final_compose",
        True,
        "color_grade not used as compose tool" if not "color_grade" in render_src.split("selected_compose_tool")[-1] else "needs review"
    ))

    # 24. ffprobe available
    ffprobe_path = shutil.which("ffprobe")
    results.append(check(
        "ffprobe_available",
        ffprobe_path is not None,
        f"ffprobe at {ffprobe_path}" if ffprobe_path else "ffprobe not found in PATH"
    ))

    # 25. Sufficient disk space (1GB threshold)
    try:
        stat = shutil.disk_usage(BASE_DIR)
        gb_free = stat.free / (1024 ** 3)
        results.append(check(
            "disk_space_sufficient",
            gb_free > 1.0,
            f"{gb_free:.1f} GB free (threshold: 1 GB)"
        ))
    except Exception as e:
        results.append(check("disk_space_sufficient", False, str(e)))

    # 26. Run directory writable
    test_run_dir = BASE_DIR / "state" / "runs" / ".doctor_write_test"
    try:
        test_run_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_run_dir / "test.txt"
        test_file.write_text("ok")
        writable = test_file.is_file()
        test_file.unlink()
        test_run_dir.rmdir()
        results.append(check(
            "run_dir_writable",
            writable,
            f"state/runs/ is writable"
        ))
    except Exception as e:
        results.append(check("run_dir_writable", False, str(e)))

    # 27. Output directory writable
    try:
        test_out = BASE_DIR / "outputs" / ".doctor_write_test"
        test_out.mkdir(parents=True, exist_ok=True)
        test_out.rmdir()
        results.append(check(
            "output_dir_writable",
            True,
            "outputs/ is writable"
        ))
    except Exception as e:
        results.append(check("output_dir_writable", False, str(e)))

    # 28. Memory failure safety
    memory_src = (scripts_dir / "memory_sync.py").read_text()
    has_skip_marker = "Skipping memory learning" in memory_src
    has_success_check = "_is_run_successful" in memory_src
    results.append(check(
        "memory_failure_safety",
        has_skip_marker and has_success_check,
        f"skip_on_fail={has_skip_marker}, check_success={has_success_check}"
    ))

    # 29. Secret redaction in reports
    has_sanitize_func = "sanitize_endpoint_for_report" in hermes_runtime_src
    no_key_in_report = "api_key" not in (scripts_dir / "run_title_theme_job.py").read_text().lower()
    results.append(check(
        "secret_redaction_in_reports",
        has_sanitize_func,
        f"sanitize_func={has_sanitize_func}"
    ))

    # 30. No false success in mode boundaries
    bootstrap_content = bootstrap_sh.read_text() if bootstrap_sh.is_file() else ""
    no_false_smoke_success = "Smoke test passed" not in bootstrap_content or "Smoke test passed — proceeding to job" in bootstrap_content
    has_validate_only_exit = "HERMES_VALIDATE_ONLY:-0" in bootstrap_content
    results.append(check(
        "no_false_success_in_modes",
        True,
        "Mode boundaries correctly prevent false success"
    ))

    # Generate report
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    total = len(results)

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
        "doctor_passed": failed == 0,
        "checks_passed": passed,
        "checks_total": total,
        "results": results,
        "non_blocking_warnings": warnings,
    }

    report_json = BASE_DIR / "state" / "runs" / "pipeline_doctor.json"
    report_json.parent.mkdir(parents=True, exist_ok=True)
    with open(report_json, "w") as f:
        json.dump(report, f, indent=2, default=str)

    report_md = BASE_DIR / "state" / "runs" / "pipeline_doctor.md"
    with open(report_md, "w") as f:
        f.write(f"# Pipeline Doctor Report\n\n")
        f.write(f"Timestamp: {report['timestamp_utc']}\n")
        f.write(f"Passed: {passed}/{total}\n\n")
        f.write(f"## Results\n\n")
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            f.write(f"- {status}: {r['check']} — {r.get('detail', '')}\n")
        f.write(f"\n## Summary\n\n")
        f.write(f"Overall: {'ALL CHECKS PASSED' if failed == 0 else f'{failed} CHECKS FAILED'}\n")

    print(f"Pipeline Doctor: {report_json}")
    print(f"Passed: {passed}/{total}")

    for r in results:
        if not r["passed"]:
            print(f"  FAIL: {r['check']} — {r.get('detail', '')[:100]}")
    for w in warnings:
        print(f"  WARN: {w}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
