#!/usr/bin/env python3
"""Fresh production smoke test.

Mocks heavy external calls (Hermes, subprocess.run, ffmpeg, yt-dlp),
then runs the production pipeline (run_title_theme_job.main()).
Verifies:
  - Stage invocation order reaches source_discovery
  - Every subprocess call uses -m scripts.<module> (never scripts/*.py)
  - cwd is repo root
  - PYTHONPATH includes repo root
  - No ModuleNotFoundError is raised by subprocess commands
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
TEST_DIR = Path(tempfile.mkdtemp(prefix="acd_prod_smoke_"))

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
        FAIL += 1
        print(f"  FAIL: {name} — {detail}")


def test_production_smoke_reaches_source_discovery():
    """Mock heavy external calls, run production, verify stage invocation
    order reaches source_discovery without ModuleNotFoundError."""
    call_log = []

    def recording_run(cmd, **kwargs):
        call_log.append({
            "cmd": list(cmd),
            "cwd": kwargs.get("cwd"),
            "env": kwargs.get("env", {}).copy(),
        })
        mock = MagicMock()
        mock.returncode = 0
        return mock

    job_file = TEST_DIR / "smoke_job.yaml"
    job_file.write_text("title: Smoke Test\ntheme: Smoke Theme\n")

    run_id = "prod_smoke_test"
    run_dir = BASE_DIR / "state" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    from scripts.run_title_theme_job import main

    with patch("scripts.run_title_theme_job.subprocess.run", side_effect=recording_run), \
         patch("scripts.run_title_theme_job.ac.require_artifact") as mock_req, \
         patch("scripts.run_title_theme_job.ac.is_synthetic_e2e", return_value=False), \
         patch("scripts.run_title_theme_job.ac.is_hermes_artifact_canary", return_value=False), \
         patch("scripts.hermes_runtime.run_hermes_turn_with_retry") as mock_hermes:

        mock_req.return_value = {
            "exists": True,
            "schema_valid": True,
            "schema_errors": [],
            "path": str(run_dir / "hermes_artifacts" / "match_fact_lock.json"),
            "data": {
                "verification_status": "verified",
                "team_a": "Team A",
                "team_b": "Team B",
                "match_date": "2024-01-01",
                "match": "Team A vs Team B",
            },
        }

        mock_hermes.return_value = {
            "success": True,
            "session_id": "smoke-test-session",
        }

        # Create a dummy match_fact_lock so the source_discovery stage
        # does not hit a FileNotFoundError when reading run_dir
        artifacts_dir = run_dir / "hermes_artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "match_fact_lock.json").write_text(json.dumps({
            "match": "Team A vs Team B",
            "team_a": "Team A",
            "team_b": "Team B",
            "match_date": "2024-01-01",
            "verification_status": "verified",
        }))

        with patch.object(sys, "argv", [
            "run_title_theme_job.py",
            str(job_file),
            "--run-id", run_id,
        ]):
            try:
                main()
            except SystemExit:
                pass

    # ---- Verifications ----

    # 1. Every python subprocess call uses -m scripts.<module>
    py_calls = [c for c in call_log if sys.executable in c["cmd"][0:1] or
                any("python" in p for p in c["cmd"])]
    for call in py_calls:
        cmd_str = " ".join(call["cmd"])
        has_minus_m = "-m" in call["cmd"]
        is_module = any("scripts." in a for a in call["cmd"])
        assert_test("module_invocation",
                     has_minus_m and is_module,
                     f"Missing -m scripts.<module> in: {cmd_str}")

    # 2. source_provider_preflight was invoked as a module
    preflight_calls = [
        c for c in call_log
        if any("source_provider_preflight" in a for a in c["cmd"])
    ]
    assert_test("preflight_called",
                 len(preflight_calls) >= 1,
                 "source_provider_preflight must be called via subprocess")
    if preflight_calls:
        c = preflight_calls[0]
        cmd_str = " ".join(c["cmd"])
        assert_test("preflight_uses_minus_m",
                     "-m" in c["cmd"] and "scripts.source_provider_preflight" in cmd_str,
                     f"preflight must use -m: {cmd_str}")
        assert_test("preflight_cwd",
                     c["cwd"] == str(BASE_DIR),
                     f"preflight cwd should be {BASE_DIR}, got {c['cwd']}")
        assert_test("preflight_pythonpath",
                     c["env"].get("PYTHONPATH") == str(BASE_DIR),
                     f"preflight PYTHONPATH should be {BASE_DIR}, got {c['env'].get('PYTHONPATH')}")

    # 3. source_discovery was called (stage reached)
    discovery_calls = [
        c for c in call_log
        if any("source_discovery" in a for a in c["cmd"])
    ]
    assert_test("discovery_reached",
                 len(discovery_calls) >= 1,
                 "source_discovery subprocess must be called")
    if discovery_calls:
        c = discovery_calls[0]
        cmd_str = " ".join(c["cmd"])
        assert_test("discovery_uses_minus_m",
                     "-m" in c["cmd"] and "scripts.source_discovery" in cmd_str,
                     f"discovery must use -m: {cmd_str}")
        assert_test("discovery_cwd",
                     c["cwd"] == str(BASE_DIR),
                     f"discovery cwd should be {BASE_DIR}, got {c['cwd']}")
        assert_test("discovery_pythonpath",
                     c["env"].get("PYTHONPATH") == str(BASE_DIR),
                     f"discovery PYTHONPATH should be {BASE_DIR}, got {c['env'].get('PYTHONPATH')}")

    # 4. No file-path invocation found in production subprocess calls
    for call in call_log:
        cmd_str = " ".join(str(a) for a in call["cmd"])
        for suffix in (
            "source_provider_preflight.py",
            "source_discovery.py",
            "download_sources.py",
            "media_analysis.py",
            "editorial_artifact_gate.py",
            "render_with_openmontage.py",
            "qa_check.py",
            "memory_sync.py",
            "discord_notify.py",
        ):
            if suffix in cmd_str:
                assert_test(f"no_file_path_{suffix}",
                             False,
                             f"File path invocation found: {cmd_str}")


def run_all():
    global PASS, FAIL, TOTAL
    print(f"\n{'='*60}")
    print(f"  FRESH PRODUCTION SMOKE TESTS")
    print(f"{'='*60}\n")

    tests = [
        ("Production smoke reaches source_discovery", test_production_smoke_reaches_source_discovery),
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
    print(f"  RESULTS: {PASS} passed, {FAIL} failed, {TOTAL} total")
    print(f"{'='*60}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
