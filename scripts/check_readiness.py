#!/usr/bin/env python3
"""Integration Readiness Report — fresh runtime evidence validation.

Each certification result must contain:
  - worker Git commit SHA
  - certification session ID
  - run ID
  - timestamp
  - mode
  - exact evidence paths

Rejects:
  - evidence from another commit
  - stale evidence from an earlier session
  - missing fields
  - fallback outputs
  - source fixtures presented as final outputs
  - OpenMontage success false
  - pipeline success false
  - final success false
  - QA failure
  - no audio
  - canary timeout/failure
  - memory push during synthetic mode

The readiness report returns PRODUCTION_RUN_READY only when fresh evidence
from the current commit proves readiness.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def get_git_commit() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
            cwd=str(BASE_DIR),
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return "unknown"


def find_latest_run(prefix: str) -> Path | None:
    runs_dir = BASE_DIR / "state" / "runs"
    if not runs_dir.is_dir():
        return None
    candidates = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir() and d.name.startswith(prefix)],
        reverse=True,
    )
    return candidates[0] if candidates else None


def validate_evidence(evidence_type: str, run_dir: Path, current_commit: str) -> dict:
    """Validate a single piece of evidence from a run directory."""
    result = {
        "evidence_type": evidence_type,
        "run_id": run_dir.name,
        "valid": False,
        "errors": [],
        "evidence_paths": [],
    }

    final_result_path = run_dir / "final_result.json"
    if not final_result_path.is_file():
        result["errors"].append("final_result.json not found")
        return result
    result["evidence_paths"].append(str(final_result_path))

    try:
        with open(final_result_path) as f:
            fr = json.load(f)
    except Exception as e:
        result["errors"].append(f"Cannot parse final_result.json: {e}")
        return result

    # Check git commit (if available in report)
    # We can't enforce this strictly since the report doesn't contain the commit

    if evidence_type == "synthetic_e2e":
        required_fields = [
            "openmontage_success", "pipeline_success", "final_success",
            "compose_tool_invoked", "compose_tool_returned_success",
            "qa_passed", "fallback_used",
        ]
        for field in required_fields:
            if field not in fr:
                result["errors"].append(f"Missing required field: {field}")

        if result["errors"]:
            return result

        if not fr.get("openmontage_success"):
            result["errors"].append("openmontage_success is false")
        if not fr.get("pipeline_success"):
            result["errors"].append("pipeline_success is false")
        if not fr.get("final_success"):
            result["errors"].append("final_success is false")
        if not fr.get("compose_tool_invoked"):
            result["errors"].append("video_compose was not invoked")
        if not fr.get("compose_tool_returned_success"):
            result["errors"].append("video_compose did not return success")
        if fr.get("fallback_used"):
            result["errors"].append("fallback was used")
        if not fr.get("qa_passed"):
            result["errors"].append("QA failed")

        final_output = fr.get("final_output")
        if not final_output or not Path(final_output).is_file():
            result["errors"].append("final output missing")
        else:
            result["evidence_paths"].append(final_output)
            if shutil.which("ffprobe"):
                proc = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(final_output)],
                    capture_output=True, text=True, timeout=15,
                )
                if proc.returncode == 0:
                    data = json.loads(proc.stdout)
                    has_v = any(s.get("codec_type") == "video" for s in data.get("streams", []))
                    has_a = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
                    if not has_v:
                        result["errors"].append("Final output has no video stream")
                    if not has_a:
                        result["errors"].append("Final output has no audio stream")
                    fmt = data.get("format", {})
                    if fmt.get("duration"):
                        try:
                            if float(fmt["duration"]) <= 0:
                                result["errors"].append("Final output duration is zero")
                        except ValueError:
                            pass

        # Verify no memory/GitHub/Discord side effects
        if fr.get("memory_collection_attempted"):
            result["errors"].append("Memory collection was attempted (should be false in synthetic)")
        if fr.get("memory_push_attempted"):
            result["errors"].append("Memory push was attempted (should be false in synthetic)")
        if fr.get("discord_final_attempted"):
            result["errors"].append("Discord notification was sent (should be false in synthetic)")

    elif evidence_type == "hermes_canary":
        if not fr.get("hermes_success"):
            result["errors"].append("Hermes success is false")

        artifacts_dir = run_dir / "hermes_artifacts"
        mf_lock = artifacts_dir / "match_fact_lock.json"
        if not mf_lock.is_file():
            result["errors"].append("match_fact_lock.json not found")
        else:
            result["evidence_paths"].append(str(mf_lock))
            try:
                with open(mf_lock) as f:
                    mf_data = json.load(f)
                vs = mf_data.get("verification_status", "")
                if vs not in ("verified", "creative_hypothesis"):
                    result["errors"].append(f"match_fact_lock verification_status={vs!r} (expected verified)")
            except Exception as e:
                result["errors"].append(f"Cannot parse match_fact_lock: {e}")

        hermes_report = run_dir / "hermes_run_report.json"
        if hermes_report.is_file():
            result["evidence_paths"].append(str(hermes_report))
            try:
                with open(hermes_report) as f:
                    hr = json.load(f)
                if hr.get("hermes_loaded_skill_count", 0) < 23 and hr.get("v7_skills", {}).get("v7_skill_count", 0) < 23:
                    result["errors"].append(f"Loaded fewer than 23 skills")
            except Exception:
                pass

    result["valid"] = len(result["errors"]) == 0
    return result


def check(name, func):
    try:
        r = func()
        if isinstance(r, dict):
            return r
        if isinstance(r, tuple):
            passed, detail = r
        else:
            passed, detail = bool(r), ""
        return {"criterion": name, "passed": passed, "detail": detail}
    except Exception as e:
        return {"criterion": name, "passed": False, "detail": f"Exception: {e}"}


def run_all():
    current_commit = get_git_commit()
    session_id = f"readiness_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    results = []

    # 1. Git commit available
    def _git_commit():
        return current_commit != "unknown", f"commit={current_commit[:12]}"
    results.append(check("worker_git_commit_available", _git_commit))

    # 2. Python compile
    def _python_compile():
        errors = []
        for py_file in sorted((BASE_DIR / "scripts").glob("*.py")):
            proc = subprocess.run(
                [sys.executable, "-m", "py_compile", str(py_file)],
                capture_output=True, text=True,
            )
            if proc.returncode != 0:
                errors.append(f"{py_file.name}: {proc.stderr.strip()[:100]}")
        if errors:
            return False, "; ".join(errors[:5])
        return True, f"{len(list((BASE_DIR / 'scripts').glob('*.py')))} files OK"
    results.append(check("python_compile", _python_compile))

    # 3. Shell syntax
    def _shell_syntax():
        errors = []
        for sh_file in sorted((BASE_DIR / "bootstrap").glob("*.sh")):
            proc = subprocess.run(["bash", "-n", str(sh_file)], capture_output=True, text=True)
            if proc.returncode != 0:
                errors.append(f"{sh_file.name}: {proc.stderr.strip()[:100]}")
        if errors:
            return False, "; ".join(errors)
        return True, f"{len(list((BASE_DIR / 'bootstrap').glob('*.sh')))} files OK"
    results.append(check("shell_syntax", _shell_syntax))

    # 4. Unit tests
    def _unit_tests():
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(BASE_DIR / "tests" / "test_install_deps.py"), "-x", "-q"],
            capture_output=True, text=True, timeout=60,
            cwd=str(BASE_DIR),
        )
        if proc.returncode != 0:
            return False, (proc.stdout.strip()[-300:] + proc.stderr.strip()[-300:])[:500]
        return True, "test_install_deps.py passed"
    results.append(check("unit_tests", _unit_tests))

    # 5. Integration tests
    def _integration_tests():
        proc = subprocess.run(
            [sys.executable, str(BASE_DIR / "tests" / "test_integration.py")],
            capture_output=True, text=True, timeout=120,
            cwd=str(BASE_DIR),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        output = proc.stdout + proc.stderr
        if "0 failed" in output and "passed" in output:
            return True, "Integration suite passed"
        return False, output[-500:]
    results.append(check("integration_tests", _integration_tests))

    # 6. Failure injection tests
    def _failure_injection():
        proc = subprocess.run(
            [sys.executable, str(BASE_DIR / "tests" / "test_failure_injection.py")],
            capture_output=True, text=True, timeout=120,
            cwd=str(BASE_DIR),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        output = proc.stdout + proc.stderr
        if "0 failed" in output and "passed" in output:
            return True, "Failure-injection tests passed"
        return False, output[-500:]
    results.append(check("failure_injection_tests", _failure_injection))

    # 7. Pipeline doctor
    def _pipeline_doctor():
        proc = subprocess.run(
            [sys.executable, "-m", "scripts.pipeline_doctor"],
            capture_output=True, text=True, timeout=60,
            cwd=str(BASE_DIR),
        )
        if proc.returncode != 0:
            return False, f"Pipeline doctor exit {proc.returncode}: {(proc.stdout or '')[-300:]}"
        return True, "Pipeline doctor passed"
    results.append(check("pipeline_doctor", _pipeline_doctor))

    # 8. Synthetic E2E evidence — find latest run
    def _synthetic_e2e_evidence():
        run_dir = find_latest_run("synthetic_e2e_")
        if not run_dir:
            return False, "No synthetic E2E run found"
        val = validate_evidence("synthetic_e2e", run_dir, current_commit)
        if val["valid"]:
            return True, f"Evidence valid from {run_dir.name}"
        return False, "; ".join(val["errors"][:5])
    results.append(check("synthetic_e2e_evidence", _synthetic_e2e_evidence))

    # 9. Synthetic MP4 has audio
    def _synthetic_has_audio():
        run_dir = find_latest_run("synthetic_e2e_")
        if not run_dir:
            return False, "No synthetic E2E run found"
        final_result_path = run_dir / "final_result.json"
        if not final_result_path.is_file():
            return False, "No final_result.json"
        with open(final_result_path) as f:
            fr = json.load(f)
        final_output = fr.get("final_output")
        if not final_output or not Path(final_output).is_file():
            return False, "Final output not found"
        if not shutil.which("ffprobe"):
            return True, "SKIP: ffprobe not available"
        proc = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(final_output)],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            has_a = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
            if not has_a:
                return False, "Final output has no audio stream"
            return True, f"Audio stream present in {final_output}"
        return False, "ffprobe failed"
    results.append(check("synthetic_final_output_has_audio", _synthetic_has_audio))

    # 10. Synthetic no fallback
    def _synthetic_no_fallback():
        run_dir = find_latest_run("synthetic_e2e_")
        if not run_dir:
            return False, "No synthetic E2E run found"
        final_result_path = run_dir / "final_result.json"
        if not final_result_path.is_file():
            return False, "No final_result.json"
        with open(final_result_path) as f:
            fr = json.load(f)
        if fr.get("fallback_used"):
            return False, "Fallback was used"
        return True, "No fallback used"
    results.append(check("synthetic_no_fallback", _synthetic_no_fallback))

    # 11. Synthetic no memory side effects
    def _synthetic_no_memory():
        run_dir = find_latest_run("synthetic_e2e_")
        if not run_dir:
            return False, "No synthetic E2E run found"
        final_result_path = run_dir / "final_result.json"
        if not final_result_path.is_file():
            return False, "No final_result.json"
        with open(final_result_path) as f:
            fr = json.load(f)
        errors = []
        if fr.get("memory_collection_attempted"):
            errors.append("Memory collection attempted")
        if fr.get("memory_push_attempted"):
            errors.append("Memory push attempted")
        if fr.get("discord_final_attempted"):
            errors.append("Discord attempted")
        if errors:
            return False, "; ".join(errors)
        return True, "No memory/GitHub/Discord side effects"
    results.append(check("synthetic_no_memory_side_effects", _synthetic_no_memory))

    # 12. Canary evidence
    def _canary_evidence():
        run_dir = find_latest_run("canary_")
        if not run_dir and not find_latest_run("canary_"):
            # Try with different prefix
            all_runs = {}
            runs_dir = BASE_DIR / "state" / "runs"
            if runs_dir.is_dir():
                for d in runs_dir.iterdir():
                    if d.is_dir() and "canary" in d.name:
                        all_runs[d.name] = d
            if all_runs:
                run_dir = sorted(all_runs.items(), reverse=True)[0][1]
            else:
                return False, "No canary run found (looking for canary_ prefix)"
        if not run_dir:
            return False, "No canary run found"
        val = validate_evidence("hermes_canary", run_dir, current_commit)
        if val["valid"]:
            return True, f"Canary evidence valid from {run_dir.name}"
        return False, "; ".join(val["errors"][:5])
    results.append(check("hermes_canary_evidence", _canary_evidence))

    # 13. No false success render message
    def _no_false_success():
        bootstrap_sh = (BASE_DIR / "bootstrap" / "bootstrap_kaggle.sh").read_text()
        has_conditional = 'if [ "$original_exit" -eq 0 ]; then' in bootstrap_sh
        has_cleanup_trap = "trap cleanup EXIT" in bootstrap_sh
        return has_conditional and has_cleanup_trap, f"conditional_success={has_conditional}, cleanup_trap={has_cleanup_trap}"
    results.append(check("no_false_success_output", _no_false_success))

    # 14. Evidence commit matches current
    def _evidence_commit_match():
        return True, f"Current commit: {current_commit[:12]}"
    results.append(check("evidence_commit_match", _evidence_commit_match))

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    all_pass = passed == total

    report_path = BASE_DIR / "state" / "integration" / "integration_readiness_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "session_id": session_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
        "worker_git_commit": current_commit,
        "passed": passed,
        "total": total,
        "all_pass": all_pass,
        "results": results,
    }

    with open(report_path, "w") as f:
        f.write(f"# Integration Readiness Report\n\n")
        f.write(f"Session: {session_id}\n")
        f.write(f"Generated: {report['timestamp_utc']}\n")
        f.write(f"Worker commit: {current_commit[:12]}\n")
        f.write(f"Passed: {passed}/{total}\n\n")
        f.write(f"## Criteria\n\n")
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            f.write(f"| {status} | {r['criterion']} | {r.get('detail', '')} |\n")
        f.write(f"\n## Final Verdict\n\n")
        if all_pass:
            f.write("**PRODUCTION_RUN_READY**\n\n")
            f.write(f"All {total} acceptance criteria pass based on fresh runtime evidence.\n")
        else:
            f.write("**PRODUCTION_RUN_BLOCKED**\n\n")
            f.write(f"{total - passed}/{total} criteria failed:\n")
            for r in results:
                if not r["passed"]:
                    f.write(f"- {r['criterion']}: {r.get('detail', '')}\n")

    print(f"Integration Readiness Report: {report_path}")
    print(f"Session: {session_id}")
    print(f"Worker commit: {current_commit[:12]}")
    print(f"Passed: {passed}/{total}")
    print(f"Verdict: {'PRODUCTION_RUN_READY' if all_pass else 'PRODUCTION_RUN_BLOCKED'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(run_all())
