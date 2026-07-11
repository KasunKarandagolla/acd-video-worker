#!/usr/bin/env python3
"""Pure offline readiness report generator.

Reads existing evidence from pre-production certification steps 1-5
and writes readiness_report.json and readiness_report.md.

No subprocess calls. No network I/O. No Hermes. No rendering.
This module is the only code invoked in STEP 6.
"""
import json
import re as _re
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# Strings that must never appear in generate_readiness_report source code.
# Checked by preproduction_certify.py at STEP 6 startup and by tests.
_FORBIDDEN_REFERENCES = [
    "run_title_theme_job",
    "run_hermes_turn",
    "llm_key_check",
    "bootstrap_kaggle.sh",
    "clone_repos.sh",
    "install_runtime_dependencies.sh",
    "install_skills.sh",
    "source_discovery",
    "download_sources",
    "render_with_openmontage",
    "memory_sync",
    "discord_notify",
    "subprocess.run",
    "subprocess.Popen",
    "os.system",
    "requests.",
    "urllib.request",
    "web_search",
    "git push",
]


def check_forbidden_references(source: str) -> list:
    """Return list of forbidden references found in source code."""
    found = []
    for ref in _FORBIDDEN_REFERENCES:
        if ref in source:
            found.append(ref)
    return found


def _read_json(path: Path) -> dict:
    """Read a JSON file safely, returning empty dict on any failure."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return {}


def generate_readiness_report(
    cert_id: str,
    cert_dir: Path,
    steps_dir: Path,
    cert_start_utc: str,
    current_commit: str,
) -> dict:
    """Generate readiness report from existing step evidence.

    Pure offline: reads only already-created artifacts from steps 1-5.
    No subprocess calls, no network I/O, no Hermes/NVIDIA/OpenMontage.

    Returns dict with keys:
      certification_id, certification_start_utc, report_generated_utc,
      worker_git_commit, production_ready, gates, blockers, step_results
    """
    now_utc = datetime.now(timezone.utc)
    _ts = cert_start_utc
    if _ts.endswith("Z"):
        _ts = _ts[:-1]
    if not _re.search(r'[+-]\d{2}:\d{2}(:\d{2})?$', _ts) and "T" in _ts:
        _ts += "+00:00"
    cert_start = datetime.fromisoformat(_ts)

    blockers: list[str] = []
    gates: dict[str, bool] = {}
    step_names = [
        "pipeline_doctor",
        "synthetic_e2e",
        "validate_synthetic_evidence",
        "hermes_artifact_canary",
        "validate_canary_evidence",
    ]

    # Read step result.json files
    step_results: dict[str, dict] = {}
    for name in step_names:
        rp = steps_dir / name / "result.json"
        step_results[name] = _read_json(rp)

    # Read step command.json files (for metadata like run_id, timestamps)
    step_commands: dict[str, dict] = {}
    for name in step_names:
        cp = steps_dir / name / "command.json"
        step_commands[name] = _read_json(cp)

    # 1. pipeline_doctor passed
    pd_passed = step_results.get("pipeline_doctor", {}).get("passed", False)
    gates["pipeline_doctor_passed"] = pd_passed
    if not pd_passed:
        blockers.append("pipeline_doctor did not pass")

    # 2. synthetic_e2e passed
    se_passed = step_results.get("synthetic_e2e", {}).get("passed", False)
    gates["synthetic_e2e_passed"] = se_passed
    if not se_passed:
        blockers.append("synthetic_e2e did not pass")

    # 3. validate_synthetic_evidence passed
    vse_passed = step_results.get("validate_synthetic_evidence", {}).get("passed", False)
    gates["validate_synthetic_evidence_passed"] = vse_passed
    if not vse_passed:
        blockers.append("validate_synthetic_evidence did not pass")

    # 4. hermes_artifact_canary passed
    hac_passed = step_results.get("hermes_artifact_canary", {}).get("passed", False)
    gates["hermes_artifact_canary_passed"] = hac_passed
    if not hac_passed:
        blockers.append("hermes_artifact_canary did not pass")

    # 5. validate_canary_evidence passed
    vce_passed = step_results.get("validate_canary_evidence", {}).get("passed", False)
    gates["validate_canary_evidence_passed"] = vce_passed
    if not vce_passed:
        blockers.append("validate_canary_evidence did not pass")

    # 6. Canary evidence freshness — timestamp >= certification start
    canary_fresh = False
    canary_report_data: dict = {}
    runs_dir = cert_dir.parent
    if runs_dir.is_dir():
        candidates = sorted(
            [d for d in runs_dir.iterdir()
             if d.is_dir() and d.name.startswith("canary_")],
            reverse=True,
        )
        if candidates:
            crp = candidates[0] / "canary_report.json"
            canary_report_data = _read_json(crp)

    canary_ts_str = canary_report_data.get("timestamp_utc", "")
    if canary_ts_str:
        try:
            _cts = canary_ts_str
            if _cts.endswith("Z"):
                _cts = _cts[:-1]
            if not _re.search(r'[+-]\d{2}:\d{2}(:\d{2})?$', _cts) and "T" in _cts:
                _cts += "+00:00"
            canary_ts = datetime.fromisoformat(_cts)
            canary_fresh = canary_ts >= cert_start
        except (ValueError, AttributeError):
            pass
    gates["canary_evidence_fresh"] = canary_fresh
    if not canary_fresh:
        blockers.append("canary evidence is stale or missing")

    # 7. Canary git commit matches current worker commit
    canary_commit = canary_report_data.get("git_commit", "")
    canary_commit_match = (
        current_commit != "unknown" and canary_commit == current_commit
    )
    gates["canary_git_commit_matches"] = canary_commit_match
    if not canary_commit_match:
        blockers.append("canary git commit does not match current commit")

    # 8. Synthetic evidence freshness — synthetic_e2e started during this cert
    se_cmd = step_commands.get("synthetic_e2e", {})
    se_started_str = se_cmd.get("started_at", "")
    se_fresh = False
    if se_started_str:
        try:
            _sts = se_started_str
            if _sts.endswith("Z"):
                _sts = _sts[:-1]
            if not _re.search(r'[+-]\d{2}:\d{2}(:\d{2})?$', _sts) and "T" in _sts:
                _sts += "+00:00"
            se_ts = datetime.fromisoformat(_sts)
            se_fresh = se_ts >= cert_start
        except (ValueError, AttributeError):
            pass
    gates["synthetic_evidence_fresh"] = se_fresh
    if not se_fresh:
        blockers.append("synthetic evidence is stale or missing")

    # 9. No step used fallback — check synthetic_e2e final_result.json
    fallback_used = False
    se_cmd_list = se_cmd.get("command", [])
    se_run_id: str | None = None
    for i, arg in enumerate(se_cmd_list):
        if arg == "--run-id" and i + 1 < len(se_cmd_list):
            se_run_id = se_cmd_list[i + 1]
            break
    if se_run_id:
        fr_path = cert_dir.parent / se_run_id / "final_result.json"
        final_result = _read_json(fr_path)
        fallback_used = final_result.get("fallback_used", False)
    gates["no_step_used_fallback"] = not fallback_used
    if fallback_used:
        blockers.append("synthetic_e2e used fallback")

    # 10. Certification commit matches current git commit
    commit_valid = current_commit != "unknown"
    gates["certification_commit_matches"] = commit_valid
    if not commit_valid:
        blockers.append("certification commit is unknown")

    production_ready = len(blockers) == 0

    step_summaries: dict[str, dict] = {}
    for name in step_names:
        sr = step_results.get(name, {})
        step_summaries[name] = {
            "passed": sr.get("passed", False),
            "error": sr.get("error"),
            "duration_s": sr.get("duration_s"),
        }

    return {
        "certification_id": cert_id,
        "certification_start_utc": cert_start_utc,
        "report_generated_utc": now_utc.isoformat() + "Z",
        "worker_git_commit": current_commit,
        "production_ready": production_ready,
        "gates": gates,
        "blockers": blockers if blockers else None,
        "step_results": step_summaries,
    }


def _build_markdown(report: dict) -> str:
    """Build a Markdown readiness report from the report dict."""
    lines: list[str] = [
        "# Readiness Report",
        "",
        f"**Certification**: {report['certification_id']}",
        f"**Generated**: {report['report_generated_utc']}",
        f"**Worker commit**: {report['worker_git_commit'][:12] if len(report['worker_git_commit']) >= 12 else report['worker_git_commit']}",
        "",
        "## Verdict",
        "",
        f"**{'PRODUCTION_RUN_READY' if report['production_ready'] else 'PRODUCTION_RUN_BLOCKED'}**",
        "",
    ]
    blockers = report.get("blockers")
    if blockers:
        lines.append("### Blockers")
        lines.append("")
        for b in blockers:
            lines.append(f"- {b}")
        lines.append("")
    lines.append("## Gates")
    lines.append("")
    lines.append("| Gate | Result |")
    lines.append("|------|--------|")
    for gate_name, gate_passed in report.get("gates", {}).items():
        lines.append(f"| {gate_name} | {'PASS' if gate_passed else 'FAIL'} |")
    lines.append("")
    lines.append("## Step Results")
    lines.append("")
    lines.append("| Step | Passed | Duration (s) |")
    lines.append("|------|--------|---------------|")
    for step_name, step_result in report.get("step_results", {}).items():
        dur = step_result.get("duration_s", "N/A")
        lines.append(
            f"| {step_name} | {'PASS' if step_result.get('passed') else 'FAIL'} | {dur} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_readiness_report_files(
    cert_dir: Path, report: dict
) -> tuple[Path, Path]:
    """Write readiness_report.json and readiness_report.md to cert_dir.

    Returns (json_path, md_path).
    """
    json_path = cert_dir / "readiness_report.json"
    md_path = cert_dir / "readiness_report.md"

    json_path.write_text(json.dumps(report, indent=2))
    md_path.write_text(_build_markdown(report))

    return json_path, md_path


def main():
    """CLI entry point for standalone use.

    Requires --cert-id, --cert-dir, --steps-dir, --cert-start-utc.
    Reads current git commit from the repo.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate readiness report from certification evidence."
    )
    parser.add_argument("--cert-id", required=True)
    parser.add_argument("--cert-dir", required=True)
    parser.add_argument("--steps-dir", required=True)
    parser.add_argument("--cert-start-utc", required=True)
    parser.add_argument("--current-commit", default="")
    args = parser.parse_args()

    cert_dir = Path(args.cert_dir)
    steps_dir = Path(args.steps_dir)
    commit = args.current_commit or "unknown"

    report = generate_readiness_report(
        args.cert_id, cert_dir, steps_dir, args.cert_start_utc, commit
    )
    write_readiness_report_files(cert_dir, report)

    if report["production_ready"]:
        print("PRODUCTION_RUN_READY")
        return 0
    else:
        print("PRODUCTION_RUN_BLOCKED")
        for b in (report.get("blockers") or []):
            print(f"  BLOCKER: {b}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
