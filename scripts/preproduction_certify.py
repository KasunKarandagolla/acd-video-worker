#!/usr/bin/env python3
"""Pre-production certification — single-command cert runner.

Modes:
  --local   Offline certification (no Hermes, no secrets, no network)
  --runtime Full certification for Kaggle (requires LLM secrets)

Execution order (stop on first failure):
  1. pipeline_doctor
  2. synthetic_e2e (local) — offline pipeline with synthetic media
  3. validate synthetic evidence (ffprobe, OpenMontage, QA)
  4. Hermes artifact canary (runtime only)
  5. validate canary evidence (runtime only)
  6. generate readiness report (runtime only)

Every step writes complete evidence to:
  state/runs/<cert_id>/steps/<step_name>/
    command.json
    stdout.log
    stderr.log
    result.json

Console failure summary includes at least the final 80 lines of stdout/stderr.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _require_mode():
    parser = argparse.ArgumentParser(
        description="Pre-production certification for acd-video-worker."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--local", action="store_true", help="Offline certification (no Hermes, no secrets)")
    group.add_argument("--runtime", action="store_true", help="Full Kaggle certification (requires LLM secrets)")
    args, _ = parser.parse_known_args()
    return args


def _runtime_preflight() -> list[str]:
    """Validate runtime environment before any expensive stage.

    Returns list of missing variable names (empty = all present).
    Does NOT print variable values.
    """
    required = ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"]
    missing = []
    for var in required:
        val = os.environ.get(var, "").strip()
        if not val:
            missing.append(var)
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg (not in PATH)")
    if not shutil.which("ffprobe"):
        missing.append("ffprobe (not in PATH)")
    pinned = BASE_DIR / "locks" / "pinned_versions.json"
    if not pinned.is_file():
        missing.append("locks/pinned_versions.json")
    run_dir = BASE_DIR / "state" / "runs"
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        test_file = run_dir / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
    except OSError:
        missing.append("state/runs/ not writable")
    out_dir = BASE_DIR / "outputs"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        test_file = out_dir / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
    except OSError:
        missing.append("outputs/ not writable")
    return missing


def _ensure_empty_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _last_n_lines(text: str, n: int = 80) -> str:
    lines = text.splitlines()
    if len(lines) <= n:
        return text
    return "...\n" + "\n".join(lines[-n:])


def _ffprobe_streams(path: Path) -> dict:
    """Return ffprobe JSON for a media file, or error dict."""
    result = {"valid": False, "streams": [], "format": {}, "error": None}
    if not path or not path.is_file():
        result["error"] = "File not found"
        return result
    if not shutil.which("ffprobe"):
        result["error"] = "ffprobe not available"
        return result
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            result["valid"] = True
            result["streams"] = data.get("streams", [])
            result["format"] = data.get("format", {})
        else:
            result["error"] = f"ffprobe exit {proc.returncode}: {proc.stderr[:200]}"
    except Exception as e:
        result["error"] = str(e)
    return result


def run_step(
    label: str,
    cmd: list,
    *,
    step_dir: Path,
    cwd: str = None,
    env: dict = None,
    timeout: int = 600,
    expected_evidence: list = None,
) -> dict:
    """Execute a certification step and write complete evidence.

    Captures command, cwd, start/end timestamps, duration, return code,
    complete stdout, complete stderr, timeout status, exception info,
    and evidence path existence.

    Returns result dict. Never raises (captures all exceptions).
    """
    _ensure_empty_dir(step_dir)
    start_ts = datetime.now(timezone.utc).isoformat() + "Z"
    start_mono = time.monotonic()

    command_info = {
        "label": label,
        "command": cmd,
        "cwd": cwd or str(BASE_DIR),
        "env_keys": sorted(env.keys()) if env else ["inherit"],
        "timeout": timeout,
        "started_at": start_ts,
    }
    _write_json(step_dir / "command.json", command_info)

    result = {
        "label": label,
        "passed": False,
        "exit_code": None,
        "duration_s": None,
        "timed_out": False,
        "exception": None,
        "traceback": None,
        "stdout_path": str(step_dir / "stdout.log"),
        "stderr_path": str(step_dir / "stderr.log"),
        "expected_evidence": {},
    }

    proc = None
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or str(BASE_DIR),
            env=env,
        )
        result["exit_code"] = proc.returncode
    except subprocess.TimeoutExpired as e:
        result["exit_code"] = -1
        result["timed_out"] = True
        result["exception"] = f"TimedOutExpired after {timeout}s"
        proc = e
    except Exception as e:
        result["exit_code"] = -1
        result["exception"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc()

    end_ts = datetime.now(timezone.utc).isoformat() + "Z"
    result["duration_s"] = round(time.monotonic() - start_mono, 3)
    result["finished_at"] = end_ts

    stdout_text = (proc.stdout or "") if proc else ""
    stderr_text = (proc.stderr or "") if proc else ""

    (step_dir / "stdout.log").write_text(stdout_text)
    (step_dir / "stderr.log").write_text(stderr_text)

    if result["exit_code"] == 0:
        result["passed"] = True
    elif result["timed_out"]:
        result["error"] = f"Timed out after {timeout}s"
    elif result["exception"]:
        result["error"] = result["exception"]
    else:
        last_stderr = _last_n_lines(stderr_text, 40)
        last_stdout = _last_n_lines(stdout_text, 40)
        result["error"] = (
            f"Exit code {result['exit_code']}:\n"
            f"  Last stdout ({len(stdout_text)} chars):\n{last_stdout}\n"
            f"  Last stderr ({len(stderr_text)} chars):\n{last_stderr}"
        )

    expected_evidence = expected_evidence or []
    ev_map = {}
    for ev_path_str in expected_evidence:
        ev_path = Path(ev_path_str)
        ev_map[ev_path_str] = ev_path.is_file()
    result["expected_evidence"] = ev_map
    if expected_evidence:
        all_found = all(ev_map.values())
        missing_ev = [p for p, found in ev_map.items() if not found]
        if not all_found:
            result["evidence_missing"] = missing_ev

    _write_json(step_dir / "result.json", result)

    status = "PASSED" if result["passed"] else "FAILED"
    duration_str = f"{result['duration_s']}s"
    print(f"\n  {status}: {label} ({duration_str})")
    if result.get("error"):
        print(f"    {result['error']}")

    return result


def validate_synthetic_evidence(run_id: str) -> dict:
    """Validate synthetic E2E evidence from the run directory.

    Requires:
      - final_result.json exists
      - video_compose was invoked
      - compose returned success
      - OpenMontage success
      - pipeline success
      - final success
      - QA passed
      - fallback not used
      - final output has video + audio streams
      - duration > 0
      - no memory collection/push
      - no Discord in synthetic mode
    """
    result = {"passed": False, "checks": [], "evidence_paths": []}
    run_dir = BASE_DIR / "state" / "runs" / run_id
    outputs_dir = BASE_DIR / "outputs" / run_id

    if not run_dir.is_dir():
        result["error"] = f"Run directory not found: {run_dir}"
        return result

    final_result_path = run_dir / "final_result.json"
    if not final_result_path.is_file():
        result["error"] = "final_result.json not found"
        return result
    result["evidence_paths"].append(str(final_result_path))
    with open(final_result_path) as f:
        fr = json.load(f)

    checks = []

    has_video_compose = fr.get("compose_tool_invoked", False)
    checks.append({"check": "video_compose_invoked", "passed": has_video_compose})
    if not has_video_compose:
        result["error"] = "video_compose was not invoked"
        return result

    compose_returned = fr.get("compose_tool_returned_success", False)
    checks.append({"check": "compose_tool_returned_success", "passed": compose_returned})
    if not compose_returned:
        result["error"] = "video_compose did not return success"
        return result

    om_success = fr.get("openmontage_success", False)
    checks.append({"check": "openmontage_success", "passed": om_success})
    if not om_success:
        result["error"] = "openmontage_success is false"
        return result

    pipeline_success = fr.get("pipeline_success", False)
    checks.append({"check": "pipeline_success", "passed": pipeline_success})

    final_success = fr.get("final_success", False)
    checks.append({"check": "final_success", "passed": final_success})

    qa_passed = fr.get("qa_passed", False)
    checks.append({"check": "qa_passed", "passed": qa_passed})
    if not qa_passed:
        result["error"] = "QA failed"
        return result

    fallback_used = fr.get("fallback_used", True)
    checks.append({"check": "fallback_not_used", "passed": not fallback_used})
    if fallback_used:
        result["error"] = "Fallback was used"
        return result

    final_output = fr.get("final_output")
    checks.append(
        {
            "check": "final_output_exists",
            "passed": final_output is not None
            and Path(final_output).is_file()
            and Path(final_output).stat().st_size > 0,
        }
    )
    if not checks[-1]["passed"]:
        result["error"] = "Final output missing or empty"
        return result

    if final_output and Path(final_output).is_file():
        probe = _ffprobe_streams(Path(final_output))
        has_v = any(s.get("codec_type") == "video" for s in probe.get("streams", []))
        has_a = any(s.get("codec_type") == "audio" for s in probe.get("streams", []))
        checks.append({"check": "final_output_has_video", "passed": has_v})
        checks.append({"check": "final_output_has_audio", "passed": has_a})
        if not has_v:
            result["error"] = "Final output has no video stream"
            return result
        if not has_a:
            result["error"] = "Final output has no audio stream"
            return result
        dur = 0
        fmt = probe.get("format", {})
        if fmt.get("duration"):
            dur = float(fmt["duration"])
        checks.append({"check": "final_output_duration_positive", "passed": dur > 0})

    mem_collected = fr.get("memory_collection_attempted", True)
    checks.append({"check": "memory_not_collected_in_synthetic", "passed": not mem_collected})
    if mem_collected:
        result["error"] = "Memory was collected in synthetic mode"
        return result

    mem_pushed = fr.get("memory_push_attempted", True)
    checks.append({"check": "memory_not_pushed_in_synthetic", "passed": not mem_pushed})
    if mem_pushed:
        result["error"] = "Memory was pushed in synthetic mode"
        return result

    discord_sent = fr.get("discord_final_attempted", True)
    checks.append({"check": "discord_not_sent_in_synthetic", "passed": not discord_sent})
    if discord_sent:
        result["error"] = "Discord notification was sent in synthetic mode"
        return result

    result["checks"] = checks
    result["passed"] = all(c["passed"] for c in checks)
    return result


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


def validate_canary_evidence(cert_start: datetime) -> dict:
    """Validate Hermes artifact canary evidence from standalone canary.

    Locates the newest canary_* run directory, reads canary_report.json,
    and validates the full evidence contract.

    Rejects:
    - stale reports (timestamp before certification start)
    - foreign Git commit reports
    - incomplete or failed canary
    """
    result = {"passed": False, "checks": [], "evidence_paths": []}
    current_commit = get_git_commit()

    run_dir = find_latest_run("canary_")
    if not run_dir:
        result["error"] = "No canary run directory found (looking for canary_* in state/runs/)"
        return result

    report_path = run_dir / "canary_report.json"
    if not report_path.is_file():
        result["error"] = f"canary_report.json not found in {run_dir}"
        result["evidence_paths"].append(str(report_path))
        return result
    result["evidence_paths"].append(str(report_path))

    try:
        with open(report_path) as f:
            report = json.load(f)
    except Exception as e:
        result["error"] = f"Cannot parse canary_report.json: {e}"
        return result

    checks = []

    # Timestamp check — must be after certification session started
    report_ts_str = report.get("timestamp_utc", "")
    try:
        import re as _re
        ts = report_ts_str
        if ts.endswith("Z"):
            ts = ts[:-1]
        if not _re.search(r'[+-]\d{2}:\d{2}(:\d{2})?$', ts) and "T" in ts:
            ts += "+00:00"
        report_ts = datetime.fromisoformat(ts)
        report_during_session = report_ts >= cert_start
    except (ValueError, AttributeError, TypeError):
        report_during_session = False
    checks.append({"check": "report_created_during_session", "passed": report_during_session})

    # Git commit check — must match current worker commit
    report_commit = report.get("git_commit", "")
    commit_matches = current_commit != "unknown" and report_commit == current_commit
    checks.append({"check": "report_git_commit_matches", "passed": commit_matches})

    # Contract field checks from the standalone canary report
    checks.append({"check": "success", "passed": report.get("canary_pass", False) is True})
    checks.append({"check": "aiagent_importable", "passed": report.get("aiagent_importable", False) is True})
    checks.append({"check": "hermes_loaded_skill_count_23", "passed": report.get("hermes_loaded_skill_count", 0) >= 23})
    checks.append({"check": "conversation_executed", "passed": report.get("conversation_executed", False) is True})
    checks.append({"check": "response_nonempty", "passed": report.get("response_nonempty", False) is True})
    checks.append({"check": "session_or_trace_exists", "passed": report.get("session_or_trace_exists", False) is True})
    checks.append({"check": "schema_valid", "passed": report.get("schema_valid", False) is True})
    checks.append({"check": "verification_status_verified", "passed": report.get("verification_status") == "verified"})
    checks.append({"check": "total_runtime_seconds_under_120", "passed": report.get("runtime_seconds", 999) < 120})

    mf_lock_path = report.get("match_fact_lock_path")
    if mf_lock_path and Path(mf_lock_path).is_file():
        result["evidence_paths"].append(mf_lock_path)
        try:
            mf_data = json.loads(Path(mf_lock_path).read_text())
            extraction_method = mf_data.get("extraction_method", "")
            is_canary_deterministic = extraction_method == "canary_deterministic_fact_packet_after_hermes_attestation"
            checks.append({"check": "extraction_method_canary_deterministic", "passed": is_canary_deterministic})
            checks.append({"check": "canary_only_true", "passed": mf_data.get("canary_only") is True})
            checks.append({"check": "production_fallback_not_used", "passed": mf_data.get("production_fallback_used") is False})
            checks.append({"check": "hermes_response_sha256_present", "passed": bool(mf_data.get("hermes_response_sha256"))})
            checks.append({"check": "fact_packet_sha256_present", "passed": bool(mf_data.get("fact_packet_sha256"))})
        except Exception:
            checks.append({"check": "match_fact_lock_readable", "passed": False})

    result["checks"] = checks
    result["passed"] = all(c["passed"] for c in checks)
    if not result["passed"]:
        failed = [c["check"] for c in checks if not c["passed"]]
        result["error"] = f"Canary evidence checks failed: {failed}"

    return result


def _print_exit_banner(success: bool, stage: str = None):
    print(f"\n{'='*60}")
    if success:
        print("  PREPRODUCTION_CERTIFICATION_PASSED")
    else:
        print("  PREPRODUCTION_CERTIFICATION_FAILED")
        print(f"  PRODUCTION_RUN_BLOCKED (stopped at: {stage})")
    print(f"{'='*60}")


def main():
    args = _require_mode()
    is_local = args.local
    is_runtime = args.runtime

    print(f"{'='*60}")
    print(f"  ACD VIDEO WORKER — PRE-PRODUCTION CERTIFICATION")
    print(f"  Mode: {'LOCAL (offline)' if is_local else 'RUNTIME (Kaggle)'}")
    print(f"  Started: {datetime.now(timezone.utc).isoformat()}Z")
    print(f"{'='*60}")

    if is_runtime:
        print("\n  [PREFLIGHT] Checking runtime environment...")
        missing = _runtime_preflight()
        if missing:
            print(f"  FAILED: runtime_environment_missing")
            for m in missing:
                print(f"    Missing: {m}")
            print()
            _print_exit_banner(False, "runtime_preflight")
            return 1
        print("  Runtime preflight: PASSED")

    cert_start = datetime.now(timezone.utc)
    cert_id = f"cert_{cert_start.strftime('%Y%m%d_%H%M%S')}"
    cert_dir = BASE_DIR / "state" / "runs" / cert_id
    cert_dir.mkdir(parents=True, exist_ok=True)
    steps_dir = cert_dir / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1: pipeline_doctor
    # ------------------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"  STEP 1/6: pipeline_doctor")
    print(f"{'='*60}")
    s1 = run_step(
        "pipeline_doctor",
        [sys.executable, "-m", "scripts.pipeline_doctor"],
        step_dir=steps_dir / "pipeline_doctor",
        timeout=120,
    )
    if not s1["passed"]:
        print()
        _print_exit_banner(False, "pipeline_doctor")
        return 1

    # ------------------------------------------------------------------
    # Step 2: synthetic_e2e
    # ------------------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"  STEP 2/6: synthetic_e2e")
    print(f"{'='*60}")
    syn_run_id = f"synthetic_e2e_{cert_start.strftime('%Y%m%d_%H%M%S')}"
    syn_env = dict(os.environ)
    syn_env["PIPELINE_SYNTHETIC_E2E"] = "1"
    syn_env["HERMES_ARTIFACT_CANARY"] = "0"
    syn_env["HERMES_VALIDATE_ONLY"] = "0"

    job_yaml = str(BASE_DIR / "jobs" / "argentina_hardest_victory.yaml")
    s2 = run_step(
        "synthetic_e2e",
        [sys.executable, "-m", "scripts.run_title_theme_job", job_yaml, "--run-id", syn_run_id],
        step_dir=steps_dir / "synthetic_e2e",
        env=syn_env,
        timeout=600,
    )
    if not s2["passed"]:
        print()
        _print_exit_banner(False, "synthetic_e2e")
        return 1

    # ------------------------------------------------------------------
    # Step 3: validate synthetic evidence
    # ------------------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"  STEP 3/6: validate synthetic evidence")
    print(f"{'='*60}")
    val = validate_synthetic_evidence(syn_run_id)
    s3_step_dir = steps_dir / "validate_synthetic_evidence"
    _ensure_empty_dir(s3_step_dir)
    _write_json(s3_step_dir / "result.json", {
        "label": "validate_synthetic_evidence",
        "passed": val["passed"],
        "checks": val.get("checks", []),
        "evidence_paths": val.get("evidence_paths", []),
        "error": val.get("error"),
    })
    if val["passed"]:
        print(f"\n  PASSED: validate_synthetic_evidence")
    else:
        print(f"\n  FAILED: validate_synthetic_evidence")
        if val.get("error"):
            print(f"    {val['error']}")
        print()
        _print_exit_banner(False, "validate_synthetic_evidence")
        return 1

    # ------------------------------------------------------------------
    # Step 4: Hermes artifact canary (runtime only)
    # ------------------------------------------------------------------
    if is_runtime:
        print(f"\n{'='*60}")
        print(f"  STEP 4/6: hermes_artifact_canary")
        print(f"{'='*60}")
        s4 = run_step(
            "hermes_artifact_canary",
            [sys.executable, "-m", "scripts.hermes_artifact_canary"],
            step_dir=steps_dir / "hermes_artifact_canary",
            timeout=150,
        )
        if not s4["passed"]:
            print()
            _print_exit_banner(False, "hermes_artifact_canary")
            return 1

        # ------------------------------------------------------------------
        # Step 5: validate canary evidence (runtime only)
        # ------------------------------------------------------------------
        print(f"\n{'='*60}")
        print(f"  STEP 5/6: validate canary evidence")
        print(f"{'='*60}")
        canary_val = validate_canary_evidence(cert_start)
        s5_step_dir = steps_dir / "validate_canary_evidence"
        _ensure_empty_dir(s5_step_dir)
        _write_json(s5_step_dir / "result.json", {
            "label": "validate_canary_evidence",
            "passed": canary_val["passed"],
            "checks": canary_val.get("checks", []),
            "evidence_paths": canary_val.get("evidence_paths", []),
            "error": canary_val.get("error"),
        })
        if canary_val["passed"]:
            print(f"\n  PASSED: validate_canary_evidence")
        else:
            print(f"\n  FAILED: validate_canary_evidence")
            if canary_val.get("error"):
                print(f"    {canary_val['error']}")
            print()
            _print_exit_banner(False, "validate_canary_evidence")
            return 1

        # ------------------------------------------------------------------
        # Step 6: generate readiness report (runtime only)
        # ------------------------------------------------------------------
        print(f"\n{'='*60}")
        print(f"  STEP 6/6: generate_readiness_report")
        print(f"{'='*60}")
        s6 = run_step(
            "generate_readiness_report",
            [sys.executable, "-m", "scripts.check_readiness"],
            step_dir=steps_dir / "generate_readiness_report",
            timeout=120,
        )
        if not s6["passed"]:
            print()
            _print_exit_banner(False, "generate_readiness_report")
            return 1

    # ------------------------------------------------------------------
    # Success
    # ------------------------------------------------------------------
    if is_local:
        print(f"\n{'='*60}")
        print(f"  LOCAL_PREPRODUCTION_CHECKS_PASSED")
        print(f"  RUNTIME_CERTIFICATION_REQUIRED")
        print(f"{'='*60}")
        return 0
    else:
        print(f"\n{'='*60}")
        print(f"  PREPRODUCTION_CERTIFICATION_PASSED")
        print(f"  PRODUCTION_RUN_READY")
        print(f"{'='*60}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
