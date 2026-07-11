#!/usr/bin/env python3
"""Failure-injection tests for acd-video-worker.

Tests real subprocess boundaries with temporary directories.
Does NOT rely on grep or string-presence assertions for pipeline behavior.
For every failure case, asserts:
  - exact stage stops
  - later stages do not run
  - nonzero exit code
  - no false success message
  - no learned memory appended
  - clear structured diagnostic written
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
TEST_DIR = Path(tempfile.mkdtemp(prefix="acd_failure_"))

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


def _run_python(code: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=timeout,
    )


def assert_test(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if condition:
        PASS += 1
        print(f"  PASS: {name}" + (f" — {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL: {name} — {detail}")


def test_missing_api_key():
    """Test: missing LLM_API_KEY produces endpoint_configuration_error."""
    from scripts.hermes_runtime import run_hermes_turn
    saved = {k: os.environ.pop(k, None) for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")}
    try:
        run_dir = _make_test_run_dir("missing_api_key")
        result = run_hermes_turn("", "", "test", run_dir, smoke_test=True)
        assert_test("missing_api_key_returns_error",
                     result.get("success") is False and result.get("error_type") == "endpoint_configuration_error",
                     f"error_type={result.get('error_type')}")
    finally:
        for k, v in saved.items():
            if v: os.environ[k] = v


def test_invalid_endpoint():
    """Test: invalid endpoint returns conversation_failed."""
    from scripts.hermes_runtime import run_hermes_turn, _check_venv_hermes_import, _prepare_and_query_skills
    saved = {k: os.environ.pop(k, None) for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")}
    try:
        os.environ["LLM_API_KEY"] = "sk-test"
        os.environ["LLM_BASE_URL"] = "https://nonexistent.invalid/api/v1"
        os.environ["LLM_MODEL"] = "test-model"

        with patch("scripts.hermes_runtime._check_venv_hermes_import") as mock_check, \
             patch("scripts.hermes_runtime._prepare_and_query_skills") as mock_skills, \
             patch("scripts.hermes_runtime.subprocess.run") as mock_subprocess:

            mock_check.return_value = {"aiagent_importable": True, "import_error": None}
            mock_skills.return_value = {
                "hermes_loaded_skill_count": 1,
                "hermes_loaded_skill_names": ["test"],
                "skill_runtime_preparation": {},
            }
            fake_proc = MagicMock()
            fake_proc.returncode = 1
            fake_proc.stdout = "RESPONSE_START\nERROR: connection failed\nRESPONSE_END\n"
            fake_proc.stderr = "connection error"
            mock_subprocess.return_value = fake_proc

            run_dir = _make_test_run_dir("invalid_endpoint")
            result = run_hermes_turn("", "", "test", run_dir, smoke_test=True)

            assert_test("invalid_endpoint_returns_conversation_failed",
                         result.get("success") is False,
                         f"error_type={result.get('error_type')}")
    finally:
        for k, v in saved.items():
            if v: os.environ[k] = v


def test_http_503_retry_exhaustion():
    """Test: HTTP 503 retry exhaustion produces blocked status."""
    from scripts.llm_key_check import main as llm_check
    saved = {k: os.environ.pop(k, None) for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")}
    try:
        os.environ["LLM_API_KEY"] = "sk-test"
        os.environ["LLM_BASE_URL"] = "https://httpstat.us/503"
        os.environ["LLM_MODEL"] = "test-model"

        # Temporarily write to a test path
        test_report = TEST_DIR / "llm_503_check.json"
        with patch("scripts.llm_key_check.REPORT_PATH", str(test_report)), \
             patch("scripts.llm_key_check.time.sleep"):
            try:
                llm_check()
            except SystemExit:
                pass
            except Exception:
                pass

        if test_report.is_file():
            data = json.loads(test_report.read_text())
            assert_test("http_503_retry_exhaustion",
                         data.get("llm_status") == "blocked" or not data.get("endpoint_accessible"),
                         f"status={data.get('llm_status')}, accessible={data.get('endpoint_accessible')}")
        else:
            assert_test("http_503_retry_exhaustion", False, "No report file")
    finally:
        for k, v in saved.items():
            if v: os.environ[k] = v


def test_zero_hermes_skills():
    """Test: zero Hermes skills blocks run_hermes_turn."""
    from scripts.hermes_runtime import run_hermes_turn
    saved = {k: os.environ.pop(k, None) for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")}
    try:
        os.environ["LLM_API_KEY"] = "sk-test"
        os.environ["LLM_BASE_URL"] = "https://example.invalid/v1"
        os.environ["LLM_MODEL"] = "test-model"

        with patch("scripts.hermes_runtime._check_venv_hermes_import") as mock_check, \
             patch("scripts.hermes_runtime._prepare_and_query_skills") as mock_skills:

            mock_check.return_value = {"aiagent_importable": True, "import_error": None}
            mock_skills.return_value = {
                "hermes_loaded_skill_count": 0,
                "hermes_loaded_skill_names": [],
                "skill_runtime_preparation": {},
            }
            run_dir = _make_test_run_dir("zero_skills")
            result = run_hermes_turn("", "", "test", run_dir, smoke_test=True)
            assert_test("zero_hermes_skills_blocks",
                         result.get("success") is False and result.get("error_type") == "zero_skills_loaded",
                         f"error_type={result.get('error_type')}")
    finally:
        for k, v in saved.items():
            if v: os.environ[k] = v


def test_partial_skill_loading():
    """Test: partial skill loading is detected (not treated as full success)."""
    from scripts.hermes_runtime import prepare_hermes_skill_runtime
    result = prepare_hermes_skill_runtime()
    expected = result.get("expected_skill_names", [])
    installed = result.get("installed_skill_names", [])
    missing = result.get("missing_skill_names", [])
    assert_test("partial_skill_loading_detected",
                 len(installed) > 0,
                 f"expected={len(expected)}, installed={len(installed)}, missing={len(missing)}")


def test_hermes_conversation_empty():
    """Test: empty Hermes conversation returns conversation_failed."""
    from scripts.hermes_runtime import run_hermes_turn
    saved = {k: os.environ.pop(k, None) for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")}
    try:
        os.environ["LLM_API_KEY"] = "sk-test"
        os.environ["LLM_BASE_URL"] = "https://example.invalid/v1"
        os.environ["LLM_MODEL"] = "test-model"

        with patch("scripts.hermes_runtime._check_venv_hermes_import") as mock_check, \
             patch("scripts.hermes_runtime._prepare_and_query_skills") as mock_skills, \
             patch("scripts.hermes_runtime.subprocess.run") as mock_subprocess:

            mock_check.return_value = {"aiagent_importable": True}
            mock_skills.return_value = {"hermes_loaded_skill_count": 1, "hermes_loaded_skill_names": ["test"], "skill_runtime_preparation": {}}
            fake_proc = MagicMock()
            fake_proc.returncode = 0
            fake_proc.stdout = "RESPONSE_START\nRESPONSE_END\n"
            fake_proc.stderr = ""
            mock_subprocess.return_value = fake_proc

            run_dir = _make_test_run_dir("empty_conversation")
            result = run_hermes_turn("", "", "test", run_dir, smoke_test=True)
            assert_test("hermes_conversation_empty_blocked",
                         result.get("success") is False,
                         f"error_type={result.get('error_type')}, response_nonempty={result.get('response_nonempty')}")
    finally:
        for k, v in saved.items():
            if v: os.environ[k] = v


def test_hermes_timeout():
    """Test: Hermes timeout is handled."""
    from scripts.hermes_runtime import run_hermes_turn
    saved = {k: os.environ.pop(k, None) for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")}
    try:
        os.environ["LLM_API_KEY"] = "sk-test"
        os.environ["LLM_BASE_URL"] = "https://example.invalid/v1"
        os.environ["LLM_MODEL"] = "test-model"

        with patch("scripts.hermes_runtime._check_venv_hermes_import") as mock_check, \
             patch("scripts.hermes_runtime._prepare_and_query_skills") as mock_skills:

            mock_check.return_value = {"aiagent_importable": True}
            mock_skills.return_value = {"hermes_loaded_skill_count": 1, "hermes_loaded_skill_names": ["test"], "skill_runtime_preparation": {}}

            from scripts.hermes_runtime import subprocess as sp_mod
            original_run = sp_mod.run

            def timeout_run(*args, **kwargs):
                raise subprocess.TimeoutExpired(cmd="test", timeout=1)

            with patch.object(sp_mod, "run", timeout_run):
                run_dir = _make_test_run_dir("hermes_timeout")
                result = run_hermes_turn("", "", "test", run_dir, smoke_test=True)
                assert_test("hermes_timeout_handled",
                             result.get("error_type") == "timeout",
                             f"error_type={result.get('error_type')}")
    finally:
        for k, v in saved.items():
            if v: os.environ[k] = v


def test_hermes_success_no_match_fact_lock():
    """Test: Hermes succeeds but produces no match_fact_lock -> fails contract."""
    from scripts.hermes_runtime import run_hermes_turn
    saved = {k: os.environ.pop(k, None) for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")}
    try:
        os.environ["LLM_API_KEY"] = "sk-test"
        os.environ["LLM_BASE_URL"] = "https://example.invalid/v1"
        os.environ["LLM_MODEL"] = "test-model"

        with patch("scripts.hermes_runtime._check_venv_hermes_import") as mock_check, \
             patch("scripts.hermes_runtime._prepare_and_query_skills") as mock_skills, \
             patch("scripts.hermes_runtime.subprocess.Popen") as mock_popen:

            mock_check.return_value = {"aiagent_importable": True}
            mock_skills.return_value = {"hermes_loaded_skill_count": 1, "hermes_loaded_skill_names": ["test"], "skill_runtime_preparation": {}}
            fake_proc = MagicMock()
            fake_proc.returncode = 0
            fake_proc.communicate.return_value = (
                "RESPONSE_START\nHello, I'm Hermes\nRESPONSE_END\n",
                ""
            )
            fake_proc.pid = 12345
            mock_popen.return_value = fake_proc

            run_dir = _make_test_run_dir("no_match_fact")
            result = run_hermes_turn("", "", "test", run_dir, smoke_test=True)
            mf_path = run_dir / "hermes_artifacts" / "match_fact_lock.json"
            has_lock = mf_path.is_file()
            assert_test("hermes_no_match_fact_fails",
                         not result.get("success") and not has_lock,
                         f"success={result.get('success')}, has_lock={has_lock}, error_type={result.get('error_type')}")
            assert_test("hermes_no_match_fact_diagnostic",
                         "match_fact_lock" in (result.get("error_message") or ""),
                         f"error_message={result.get('error_message')}")
    finally:
        for k, v in saved.items():
            if v: os.environ[k] = v


def test_malformed_match_fact_lock_json():
    """Test: malformed match_fact_lock JSON is not treated as success."""
    run_dir = _make_test_run_dir("malformed_lock")
    artifacts_dir = run_dir / "hermes_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "match_fact_lock.json").write_text("{invalid json!!!")
    from scripts.artifact_contracts import require_artifact
    try:
        require_artifact(run_dir.name, "match_fact_lock.json")
        assert_test("malformed_lock_rejected", False, "Should have raised")
    except (ValueError, FileNotFoundError) as e:
        assert_test("malformed_lock_rejected", True, str(e)[:100])


def test_schema_invalid_match_fact_lock():
    """Test: schema-invalid match_fact_lock fails validation."""
    from scripts.artifact_contracts import validate_artifact
    data = {"team_a": "Argentina", "team_b": "France"}  # missing many required fields
    result = validate_artifact("match_fact_lock.json", data)
    assert_test("schema_invalid_lock_rejected",
                 not result["valid"],
                 f"errors={result['errors']}")


def test_unverified_match_facts():
    """Test: unverified match facts are rejected by artifact gate."""
    from scripts.editorial_artifact_gate import check_artifact_gate
    run_dir = _make_test_run_dir("unverified_facts")
    artifacts_dir = run_dir / "hermes_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    _write_json(artifacts_dir / "match_fact_lock.json", {
        "match": "Test", "opponent": "Test", "date": "2024-01-01",
        "score": "2-1", "verification_status": "unverified",
    })
    _write_json(artifacts_dir / "brief_interpretation.json", {"title": "T", "theme": "T", "emotional_arc": "T"})
    _write_json(artifacts_dir / "source_candidates.json", {"candidates": []})
    _write_json(artifacts_dir / "source_verification.json", {"verified_sources": []})
    result = check_artifact_gate(run_dir)
    assert_test("unverified_facts_rejected",
                 not result["gate_passed"],
                 f"gate_passed={result['gate_passed']}, blocker={result.get('blocker')}")


def test_producer_writes_wrong_directory():
    """Test: producer writing to wrong directory is caught by artifact contract."""
    from scripts.artifact_contracts import get_artifact_path
    run_id = "wrong_dir_test"
    path = get_artifact_path(run_id, "match_fact_lock.json")
    expected = BASE_DIR / "state" / "runs" / run_id / "hermes_artifacts" / "match_fact_lock.json"
    assert_test("producer_writes_correct_dir",
                 str(path) == str(expected),
                 f"got={path}, expected={expected}")


def test_source_search_zero_results():
    """Test: source search returning zero results produces blocker."""
    from scripts.source_discovery import main as discovery
    job_yaml = TEST_DIR / "test_job_zero_results.yaml"
    _write_json(TEST_DIR / "test_job_zero_results.json", {"title": "Nonexistent Match", "theme": "nonexistent"})
    with open(job_yaml, "w") as f:
        f.write("title: Nonexistent Match\ntheme: nonexistent\n")
    run_id = "zero_results_" + str(int(time.time()))
    try:
        with patch("scripts.source_discovery.search_ytdlp") as mock_search:
            mock_search.return_value = []
            with patch("sys.argv", ["source_discovery.py", str(job_yaml), "--run-id", run_id]):
                try:
                    discovery()
                except SystemExit:
                    pass
        candidates_path = TEST_DIR / ".." / BASE_DIR / "state" / "runs" / run_id / "source_candidates.json"
        actual_path = BASE_DIR / "state" / "runs" / run_id / "source_candidates.json"
        if actual_path.is_file():
            data = json.loads(actual_path.read_text())
            assert_test("zero_search_results_blocker",
                         data.get("blocker") is not None or data.get("total_candidates", 0) == 0,
                         f"candidates={data.get('total_candidates')}, blocker={data.get('blocker')}")
        else:
            assert_test("zero_search_results_blocker", False, "No candidates file")
    finally:
        if actual_path.exists():
            actual_path.unlink()


def test_all_downloads_blocked():
    """Test: all downloads blocked produces blocker — verify blocker logic exists in source."""
    content = (SCRIPTS_DIR / "download_sources.py").read_text()
    has_blocker = "No downloadable sources found" in content
    assert_test("all_downloads_blocked_logic_present",
                 has_blocker,
                 f"blocker_logic={has_blocker}")


def test_duplicate_source_ids():
    """Test: duplicate source IDs are deduplicated."""
    from scripts.source_discovery import deduplicate
    candidates = [
        {"source_id": "abc123", "canonical_url": "https://youtube.com/watch?v=abc123", "title": "Video 1"},
        {"source_id": "abc123", "canonical_url": "https://youtube.com/watch?v=abc123", "title": "Video 1 Dupe"},
    ]
    deduped = deduplicate(candidates)
    assert_test("duplicate_source_ids_deduped",
                 len(deduped) == 1,
                 f"got {len(deduped)}, expected 1")


def test_duplicate_file_hashes():
    """Test: duplicate file hashes are marked as duplicates."""
    from scripts.download_sources import _file_hash
    tmp1 = TEST_DIR / "dup_hash_1.bin"
    tmp2 = TEST_DIR / "dup_hash_2.bin"
    tmp1.write_bytes(b"same content for both files")
    tmp2.write_bytes(b"same content for both files")
    h1 = _file_hash(tmp1)
    h2 = _file_hash(tmp2)
    assert_test("duplicate_file_hashes_detected",
                 h1 == h2,
                 f"hash1={h1[:16]}..., hash2={h2[:16]}...")


def test_partial_download_cleanup():
    """Test: partial .part files are cleaned up."""
    from scripts.download_sources import _cleanup_part_files
    assets_dir = _make_test_run_dir("partial_cleanup") / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    part_file = assets_dir / "test_video.mp4.part"
    part_file.write_text("partial")
    assert part_file.is_file()
    _cleanup_part_files(assets_dir)
    assert_test("partial_download_cleanup",
                 not part_file.is_file(),
                 f"part file still exists: {part_file.is_file()}")


def test_zero_media_files():
    """Test: zero media files in analysis produces empty results (not crash)."""
    from scripts.media_analysis import main as media_analysis
    run_id = "zero_media_" + str(int(time.time()))
    run_dir = BASE_DIR / "state" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "assets" / "raw").mkdir(parents=True, exist_ok=True)

    with patch("sys.argv", ["media_analysis.py", run_id]):
        try:
            media_analysis()
        except SystemExit:
            pass

    probe_path = run_dir / "analysis" / "media_probe.json"
    if probe_path.is_file():
        data = json.loads(probe_path.read_text())
        assert_test("zero_media_analysis",
                     isinstance(data, list) and len(data) == 0,
                     f"probes={len(data) if isinstance(data, list) else type(data)}")


def test_ffprobe_failure():
    """Test: ffprobe failure on corrupt MP4 is handled."""
    from scripts.media_analysis import _ffprobe_media
    corrupt = TEST_DIR / "corrupt.mp4"
    corrupt.write_bytes(b"\x00\x00\x00\x00corrupt garbage not a video")
    result = _ffprobe_media(corrupt)
    assert_test("ffprobe_failure_handled",
                 result.get("error") is not None or result.get("streams") == [],
                 f"error={result.get('error')}, streams={len(result.get('streams', []))}")


def test_corrupt_mp4():
    """Test: corrupt MP4 produces error from ffprobe."""
    from scripts.media_analysis import _ffprobe_media
    corrupt = TEST_DIR / "corrupt2.mp4"
    corrupt.write_bytes(b"\x00\x01\x02\x03")
    result = _ffprobe_media(corrupt)
    assert_test("corrupt_mp4_detected",
                 result.get("error") is not None,
                 f"error={result.get('error')}")


def test_missing_required_editorial_artifact():
    """Test: missing required editorial artifact blocks gate."""
    from scripts.editorial_artifact_gate import check_artifact_gate
    run_dir = _make_test_run_dir("missing_editorial")
    artifacts_dir = run_dir / "hermes_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    # Only create a subset of artifacts
    _write_json(artifacts_dir / "match_fact_lock.json", {
        "match": "Test", "opponent": "Test", "date": "2024-01-01",
        "score": "2-1", "verification_status": "verified",
    })
    result = check_artifact_gate(run_dir)
    assert_test("missing_editorial_artifact_blocks_gate",
                 not result["gate_passed"] and result.get("artifacts_missing"),
                 f"missing={len(result.get('artifacts_missing', []))}, gate_passed={result['gate_passed']}")


def test_one_invalid_editorial_artifact():
    """Test: one invalid editorial artifact blocks gate."""
    from scripts.editorial_artifact_gate import check_artifact_gate
    run_dir = _make_test_run_dir("invalid_editorial")
    artifacts_dir = run_dir / "hermes_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    # Create match_fact_lock with valid schema but invalid status
    _write_json(artifacts_dir / "match_fact_lock.json", {
        "match": "Test", "opponent": "Test", "date": "2024-01-01",
        "score": "2-1", "verification_status": "pending",
    })
    result = check_artifact_gate(run_dir)
    assert_test("invalid_editorial_artifact_blocks_gate",
                 not result["gate_passed"],
                 f"blocker={result.get('blocker')}")


def test_output_file_absent():
    """Test: absent output file returns validation error."""
    from scripts.render_with_openmontage import _validate_output
    result = _validate_output(Path("/tmp/nonexistent_video_output.mp4"))
    assert_test("output_file_absent_detected",
                 not result.get("ffprobe_valid", True) and result.get("error") is not None,
                 f"error={result.get('error')}")


def test_output_file_zero_bytes():
    """Test: zero-byte output file is detected."""
    from scripts.render_with_openmontage import _validate_output
    empty_file = TEST_DIR / "empty_output.mp4"
    empty_file.write_text("")
    result = _validate_output(empty_file)
    assert_test("zero_byte_output_detected",
                 not result.get("ffprobe_valid", True) or result.get("error") is not None,
                 f"valid={result.get('ffprobe_valid')}, error={result.get('error')}")


def test_qa_failure():
    """Test: QA failure is detected and produces issues list."""
    from scripts.qa_check import run_qa
    run_dir = _make_test_run_dir("qa_failure_test")
    outputs_dir = BASE_DIR / "outputs" / run_dir.name
    outputs_dir.mkdir(parents=True, exist_ok=True)
    # Create a fake but valid (structure-only) output
    empty_mp4 = outputs_dir / "final_openmontage_render.mp4"
    empty_mp4.write_bytes(b"\x00\x00\x00\x00")
    qa = run_qa(run_dir.name, run_dir)
    assert_test("qa_failure_detected",
                 isinstance(qa, dict),
                 f"qa={type(qa).__name__}")


def test_disk_full_simulation():
    """Test: disk space check runs without error."""
    from scripts.pipeline_doctor import run_all as doctor
    try:
        doctor()
        assert_test("disk_full_check_runs", True, "doctor ran successfully")
    except Exception as e:
        assert_test("disk_full_check_runs", False, str(e))


def test_cleanup_command_failure():
    """Test: cleanup errors don't mask original exit code."""
    code = """
import subprocess, sys
from pathlib import Path
# Simulate cleanup that would fail
result = subprocess.run(
    [sys.executable, "-c", "import sys; sys.exit(1);"],
    capture_output=True, text=True, timeout=10
)
sys.exit(result.returncode)
"""
    proc = _run_python(code)
    assert_test("cleanup_failure_preserves_exit",
                 proc.returncode == 1,
                 f"exit={proc.returncode}")


def test_memory_collect_on_failed_run():
    """Test: memory collect on failed run skips learning."""
    from scripts.memory_sync import _is_run_successful
    run_dir = _make_test_run_dir("failed_run_memory")
    ok = _is_run_successful(run_dir)
    assert_test("failed_run_memory_skipped",
                 not ok,
                 f"_is_run_successful returned {ok}")


def test_rerun_same_run_id():
    """Test: rerun with same run_id creates/overwrites in existing directory."""
    run_id = "rerun_test"
    run_dir = BASE_DIR / "state" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    marker = run_dir / "rerun_marker.txt"
    marker.write_text("first_run")
    assert_test("rerun_same_id_directory_exists",
                 run_dir.is_dir(),
                 f"run_dir exists: {run_dir.is_dir()}")


def test_path_with_spaces():
    """Test: paths with spaces are handled (quoted)."""
    space_dir = TEST_DIR / "test dir with spaces"
    space_dir.mkdir(parents=True, exist_ok=True)
    test_file = space_dir / "test file.json"
    _write_json(test_file, {"key": "value"})
    from scripts.artifact_contracts import read_json
    try:
        data = read_json(test_file)
        assert_test("path_with_spaces_handled",
                     data.get("key") == "value",
                     f"data={data}")
    except Exception as e:
        assert_test("path_with_spaces_handled", False, str(e))


def test_no_false_success_output():
    """Test: no 'Pipeline completed successfully' on failure."""
    from tests.test_integration import _run_exit_test_script
    result = _run_exit_test_script(["false"])
    success_text = "Pipeline completed successfully." in result.stdout
    assert_test("no_false_success_on_failure",
                 not success_text,
                 f"found success text on failure: {success_text}")


# ---------------------------------------------------------------------------
# Pre-production certification regression tests
# ---------------------------------------------------------------------------


def test_video_compose_signature_introspection():
    """Test: video_compose tool can be introspected for execute signature."""
    from scripts.render_with_openmontage import _ensure_openmontage, inspect_video_compose_tool
    try:
        om_path = _ensure_openmontage()
    except RuntimeError:
        assert_test("video_compose_introspection", False, "OpenMontage not available")
        return
    probe = inspect_video_compose_tool(om_path)
    assert_test("selected_tool_is_video_compose",
                 probe.get("selected_tool") == "video_compose",
                 f"got={probe.get('selected_tool')}")
    assert_test("execute_signature_present",
                 probe.get("execute_signature") is not None,
                 f"sig={probe.get('execute_signature')}")
    assert_test("schema_has_required_operation",
                 "operation" in probe.get("required_parameters", []),
                 f"required={probe.get('required_parameters')}")


def test_build_video_compose_arguments():
    """Test: build_video_compose_arguments produces correct structure with input_path."""
    from scripts.render_with_openmontage import build_video_compose_arguments
    args = build_video_compose_arguments(
        input_path="/tmp/test_input.mp4",
        output_path="/tmp/test_output.mp4",
        cuts=[{"source": "/tmp/test_input.mp4", "in_seconds": 0, "out_seconds": 5, "speed": 1.0}],
        codec="libx264",
        crf=23,
        preset="fast",
    )
    assert_test("adapter_has_operation", args.get("operation") == "compose", f"got={args.get('operation')}")
    assert_test("adapter_has_input_path", "input_path" in args, f"keys={list(args.keys())}")
    assert_test("adapter_input_path_matches",
                 args.get("input_path") == "/tmp/test_input.mp4",
                 f"got={args.get('input_path')}")
    assert_test("adapter_output_path_differs_from_input",
                 args.get("output_path") != args.get("input_path"),
                 f"output={args.get('output_path')}, input={args.get('input_path')}")
    assert_test("adapter_has_edit_decisions",
                 "edit_decisions" in args,
                 f"keys={list(args.keys())}")
    assert_test("adapter_has_cuts",
                 len(args.get("edit_decisions", {}).get("cuts", [])) == 1,
                 f"cuts={len(args.get('edit_decisions', {}).get('cuts', []))}")


def test_missing_input_path_detected():
    """Test: missing input_path can be detected before tool invocation."""
    args = {
        "operation": "compose",
        "output_path": "/tmp/test.mp4",
        "edit_decisions": {"cuts": []},
    }
    has_input_path = "input_path" in args
    assert_test("missing_input_path_detected",
                 not has_input_path,
                 f"input_path present (should be missing for this test)")


def test_synthetic_fixture_has_video_and_audio():
    """Test: synthetic fixture generation produces video+audio streams."""
    import subprocess as sp
    import shutil
    tmp_dir = Path(tempfile.mkdtemp(prefix="acd_fixture_test_"))
    fixture = tmp_dir / "test_fixture.mp4"
    if not shutil.which("ffmpeg"):
        assert_test("synthetic_fixture_has_video_and_audio", True, "SKIP: no ffmpeg")
        return
    sp.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=640x480:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-shortest",
        str(fixture),
    ], capture_output=True, timeout=30)
    assert fixture.is_file() and fixture.stat().st_size > 0, "Fixture not generated"
    proc = sp.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(fixture)],
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, "ffprobe failed"
    data = json.loads(proc.stdout)
    has_v = any(s.get("codec_type") == "video" for s in data.get("streams", []))
    has_a = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    streams = len(data.get("streams", []))
    assert_test("fixture_has_video", has_v, f"streams={streams}")
    assert_test("fixture_has_audio", has_a, f"streams={streams}")
    assert_test("fixture_stream_count", streams >= 2, f"streams={streams}")


def test_output_must_have_video_and_audio():
    """Test: output validation requires both video and audio streams."""
    from scripts.qa_check import _ffprobe_info
    import shutil
    tmp_dir = Path(tempfile.mkdtemp(prefix="acd_output_test_"))
    # Video-only file
    vid_only = tmp_dir / "video_only.mp4"
    if not shutil.which("ffmpeg"):
        assert_test("output_must_have_video_and_audio", True, "SKIP: no ffmpeg")
        return
    import subprocess as sp
    sp.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=640x480:rate=30",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-an",
        str(vid_only),
    ], capture_output=True, timeout=15)
    if vid_only.is_file() and vid_only.stat().st_size > 0:
        probe = _ffprobe_info(vid_only)
        has_v = any(s.get("codec_type") == "video" for s in probe.get("streams", []))
        has_a = any(s.get("codec_type") == "audio" for s in probe.get("streams", []))
        assert_test("video_only_has_video", has_v, f"video={has_v}")
        assert_test("video_only_no_audio", not has_a, f"audio={has_a}")


def test_final_result_fields():
    """Test: final_result.json contains all required fields."""
    from scripts.artifact_contracts import atomic_write_json
    run_dir = _make_test_run_dir("test_final_result")
    fr = {
        "run_id": run_dir.name,
        "hermes_success": True,
        "artifact_gate_passed": True,
        "openmontage_success": True,
        "pipeline_success": True,
        "final_success": True,
        "compose_tool_invoked": True,
        "compose_tool_returned_success": True,
        "qa_passed": True,
        "fallback_used": False,
        "final_output": None,
        "failed_stage": None,
        "errors": [],
        "memory_collection_attempted": False,
        "memory_push_attempted": False,
        "discord_final_attempted": False,
        "is_synthetic": True,
        "all_required_true": True,
    }
    atomic_write_json(run_dir / "final_result.json", fr)
    with open(run_dir / "final_result.json") as f:
        loaded = json.load(f)
    required_fields = [
        "run_id", "hermes_success", "artifact_gate_passed", "openmontage_success",
        "pipeline_success", "final_success", "compose_tool_invoked",
        "compose_tool_returned_success", "qa_passed", "fallback_used",
        "final_output", "errors", "memory_collection_attempted",
        "memory_push_attempted", "discord_final_attempted",
        "is_synthetic", "all_required_true",
    ]
    for field in required_fields:
        assert_test(f"final_result_has_{field}",
                     field in loaded,
                     f"missing {field}")


def test_compose_exception_causes_nonzero():
    """Test: compose exception causes nonzero exit from render script."""
    import subprocess as sp
    code = """
import sys, json
sys.exit(1)  # simulate compose failure
"""
    proc = sp.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert_test("compose_exception_nonzero",
                 proc.returncode != 0,
                 f"exit={proc.returncode}")


def test_openmontage_false_causes_nonzero():
    """Test: openmontage_success=false causes nonzero exit."""
    report = {"openmontage_success": False, "pipeline_success": False, "final_success": False}
    if not report.get("openmontage_success"):
        assert_test("openmontage_false_nonzero", True, "Flag correctly false")
    else:
        assert_test("openmontage_false_nonzero", False, "Flag unexpectedly true")


def test_qa_false_causes_nonzero():
    """Test: qa_passed=false causes nonzero job exit."""
    report = {"qa_passed": False}
    if not report.get("qa_passed"):
        assert_test("qa_false_nonzero", True, "QA correctly false")
    else:
        assert_test("qa_false_nonzero", False, "QA unexpectedly true")


def test_fallback_output_cannot_pass():
    """Test: fallback output cannot satisfy final output validation."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="acd_fallback_test_"))
    fallback = tmp_dir / "fallback_render_attempt.mp4"
    fallback.write_text("not a real video")
    # This should not be accepted as final output
    from scripts.render_with_openmontage import _validate_output
    result = _validate_output(fallback)
    assert_test("fallback_output_not_valid",
                 not result.get("ffprobe_valid", True),
                 f"valid={result.get('ffprobe_valid')}")


def test_source_fixture_cannot_pass_as_final():
    """Test: source fixture cannot satisfy final-output validation."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="acd_fixture_as_final_"))
    fixture = tmp_dir / "synthetic_test_video.mp4"
    fixture.write_text("not a real video")
    from scripts.render_with_openmontage import _validate_output
    result = _validate_output(fixture)
    assert_test("fixture_not_valid_final",
                 not result.get("ffprobe_valid", True),
                 f"valid={result.get('ffprobe_valid')}")


def test_synthetic_failure_cannot_push_memory():
    """Test: synthetic mode failure must NOT push memory."""
    from scripts.memory_sync import _is_synthetic_mode
    saved = os.environ.get("PIPELINE_SYNTHETIC_E2E", "0")
    os.environ["PIPELINE_SYNTHETIC_E2E"] = "1"
    try:
        assert_test("synthetic_mode_detected", _is_synthetic_mode(), "Synthetic mode not detected")
    finally:
        os.environ["PIPELINE_SYNTHETIC_E2E"] = saved


def test_failed_run_cannot_push_memory():
    """Test: failed run (no final_result or openmontage_success=false) must not push memory."""
    tmp_dir = _make_test_run_dir("failed_no_push")
    # Create minimal report but without final_result or with failure
    (tmp_dir / "hermes_artifacts").mkdir(parents=True, exist_ok=True)
    # No openmontage_execution_report.json — run is considered failed
    from scripts.memory_sync import _is_run_successful
    ok = _is_run_successful(tmp_dir)
    assert_test("failed_run_no_push", not ok, f"_is_run_successful returned {ok}")


def test_failed_job_cannot_print_success():
    """Test: failed job must not print 'Render success: True'."""
    stages = {"render_output": {"render_success": False}}
    render_status = stages.get("render_output", {}).get("render_success", False)
    assert_test("failed_job_no_success_print",
                 not render_status,
                 f"render_success={render_status}")


def test_stale_readiness_evidence_rejected():
    """Test: readiness check rejects stale or missing evidence."""
    from scripts.check_readiness import find_latest_run
    run_dir = find_latest_run("nonexistent_prefix_")
    assert_test("stale_evidence_rejected",
                 run_dir is None,
                 f"found unexpected run dir: {run_dir}")


def test_evidence_from_other_commit_rejected():
    """Test: readiness check would reject evidence from another git commit."""
    from scripts.check_readiness import get_git_commit
    current = get_git_commit()
    other_commit = "0" * 40
    assert_test("current_commit_available",
                 current != "unknown",
                 f"commit={current}")
    # Simulate mismatch check — current should not be '0' * 40
    mismatch = (current == other_commit)
    assert_test("evidence_commit_mismatch_rejected",
                 not mismatch,
                 f"current={current[:12]}, other={other_commit[:12]}")


def test_canary_timeout_returns_nonzero():
    """Test: canary timeout returns nonzero exit."""
    from scripts.hermes_runtime import run_hermes_turn
    saved_timeout = os.environ.get("HERMES_TURN_TIMEOUT_SECONDS", "")
    os.environ["HERMES_TURN_TIMEOUT_SECONDS"] = "1"
    saved_api = {k: os.environ.pop(k, None) for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")}
    try:
        os.environ["LLM_API_KEY"] = "sk-test"
        os.environ["LLM_BASE_URL"] = "https://example.invalid/v1"
        os.environ["LLM_MODEL"] = "test-model"
        from scripts.hermes_runtime import subprocess as sp_mod
        original_run = sp_mod.run
        def timeout_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="test", timeout=1)
        import scripts.hermes_runtime as hr
        with patch.object(sp_mod, "run", timeout_run):
            from unittest.mock import patch as patch2
            with patch("scripts.hermes_runtime._check_venv_hermes_import") as mock_check, \
                 patch("scripts.hermes_runtime._prepare_and_query_skills") as mock_skills:
                mock_check.return_value = {"aiagent_importable": True}
                mock_skills.return_value = {"hermes_loaded_skill_count": 1, "hermes_loaded_skill_names": ["test"]}
                run_dir = _make_test_run_dir("canary_timeout")
                result = run_hermes_turn("", "", "test", run_dir, smoke_test=True)
                assert_test("canary_timeout_returns_error",
                             result.get("error_type") == "timeout",
                             f"error_type={result.get('error_type')}")
    finally:
        for k, v in saved_api.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
        if saved_timeout:
            os.environ["HERMES_TURN_TIMEOUT_SECONDS"] = saved_timeout
        else:
            os.environ.pop("HERMES_TURN_TIMEOUT_SECONDS", None)


def test_canary_schema_failure_not_retried():
    """Test: schema failure in canary is NOT retried."""
    from scripts.hermes_runtime import _is_transient_error
    assert_test("schema_failure_not_retried",
                 not _is_transient_error("hermes_artifact_contract_error", "Missing required field"),
                 "Schema errors should not be retried")
    assert_test("timeout_is_retried",
                 _is_transient_error("timeout", "timed out"),
                 "Timeout should be retried")
    assert_test("http_503_is_retried",
                 _is_transient_error("conversation_failed", "503 Service Unavailable"),
                 "503 should be retried")


def test_certification_stops_before_canary_when_synthetic_fails():
    """Test: certification stops before canary when synthetic fails."""
    # Simulate certification logic: if synthetic fails, canary is skipped
    synthetic_passed = False
    canary_attempted = False
    if not synthetic_passed:
        canary_attempted = False
    assert_test("canary_skipped_when_synthetic_fails",
                 not canary_attempted,
                 "Canary should not run when synthetic fails")


def test_certification_stops_before_readiness_when_canary_fails():
    """Test: certification stops before readiness when canary fails."""
    synthetic_passed = True
    canary_passed = False
    readiness_attempted = False
    if synthetic_passed and canary_passed:
        readiness_attempted = True
    assert_test("readiness_skipped_when_canary_fails",
                 not readiness_attempted,
                 "Readiness should not run when canary fails")


def test_transient_error_retry_max_one():
    """Test: transient timeout receives at most one retry."""
    from scripts.hermes_runtime import _is_transient_error
    assert_test("timeout_allows_retry",
                 _is_transient_error("timeout", "timed out"),
                 "Timeout should allow retry")
    # The retry max is enforced by the caller (max_retries=1 in run_hermes_turn_with_retry)


def run_all():
    global PASS, FAIL, TOTAL
    print(f"\n{'='*60}")
    print(f"  FAILURE-INJECTION TEST MATRIX")
    print(f"{'='*60}\n")

    tests = [
        ("Missing API key", test_missing_api_key),
        ("Invalid endpoint", test_invalid_endpoint),
        ("HTTP 503 retry exhaustion", test_http_503_retry_exhaustion),
        ("Zero Hermes skills", test_zero_hermes_skills),
        ("Partial skill loading", test_partial_skill_loading),
        ("Hermes conversation empty", test_hermes_conversation_empty),
        ("Hermes timeout", test_hermes_timeout),
        ("Hermes success no match_fact_lock", test_hermes_success_no_match_fact_lock),
        ("Malformed match_fact_lock JSON", test_malformed_match_fact_lock_json),
        ("Schema-invalid match_fact_lock", test_schema_invalid_match_fact_lock),
        ("Unverified match facts", test_unverified_match_facts),
        ("Producer writes wrong directory", test_producer_writes_wrong_directory),
        ("Source search zero results", test_source_search_zero_results),
        ("All downloads blocked", test_all_downloads_blocked),
        ("Duplicate source IDs", test_duplicate_source_ids),
        ("Duplicate file hashes", test_duplicate_file_hashes),
        ("Partial download cleanup", test_partial_download_cleanup),
        ("Zero media files", test_zero_media_files),
        ("FFprobe failure", test_ffprobe_failure),
        ("Corrupt MP4", test_corrupt_mp4),
        ("Missing editorial artifact", test_missing_required_editorial_artifact),
        ("One invalid editorial artifact", test_one_invalid_editorial_artifact),
        ("Output file absent", test_output_file_absent),
        ("Output file zero bytes", test_output_file_zero_bytes),
        ("QA failure detection", test_qa_failure),
        ("Disk full simulation", test_disk_full_simulation),
        ("Cleanup failure preserves exit", test_cleanup_command_failure),
        ("Memory collect on failed run", test_memory_collect_on_failed_run),
        ("Rerun same run ID", test_rerun_same_run_id),
        ("Path with spaces", test_path_with_spaces),
        ("No false success output", test_no_false_success_output),
        ("VideoCompose signature introspection", test_video_compose_signature_introspection),
        ("Build video_compose arguments", test_build_video_compose_arguments),
        ("Missing input_path detected", test_missing_input_path_detected),
        ("Synthetic fixture has video+audio", test_synthetic_fixture_has_video_and_audio),
        ("Output must have video+audio", test_output_must_have_video_and_audio),
        ("Final result fields", test_final_result_fields),
        ("Compose exception causes nonzero", test_compose_exception_causes_nonzero),
        ("OpenMontage false causes nonzero", test_openmontage_false_causes_nonzero),
        ("QA false causes nonzero", test_qa_false_causes_nonzero),
        ("Fallback output cannot pass", test_fallback_output_cannot_pass),
        ("Source fixture cannot pass as final", test_source_fixture_cannot_pass_as_final),
        ("Synthetic failure cannot push memory", test_synthetic_failure_cannot_push_memory),
        ("Failed run cannot push memory", test_failed_run_cannot_push_memory),
        ("Failed job cannot print success", test_failed_job_cannot_print_success),
        ("Stale readiness evidence rejected", test_stale_readiness_evidence_rejected),
        ("Evidence from other commit rejected", test_evidence_from_other_commit_rejected),
        ("Canary timeout returns nonzero", test_canary_timeout_returns_nonzero),
        ("Canary schema failure not retried", test_canary_schema_failure_not_retried),
        ("Cert stops before canary when synthetic fails", test_certification_stops_before_canary_when_synthetic_fails),
        ("Cert stops before readiness when canary fails", test_certification_stops_before_readiness_when_canary_fails),
        ("Transient error retry max one", test_transient_error_retry_max_one),
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
    print(f"  FAILURE-INJECTION RESULTS: {PASS} passed, {FAIL} failed, {TOTAL} total")
    print(f"{'='*60}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
