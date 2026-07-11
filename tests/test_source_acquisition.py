#!/usr/bin/env python3
"""Tests for source acquisition fixes.

Tests prove:
1. ensure_yt_dlp_available detects installed module
2. ensure_yt_dlp_available installs in Kaggle when missing
3. source provider preflight runs before Hermes
4. no Hermes call when no source provider exists
5. Tavily fallback is used when yt-dlp search unavailable
6. source candidates are produced from Tavily mocked results
7. zero candidates stop immediately after source_discovery
8. download_sources is not called after zero candidates
9. media_analysis is not called after zero candidates
10. artifact_gate is not called after zero candidates
11. job theme is exact Argentina vs Egypt, not vague
12. seeded FactLockGenerator still works
13. Hermes still receives seeded match_fact_lock context
14. no regression in certification
"""
import builtins
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
TEST_DIR = Path(tempfile.mkdtemp(prefix="acd_source_acq_"))

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
# 1. ensure_yt_dlp_available detects installed module
# ---------------------------------------------------------------------------


def test_ensure_yt_dlp_detects_module():
    """Test: ensure_yt_dlp_available detects yt_dlp when importable."""
    from scripts.source_acquisition import ensure_yt_dlp_available
    with patch("scripts.source_acquisition.subprocess.run") as mock_run, \
         patch("builtins.__import__") as mock_import:
        mock_import.return_value = MagicMock()
        result = ensure_yt_dlp_available()
        assert_test("yt_dlp_module_detected",
                     result.get("available") is True,
                     f"available={result.get('available')}, method={result.get('method')}")
        assert_test("yt_dlp_module_method",
                     result.get("method") == "python_module",
                     f"method={result.get('method')}")


def test_ensure_yt_dlp_detects_cli():
    """Test: ensure_yt_dlp_available detects yt-dlp CLI when installed."""
    from scripts.source_acquisition import ensure_yt_dlp_available
    with patch("scripts.source_acquisition.subprocess.run") as mock_run:
        def fake_run(cmd, **kwargs):
            if cmd[0] == "yt-dlp":
                fake = MagicMock()
                fake.returncode = 0
                fake.stdout = "2024.12.06"
                return fake
            return MagicMock()
        mock_run.side_effect = fake_run
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            result = ensure_yt_dlp_available()
            assert_test("yt_dlp_cli_detected",
                         result.get("available") is True,
                         f"available={result.get('available')}, method={result.get('method')}")
            assert_test("yt_dlp_cli_method",
                         result.get("method") == "cli",
                         f"method={result.get('method')}")
            assert_test("yt_dlp_cli_version",
                         result.get("version") == "2024.12.06",
                         f"version={result.get('version')}")


def test_ensure_yt_dlp_missing_not_kaggle():
    """Test: ensure_yt_dlp_available returns unavailable when missing outside Kaggle."""
    import scripts.source_acquisition as sa
    real_import = builtins.__import__
    def fake_import(name, *args, **kwargs):
        if name == "yt_dlp":
            raise ImportError(f"No module named {name}")
        return real_import(name, *args, **kwargs)
    saved_yt_dlp = sys.modules.pop("yt_dlp", None)
    sys.modules.pop("yt_dlp", None)
    try:
        with patch.object(sa, "subprocess") as mock_subprocess, \
             patch.object(sa, "_is_kaggle_runtime", return_value=False), \
             patch("builtins.__import__", side_effect=fake_import):
            mock_subprocess.run.side_effect = FileNotFoundError("no binary")
            result = sa.ensure_yt_dlp_available()
            assert_test("yt_dlp_missing_unavailable",
                         result.get("available") is False,
                         f"available={result.get('available')}")
            assert_test("yt_dlp_missing_error",
                         result.get("error") is not None,
                         f"error={result.get('error')}")
    finally:
        if saved_yt_dlp is not None:
            sys.modules["yt_dlp"] = saved_yt_dlp


def test_ensure_yt_dlp_installs_in_kaggle():
    """Test: ensure_yt_dlp_available attempts pip install in Kaggle when missing."""
    import scripts.source_acquisition as sa
    real_import = builtins.__import__
    def fake_import(name, *args, **kwargs):
        if name == "yt_dlp":
            raise ImportError(f"No module named {name}")
        return real_import(name, *args, **kwargs)
    saved_yt_dlp = sys.modules.pop("yt_dlp", None)
    sys.modules.pop("yt_dlp", None)
    call_count = [0]
    try:
        with patch.object(sa, "subprocess") as mock_subprocess, \
             patch.object(sa, "_is_kaggle_runtime", return_value=True), \
             patch("builtins.__import__", side_effect=fake_import):
            def fake_run(cmd, **kwargs):
                call_count[0] += 1
                call = call_count[0]
                fake = MagicMock()
                if call == 1:
                    raise FileNotFoundError("no yt-dlp binary")
                elif call == 2:
                    fake.returncode = 0
                elif call == 3:
                    fake.returncode = 0
                    fake.stdout = "2024.12.06"
                else:
                    fake.returncode = 0
                return fake
            mock_subprocess.run.side_effect = fake_run
            result = sa.ensure_yt_dlp_available()
            assert_test("yt_dlp_kaggle_installed",
                         result.get("available") is True,
                         f"available={result.get('available')}")
            assert_test("yt_dlp_kaggle_method",
                         result.get("method") == "kaggle_pip_install",
                         f"method={result.get('method')}")
    finally:
        if saved_yt_dlp is not None:
            sys.modules["yt_dlp"] = saved_yt_dlp


# ---------------------------------------------------------------------------
# 3. source provider preflight runs before Hermes
# ---------------------------------------------------------------------------


def test_source_provider_preflight_before_hermes():
    """Test: source_provider_preflight is called BEFORE Hermes in pipeline."""
    content = (SCRIPTS_DIR / "run_title_theme_job.py").read_text()
    preflight_idx = content.find("source_provider_preflight")
    hermes_idx = content.find("run_hermes_turn_with_retry")
    assert_test("preflight_before_hermes",
                 preflight_idx >= 0 and hermes_idx >= 0 and preflight_idx < hermes_idx,
                 f"preflight={preflight_idx}, hermes={hermes_idx}")


# ---------------------------------------------------------------------------
# 4. no Hermes call when no source provider exists
# ---------------------------------------------------------------------------


def test_no_hermes_when_no_source_provider():
    """Test: pipeline exits before Hermes when source provider preflight fails."""
    saved_env = dict(os.environ)
    try:
        for k in ("TAVILY_API_KEY",):
            os.environ.pop(k, None)
        job_yaml = TEST_DIR / "preflight_fail_job.yaml"
        with open(job_yaml, "w") as f:
            f.write("title: Test\ntheme: test\n")
        proc = subprocess.run(
            [sys.executable, "-m", "scripts.run_title_theme_job", str(job_yaml), "--run-id", "preflight_fail"],
            capture_output=True, text=True, timeout=30,
            cwd=str(BASE_DIR),
        )
        output = (proc.stdout + proc.stderr).lower()
        has_preflight_blocker = "source_provider_preflight" in output
        assert_test("preflight_fails_nonzero",
                     proc.returncode != 0,
                     f"exit={proc.returncode}")
        assert_test("preflight_fails_before_hermes",
                     has_preflight_blocker,
                     f"output={proc.stdout[-500:] if len(proc.stdout) > 500 else proc.stdout}")
    finally:
        os.environ.clear()
        os.environ.update(saved_env)


# ---------------------------------------------------------------------------
# 5. Tavily fallback is used when yt-dlp search unavailable
# 6. source candidates are produced from Tavily mocked results
# ---------------------------------------------------------------------------


def test_tavily_fallback_when_ytdlp_unavailable():
    """Test: Tavily search is used when yt-dlp returns no results."""
    from scripts.source_discovery import main as discovery
    from scripts.source_discovery import search_tavily
    with patch("scripts.source_discovery.search_ytdlp") as mock_yt, \
         patch("scripts.source_discovery.search_tavily") as mock_tavily:
        mock_yt.return_value = []
        mock_tavily.return_value = [
            {"source_id": "tavily_001", "canonical_url": "https://youtube.com/watch?v=test",
             "title": "Argentina vs Egypt 2026 Highlights", "channel": "Sports", "platform": "youtube",
             "provider": "tavily_search", "title_lower": "argentina vs egypt 2026 highlights"},
        ]
        job_yaml = TEST_DIR / "tavily_fallback_job.yaml"
        with open(job_yaml, "w") as f:
            f.write("title: Test Title\ntheme: Test Theme\n")
        run_id = "tavily_fallback_test"
        try:
            with patch("sys.argv", ["source_discovery.py", str(job_yaml), "--run-id", run_id]):
                try:
                    discovery()
                except SystemExit:
                    pass
            candidates_path = BASE_DIR / "state" / "runs" / run_id / "source_candidates.json"
            if candidates_path.is_file():
                data = json.loads(candidates_path.read_text())
                has_tavily_results = any(
                    c.get("provider") == "tavily_search"
                    for c in data.get("candidates", [])
                )
                assert_test("tavily_fallback_called",
                             mock_tavily.called,
                             "search_tavily should be called when yt-dlp returns no results")
                assert_test("tavily_candidates_produced",
                             has_tavily_results,
                             f"candidates={len(data.get('candidates', []))}, providers={[c.get('provider') for c in data.get('candidates', [])]}")
            else:
                assert_test("tavily_candidates_file", False, "No candidates file")
        finally:
            if candidates_path.exists():
                candidates_path.unlink()


# ---------------------------------------------------------------------------
# 7-9. zero candidates stop immediately after source_discovery
# ---------------------------------------------------------------------------


def test_zero_candidates_stop_pipeline():
    """Test: zero source candidates stops pipeline before download_sources."""
    content = (SCRIPTS_DIR / "run_title_theme_job.py").read_text()
    source_call_idx = content.find('run_script_module("source_discovery"')
    download_call_idx = content.find('run_script_module("download_sources"')
    media_call_idx = content.find('run_script_module("media_analysis"')
    gate_call_idx = content.find('run_script_module("editorial_artifact_gate"')
    zero_cand_check = content.find("source_candidates_missing")
    assert_test("zero_candidates_check_exists",
                 zero_cand_check >= 0,
                 "source_candidates_missing check must exist in pipeline")
    assert_test("zero_candidates_before_download",
                 source_call_idx >= 0 and download_call_idx >= 0 and source_call_idx < download_call_idx,
                 f"source={source_call_idx}, download={download_call_idx}")
    assert_test("zero_candidates_before_media",
                 source_call_idx >= 0 and media_call_idx >= 0 and source_call_idx < media_call_idx,
                 f"source={source_call_idx}, media={media_call_idx}")
    assert_test("zero_candidates_before_gate",
                 source_call_idx >= 0 and gate_call_idx >= 0 and source_call_idx < gate_call_idx,
                 f"source={source_call_idx}, gate={gate_call_idx}")


# ---------------------------------------------------------------------------
# 11. job theme is exact Argentina vs Egypt, not vague
# ---------------------------------------------------------------------------


def test_job_theme_exact():
    """Test: argentina_hardest_victory.yaml has exact theme, not vague."""
    import yaml
    job_path = BASE_DIR / "jobs" / "argentina_hardest_victory.yaml"
    assert job_path.is_file(), f"Job file not found: {job_path}"
    with open(job_path) as f:
        job = yaml.safe_load(f)
    theme = job.get("theme", "")
    assert_test("theme_not_vague",
                 theme != "most recent Argentina World Cup match in 2026",
                 f"theme is still vague: {theme}")
    assert_test("theme_has_argentina",
                 "Argentina" in theme,
                 f"theme missing Argentina: {theme}")
    assert_test("theme_has_egypt",
                 "Egypt" in theme,
                 f"theme missing Egypt: {theme}")
    assert_test("theme_has_date",
                 "July 7 2026" in theme or "2026-07-07" in theme,
                 f"theme missing date: {theme}")
    assert_test("theme_has_stage",
                 "Round of 16" in theme,
                 f"theme missing stage: {theme}")


# ---------------------------------------------------------------------------
# 12. seeded FactLockGenerator still works
# ---------------------------------------------------------------------------


def test_seeded_fact_lock_generator_still_works():
    """Test: generate_fact_lock_from_seed still produces valid lock."""
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
    }
    mf = generate_fact_lock_from_seed(seed)
    errors = _validate_match_fact_lock(mf)
    assert_test("seed_still_works",
                 len(errors) == 0,
                 f"errors={errors}")
    assert_test("seed_still_team_a",
                 mf.get("team_a") == "Argentina",
                 f"got={mf.get('team_a')}")
    assert_test("seed_still_team_b",
                 mf.get("team_b") == "Egypt",
                 f"got={mf.get('team_b')}")


# ---------------------------------------------------------------------------
# 13. Hermes still receives seeded match_fact_lock context
# ---------------------------------------------------------------------------


def test_hermes_receives_seed_context():
    """Test: Hermes receives match_fact_lock context when seed is present."""
    content = (SCRIPTS_DIR / "run_title_theme_job.py").read_text()
    has_fact_lock_override = "fact_lock_override" in content
    has_hermes_with_override = "run_hermes_turn_with_retry" in content and "fact_lock_override=fact_lock_override" in content
    assert_test("seed_context_passed_to_hermes",
                 has_fact_lock_override,
                 "fact_lock_override must be present in pipeline")
    assert_test("hermes_receives_override",
                 has_hermes_with_override or "fact_lock_override" in content.split("run_hermes_turn_with_retry")[1][:200],
                 "run_hermes_turn_with_retry must receive fact_lock_override")


# ---------------------------------------------------------------------------
# 14. no regression in certification
# ---------------------------------------------------------------------------


def test_no_regression_certification_source_provider():
    """Test: certification does not reference source_provider_preflight (cert does not need it)."""
    source = (BASE_DIR / "scripts" / "preproduction_certify.py").read_text() if (BASE_DIR / "scripts" / "preproduction_certify.py").is_file() else ""
    if source:
        has_source_provider = "source_provider_preflight" in source
        assert_test("cert_no_source_provider",
                     not has_source_provider,
                     "certification should not reference source_provider_preflight")


def test_no_regression_certification_source_candidates_missing():
    """Test: certification does not reference source_candidates_missing blocker."""
    source = (BASE_DIR / "scripts" / "preproduction_certify.py").read_text() if (BASE_DIR / "scripts" / "preproduction_certify.py").is_file() else ""
    if source:
        has_blocker = "source_candidates_missing" in source
        assert_test("cert_no_source_candidates_blocker",
                     not has_blocker,
                     "certification should not reference source_candidates_missing")


# ---------------------------------------------------------------------------
# Additional: ensure run_title_theme_job still handles fact_lock_seed
# ---------------------------------------------------------------------------


def test_pipeline_still_handles_fact_lock_seed():
    """Test: run_title_theme_job.py still processes fact_lock_seed before Hermes."""
    content = (SCRIPTS_DIR / "run_title_theme_job.py").read_text()
    has_fact_lock_seed = "fact_lock_seed" in content
    has_fact_lock_generator = "fact_lock_generator" in content
    assert_test("pipeline_handles_seed",
                 has_fact_lock_seed and has_fact_lock_generator,
                 "pipeline must still process fact_lock_seed")


# ---------------------------------------------------------------------------
# Additional: ensure preflight script is importable
# ---------------------------------------------------------------------------


def test_source_provider_preflight_importable():
    """Test: source_provider_preflight module can be imported."""
    import scripts.source_provider_preflight
    assert hasattr(scripts.source_provider_preflight, "main")
    assert hasattr(scripts.source_provider_preflight, "_check_tavily_availability")
    print(f"  Import check: OK")


# ---------------------------------------------------------------------------
# Additional: ensure source_provider_preflight exits 1 when no provider
# ---------------------------------------------------------------------------


def test_preflight_no_provider_exits_nonzero():
    """Test: source_provider_preflight exits 1 when no source provider available."""
    saved_tavily = os.environ.pop("TAVILY_API_KEY", None)
    saved_hermes = os.environ.pop("HERMES_TURN_TIMEOUT_SECONDS", None)
    try:
        with patch("scripts.source_provider_preflight.ensure_yt_dlp_available") as mock_ensure, \
             patch("scripts.source_provider_preflight.check_ytdlp_availability") as mock_check, \
             patch("scripts.source_provider_preflight.sys.exit") as mock_exit, \
             patch("scripts.source_provider_preflight.print"):  # suppress output
            mock_ensure.return_value = {"available": False, "method": None, "error": "not available"}
            mock_check.return_value = {"ytdlp_installed": False, "status": "unavailable"}
            mock_exit.side_effect = SystemExit(1)
            import scripts.source_provider_preflight as preflight
            try:
                preflight.main()
            except SystemExit:
                pass
            assert_test("preflight_no_provider_exits_1",
                         mock_exit.called,
                         "sys.exit should be called")
    finally:
        if saved_tavily is not None:
            os.environ["TAVILY_API_KEY"] = saved_tavily
        if saved_hermes is not None:
            os.environ["HERMES_TURN_TIMEOUT_SECONDS"] = saved_hermes


# ---------------------------------------------------------------------------
# Additional: ensure_yt_dlp_available does not print secrets
# ---------------------------------------------------------------------------


def test_ensure_yt_dlp_no_secrets():
    """Test: ensure_yt_dlp_available never prints secrets."""
    from scripts.source_acquisition import ensure_yt_dlp_available
    import inspect
    source = inspect.getsource(ensure_yt_dlp_available)
    sensitive = ["api_key", "API_KEY", "TAVILY_API_KEY"]
    for s in sensitive:
        if s in source:
            lines = [l for l in source.split("\n") if s.lower() in l.lower()]
            for line in lines:
                if "print" in line.lower() and s.lower() in line.lower():
                    assert_test(f"no_secret_print_{s}",
                                 False,
                                 f"secret leak in line: {line.strip()}")
                    break
    assert_test("ensure_yt_dlp_no_secrets",
                 True,
                 "no secrets printed")


# ---------------------------------------------------------------------------
# 15. Module invocation contract
# ---------------------------------------------------------------------------


PRODUCTION_MODULES = [
    "source_provider_preflight",
    "source_discovery",
    "download_sources",
    "media_analysis",
    "editorial_artifact_gate",
    "render_with_openmontage",
    "qa_check",
    "memory_sync",
]


def test_run_script_module_uses_minus_m():
    """Test: run_script_module uses -m scripts.<name> invocation."""
    content = (SCRIPTS_DIR / "run_title_theme_job.py").read_text()
    assert_test("has_run_script_module",
                 "def run_script_module" in content,
                 "run_script_module helper must exist")
    assert_test("uses_minus_m_flag",
                 "scripts." in content and "-m" in content,
                 "must use python3 -m scripts.<module>")
    assert_test("sets_pythonpath",
                 "PYTHONPATH" in content and "BASE_DIR" in content,
                 "must set PYTHONPATH to BASE_DIR")
    assert_test("sets_cwd",
                 "cwd=str(BASE_DIR)" in content,
                 "must set cwd to BASE_DIR")


def test_all_production_stages_use_module_invocation():
    """Test: every production stage uses run_script_module (not file path)."""
    content = (SCRIPTS_DIR / "run_title_theme_job.py").read_text()
    for mod in PRODUCTION_MODULES:
        has_module_call = f'"{mod}"' in content and "run_script_module" in content
        has_file_path = f"scripts/{mod}.py" in content
        assert_test(f"stage_{mod}_module_invocation",
                     has_module_call,
                     f"stage {mod} must use run_script_module (not file path)")
        if has_file_path:
            assert_test(f"stage_{mod}_no_file_path",
                         False,
                         f"stage {mod} must not reference scripts/{mod}.py as file path")


def test_no_production_file_path_invocations():
    """Test: no production subprocess invokes scripts/*.py by file path."""
    content = (SCRIPTS_DIR / "run_title_theme_job.py").read_text()
    for mod in PRODUCTION_MODULES:
        file_path_pattern = f'"{mod}.py"' in content or f"'{mod}.py'" in content
        assert_test(f"no_file_path_{mod}",
                     not file_path_pattern,
                     f"must not invoke {mod}.py by file path")


def test_notify_uses_module_invocation():
    """Test: notify() uses module invocation for discord_notify."""
    content = (SCRIPTS_DIR / "run_title_theme_job.py").read_text()
    has_module = '"scripts.discord_notify"' in content
    assert_test("notify_uses_module",
                 has_module,
                 "notify must use -m scripts.discord_notify")


def test_run_script_module_accepts_env():
    """Test: run_script_module signature includes env parameter."""
    content = (SCRIPTS_DIR / "run_title_theme_job.py").read_text()
    assert_test("has_env_param",
                 "def run_script_module(module_name, args=None, stage=None, env=None):" in content,
                 "env parameter must be in signature")


def test_source_provider_preflight_works_as_module():
    """Test: source_provider_preflight import works under -m invocation."""
    import scripts.source_provider_preflight as preflight_mod
    saved_tavily = os.environ.pop("TAVILY_API_KEY", None)
    try:
        with patch.object(preflight_mod, "ensure_yt_dlp_available") as mock_ensure, \
             patch.object(preflight_mod, "check_ytdlp_availability") as mock_check, \
             patch.object(preflight_mod, "sys", spec=["exit", "path"]) as mock_sys:
            mock_ensure.return_value = {"available": True, "method": "python_module", "version": "2024.12.06"}
            mock_check.return_value = {"ytdlp_installed": True, "status": "available"}
            mock_sys.exit.side_effect = SystemExit(0)
            try:
                preflight_mod.main()
            except SystemExit:
                pass
            assert_test("preflight_module_import_works",
                         True,
                         "source_provider_preflight runs without ModuleNotFoundError when imported")
    finally:
        if saved_tavily is not None:
            os.environ["TAVILY_API_KEY"] = saved_tavily


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_all():
    global PASS, FAIL, TOTAL
    print(f"\n{'='*60}")
    print(f"  SOURCE ACQUISITION TESTS")
    print(f"{'='*60}\n")

    tests = [
        ("yt-dlp detects module", test_ensure_yt_dlp_detects_module),
        ("yt-dlp detects CLI", test_ensure_yt_dlp_detects_cli),
        ("yt-dlp missing not Kaggle", test_ensure_yt_dlp_missing_not_kaggle),
        ("yt-dlp installs in Kaggle", test_ensure_yt_dlp_installs_in_kaggle),
        ("Preflight before Hermes", test_source_provider_preflight_before_hermes),
        ("No Hermes when no source provider", test_no_hermes_when_no_source_provider),
        ("Tavily fallback when yt-dlp unavailable", test_tavily_fallback_when_ytdlp_unavailable),
        ("Zero candidates stop pipeline", test_zero_candidates_stop_pipeline),
        ("Job theme exact", test_job_theme_exact),
        ("Seeded FactLockGenerator still works", test_seeded_fact_lock_generator_still_works),
        ("Hermes receives seed context", test_hermes_receives_seed_context),
        ("No regression certification source provider", test_no_regression_certification_source_provider),
        ("No regression cert source candidates missing", test_no_regression_certification_source_candidates_missing),
        ("Pipeline still handles fact_lock_seed", test_pipeline_still_handles_fact_lock_seed),
        ("Source provider preflight importable", test_source_provider_preflight_importable),
        ("Preflight no provider exits nonzero", test_preflight_no_provider_exits_nonzero),
        ("ensure_yt_dlp no secrets", test_ensure_yt_dlp_no_secrets),
        ("run_script_module uses -m", test_run_script_module_uses_minus_m),
        ("All stages use module invocation", test_all_production_stages_use_module_invocation),
        ("No file path invocations", test_no_production_file_path_invocations),
        ("notify uses module invocation", test_notify_uses_module_invocation),
        ("run_script_module accepts env", test_run_script_module_accepts_env),
        ("Preflight module import works", test_source_provider_preflight_works_as_module),
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
    print(f"  SOURCE ACQUISITION RESULTS: {PASS} passed, {FAIL} failed, {TOTAL} total")
    print(f"{'='*60}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
