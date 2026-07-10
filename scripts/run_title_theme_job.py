#!/usr/bin/env python3
"""Orchestrator: runs the full title/theme job pipeline — fail-fast.

Critical gates that must pass or the job stops immediately:
1. Hermes runtime success
2. match_fact_lock.json exists, schema-valid, and has correct verification_status

If either gate fails, the job exits nonzero and does NOT run:
- source discovery
- downloads
- media analysis
- artifact gate
- OpenMontage
- any downstream stage

Modes:
  Production (default): Full pipeline with real YouTube discovery and media.
  PIPELINE_SYNTHETIC_E2E=1: Uses synthetic test media, no YouTube, no memory push, no Discord success.
  HERMES_ARTIFACT_CANARY=1: Runs only environment + Hermes, proves match_fact_lock is fixed.
  --resume-run <run_id>: Resume from the first failed/missing stage.
"""
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import scripts.artifact_contracts as ac

BASE_DIR = Path(__file__).resolve().parent.parent


def notify(msg):
    subprocess.run(
        [sys.executable, str(BASE_DIR / "scripts" / "discord_notify.py"), msg],
        capture_output=True
    )


def run_script(script_name, args=None, stage_label=None):
    script_path = BASE_DIR / "scripts" / script_name
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    print(f"\n{'='*60}")
    print(f"  STAGE: {stage_label or script_name}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        print(f"FAIL: {script_name} exited with code {result.returncode}")
    return result.returncode


def write_failure_summary(run_id, failed_stage, exception_info, stages, run_dir):
    summary = {
        "run_id": run_id,
        "failed_stage": failed_stage,
        "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
        "root_exception_type": exception_info.get("type"),
        "original_traceback": exception_info.get("traceback"),
        "stage_inputs": ac.validate_stage_inputs(failed_stage, run_id) if failed_stage else [],
        "stage_outputs": ac.validate_stage_outputs(failed_stage, run_id) if failed_stage else [],
        "expected_contract": None,
        "actual_contract": None,
        "recommended_repair": None,
        "stages_skipped": [],
        "resume_command": f"python3 -m scripts.run_title_theme_job <job.yaml> --resume-run {run_id}" if run_id else None,
    }
    contracts = ac._load_contracts()
    for s in contracts.get("stages", []):
        if s["stage_name"] == failed_stage:
            summary["expected_contract"] = {
                "producer": s["producer"],
                "required_outputs": s["exact_output_paths"],
                "success_criteria": s["success_criteria"],
            }
            break
    found_failed = False
    for s in contracts.get("stages", []):
        if s["stage_name"] == failed_stage:
            found_failed = True
            continue
        if found_failed:
            summary["stages_skipped"].append(s["stage_name"])

    failure_dir = run_dir if run_dir else ac.get_run_dir(run_id)
    failure_dir.mkdir(parents=True, exist_ok=True)
    summary_path = failure_dir / "failure_summary.json"
    ac.atomic_write_json(summary_path, summary)
    md_path = failure_dir / "failure_summary.md"
    with open(md_path, "w") as f:
        f.write(f"# Failure Summary\n\n")
        f.write(f"Run: {run_id}\n")
        f.write(f"Failed Stage: {failed_stage}\n")
        f.write(f"Timestamp: {summary['timestamp_utc']}\n\n")
        f.write(f"## Exception\n\n")
        f.write(f"Type: {exception_info.get('type', 'N/A')}\n")
        f.write(f"Message: {exception_info.get('message', 'N/A')}\n\n")
        f.write(f"## Traceback\n\n```\n{exception_info.get('traceback', 'N/A')}\n```\n\n")
        f.write(f"## Stages Skipped\n\n")
        for s in summary["stages_skipped"]:
            f.write(f"- {s}\n")
        f.write(f"\n## Resume Command\n\n{summary['resume_command']}\n")
    return summary


def main():
    is_synthetic = ac.is_synthetic_e2e()
    is_canary = ac.is_hermes_artifact_canary()

    if len(sys.argv) < 2:
        print("Usage: python run_title_theme_job.py <job.yaml> [--run-id <run_id>] [--resume-run <run_id>]")
        sys.exit(1)

    job_path = sys.argv[1]
    run_id = None
    resume_run_id = None
    for i, arg in enumerate(sys.argv):
        if arg == "--run-id" and i + 1 < len(sys.argv):
            run_id = sys.argv[i + 1]
        if arg == "--resume-run" and i + 1 < len(sys.argv):
            resume_run_id = sys.argv[i + 1]

    if resume_run_id:
        run_id = resume_run_id

    if not run_id:
        run_id = "run_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    import yaml
    with open(job_path) as f:
        job = yaml.safe_load(f)

    run_dir = BASE_DIR / "state" / "runs" / run_id
    outputs_dir = BASE_DIR / "outputs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    title = job.get("title", "")
    theme = job.get("theme", "")

    print(f"Run ID: {run_id}")
    print(f"Job: {job_path}")
    print(f"Title: {title}")
    print(f"Theme: {theme}")
    print(f"Run dir: {run_dir}")
    print(f"Outputs dir: {outputs_dir}")
    print(f"Mode: {ac.get_pipeline_mode()}")

    stages = {}
    exception_info = {"type": None, "message": None, "traceback": None}
    failed_stage = None

    if resume_run_id:
        manifest_path = run_dir / "artifact_manifest.json"
        if manifest_path.is_file():
            print(f"Resuming run {resume_run_id} from manifest...")
            try:
                manifest = json.loads(manifest_path.read_text())
                for art_name, art_record in manifest.get("artifacts", {}).items():
                    status = art_record.get("status", "")
                    if status in ("missing", "invalid_json", "schema_invalid", "invalid_structure"):
                        print(f"  Artifact needs redo: {art_name} ({status})")
            except Exception as e:
                print(f"  Could not parse manifest: {e}")

    try:
        # Stage 1: repo_setup_status
        notify(f"[{run_id}] Stage 1/22: repo setup")
        preflight_json = BASE_DIR / "state" / "runs" / "repo_preflight.json"
        if preflight_json.is_file():
            with open(preflight_json) as f:
                preflight = json.load(f)
            stages["repo_setup_status"] = {
                "hermes_available": preflight.get("hermes_agent", {}).get("exists", False),
                "openmontage_available": preflight.get("openmontage", {}).get("exists", False),
            }
        else:
            stages["repo_setup_status"] = {"note": "Preflight report not yet generated"}
        print(f"  Repo status: {json.dumps(stages['repo_setup_status'])}")

        # Stage 2: skill_system_status
        notify(f"[{run_id}] Stage 2/22: skill system")
        skill_report = BASE_DIR / "state" / "runs" / "skill_install_report.md"
        stages["skill_system_status"] = {"report_exists": skill_report.is_file()}
        print(f"  Skill report exists: {skill_report.is_file()}")

        # Stage 3: llm_api_status
        notify(f"[{run_id}] Stage 3/22: LLM API")
        llm_check = BASE_DIR / "state" / "runs" / "llm_key_check.json"
        if llm_check.is_file():
            with open(llm_check) as f:
                llm_data = json.load(f)
            stages["llm_api_status"] = {
                "accessible": llm_data.get("endpoint_accessible", False),
                "api_key_set": llm_data.get("api_key_set", False),
            }
        else:
            stages["llm_api_status"] = {"accessible": False, "api_key_set": False}
        print(f"  LLM accessible: {stages['llm_api_status'].get('accessible', False)}")

        # Synthetic E2E mode: skip Hermes, generate synthetic artifacts
        if is_synthetic:
            print("PIPELINE_SYNTHETIC_E2E mode: generating synthetic fixtures (skipping real Hermes).")
            _generate_synthetic_match_fact(run_id, run_dir, title, theme)
            stages["hermes_runtime"] = {"success": True, "synthetic": True, "note": "Synthetic E2E mode"}
            mf_info = ac.require_artifact(run_id, "match_fact_lock.json")
            stages["match_fact_lock"] = {
                "status": "verified",
                "match": "Synthetic Team A vs Synthetic Team B",
                "team_a": "Team A",
                "team_b": "Team B",
                "date": "2024-01-01",
                "schema_valid": mf_info["schema_valid"],
                "path": mf_info["path"],
            }
            print(f"  Synthetic match facts created and validated.")
            ac.write_artifact_manifest(run_id)
            print("  [SYNTHETIC] Proceeding to synthetic source discovery and media analysis.")
            _run_synthetic_stages(run_id, run_dir, outputs_dir, stages, job_path, title, theme, job)
        else:
            # Stage 4: Hermes runtime — canonical run_hermes_turn (with retry for transient errors)
            notify(f"[{run_id}] Stage 4/22: Hermes runtime")
            from scripts.hermes_runtime import run_hermes_turn_with_retry
            hermes_result = run_hermes_turn_with_retry(title, theme, run_id, run_dir, max_retries=1)
            stages["hermes_runtime"] = hermes_result

            print(f"  Hermes success: {hermes_result.get('success', False)}")
            if not hermes_result.get("success"):
                failed_stage = "hermes_reasoning"
                msg = hermes_result.get('error_message', 'unknown')
                print(f"  Hermes FAILED: {hermes_result.get('error_type')}: {msg}")
                print("  Job stopped — Hermes runtime failure.")
                notify(f"[{run_id}] Hermes runtime FAILED: {hermes_result.get('error_type')}")
                exception_info = {"type": hermes_result.get("error_type"), "message": msg, "traceback": None}
                write_failure_summary(run_id, failed_stage, exception_info, stages, run_dir)
                sys.exit(1)

            hermes_report = run_dir / "hermes_run_report.json"
            if hermes_report.is_file():
                with open(hermes_report) as f:
                    hr = json.load(f)
                stages["hermes_runtime"]["session_id"] = hr.get("session_id")

            # Stage 5: match_fact_lock — required gate
            notify(f"[{run_id}] Stage 5/22: match fact lock")
            try:
                mf_info = ac.require_artifact(run_id, "match_fact_lock.json")
                mf = mf_info["data"]
                stages["match_fact_lock"] = {
                    "status": mf.get("verification_status", "unknown"),
                    "match": f"{mf.get('team_a', '')} vs {mf.get('team_b', '')}",
                    "team_a": mf.get("team_a"),
                    "team_b": mf.get("team_b"),
                    "date": mf.get("match_date"),
                    "schema_valid": mf_info["schema_valid"],
                    "path": mf_info["path"],
                }
                print(f"  Match facts: {mf.get('team_a')} vs {mf.get('team_b')} ({mf.get('verification_status')})")

                if not mf_info["schema_valid"]:
                    errors = "; ".join(mf_info["schema_errors"])
                    print(f"  FAIL: match_fact_lock schema invalid: {errors}")
                    notify(f"[{run_id}] match_fact_lock schema invalid: {errors}")
                    failed_stage = "match_fact_lock"
                    exception_info = {"type": "schema_validation_error", "message": errors, "traceback": None}
                    write_failure_summary(run_id, failed_stage, exception_info, stages, run_dir)
                    sys.exit(1)

                vs = mf.get("verification_status", "")
                if vs not in ("verified", "creative_hypothesis"):
                    print(f"  FAIL: match_fact_lock verification_status='{vs}' is not valid. Job stopped.")
                    notify(f"[{run_id}] match_fact_lock invalid status: {vs}")
                    failed_stage = "match_fact_lock"
                    exception_info = {"type": "invalid_status", "message": f"verification_status='{vs}'", "traceback": None}
                    write_failure_summary(run_id, failed_stage, exception_info, stages, run_dir)
                    sys.exit(1)
            except FileNotFoundError as e:
                print(f"  FAIL: {e}")
                notify(f"[{run_id}] match_fact_lock.json missing — job stopped")
                failed_stage = "match_fact_lock"
                exception_info = {"type": "FileNotFoundError", "message": str(e), "traceback": None}
                write_failure_summary(run_id, failed_stage, exception_info, stages, run_dir)
                sys.exit(1)

            # Write artifact manifest after Hermes artifacts are created
            ac.write_artifact_manifest(run_id)

            if is_canary:
                print("HERMES_ARTIFACT_CANARY mode: stopping after Hermes artifact validation.")
                print("match_fact_lock.json: VALID")
                print("artifact_manifest.json: WRITTEN")
                stages["hermes_artifact_canary"] = {"passed": True}
                canary_result = {
                    "run_id": run_id,
                    "hermes_success": stages.get("hermes_runtime", {}).get("success", False),
                    "artifact_gate_passed": False,
                    "openmontage_success": False,
                    "pipeline_success": False,
                    "final_success": False,
                    "compose_tool_invoked": False,
                    "compose_tool_returned_success": False,
                    "qa_passed": False,
                    "fallback_used": False,
                    "final_output": None,
                    "failed_stage": None,
                    "errors": [],
                    "all_required_true": False,
                    "memory_collection_attempted": False,
                    "memory_push_attempted": False,
                    "discord_final_attempted": False,
                    "canary_mode": True,
                    "canary_passed": True,
                }
                stages["final_result"] = canary_result
                stages["render_output"] = {"render_success": False, "note": "Stopped after canary — no render attempted"}
                _write_session_summary(run_id, job_path, title, theme, stages, run_dir)
                _write_success_status(stages, run_dir, canary_result)
                sys.exit(0)
            # Stage 6: source discovery and verification
            notify(f"[{run_id}] Stage 6/22: source discovery")
            rc = run_script("source_discovery.py", [job_path, "--run-id", run_id], "source_discovery")
            stages["source_discovery"] = {"exit_code": rc}
            candidates_path = run_dir / "source_candidates.json"
            if candidates_path.is_file():
                with open(candidates_path) as f:
                    cand_data = json.load(f)
                stages["source_discovery"]["candidates_count"] = cand_data.get("total_candidates", 0)
                stages["source_discovery"]["blocker"] = cand_data.get("blocker")

            if rc != 0:
                failed_stage = "source_discovery"
                exception_info = {"type": "exit_code", "message": f"source_discovery exited with {rc}", "traceback": None}
                write_failure_summary(run_id, failed_stage, exception_info, stages, run_dir)
                sys.exit(rc)

            # Stage 7: proxy download
            if candidates_path.is_file():
                notify(f"[{run_id}] Stage 7/22: proxy download")
                rc = run_script("download_sources.py", [str(candidates_path), "--run-id", run_id], "download_sources")
                stages["download_sources"] = {"exit_code": rc}

                if rc != 0:
                    failed_stage = "downloads"
                    exception_info = {"type": "exit_code", "message": f"download_sources exited with {rc}", "traceback": None}
                    write_failure_summary(run_id, failed_stage, exception_info, stages, run_dir)
                    sys.exit(rc)
            else:
                print("  Skipping download: no candidates file")
                stages["download_sources"] = {"skipped": True}

            # Stage 8: visual/audio analysis
            notify(f"[{run_id}] Stage 8/22: visual/audio analysis")
            rc = run_script("media_analysis.py", [run_id], "media_analysis")
            stages["media_analysis"] = {"exit_code": rc}

        # Stage 12: artifact gate
        self_hermes_success = stages.get("hermes_runtime", {}).get("success", False)
        self_mf_valid = stages.get("match_fact_lock", {}).get("schema_valid", False)
        notify(f"[{run_id}] Stage 12/22: artifact gate")
        rc = run_script("editorial_artifact_gate.py", [run_id], "artifact_gate")
        stages["artifact_gate"] = {"exit_code": rc, "hermes_success": self_hermes_success, "match_fact_schema_valid": self_mf_valid}
        gate_result = run_dir / "artifact_gate_result.json"
        if gate_result.is_file():
            with open(gate_result) as f:
                gr = json.load(f)
            stages["artifact_gate"]["gate_passed"] = gr.get("gate_passed", False)
            stages["artifact_gate"]["blocker"] = gr.get("blocker")
            print(f"  Artifact gate: {'PASSED' if gr.get('gate_passed') else 'BLOCKED'}")
            if not gr.get("gate_passed"):
                failed_stage = "artifact_gate"
                exception_info = {"type": "gate_blocked", "message": gr.get("blocker", "Unknown"), "traceback": None}
                write_failure_summary(run_id, failed_stage, exception_info, stages, run_dir)
                sys.exit(1)

        # Write manifest again after all artifacts
        ac.write_artifact_manifest(run_id)

        # Stage 13: OpenMontage artifact conversion (inside render step)

        # Stage 14: OpenMontage render
        assets_path = run_dir / "downloaded_assets.json"
        candidates_path = run_dir / "source_candidates.json"
        if assets_path.is_file() and candidates_path.is_file():
            notify(f"[{run_id}] Stage 14/22: OpenMontage render")
            rc = run_script(
                "render_with_openmontage.py",
                [job_path, str(assets_path), str(candidates_path), "--run-id", run_id],
                "render_with_openmontage",
            )
            stages["render_attempt"] = {"exit_code": rc}
        else:
            stages["render_attempt"] = {"skipped": True, "reason": "No assets or candidates"}
            print("  Skipping render: missing assets or candidates")

        # Stage 15: QA
        notify(f"[{run_id}] Stage 15/22: QA")
        rc = run_script("qa_check.py", [run_id], "qa_check")
        stages["qa_check"] = {"exit_code": rc}
        qa_report = run_dir / "full_qa_report.json"
        if qa_report.is_file():
            with open(qa_report) as f:
                qa = json.load(f)
            stages["qa_check"]["qa_passed"] = qa.get("qa_passed", False)
            stages["qa_check"]["issues"] = qa.get("issues", [])
            if not qa.get("qa_passed", False):
                print("  QA FAILED — issues found")
                stages["qa_check"]["blocker"] = "QA checks failed"

        # Read the OpenMontage execution report to determine authoritative status
        om_report_path = run_dir / "openmontage_execution_report.json"
        om_success = False
        om_pipeline_success = False
        om_final_success = False
        compose_tool_invoked = False
        compose_tool_returned_success = False
        fallback_used = False
        if om_report_path.is_file():
            try:
                with open(om_report_path) as f:
                    om_data = json.load(f)
                om_success = om_data.get("openmontage_success", False)
                om_pipeline_success = om_data.get("pipeline_success", False)
                om_final_success = om_data.get("final_success", False)
                compose_tool_invoked = om_data.get("compose_tool_invoked", False)
                compose_tool_returned_success = om_data.get("compose_tool_returned_success", False)
                fallback_used = om_data.get("fallback_used", False)
            except Exception:
                pass

        qa_passed = stages.get("qa_check", {}).get("qa_passed", False)

        final_output = outputs_dir / "final_openmontage_render.mp4"
        fallback_mp4 = outputs_dir / "fallback_render_attempt.mp4"

        render_success = bool(
            om_success
            and om_pipeline_success
            and om_final_success
            and compose_tool_invoked
            and compose_tool_returned_success
            and not fallback_used
            and final_output.is_file()
            and final_output.stat().st_size > 0
        )

        stages["render_output"] = {
            "render_success": render_success,
            "openmontage_success": om_success,
            "pipeline_success": om_pipeline_success,
            "final_success": om_final_success,
            "compose_tool_invoked": compose_tool_invoked,
            "compose_tool_returned_success": compose_tool_returned_success,
            "fallback_used": fallback_used,
            "qa_passed": qa_passed,
            "output": str(final_output) if final_output.is_file() else None,
            "size_bytes": final_output.stat().st_size if final_output.is_file() else 0,
        }
        if final_output.is_file():
            stages["render_output"]["output"] = str(final_output)
            stages["render_output"]["size_bytes"] = final_output.stat().st_size

    except SystemExit:
        raise
    except Exception as e:
        failed_stage = failed_stage or "unknown"
        exception_info = {"type": type(e).__name__, "message": str(e), "traceback": traceback.format_exc()}
        print(f"\nUNHANDLED EXCEPTION at stage '{failed_stage}': {type(e).__name__}: {e}")
        traceback.print_exc()
        write_failure_summary(run_id, failed_stage, exception_info, stages, run_dir)
        sys.exit(1)

    # Build final authoritative result object
    qa_passed = stages.get("qa_check", {}).get("qa_passed", False)
    om_report_path = run_dir / "openmontage_execution_report.json"
    hermes_success = stages.get("hermes_runtime", {}).get("success", False)
    artifact_gate_passed = stages.get("artifact_gate", {}).get("gate_passed", False)
    om_success = stages.get("render_output", {}).get("openmontage_success", False)
    pipeline_success = stages.get("render_output", {}).get("pipeline_success", False)
    final_success = stages.get("render_output", {}).get("final_success", False)
    compose_tool_invoked = stages.get("render_output", {}).get("compose_tool_invoked", False)
    compose_tool_returned_success = stages.get("render_output", {}).get("compose_tool_returned_success", False)
    fallback_used = stages.get("render_output", {}).get("fallback_used", True)
    render_success = stages.get("render_output", {}).get("render_success", False)

    final_result = {
        "run_id": run_id,
        "hermes_success": hermes_success,
        "artifact_gate_passed": artifact_gate_passed,
        "openmontage_success": om_success,
        "pipeline_success": pipeline_success,
        "final_success": final_success,
        "compose_tool_invoked": compose_tool_invoked,
        "compose_tool_returned_success": compose_tool_returned_success,
        "qa_passed": qa_passed,
        "fallback_used": fallback_used,
        "final_output": str(outputs_dir / "final_openmontage_render.mp4") if (outputs_dir / "final_openmontage_render.mp4").is_file() else None,
        "failed_stage": failed_stage,
        "errors": [],
        "memory_collection_attempted": False,
        "memory_push_attempted": False,
        "discord_final_attempted": False,
        "is_synthetic": is_synthetic,
    }
    if not render_success:
        if not hermes_success:
            final_result["errors"].append("hermes_success is false")
        if not artifact_gate_passed:
            final_result["errors"].append("artifact_gate not passed")
        if not om_success:
            final_result["errors"].append("openmontage_success is false")
        if not pipeline_success:
            final_result["errors"].append("pipeline_success is false")
        if not final_success:
            final_result["errors"].append("final_success is false")
        if not compose_tool_invoked:
            final_result["errors"].append("compose_tool not invoked")
        if not compose_tool_returned_success:
            final_result["errors"].append("compose_tool did not return success")
        if fallback_used:
            final_result["errors"].append("fallback was used instead of OpenMontage")
        if not qa_passed:
            final_result["errors"].append("QA failed")
        if not (outputs_dir / "final_openmontage_render.mp4").is_file():
            final_result["errors"].append("final output missing")
    final_result["all_required_true"] = render_success

    # Stage 16: session summary
    _write_session_summary(run_id, job_path, title, theme, stages, run_dir)

    if not is_synthetic and render_success:
        # Stage 17: one memory update
        notify(f"[{run_id}] Stage 17/22: memory update")
        rc = run_script("memory_sync.py", ["collect", "--run-id", run_id], "memory_collect")
        stages["memory_update"] = {"exit_code": rc}
        final_result["memory_collection_attempted"] = True

        # Stage 18: one GitHub push
        notify(f"[{run_id}] Stage 18/22: GitHub push")
        rc = run_script("memory_sync.py", ["push", "--run-id", run_id], "memory_push")
        stages["github_push"] = {"exit_code": rc}
        final_result["memory_push_attempted"] = True
    elif is_synthetic:
        print("  [SYNTHETIC] Skipping memory collect/push — synthetic mode.")
        stages["memory_update"] = {"skipped": True, "reason": "synthetic_mode"}
        stages["github_push"] = {"skipped": True, "reason": "synthetic_mode"}
        final_result["memory_collection_attempted"] = False
        final_result["memory_push_attempted"] = False
    else:
        print("  Skipping memory collect/push — render did not succeed.")
        stages["memory_update"] = {"skipped": True, "reason": "render_not_successful"}
        stages["github_push"] = {"skipped": True, "reason": "render_not_successful"}
        final_result["memory_collection_attempted"] = False
        final_result["memory_push_attempted"] = False

    # Discord final status — never send on synthetic or failure
    if is_synthetic:
        print("  [SYNTHETIC] Skipping Discord notification — synthetic mode.")
        stages["discord_final"] = {"sent": False, "reason": "synthetic_mode"}
        final_result["discord_final_attempted"] = False
    elif not render_success:
        print("  Skipping Discord notification — render did not succeed.")
        stages["discord_final"] = {"sent": False, "reason": "render_not_successful"}
        final_result["discord_final_attempted"] = False
    else:
        msg = f"[{run_id}] Job complete. Render: {stages['render_output'].get('output', 'unknown')}"
        notify(msg)
        stages["discord_final"] = {"sent": True}
        final_result["discord_final_attempted"] = True

    # Write final manifest
    ac.write_artifact_manifest(run_id)

    # Write final_result
    final_result_path = run_dir / "final_result.json"
    with open(final_result_path, "w") as f:
        json.dump(final_result, f, indent=2)
    stages["final_result"] = final_result

    _write_success_status(stages, run_dir, final_result)

    if not render_success or not qa_passed or not final_success or fallback_used:
        print(f"\n  Pipeline FAILED — final_success={final_success}, qa_passed={qa_passed}, fallback_used={fallback_used}")
        sys.exit(1)


def _generate_synthetic_match_fact(run_id, run_dir, title, theme):
    """Generate a synthetic match_fact_lock.json for E2E testing without API keys."""
    artifacts_dir = run_dir / "hermes_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat() + "Z"
    match_fact = {
        "status": "verified",
        "competition": "Synthetic E2E Test",
        "match_date": "2024-06-15",
        "team_a": "Synthetic Team A",
        "team_b": "Synthetic Team B",
        "score": "2-1",
        "stage_or_round": "Synthetic Round",
        "evidence_sources": ["synthetic_fixture"],
        "evidence_claims": ["Synthetic match fact for E2E testing"],
        "verification_status": "verified",
        "confidence": "high",
        "unresolved_conflicts": [],
        "generated_by": "synthetic_e2e_mode",
        "timestamp_utc": now,
        "match": "Synthetic Team A vs Synthetic Team B",
        "opponent": "Synthetic Team B",
        "date": "2024-06-15",
    }
    ac.atomic_write_json(artifacts_dir / "match_fact_lock.json", match_fact)
    brief = {
        "title": title or "Synthetic Match",
        "theme": theme or "Synthetic E2E Test",
        "emotional_arc": "synthetic",
    }
    ac.atomic_write_json(artifacts_dir / "brief_interpretation.json", brief)


def _run_synthetic_stages(run_id, run_dir, outputs_dir, stages, job_path, title, theme, job):
    """Run synthetic E2E stages with controlled fixtures."""
    print("\n  [SYNTHETIC E2E] Generating synthetic test fixtures...")

    assets_dir = run_dir / "assets" / "raw"
    assets_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir = run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = run_dir / "hermes_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    import shutil
    has_ffmpeg = shutil.which("ffmpeg") is not None

    # Generate synthetic test fixture with video (testsrc) AND audio (sine wave, AAC)
    syn_video = assets_dir / "synthetic_test_video.mp4"
    if has_ffmpeg:
        import subprocess as sp
        sp.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=5:size=640x480:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-shortest",
            str(syn_video),
        ], capture_output=True, timeout=30)

    if syn_video.is_file() and syn_video.stat().st_size > 0:
        print(f"  Synthetic video: {syn_video} ({syn_video.stat().st_size} bytes)")
        # ffprobe the fixture and require video + audio
        probe_cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(syn_video)]
        try:
            probe_proc = sp.run(probe_cmd, capture_output=True, text=True, timeout=15)
            if probe_proc.returncode == 0:
                probe_data = json.loads(probe_proc.stdout)
                has_v = any(s.get("codec_type") == "video" for s in probe_data.get("streams", []))
                has_a = any(s.get("codec_type") == "audio" for s in probe_data.get("streams", []))
                print(f"  Fixture: video={has_v}, audio={has_a}, streams={len(probe_data.get('streams', []))}")
                if not has_v or not has_a:
                    print("  ERROR: Fixture missing video or audio stream — regenerating")
                    if syn_video.is_file():
                        syn_video.unlink()
        except Exception:
            pass
    else:
        print("  WARN: Could not generate synthetic video with ffmpeg")
        syn_video.write_text("placeholder")
        print("  WARN: Created placeholder file — real OpenMontage render will fail")

    # Synthetic source_candidates.json (in both run_dir AND hermes_artifacts for gate compatibility)
    syn_candidates = {
        "run_id": run_id,
        "job_title": title,
        "job_theme": theme,
        "total_candidates": 1,
        "sources_queried": ["synthetic_e2e"],
        "match_facts_loaded": True,
        "candidates": [{
            "source_id": "synthetic_001",
            "canonical_url": "https://example.com/synthetic_e2e_source",
            "title": "Synthetic Test Video",
            "platform": "synthetic",
            "initial_rank": 1,
            "verified_match_relevance": "relevant",
        }],
        "blocker": None,
    }
    for target_dir in [run_dir, artifacts_dir]:
        ac.atomic_write_json(target_dir / "source_candidates.json", syn_candidates)
    stages["source_discovery"] = {"exit_code": 0, "candidates_count": 1, "synthetic": True}

    # Synthetic source_verification.json (in both locations)
    syn_verification = {
        "verified_sources": [{
            "source_id": "synthetic_001",
            "verified": True,
            "verification_method": "synthetic_fixture",
        }],
        "blocker": None,
    }
    for target_dir in [run_dir, artifacts_dir]:
        ac.atomic_write_json(target_dir / "source_verification.json", syn_verification)

    # Synthetic downloaded_assets.json
    syn_assets = {
        "run_id": run_id,
        "assets_dir": str(assets_dir),
        "total_attempted": 1,
        "downloads": [{
            "source_id": "synthetic_001",
            "status": "downloaded",
            "file": "synthetic_test_video.mp4",
            "file_path": str(syn_video),
            "file_hash": "synthetic_e2e_hash",
            "file_size_bytes": syn_video.stat().st_size if syn_video.is_file() else 0,
            "duration_seconds": 5.0,
            "resolution": "640x480",
        }],
        "errors": [],
        "blocker": None,
    }
    ac.atomic_write_json(run_dir / "downloaded_assets.json", syn_assets)
    stages["download_sources"] = {"exit_code": 0, "synthetic": True}

    # Stage 8: media analysis
    if has_ffmpeg:
        print("  Running synthetic media analysis...")
        rc = run_script("media_analysis.py", [run_id], "media_analysis")
        stages["media_analysis"] = {"exit_code": rc, "synthetic": True}
        # Copy analysis outputs to hermes_artifacts for the artifact gate
        for fname in ["media_probe.json", "visual_scene_analysis.json"]:
            src = analysis_dir / fname
            dst = artifacts_dir / fname
            if src.is_file():
                shutil.copy2(str(src), str(dst))
    else:
        print("  Skipping media analysis (no ffmpeg)")
        syn_probe = [{
            "file": "synthetic_test_video.mp4",
            "path": str(syn_video),
            "size_bytes": syn_video.stat().st_size if syn_video.is_file() else 0,
            "streams": [{"index": 0, "codec_type": "video", "codec_name": "h264", "width": 640, "height": 480}],
            "format": {"duration": "5.0"},
        }]
        for target_dir in [analysis_dir, artifacts_dir]:
            ac.atomic_write_json(target_dir / "media_probe.json", syn_probe)
            ac.atomic_write_json(target_dir / "visual_scene_analysis.json", {
                "run_id": run_id, "files_analyzed": 1, "probes": syn_probe,
            })
        ac.atomic_write_json(analysis_dir / "audio_analysis.json", {
            "run_id": run_id, "files_analyzed": 1, "audio_streams": [],
        })
        stages["media_analysis"] = {"exit_code": 0, "synthetic": True}

    # Stages 9-11: synthetic editorial artifacts
    syn_artifacts = {
        "timestamp_candidates.json": {"timestamps": [{"source": "synthetic_001", "start": 0, "end": 5}]},
        "clip_scores.json": {"scores": [{"source_id": "synthetic_001", "score": 0.9}]},
        "arc_revision_gate.json": {"arc_decision": "proceed", "status": "passed"},
        "story_plan.json": {"structure": ["intro", "highlight", "closing"], "segments": [{"type": "highlight", "duration_seconds": 5}]},
        "audio_music_plan.json": {"audio_plan": {"mix": "voiceover+music"}, "music_tracks": []},
        "commentary_rights_check.json": {"rights_status": "cleared", "commentary_status": "not_applicable"},
        "visual_cohesion_plan.json": {"style_guide": {"grade": "neutral"}, "grade_decisions": {}},
        "graphics_text_plan.json": {"text_elements": [], "graphic_elements": []},
        "assembly_plan.json": {"structure": [{"clip": "synthetic_001", "start": 0, "end": 5}], "total_duration_seconds": 5},
        "fact_provenance_gate.json": {"verification_summary": {"verified": True}, "provenance_trail": [{"claim": "synthetic", "source": "synthetic_001"}]},
        "editorial_journey_state.json": {"current_stage": "gate", "artifacts_produced": ["match_fact_lock", "source_candidates"], "artifacts_pending": []},
    }
    for name, data in syn_artifacts.items():
        ac.atomic_write_json(artifacts_dir / name, data)

    print("  [SYNTHETIC E2E] Fixtures ready. Proceeding to artifact gate and OpenMontage.")


def _write_session_summary(run_id, job_path, title, theme, stages, run_dir):
    summary_path = run_dir / "session_summary.md"
    with open(summary_path, "w") as f:
        f.write(f"# Session Summary\n\n")
        f.write(f"Run ID: {run_id}\n")
        f.write(f"Job: {job_path}\n")
        f.write(f"Title: {title}\n")
        f.write(f"Theme: {theme}\n")
        f.write(f"Completed: {datetime.now(timezone.utc).isoformat()}Z\n\n")
        f.write(f"## Stages\n\n")
        for stage_name, stage_data in stages.items():
            f.write(f"### {stage_name}\n\n")
            if isinstance(stage_data, dict):
                for k, v in stage_data.items():
                    f.write(f"- {k}: {v}\n")
            else:
                f.write(f"- {stage_data}\n")
            f.write("\n")
        f.write(f"## Render Result\n\n")
        f.write(f"Render success: {stages.get('render_output', {}).get('render_success', False)}\n")
        output = stages.get("render_output", {}).get("output", "N/A")
        f.write(f"Output: {output}\n")


def _write_success_status(stages, run_dir, final_result=None):
    if final_result:
        all_ok = final_result.get("all_required_true", False)
        render_status = all_ok
    else:
        render_status = stages.get("render_output", {}).get("render_success", False)

    print(f"\n{'='*60}")
    print(f"  RUN COMPLETE")
    print(f"  Summary: {run_dir / 'session_summary.md'}")
    if final_result:
        print(f"  openmontage_success: {final_result.get('openmontage_success')}")
        print(f"  pipeline_success: {final_result.get('pipeline_success')}")
        print(f"  final_success: {final_result.get('final_success')}")
        print(f"  qa_passed: {final_result.get('qa_passed')}")
        print(f"  fallback_used: {final_result.get('fallback_used')}")
    if render_status:
        print(f"  Render success: True")
    else:
        print(f"  Render success: False")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
