#!/usr/bin/env python3
"""Standalone Hermes Artifact Canary.

Runs a single minimal Hermes AIAgent turn to prove:
  - pinned Hermes-Agent repo is available and importable
  - all 23 V7 skills are officially loadable
  - one real NVIDIA model turn produces a valid match_fact_lock.json
  - session/trace evidence is written
  - total runtime < 120 seconds

Usage:
    python3 -m scripts.hermes_artifact_canary

This is the only command that should be invoked for canary certification.
It does NOT run pipeline doctor, synthetic E2E, OpenMontage, downloads,
memory, GitHub push, or Discord notifications.
"""
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(BASE_DIR))
import scripts.artifact_contracts as ac
from scripts.hermes_runtime import run_hermes_turn, _phase_log, _discover_v7_skills
from scripts.hermes_runtime import _check_venv_hermes_import, _prepare_and_query_skills
from scripts.hermes_runtime import _validate_match_fact_lock, _extract_and_validate_artifacts
from scripts.hermes_runtime import _MATCH_FACT_LOCK_SCHEMA

EXPECTED_V7_SKILL_COUNT = 23
ACTIVE_CANARY_SKILLS = [
    "football-match-identification",
    "football-fact-provenance-gate",
]
CANARY_TIMEOUT_SECONDS = 120

FACT_PACKET = {
    "competition": "2014 FIFA World Cup",
    "match_date": "2014-07-13",
    "team_a": "Germany",
    "team_b": "Argentina",
    "score": "1-0",
    "stage_or_round": "Final",
    "venue": "Estádio do Maracanã, Rio de Janeiro",
    "verification_status": "verified",
    "confidence": "high",
    "key_events": [
        "Mario Götze scored in the 113th minute",
        "Bastian Schweinsteiger was named Man of the Match",
        "Germany's fourth World Cup title",
    ],
    "evidence_sources": [
        "FIFA official match report",
        "BBC Sport match report",
    ],
    "evidence_claims": [
        "Germany defeated Argentina 1-0 in the 2014 World Cup Final",
        "Mario Götze scored the only goal in extra time",
    ],
}


def _get_git_commit() -> str:
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


def _check_runtime_endpoint() -> dict:
    """Verify runtime endpoint env vars are set."""
    result = {"endpoint_configured": False, "missing": []}
    for var in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        if not os.environ.get(var, "").strip():
            result["missing"].append(var)
    result["endpoint_configured"] = len(result["missing"]) == 0
    return result


def _check_skills_visibility() -> dict:
    """Verify all 23 V7 skills are visible to the official Hermes loader."""
    result = {
        "v7_filesystem_count": 0,
        "v7_filesystem_skill_names": [],
        "hermes_loaded_count": 0,
        "hermes_loaded_skill_names": [],
        "all_23_visible": False,
        "active_canary_skills_visible": False,
    }
    v7 = _discover_v7_skills()
    result["v7_filesystem_count"] = v7.get("v7_skill_count", 0)
    result["v7_filesystem_skill_names"] = v7.get("v7_skill_names", [])

    loaded = _prepare_and_query_skills()
    result["hermes_loaded_count"] = loaded.get("hermes_loaded_skill_count", 0)
    result["hermes_loaded_skill_names"] = loaded.get("hermes_loaded_skill_names", [])
    result["all_23_visible"] = result["hermes_loaded_count"] >= EXPECTED_V7_SKILL_COUNT
    loaded_names = set(result["hermes_loaded_skill_names"])
    result["active_canary_skills_visible"] = all(
        s in loaded_names for s in ACTIVE_CANARY_SKILLS
    )
    return result


def _detect_disallowed_calls(stderr_text: str) -> list:
    """Detect if the canary attempted any disallowed operations."""
    violations = []
    disallowed_patterns = {
        "web_search": "web_search",
        "web_extract": "web_extract",
        "download": "download",
        "terminal": "terminal",
        "memory": "memory",
        "render": "render",
        "openmontage": "openmontage",
        "discord": "discord",
        "github": "github",
        "push": "push",
    }
    stderr_lower = stderr_text.lower()
    for name, pattern in disallowed_patterns.items():
        if pattern in stderr_lower:
            violations.append(name)
    return violations


def main() -> int:
    start_ts = time.time()

    print("=" * 60, flush=True)
    print("  HERMES ARTIFACT CANARY", flush=True)
    print("=" * 60, flush=True)

    _phase_log("checking runtime endpoint")
    endpoint_check = _check_runtime_endpoint()
    if not endpoint_check["endpoint_configured"]:
        print(f"FAIL: Missing endpoint vars: {endpoint_check['missing']}", flush=True)
        return 1
    print(f"  endpoint: configured ({endpoint_check['endpoint_configured']})", flush=True)

    _phase_log("checking Hermes venv import")
    venv_check = _check_venv_hermes_import()
    if not venv_check.get("aiagent_importable"):
        print(f"FAIL: AIAgent not importable: {venv_check.get('import_error')}", flush=True)
        return 1
    print(f"  AIAgent importable: True", flush=True)

    _phase_log("verifying 23-skill visibility")
    skills_check = _check_skills_visibility()
    print(f"  V7 filesystem count: {skills_check['v7_filesystem_count']}", flush=True)
    print(f"  Hermes-loaded count: {skills_check['hermes_loaded_count']}", flush=True)
    if not skills_check["all_23_visible"]:
        print(f"FAIL: Not all 23 skills loaded. Loaded: {skills_check['hermes_loaded_count']}", flush=True)
        return 1
    print(f"  All 23 skills visible: True", flush=True)
    if not skills_check["active_canary_skills_visible"]:
        print(f"FAIL: Active canary skills not visible to Hermes loader", flush=True)
        return 1
    print(f"  Active canary skills visible: {skills_check['active_canary_skills_visible']}", flush=True)

    _phase_log("executing minimal Hermes conversation turn")
    run_id = "canary_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = BASE_DIR / "state" / "runs" / run_id

    turn_result = run_hermes_turn(
        title="Historical Fact Verification — 2014 World Cup Final",
        theme="Germany vs Argentina, 2014 FIFA World Cup Final, July 13 2014, 1-0",
        run_id=run_id,
        run_dir=run_dir,
        canary_mode=True,
        canary_fact_packet=FACT_PACKET,
    )

    elapsed = time.time() - start_ts
    print(f"  Turn runtime: {turn_result.get('runtime_seconds', 0)}s", flush=True)
    print(f"  Total elapsed: {elapsed:.1f}s", flush=True)

    if not turn_result.get("success"):
        err_type = turn_result.get("error_type", "unknown")
        err_msg = turn_result.get("error_message", "")
        phase = turn_result.get("phase", "")
        print(f"FAIL: Hermes turn failed ({err_type})", flush=True)
        print(f"  Phase: {phase}", flush=True)
        print(f"  Error: {err_msg[:500]}", flush=True)
        return 1

    print(f"  Conversation executed: {turn_result.get('conversation_executed')}", flush=True)
    print(f"  Response nonempty: {turn_result.get('response_nonempty')}", flush=True)
    print(f"  Session/trace exists: {turn_result.get('session_or_trace_exists')}", flush=True)

    child_stderr = turn_result.get("details", {}).get("child_stderr", "")
    violations = _detect_disallowed_calls(child_stderr)
    if violations:
        print(f"FAIL: Disallowed operations detected in canary: {violations}", flush=True)
        return 1

    _phase_log("validating match_fact_lock.json")
    session_dir = run_dir / "hermes_artifacts"
    match_fact_path = session_dir / "match_fact_lock.json"

    if not match_fact_path.is_file():
        print(f"FAIL: match_fact_lock.json not found at {match_fact_path}", flush=True)
        return 1
    print(f"  match_fact_lock.json: EXISTS", flush=True)

    try:
        match_fact = json.loads(match_fact_path.read_text())
    except (json.JSONDecodeError, ValueError) as e:
        print(f"FAIL: match_fact_lock.json is invalid JSON: {e}", flush=True)
        return 1

    validation_errors = _validate_match_fact_lock(match_fact)
    if validation_errors:
        print(f"FAIL: match_fact_lock schema invalid:", flush=True)
        for err in validation_errors:
            print(f"  - {err}", flush=True)
        return 1
    print(f"  Schema valid: True", flush=True)

    vs = match_fact.get("verification_status", "")
    if vs != "verified":
        print(f"FAIL: verification_status='{vs}' (expected 'verified')", flush=True)
        return 1
    print(f"  verification_status: {vs}", flush=True)
    print(f"  Match: {match_fact.get('team_a')} vs {match_fact.get('team_b')}", flush=True)

    # Canary-specific provenance field verification
    extraction_method = match_fact.get("extraction_method", "")
    expected_method = "canary_deterministic_fact_packet_after_hermes_attestation"
    if extraction_method != expected_method:
        print(f"FAIL: extraction_method='{extraction_method}' (expected '{expected_method}')", flush=True)
        return 1
    print(f"  extraction_method: {extraction_method}", flush=True)

    if match_fact.get("canary_only") is not True:
        print(f"FAIL: canary_only flag must be true", flush=True)
        return 1
    print(f"  canary_only: True", flush=True)

    if match_fact.get("production_fallback_used") is not False:
        print(f"FAIL: production_fallback_used must be false", flush=True)
        return 1
    print(f"  production_fallback_used: False", flush=True)

    hermes_response_sha256 = match_fact.get("hermes_response_sha256", "")
    if not hermes_response_sha256:
        print(f"FAIL: hermes_response_sha256 is missing", flush=True)
        return 1
    print(f"  hermes_response_sha256: {hermes_response_sha256[:16]}...", flush=True)

    fact_packet_sha256 = match_fact.get("fact_packet_sha256", "")
    if not fact_packet_sha256:
        print(f"FAIL: fact_packet_sha256 is missing", flush=True)
        return 1
    print(f"  fact_packet_sha256: {fact_packet_sha256[:16]}...", flush=True)

    provenance_checks = [
        ("match", "Germany vs Argentina"),
        ("competition", "2014 FIFA World Cup Final"),
        ("match_date", "2014-07-13"),
        ("score", "Germany 1-0 Argentina"),
        ("decisive_goal", "Mario Götze, 113'"),
        ("source_mode", "stable_canary_fact_packet"),
    ]
    for field, expected in provenance_checks:
        actual = match_fact.get(field, "")
        if actual != expected:
            print(f"FAIL: {field}='{actual}' (expected '{expected}')", flush=True)
            return 1
        print(f"  {field}: {actual}", flush=True)

    if match_fact.get("hermes_attestation_required") is not True:
        print(f"FAIL: hermes_attestation_required must be true", flush=True)
        return 1
    print(f"  hermes_attestation_required: True", flush=True)

    if elapsed > CANARY_TIMEOUT_SECONDS:
        print(f"FAIL: Canary exceeded {CANARY_TIMEOUT_SECONDS}s timeout ({elapsed:.1f}s)", flush=True)
        return 1

    print(f"  Total runtime: {elapsed:.1f}s (limit: {CANARY_TIMEOUT_SECONDS}s)", flush=True)

    print("=" * 60, flush=True)
    print("  CANARY PASSED", flush=True)
    print("=" * 60, flush=True)

    report = {
        "canary_pass": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
        "runtime_seconds": round(elapsed, 1),
        "git_commit": _get_git_commit(),
        "aiagent_importable": turn_result.get("aiagent_importable"),
        "v7_skill_count": skills_check["v7_filesystem_count"],
        "hermes_loaded_skill_count": skills_check["hermes_loaded_count"],
        "conversation_executed": turn_result.get("conversation_executed"),
        "response_nonempty": turn_result.get("response_nonempty"),
        "session_or_trace_exists": turn_result.get("session_or_trace_exists"),
        "match_fact_lock_exists": match_fact_path.is_file(),
        "schema_valid": len(validation_errors) == 0,
        "verification_status": vs,
        "match_summary": f"{match_fact.get('team_a')} vs {match_fact.get('team_b')}",
        "run_id": run_id,
        "run_dir": str(run_dir),
        "match_fact_lock_path": str(match_fact_path),
        "violations": violations,
        "extraction_method": match_fact.get("extraction_method"),
        "canary_only": match_fact.get("canary_only"),
        "production_fallback_used": match_fact.get("production_fallback_used"),
        "hermes_response_sha256": match_fact.get("hermes_response_sha256"),
        "fact_packet_sha256": match_fact.get("fact_packet_sha256"),
        "match": match_fact.get("match"),
        "competition": match_fact.get("competition"),
        "decisive_goal": match_fact.get("decisive_goal"),
        "source_mode": match_fact.get("source_mode"),
        "hermes_attestation_required": match_fact.get("hermes_attestation_required"),
    }

    report_path = run_dir / "canary_report.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    ac.atomic_write_json(report_path, report)

    md_path = run_dir / "canary_report.md"
    with open(md_path, "w") as f:
        f.write(f"# Hermes Artifact Canary Report\n\n")
        f.write(f"Timestamp: {report['timestamp_utc']}\n")
        f.write(f"Runtime: {report['runtime_seconds']}s\n")
        f.write(f"Result: PASS\n\n")
        for k, v in report.items():
            f.write(f"- {k}: {v}\n")

    print(f"Canary report: {report_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
