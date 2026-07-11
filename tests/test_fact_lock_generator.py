#!/usr/bin/env python3
"""Tests for FactLockGenerator — deterministic seed-based match_fact_lock.

Tests prove:
1. job fact_lock_seed creates valid match_fact_lock.json
2. Hermes is not asked to generate match_fact_lock when seed is valid
3. invalid seed blocks immediately
4. missing seed preserves existing Hermes path
5. seed method is not treated as fallback_constructed
6. downstream stages do not run on invalid seed
7. production run uses seeded fact lock for argentina_hardest_victory.yaml
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
TEST_DIR = Path(tempfile.mkdtemp(prefix="acd_fact_lock_"))

PASS = 0
FAIL = 0
TOTAL = 0


def _make_test_run_dir(name: str) -> Path:
    d = TEST_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _read_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def assert_test(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if condition:
        PASS += 1
        print(f"  PASS: {name}" + (f" — {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL: {name} — {detail}")


# ---------------------------------------------------------------------------
# 1. job fact_lock_seed creates valid match_fact_lock.json
# ---------------------------------------------------------------------------


def test_seed_creates_valid_match_fact_lock():
    """Test: generate_fact_lock_from_seed returns schema-valid match_fact_lock."""
    from scripts.hermes_runtime import generate_fact_lock_from_seed, _validate_match_fact_lock

    seed = {
        "status": "verified",
        "competition": "2026 FIFA World Cup",
        "match_date": "2026-07-07",
        "team_a": "Argentina",
        "team_b": "Egypt",
        "score": "",
        "stage_or_round": "Round of 16",
        "verification_status": "creative_hypothesis",
        "confidence": "high",
        "evidence_sources": ["FIFA official schedule"],
        "evidence_claims": ["Argentina vs Egypt on 2026-07-07"],
    }
    mf = generate_fact_lock_from_seed(seed)
    errors = _validate_match_fact_lock(mf)
    assert_test("seed_produces_valid_lock", len(errors) == 0, f"errors={errors}")
    assert_test("seed_sets_extraction_method",
                 mf.get("extraction_method") == "job_verified_fact_lock_seed",
                 f"got={mf.get('extraction_method')}")
    assert_test("seed_sets_source_mode",
                 mf.get("source_mode") == "job_seed",
                 f"got={mf.get('source_mode')}")
    assert_test("seed_no_fallback",
                 mf.get("production_fallback_used") is False,
                 f"got={mf.get('production_fallback_used')}")
    assert_test("seed_user_supplied",
                 mf.get("user_supplied_seed") is True,
                 f"got={mf.get('user_supplied_seed')}")
    assert_test("seed_team_a",
                 mf.get("team_a") == "Argentina",
                 f"got={mf.get('team_a')}")
    assert_test("seed_team_b",
                 mf.get("team_b") == "Egypt",
                 f"got={mf.get('team_b')}")
    assert_test("seed_verification_status",
                 mf.get("verification_status") == "creative_hypothesis",
                 f"got={mf.get('verification_status')}")
    assert_test("seed_generated_by",
                 mf.get("generated_by") == "job_verified_fact_lock_seed",
                 f"got={mf.get('generated_by')}")
    assert_test("seed_has_timestamp",
                 bool(mf.get("timestamp_utc")),
                 "timestamp_utc is empty")


def test_seed_all_required_fields_present():
    """Test: generated match_fact_lock contains all _REQUIRED_MATCH_FACT_FIELDS."""
    from scripts.hermes_runtime import generate_fact_lock_from_seed, _REQUIRED_MATCH_FACT_FIELDS

    seed = {
        "team_a": "Argentina", "team_b": "Egypt",
        "competition": "2026 FIFA World Cup",
        "match_date": "2026-07-07",
        "stage_or_round": "Round of 16",
        "verification_status": "creative_hypothesis",
    }
    mf = generate_fact_lock_from_seed(seed)
    for field in _REQUIRED_MATCH_FACT_FIELDS:
        assert_test(f"seed_has_field_{field}",
                     field in mf,
                     f"missing field: {field}")


def test_seed_compatible_with_artifact_gate():
    """Test: seed-based match_fact_lock passes editorial artifact gate."""
    from scripts.hermes_runtime import generate_fact_lock_from_seed
    from scripts.editorial_artifact_gate import check_artifact_gate

    seed = {
        "team_a": "Argentina", "team_b": "Egypt",
        "competition": "2026 FIFA World Cup",
        "match_date": "2026-07-07",
        "stage_or_round": "Round of 16",
        "verification_status": "creative_hypothesis",
        "score": "",
    }
    mf = generate_fact_lock_from_seed(seed)
    run_dir = _make_test_run_dir("seed_gate_compat")
    artifacts_dir = run_dir / "hermes_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    _write_json(artifacts_dir / "match_fact_lock.json", mf)
    _write_json(artifacts_dir / "brief_interpretation.json",
                {"title": "Test", "theme": "Test", "emotional_arc": "Rise"})
    _write_json(artifacts_dir / "source_candidates.json", {"candidates": []})
    _write_json(artifacts_dir / "source_verification.json", {"verified_sources": []})
    _write_json(artifacts_dir / "media_probe.json", {"probe_results": {}})
    _write_json(artifacts_dir / "visual_scene_analysis.json",
                {"run_id": "test", "files_analyzed": 1, "probes": []})
    _write_json(artifacts_dir / "timestamp_candidates.json", {"timestamps": []})
    _write_json(artifacts_dir / "clip_scores.json", {"scores": []})
    _write_json(artifacts_dir / "arc_revision_gate.json",
                {"arc_decision": "proceed", "status": "passed"})
    _write_json(artifacts_dir / "story_plan.json", {"structure": [], "segments": []})
    _write_json(artifacts_dir / "audio_music_plan.json", {"audio_plan": {}, "music_tracks": []})
    _write_json(artifacts_dir / "commentary_rights_check.json",
                {"rights_status": "cleared", "commentary_status": "cleared"})
    _write_json(artifacts_dir / "visual_cohesion_plan.json",
                {"style_guide": {}, "grade_decisions": {}})
    _write_json(artifacts_dir / "graphics_text_plan.json",
                {"text_elements": [], "graphic_elements": []})
    _write_json(artifacts_dir / "assembly_plan.json",
                {"structure": [], "total_duration_seconds": 60})
    _write_json(artifacts_dir / "fact_provenance_gate.json",
                {"verification_summary": {}, "provenance_trail": []})
    _write_json(artifacts_dir / "editorial_journey_state.json",
                {"current_stage": "gate", "artifacts_produced": [], "artifacts_pending": []})

    result = check_artifact_gate(run_dir)
    assert_test("seed_passes_artifact_gate",
                 result["gate_passed"],
                 f"blocker={result.get('blocker')}")


# ---------------------------------------------------------------------------
# 2. Hermes is not asked to generate match_fact_lock when seed is valid
# ---------------------------------------------------------------------------


def test_hermes_not_asked_when_seed_valid():
    """Test: run_hermes_turn with fact_lock_override uses override, not extraction."""
    from scripts.hermes_runtime import run_hermes_turn, generate_fact_lock_from_seed

    saved = {k: os.environ.pop(k, None) for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")}
    try:
        os.environ["LLM_API_KEY"] = "sk-test"
        os.environ["LLM_BASE_URL"] = "https://example.invalid/v1"
        os.environ["LLM_MODEL"] = "test-model"

        seed = {
            "team_a": "Argentina", "team_b": "Egypt",
            "competition": "2026 FIFA World Cup",
            "match_date": "2026-07-07",
            "stage_or_round": "Round of 16",
            "verification_status": "creative_hypothesis",
        }
        fact_lock_override = generate_fact_lock_from_seed(seed)

        with patch("scripts.hermes_runtime._check_venv_hermes_import") as mock_check, \
             patch("scripts.hermes_runtime._prepare_and_query_skills") as mock_skills, \
             patch("scripts.hermes_runtime.subprocess.Popen") as mock_popen:

            mock_check.return_value = {"aiagent_importable": True}
            mock_skills.return_value = {
                "hermes_loaded_skill_count": 1,
                "hermes_loaded_skill_names": ["test"],
                "skill_runtime_preparation": {},
            }
            fake_proc = MagicMock()
            fake_proc.returncode = 0
            fake_proc.communicate.return_value = (
                "RESPONSE_START\nSome creative planning response\nRESPONSE_END\n",
                ""
            )
            fake_proc.pid = 12345
            mock_popen.return_value = fake_proc

            run_dir = _make_test_run_dir("seed_override")
            result = run_hermes_turn("test", "test", "test", run_dir,
                                     fact_lock_override=fact_lock_override)

            assert_test("seed_hermes_success",
                         result.get("success"),
                         f"error_type={result.get('error_type')}, error={result.get('error_message')}")

            mf_path = run_dir / "hermes_artifacts" / "match_fact_lock.json"
            assert_test("seed_lock_file_exists",
                         mf_path.is_file(),
                         f"exists={mf_path.is_file()}")
            if mf_path.is_file():
                mf = _read_json(mf_path)
                assert_test("seed_lock_has_extraction_method",
                             mf.get("extraction_method") == "job_verified_fact_lock_seed",
                             f"got={mf.get('extraction_method')}")
                assert_test("seed_lock_team_a",
                             mf.get("team_a") == "Argentina",
                             f"got={mf.get('team_a')}")

            ext = result.get("details", {}).get("match_fact_lock", {}).get("extraction")
            assert_test("seed_extraction_method_in_result",
                         ext == "job_verified_fact_lock_seed",
                         f"got={ext}")

            # Verify the prompt included match_fact_lock context and NOT "Produce match_fact_lock"
            if mock_popen.call_count >= 1:
                call_args = mock_popen.call_args[0]
                code_text = str(call_args)
                assert_test("seed_prompt_has_context",
                             "match_fact_lock" in code_text,
                             "override prompt must include match_fact_lock summary")
                assert_test("seed_prompt_no_produce",
                             "Do NOT produce match_fact_lock" in code_text,
                             "override prompt must tell Hermes not to produce match_fact_lock")

    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# 3. invalid seed blocks immediately
# ---------------------------------------------------------------------------


def test_invalid_seed_blocks():
    """Test: validate_fact_lock_seed_structure catches missing critical fields."""
    from scripts.hermes_runtime import validate_fact_lock_seed_structure

    seed = {"team_a": "Argentina"}  # severely incomplete
    errors = validate_fact_lock_seed_structure(seed)
    assert_test("invalid_seed_has_errors",
                 len(errors) > 0,
                 f"errors={errors}")
    field_names = [e for e in errors]
    assert_test("missing_team_b_detected",
                 any("team_b" in e for e in errors),
                 f"errors={errors}")
    assert_test("missing_competition_detected",
                 any("competition" in e for e in errors),
                 f"errors={errors}")


def test_invalid_seed_stops_pipeline():
    """Test: run_title_theme_job exits 1 when fact_lock_seed produces invalid lock.

    The non-synthetic path hits FactLockGenerator before Hermes, so no API keys
    are needed — seed validation failure stops the pipeline before any Hermes call.
    """
    saved_env = dict(os.environ)
    try:
        # Create a job YAML with invalid seed (missing critical fields)
        job_yaml = TEST_DIR / "invalid_seed_job.yaml"
        job_data = {
            "title": "Invalid Seed Test",
            "theme": "test",
            "fact_lock_seed": {
                "team_a": "Argentina",
                # missing team_b, competition, match_date, stage_or_round
            },
        }
        with open(job_yaml, "w") as f:
            import yaml
            yaml.dump(job_data, f)

        proc = subprocess.run(
            [sys.executable, "-m", "scripts.run_title_theme_job", str(job_yaml), "--run-id", "invalid_seed_test"],
            capture_output=True, text=True, timeout=30,
            cwd=str(BASE_DIR),
        )
        output = (proc.stdout + proc.stderr).lower()
        has_seed_error = "seed" in output and ("error" in output or "missing" in output)
        assert_test("invalid_seed_exits_nonzero",
                     proc.returncode != 0,
                     f"exit={proc.returncode}")
        assert_test("invalid_seed_diagnostic",
                     has_seed_error,
                     f"output={proc.stdout[-500:] if len(proc.stdout) > 500 else proc.stdout}")
    finally:
        os.environ.clear()
        os.environ.update(saved_env)


def test_missing_team_a_in_seed():
    """Test: missing team_a in seed produces validation error."""
    from scripts.hermes_runtime import validate_fact_lock_seed_structure

    seed = {
        "team_b": "Egypt",
        "competition": "2026 FIFA World Cup",
        "match_date": "2026-07-07",
        "verification_status": "creative_hypothesis",
        # missing team_a, stage_or_round
    }
    errors = validate_fact_lock_seed_structure(seed)
    team_a_error = any("team_a" in e for e in errors)
    stage_error = any("stage_or_round" in e for e in errors)
    assert_test("missing_team_a_detected",
                 team_a_error,
                 f"errors={errors}")
    assert_test("missing_stage_detected",
                 stage_error,
                 f"errors={errors}")
    team_b_ok = not any("team_b" in e for e in errors)
    competition_ok = not any("competition" in e for e in errors)
    assert_test("missing_team_b_ok",
                 team_b_ok,
                 "team_b should not error because it was in the seed")


# ---------------------------------------------------------------------------
# 4. missing seed preserves existing Hermes path
# ---------------------------------------------------------------------------


def test_missing_seed_preserves_hermes_path():
    """Test: when fact_lock_override is None, run_hermes_turn extracts from response."""
    from scripts.hermes_runtime import run_hermes_turn

    saved = {k: os.environ.pop(k, None) for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")}
    try:
        os.environ["LLM_API_KEY"] = "sk-test"
        os.environ["LLM_BASE_URL"] = "https://example.invalid/v1"
        os.environ["LLM_MODEL"] = "test-model"

        # Response contains complete match_fact_lock with ALL required fields
        hermes_response = json.dumps({
            "status": "verified",
            "competition": "Test Cup",
            "match_date": "2024-01-01",
            "team_a": "Team A",
            "team_b": "Team B",
            "score": "2-1",
            "stage_or_round": "Final",
            "evidence_sources": ["Test source"],
            "evidence_claims": ["Team A won"],
            "verification_status": "verified",
            "confidence": "high",
            "unresolved_conflicts": [],
            "generated_by": "Hermes-Agent AIAgent",
            "timestamp_utc": "2024-01-01T00:00:00Z",
        })

        with patch("scripts.hermes_runtime._check_venv_hermes_import") as mock_check, \
             patch("scripts.hermes_runtime._prepare_and_query_skills") as mock_skills, \
             patch("scripts.hermes_runtime.subprocess.Popen") as mock_popen:

            mock_check.return_value = {"aiagent_importable": True}
            mock_skills.return_value = {
                "hermes_loaded_skill_count": 1,
                "hermes_loaded_skill_names": ["test"],
                "skill_runtime_preparation": {},
            }
            fake_proc = MagicMock()
            fake_proc.returncode = 0
            fake_proc.communicate.return_value = (
                f"RESPONSE_START\n{hermes_response}\nRESPONSE_END\n",
                ""
            )
            fake_proc.pid = 12345
            mock_popen.return_value = fake_proc

            run_dir = _make_test_run_dir("no_seed_hermes")
            # fact_lock_override defaults to None
            result = run_hermes_turn("test", "test", "test", run_dir)

            ext = result.get("details", {}).get("match_fact_lock", {}).get("extraction")
            assert_test("no_seed_uses_hermes_extraction",
                         ext == "parsed_from_response",
                         f"extraction={ext}")

            # Verify prompt asks Hermes to produce match_fact_lock
            if mock_popen.call_count >= 1:
                call_args = mock_popen.call_args[0]
                code_text = str(call_args)
                assert_test("no_seed_prompt_has_produce",
                             "Produce match_fact_lock" in code_text,
                             "standard prompt must ask Hermes to produce match_fact_lock")

    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# 5. seed method is not treated as fallback_constructed
# ---------------------------------------------------------------------------


def test_seed_not_fallback():
    """Test: extraction_method for seed is 'job_verified_fact_lock_seed' not 'fallback_constructed'."""
    from scripts.hermes_runtime import generate_fact_lock_from_seed

    seed = {
        "team_a": "Argentina", "team_b": "Egypt",
        "competition": "2026 FIFA World Cup",
        "match_date": "2026-07-07",
        "stage_or_round": "Round of 16",
        "verification_status": "creative_hypothesis",
    }
    mf = generate_fact_lock_from_seed(seed)
    assert_test("seed_extraction_not_fallback",
                 mf.get("extraction_method") != "fallback_constructed",
                 f"got={mf.get('extraction_method')}")
    assert_test("seed_extraction_is_job_verified",
                 mf.get("extraction_method") == "job_verified_fact_lock_seed",
                 f"got={mf.get('extraction_method')}")
    assert_test("seed_production_fallback_false",
                 mf.get("production_fallback_used") is False,
                 f"got={mf.get('production_fallback_used')}")


def test_seed_runs_before_hermes_not_after():
    """Test: FactLockGenerator runs BEFORE Hermes in pipeline order."""
    content = (SCRIPTS_DIR / "run_title_theme_job.py").read_text()
    fact_gen_idx = content.find("fact_lock_generator")
    hermes_call_idx = content.find("run_hermes_turn_with_retry")
    assert_test("seed_before_hermes",
                 fact_gen_idx >= 0 and hermes_call_idx >= 0 and fact_gen_idx < hermes_call_idx,
                 f"fact_gen={fact_gen_idx}, hermes={hermes_call_idx}")


# ---------------------------------------------------------------------------
# 6. downstream stages do not run on invalid seed
# ---------------------------------------------------------------------------


def test_downstream_blocked_on_invalid_seed():
    """Test: invalid seed blocks pipeline before Hermes call and downstream stages."""
    content = (SCRIPTS_DIR / "run_title_theme_job.py").read_text()
    invalid_seed_exit = content.find('sys.exit(1)')
    seed_validation = content.find("seed_validation_error")
    hermes_call = content.find("run_hermes_turn_with_retry")
    source_discovery = content.find("source_discovery")
    assert_test("invalid_seed_exits_before_hermes",
                 invalid_seed_exit > 0 and hermes_call > invalid_seed_exit,
                 f"exit={invalid_seed_exit}, hermes_call={hermes_call}")
    assert_test("invalid_seed_exits_before_source_discovery",
                 invalid_seed_exit > 0 and source_discovery > invalid_seed_exit,
                 f"exit={invalid_seed_exit}, source={source_discovery}")
    assert_test("seed_validation_check_exists",
                 seed_validation >= 0,
                 "seed validation error check must exist")


def test_invalid_seed_writes_failure_summary():
    """Test: invalid seed writes failure_summary.json with failed_stage fact_lock_generator."""
    from scripts.artifact_contracts import atomic_write_json
    from scripts.run_title_theme_job import write_failure_summary

    run_dir = _make_test_run_dir("seed_failure_summary")
    run_id = run_dir.name
    stages = {}
    exc = {"type": "seed_validation_error", "message": "test error", "traceback": None}
    summary = write_failure_summary(run_id, "fact_lock_generator", exc, stages, run_dir)
    assert_test("seed_failure_summary_written",
                 summary is not None,
                 "write_failure_summary returned None")
    summary_path = run_dir / "failure_summary.json"
    assert_test("seed_failure_summary_exists",
                 summary_path.is_file(),
                 f"exists={summary_path.is_file()}")


# ---------------------------------------------------------------------------
# 7. production run uses seeded fact lock for argentina_hardest_victory.yaml
# ---------------------------------------------------------------------------


def test_argentina_yaml_has_fact_lock_seed():
    """Test: argentina_hardest_victory.yaml contains fact_lock_seed."""
    import yaml
    job_path = BASE_DIR / "jobs" / "argentina_hardest_victory.yaml"
    assert job_path.is_file(), f"Job file not found: {job_path}"
    with open(job_path) as f:
        job = yaml.safe_load(f)
    seed = job.get("fact_lock_seed")
    assert_test("yaml_has_seed", seed is not None, "fact_lock_seed not found in YAML")
    if seed:
        assert_test("yaml_seed_has_team_a", seed.get("team_a") == "Argentina", f"got={seed.get('team_a')}")
        assert_test("yaml_seed_has_team_b", seed.get("team_b") == "Egypt", f"got={seed.get('team_b')}")
        assert_test("yaml_seed_has_competition", seed.get("competition") == "2026 FIFA World Cup", f"got={seed.get('competition')}")
        assert_test("yaml_seed_has_match_date", seed.get("match_date") == "2026-07-07", f"got={seed.get('match_date')}")
        assert_test("yaml_seed_has_stage", seed.get("stage_or_round") == "Round of 16", f"got={seed.get('stage_or_round')}")
        assert_test("yaml_seed_status_verified", seed.get("status") == "verified", f"got={seed.get('status')}")
        assert_test("yaml_seed_has_evidence_sources",
                     isinstance(seed.get("evidence_sources"), list) and len(seed["evidence_sources"]) > 0,
                     "evidence_sources missing or empty")


def test_argentina_seed_loads_into_pipeline():
    """Test: loading argentina_hardest_victory.yaml and processing fact_lock_seed
    would produce a valid match_fact_lock."""
    import yaml
    from scripts.hermes_runtime import generate_fact_lock_from_seed, _validate_match_fact_lock

    job_path = BASE_DIR / "jobs" / "argentina_hardest_victory.yaml"
    with open(job_path) as f:
        job = yaml.safe_load(f)
    seed = job.get("fact_lock_seed")
    assert_test("seed_found_in_yaml", seed is not None, "fact_lock_seed missing")
    if seed:
        mf = generate_fact_lock_from_seed(seed)
        errors = _validate_match_fact_lock(mf)
        assert_test("argentina_seed_produces_valid_lock",
                     len(errors) == 0,
                     f"validation_errors={errors}")
        assert_test("argentina_team_a",
                     mf.get("team_a") == "Argentina",
                     f"got={mf.get('team_a')}")
        assert_test("argentina_team_b",
                     mf.get("team_b") == "Egypt",
                     f"got={mf.get('team_b')}")
        assert_test("argentina_competition",
                     mf.get("competition") == "2026 FIFA World Cup",
                     f"got={mf.get('competition')}")
        assert_test("argentina_stage",
                     mf.get("stage_or_round") == "Round of 16",
                     f"got={mf.get('stage_or_round')}")
        assert_test("argentina_extraction_method",
                     mf.get("extraction_method") == "job_verified_fact_lock_seed",
                     f"got={mf.get('extraction_method')}")
        assert_test("argentina_source_mode",
                     mf.get("source_mode") == "job_seed",
                     f"got={mf.get('source_mode')}")
        assert_test("argentina_no_fallback",
                     mf.get("production_fallback_used") is False,
                     f"got={mf.get('production_fallback_used')}")
        assert_test("argentina_user_supplied_seed",
                     mf.get("user_supplied_seed") is True,
                     f"got={mf.get('user_supplied_seed')}")


# ---------------------------------------------------------------------------
# Additional: creative_hypothesis allowed through validation
# ---------------------------------------------------------------------------


def test_creative_hypothesis_allowed():
    """Test: creative_hypothesis is no longer forbidden by _validate_match_fact_lock."""
    from scripts.hermes_runtime import _validate_match_fact_lock

    data = {
        "status": "verified",
        "competition": "Test",
        "match_date": "2024-01-01",
        "team_a": "A",
        "team_b": "B",
        "score": "",
        "stage_or_round": "Final",
        "evidence_sources": [],
        "evidence_claims": [],
        "verification_status": "creative_hypothesis",
        "confidence": "high",
        "unresolved_conflicts": [],
        "generated_by": "test",
        "timestamp_utc": "2024-01-01T00:00:00Z",
    }
    errors = _validate_match_fact_lock(data)
    ch_error = [e for e in errors if "creative_hypothesis" in e]
    assert_test("creative_hypothesis_not_forbidden",
                 len(ch_error) == 0,
                 f"errors={ch_error}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_all():
    global PASS, FAIL, TOTAL
    print(f"\n{'='*60}")
    print(f"  FACT-LOCK GENERATOR TESTS")
    print(f"{'='*60}\n")

    tests = [
        ("Seed creates valid match_fact_lock", test_seed_creates_valid_match_fact_lock),
        ("Seed has all required fields", test_seed_all_required_fields_present),
        ("Seed compatible with artifact gate", test_seed_compatible_with_artifact_gate),
        ("Hermes not asked when seed valid", test_hermes_not_asked_when_seed_valid),
        ("Invalid seed blocks validation", test_invalid_seed_blocks),
        ("Invalid seed stops pipeline", test_invalid_seed_stops_pipeline),
        ("Missing team_a in seed detected", test_missing_team_a_in_seed),
        ("Missing seed preserves Hermes path", test_missing_seed_preserves_hermes_path),
        ("Seed not fallback", test_seed_not_fallback),
        ("Seed runs before Hermes", test_seed_runs_before_hermes_not_after),
        ("Downstream blocked on invalid seed", test_downstream_blocked_on_invalid_seed),
        ("Invalid seed writes failure summary", test_invalid_seed_writes_failure_summary),
        ("Argentina YAML has fact_lock_seed", test_argentina_yaml_has_fact_lock_seed),
        ("Argentina seed loads into pipeline", test_argentina_seed_loads_into_pipeline),
        ("creative_hypothesis allowed", test_creative_hypothesis_allowed),
    ]

    for name, func in tests:
        try:
            func()
        except Exception as e:
            TOTAL += 1
            FAIL += 1
            import traceback
            print(f"  FAIL: {name}: {e}")
            traceback.print_exc()
        print()

    print(f"{'='*60}")
    print(f"  FACT-LOCK RESULTS: {PASS} passed, {FAIL} failed, {TOTAL} total")
    print(f"{'='*60}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
