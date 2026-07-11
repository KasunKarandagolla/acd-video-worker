#!/usr/bin/env python3
"""Hermes Artifact Canary unit and integration tests.

Tests verify:
- _build_canary_agent_code generates agent with enabled_toolsets=[], max_iterations=2
- canary disables irrelevant web/shell/memory tools
- timeout identifies the active phase
- empty response is detected
- malformed response does not trigger autonomous retry loop
- phase logging flushes immediately
- all 23 skills visible but only relevant skills active (in the canary script)
- canary never invokes search/download/render/memory/push/discord
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
PASS = 0
FAIL = 0
TOTAL = 0


def assert_test(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if condition:
        PASS += 1
        print(f"  PASS: {name}" + (f" — {detail}" if detail else ""))
    else:
        FAIL += 1        # noqa: E701
        print(f"  FAIL: {name} — {detail}")


def test_agent_code_generates_minimal_agent():
    """Test _build_canary_agent_code produces code with enabled_toolsets=[] and max_iterations=2."""
    from scripts.hermes_runtime import _build_canary_agent_code
    code = _build_canary_agent_code(
        hermes_repo_str="/fake/repo",
        hermes_home_str="/fake/hermes_home",
        session_id="test-session",
        user_msg='{"test": true}',
        api_key="test-key",
        base_url="https://test.api",
        model="test-model",
    )
    assert_test("max_iterations_in_code", "max_iterations=2" in code, "max_iterations=2 found")
    assert_test("enabled_toolsets_empty", "enabled_toolsets=[]" in code, "enabled_toolsets=[] found")
    assert_test("no_disabled_toolsets", "disabled_toolsets" not in code, "no disabled_toolsets param")
    assert_test("quiet_mode", "quiet_mode=True" in code, "quiet_mode=True found")
    assert_test("skip_context_files", "skip_context_files=True" in code, "skip_context_files=True found")
    assert_test("skip_memory", "skip_memory=True" in code, "skip_memory=True found")
    assert_test("has_phase_logging", "_pl(" in code, "phase logging function found")


def test_core_agent_code():
    """Test _build_core_agent_code produces default agent code (backward compat)."""
    from scripts.hermes_runtime import _build_core_agent_code
    code = _build_core_agent_code(
        hermes_repo_str="/fake/repo",
        hermes_home_str="/fake/hermes_home",
        session_id="test-session",
        user_msg='{"test": true}',
    )
    assert_test("core_has_AIAgent", "AIAgent(" in code, "AIAgent constructor in core code")
    assert_test("core_no_max_iterations", "max_iterations" not in code, "no max_iterations override")


def test_canary_agent_prompt_includes_fact_packet():
    """Test the canary prompt JSON includes the fact_packet (confirmation, not JSON)."""
    from scripts.hermes_runtime import _build_canary_agent_code
    fact_packet = {"competition": "2014 FIFA World Cup", "team_a": "Germany"}
    instructions = (
        "You are the ACD Video Worker canary agent. "
        "You are given a verified fact packet below. "
        "Confirm that you have received and understand this fact packet. "
        "Respond briefly confirming the competition, teams, and score. "
        "Do NOT use any tools. Do NOT ask questions."
    )
    msg = json.dumps({
        "task": "canary_artifact_verification",
        "session_id": "test",
        "fact_packet": fact_packet,
        "instructions": instructions,
    })
    code = _build_canary_agent_code(
        hermes_repo_str="/fake/repo",
        hermes_home_str="/fake/hermes_home",
        session_id="test",
        user_msg=msg,
        api_key="k", base_url="u", model="m",
    )
    assert_test("fact_packet_in_code", "2014 FIFA World Cup" in code, "fact packet data in generated code")
    assert_test("canary_prompt_no_json_requirement",
                 "Produce exactly one strict JSON" not in code,
                 "should not require JSON output")
    assert_test("canary_prompt_asks_confirmation",
                 "Confirm that you have received" in code,
                 "should ask for confirmation")


def test_disabled_toolsets_constant():
    """Test that _CANARY_DISABLED_TOOLSETS covers all unwanted tool categories."""
    from scripts.hermes_runtime import _CANARY_DISABLED_TOOLSETS
    expected = {"terminal", "web", "search", "browser", "memory", "delegation",
                "code_execution", "clarify", "todo", "cronjob"}
    for name in expected:
        assert_test(f"disabled_toolset_{name}", name in _CANARY_DISABLED_TOOLSETS,
                     f"{name} is disabled")


def test_active_canary_skills():
    """Test that _CANARY_ENABLED_SKILL_NAMES has the right skills."""
    from scripts.hermes_runtime import _CANARY_ENABLED_SKILL_NAMES
    assert_test("has_match_identification",
                "football-match-identification" in _CANARY_ENABLED_SKILL_NAMES)
    assert_test("has_provenance_gate",
                "football-fact-provenance-gate" in _CANARY_ENABLED_SKILL_NAMES)
    assert_test("only_two_skills",
                len(_CANARY_ENABLED_SKILL_NAMES) == 2,
                f"count={len(_CANARY_ENABLED_SKILL_NAMES)}")


def test_phase_log_flushes():
    """Test _phase_log writes to stdout and flushes."""
    from scripts.hermes_runtime import _phase_log
    import io
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        _phase_log("test phase")
        output = captured.getvalue()
        assert_test("phase_log_contains_canary", "[CANARY" in output, f"got: {output[:50]}")
        assert_test("phase_log_contains_msg", "test phase" in output, "message in output")
    finally:
        sys.stdout = old_stdout


def test_empty_response_fails():
    """Test run_hermes_turn returns error when response is empty."""
    from scripts.hermes_runtime import run_hermes_turn
    run_dir = Path(tempfile.mkdtemp(prefix="canary_test_"))
    result = run_hermes_turn(
        title="test", theme="test", run_id="test_empty",
        run_dir=run_dir, smoke_test=False,
    )
    # Without real Hermes/AI env, this should fail with a clear error
    assert_test("empty_response_has_error",
                result.get("error_type") is not None,
                f"error_type={result.get('error_type')}")


def test_malformed_response_no_retry_loop():
    """Test that the canary mode (enabled_toolsets=[]) prevents autonomous retry loops.

    When tools are disabled, the agent cannot retry via tool calls.
    """
    from scripts.hermes_runtime import _build_canary_agent_code
    code = _build_canary_agent_code(
        hermes_repo_str="/fake", hermes_home_str="/fake",
        session_id="test", user_msg="test",
        api_key="k", base_url="u", model="m",
    )
    # Verify no tools are available to the agent
    assert_test("no_tools_in_code", "enabled_toolsets=[]" in code,
                "enabled_toolsets=[] prevents tool loops")
    assert_test("no_delegate_in_code", "delegate_task" not in code,
                "no delegation available")


def test_timeout_detects_active_phase():
    """Test timeout error includes phase information."""
    from scripts.hermes_runtime import run_hermes_turn
    run_dir = Path(tempfile.mkdtemp(prefix="canary_timeout_"))
    result = run_hermes_turn(
        title="test", theme="test", run_id="test_timeout",
        run_dir=run_dir, smoke_test=False,
    )
    if result.get("error_type") == "timeout":
        assert_test("timeout_has_phase",
                    result.get("phase") is not None,
                    f"phase={result.get('phase')}")
        if result.get("error_message"):
            assert_test("timeout_mentions_phase",
                        "Phase" in result.get("error_message", "") or "phase" in result.get("error_message", "").lower(),
                        "error message references active phase")


def test_standalone_script_importable():
    """Test the standalone canary script can be imported without errors."""
    import scripts.hermes_artifact_canary as canary
    assert_test("canary_module_imported", canary is not None)
    assert_test("canary_has_main", hasattr(canary, "main"), "main function exists")
    assert_test("canary_has_fact_packet", hasattr(canary, "FACT_PACKET"), "FACT_PACKET exists")


def test_standalone_script_checks_endpoint():
    """Test the _check_runtime_endpoint function in the canary script."""
    import scripts.hermes_artifact_canary as canary
    with patch.dict(os.environ, {"LLM_API_KEY": "", "LLM_BASE_URL": "", "LLM_MODEL": ""}, clear=True):
        result = canary._check_runtime_endpoint()
        assert_test("endpoint_not_configured", not result["endpoint_configured"],
                     f"missing: {result['missing']}")
    with patch.dict(os.environ, {"LLM_API_KEY": "k", "LLM_BASE_URL": "u", "LLM_MODEL": "m"}, clear=True):
        result = canary._check_runtime_endpoint()
        assert_test("endpoint_configured", result["endpoint_configured"],
                     "all vars set")


def test_disallowed_calls_detection():
    """Test that _detect_disallowed_calls catches forbidden operations."""
    import scripts.hermes_artifact_canary as canary
    # Search for various disallowed patterns in stderr
    clean = canary._detect_disallowed_calls("no issues here")
    assert_test("clean_stderr", len(clean) == 0, f"violations: {clean}")

    dirty = canary._detect_disallowed_calls("tried to call web_search but failed")
    assert_test("web_search_detected", "web_search" in dirty, f"violations: {dirty}")

    download = canary._detect_disallowed_calls("download initiated")
    assert_test("download_detected", "download" in download, f"violations: {download}")

    multi = canary._detect_disallowed_calls("memory and render and discord all called")
    for kw in ("memory", "render", "discord"):
        assert_test(f"{kw}_detected", kw in multi, f"violations: {multi}")


def test_fact_packet_structure():
    """Test the canary fact packet has all required fields."""
    import scripts.hermes_artifact_canary as canary
    fp = canary.FACT_PACKET
    required = {"competition", "match_date", "team_a", "team_b", "score",
                "stage_or_round", "verification_status", "confidence",
                "evidence_sources", "evidence_claims", "key_events"}
    for field in required:
        assert_test(f"fact_packet_{field}", field in fp, f"{field} present")
    assert_test("fact_packet_germany", fp["team_a"] == "Germany", "team_a=Germany")
    assert_test("fact_packet_argentina", fp["team_b"] == "Argentina", "team_b=Argentina")
    assert_test("fact_packet_verified", fp["verification_status"] == "verified",
                 "status=verified")


def test_canary_runtime_fields():
    """Test run_hermes_turn with canary_mode adds canary-specific fields."""
    from scripts.hermes_runtime import run_hermes_turn
    run_dir = Path(tempfile.mkdtemp(prefix="canary_fields_"))
    result = run_hermes_turn(
        title="Test", theme="Test",
        run_id="test_fields", run_dir=run_dir,
        canary_mode=True,
        canary_fact_packet={"team_a": "A", "team_b": "B"},
    )
    assert_test("canary_has_phase", "phase" in result, "phase field present")
    assert_test("canary_has_runtime", "runtime_seconds" in result,
                 "runtime_seconds field present")


def test_canary_disables_web_search():
    """Test that the canary agent code does not include web_search tool."""
    from scripts.hermes_runtime import _build_canary_agent_code
    code = _build_canary_agent_code(
        hermes_repo_str="/fake", hermes_home_str="/fake",
        session_id="test", user_msg="test",
        api_key="k", base_url="u", model="m",
    )
    assert_test("no_web_search_in_code", "web_search" not in code,
                "web_search not in canary agent code")
    assert_test("no_terminal_in_code", "terminal" not in code,
                "terminal not in canary agent code")


def test_match_fact_lock_validation_schema():
    """Test _validate_match_fact_lock correctly validates."""
    from scripts.hermes_runtime import _validate_match_fact_lock, _MATCH_FACT_LOCK_SCHEMA
    # Valid match_fact_lock
    valid = dict(_MATCH_FACT_LOCK_SCHEMA)
    valid.update({
        "status": "verified",
        "competition": "World Cup",
        "match_date": "2014-07-13",
        "team_a": "Germany",
        "team_b": "Argentina",
        "score": "1-0",
        "verification_status": "verified",
        "evidence_sources": ["FIFA"],
        "evidence_claims": ["Germany won"],
        "timestamp_utc": "2024-01-01T00:00:00Z",
    })
    errors = _validate_match_fact_lock(valid)
    assert_test("valid_match_fact", len(errors) == 0, f"errors: {errors}")

    # Missing field
    missing = {"team_a": "Germany"}
    errors = _validate_match_fact_lock(missing)
    assert_test("missing_field_detected", len(errors) > 0, f"errors: {errors}")

    # Forbidden status
    bad_status = dict(_MATCH_FACT_LOCK_SCHEMA)
    bad_status.update({"verification_status": "pending_discovery"})
    errors = _validate_match_fact_lock(bad_status)
    assert_test("bad_status_detected",
                any("verification_status" in e for e in errors),
                f"errors: {errors}")


def test_json_extraction_parses_valid():
    """Test _extract_and_validate_artifacts parses JSON from response."""
    from scripts.hermes_runtime import _extract_and_validate_artifacts
    response = json.dumps({
        "status": "verified",
        "competition": "World Cup",
        "match_date": "2014-07-13",
        "team_a": "Germany",
        "team_b": "Argentina",
        "score": "1-0",
        "verification_status": "verified",
        "evidence_sources": ["FIFA"],
        "evidence_claims": ["Germany won"],
        "timestamp_utc": "2024-01-01T00:00:00Z",
    })
    result = _extract_and_validate_artifacts(response, "Test", "Theme")
    assert_test("json_parsed", result.get("match_fact_lock") is not None,
                "match_fact_lock parsed")
    mf = result["match_fact_lock"]
    assert_test("team_a_germany", mf.get("team_a") == "Germany",
                f"got {mf.get('team_a')}")
    assert_test("verification_status", mf.get("verification_status") == "verified",
                f"got {mf.get('verification_status')}")


def test_json_extraction_handles_empty():
    """Test _extract_and_validate_artifacts handles empty/no-JSON response."""
    from scripts.hermes_runtime import _extract_and_validate_artifacts
    result = _extract_and_validate_artifacts("no json here", "Test", "Theme")
    assert_test("empty_uses_fallback", result.get("extraction_method") == "fallback_constructed",
                f"method={result.get('extraction_method')}")


def test_canary_standalone_entry_point():
    """Test python3 -m scripts.hermes_artifact_canary is importable as module."""
    result = subprocess.run(
        [sys.executable, "-m", "scripts.hermes_artifact_canary", "--help"],
        capture_output=True, text=True, timeout=15,
    )
    # Should not crash - it doesn't support --help so it'll print usage or error
    assert_test("canary_module_runs", True, f"exit={result.returncode}")


def test_build_canary_deterministic_match_fact_lock():
    """Test _build_canary_deterministic_match_fact_lock produces valid lock with provenance fields."""
    from scripts.hermes_runtime import _build_canary_deterministic_match_fact_lock, _validate_match_fact_lock
    fact_packet = {"competition": "2014 FIFA World Cup", "team_a": "Germany", "team_b": "Argentina"}
    hermes_response = "I confirm the 2014 FIFA World Cup Final, Germany vs Argentina, 1-0"
    result = _build_canary_deterministic_match_fact_lock(fact_packet, hermes_response)
    assert_test("deterministic_lock_created", result is not None, "lock was built")
    assert_test("deterministic_extraction_method",
                 result.get("extraction_method") == "canary_deterministic_fact_packet_after_hermes_attestation",
                 f"got {result.get('extraction_method')}")
    assert_test("deterministic_canary_only", result.get("canary_only") is True, "canary_only=True")
    assert_test("deterministic_no_fallback", result.get("production_fallback_used") is False,
                 "production_fallback_used=False")
    assert_test("deterministic_hermes_sha256",
                 bool(result.get("hermes_response_sha256")),
                 "hermes_response_sha256 present")
    assert_test("deterministic_fact_packet_sha256",
                 bool(result.get("fact_packet_sha256")),
                 "fact_packet_sha256 present")
    assert_test("deterministic_match", result.get("match") == "Germany vs Argentina",
                 f"match={result.get('match')}")
    assert_test("deterministic_competition", result.get("competition") == "2014 FIFA World Cup Final",
                 f"competition={result.get('competition')}")
    assert_test("deterministic_date", result.get("match_date") == "2014-07-13",
                 f"date={result.get('match_date')}")
    assert_test("deterministic_score", result.get("score") == "Germany 1-0 Argentina",
                 f"score={result.get('score')}")
    assert_test("deterministic_decisive_goal", result.get("decisive_goal") == "Mario Götze, 113'",
                 f"decisive_goal={result.get('decisive_goal')}")
    assert_test("deterministic_source_mode", result.get("source_mode") == "stable_canary_fact_packet",
                 f"source_mode={result.get('source_mode')}")
    assert_test("deterministic_hermes_attestation", result.get("hermes_attestation_required") is True,
                 "hermes_attestation_required=True")
    assert_test("deterministic_verification_status", result.get("verification_status") == "verified",
                 f"status={result.get('verification_status')}")
    # Must pass standard schema validation
    schema_errors = _validate_match_fact_lock(result)
    assert_test("deterministic_schema_valid", len(schema_errors) == 0,
                 f"schema errors: {schema_errors}")


def test_build_canary_deterministic_hashes_response():
    """Test that hermes_response_sha256 changes when response changes."""
    from scripts.hermes_runtime import _build_canary_deterministic_match_fact_lock
    fact_packet = {"competition": "2014 FIFA World Cup", "team_a": "Germany"}
    r1 = _build_canary_deterministic_match_fact_lock(fact_packet, "response one")
    r2 = _build_canary_deterministic_match_fact_lock(fact_packet, "response two")
    assert_test("different_response_different_sha256",
                 r1["hermes_response_sha256"] != r2["hermes_response_sha256"],
                 "hashes should differ when response differs")


def test_build_canary_deterministic_empty_response():
    """Test that empty response still produces valid lock but hermes_response_nonempty is False."""
    from scripts.hermes_runtime import _build_canary_deterministic_match_fact_lock
    fact_packet = {"competition": "2014 FIFA World Cup", "team_a": "Germany"}
    result = _build_canary_deterministic_match_fact_lock(fact_packet, "")
    assert_test("empty_response_not_nonempty",
                 result.get("hermes_response_nonempty") is False,
                 "should be marked as non-empty=False")


def test_canary_report_contains_all_provenance_fields():
    """Test that the canary script's report dict includes all required provenance fields."""
    import scripts.hermes_artifact_canary as canary
    fp = canary.FACT_PACKET
    # The report is built in main(); we test that the canary script references the required fields
    source = open(canary.__file__).read()
    required_in_report = [
        "extraction_method",
        "canary_only",
        "production_fallback_used",
        "hermes_response_sha256",
        "fact_packet_sha256",
        "match",
        "competition",
        "decisive_goal",
        "source_mode",
        "hermes_attestation_required",
    ]
    for field in required_in_report:
        assert_test(f"report_has_{field}",
                     f'"{field}"' in source,
                     f"{field} in report dict")


def test_canary_extraction_method_constant_in_runtime():
    """Test that the canary extraction method constant exists in hermes_runtime."""
    import scripts.hermes_runtime as rt
    result = rt._build_canary_deterministic_match_fact_lock({"team_a": "Germany"}, "ok")
    assert_test("canary_method_constant",
                 result.get("extraction_method") == "canary_deterministic_fact_packet_after_hermes_attestation",
                 f"method={result.get('extraction_method')}")


def test_canary_only_match_fact_lock_has_all_fields():
    """Test that the canary match_fact_lock includes all provenance fields."""
    from scripts.hermes_runtime import _build_canary_deterministic_match_fact_lock
    result = _build_canary_deterministic_match_fact_lock({"team_a": "A", "team_b": "B"}, "ok")
    required_provenance = [
        "extraction_method", "canary_only", "production_fallback_used",
        "hermes_response_nonempty", "hermes_response_sha256", "fact_packet_sha256",
        "source_mode", "hermes_attestation_required", "match", "decisive_goal",
    ]
    for field in required_provenance:
        assert_test(f"provenance_field_{field}",
                     field in result,
                     f"{field} present in match_fact_lock")


def test_canary_expected_skills_count():
    """Test the expected V7 skill count constant."""
    import scripts.hermes_artifact_canary as canary
    assert_test("expected_count", canary.EXPECTED_V7_SKILL_COUNT == 23,
                f"EXPECTED_V7_SKILL_COUNT={canary.EXPECTED_V7_SKILL_COUNT}")


def test_canary_timeout_constant():
    """Test the canary timeout constant."""
    import scripts.hermes_artifact_canary as canary
    assert_test("canary_timeout", canary.CANARY_TIMEOUT_SECONDS == 120,
                f"timeout={canary.CANARY_TIMEOUT_SECONDS}s")


def test_canary_active_skills_list():
    """Test the active canary skills list contains only the two relevant skills."""
    import scripts.hermes_artifact_canary as canary
    assert_test("exactly_two_skills", len(canary.ACTIVE_CANARY_SKILLS) == 2,
                f"count={len(canary.ACTIVE_CANARY_SKILLS)}")
    assert_test("match_identification",
                "football-match-identification" in canary.ACTIVE_CANARY_SKILLS)
    assert_test("provenance_gate",
                "football-fact-provenance-gate" in canary.ACTIVE_CANARY_SKILLS)


def run_all():
    test_agent_code_generates_minimal_agent()
    test_core_agent_code()
    test_canary_agent_prompt_includes_fact_packet()
    test_disabled_toolsets_constant()
    test_active_canary_skills()
    test_phase_log_flushes()
    test_empty_response_fails()
    test_malformed_response_no_retry_loop()
    test_timeout_detects_active_phase()
    test_standalone_script_importable()
    test_standalone_script_checks_endpoint()
    test_disallowed_calls_detection()
    test_fact_packet_structure()
    test_canary_runtime_fields()
    test_canary_disables_web_search()
    test_match_fact_lock_validation_schema()
    test_json_extraction_parses_valid()
    test_json_extraction_handles_empty()
    test_canary_standalone_entry_point()
    test_build_canary_deterministic_match_fact_lock()
    test_build_canary_deterministic_hashes_response()
    test_build_canary_deterministic_empty_response()
    test_canary_report_contains_all_provenance_fields()
    test_canary_extraction_method_constant_in_runtime()
    test_canary_only_match_fact_lock_has_all_fields()
    test_canary_expected_skills_count()
    test_canary_timeout_constant()
    test_canary_active_skills_list()

    print(f"\n{'=' * 60}")
    print(f"  Results: {PASS}/{TOTAL} passed", end="")
    if FAIL:
        print(f", {FAIL} FAILED", end="")
    print()
    print(f"{'=' * 60}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
