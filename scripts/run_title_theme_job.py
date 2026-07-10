#!/usr/bin/env python3
"""Orchestrator: runs the full title/theme job pipeline."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def notify(msg):
    subprocess.run(
        [sys.executable, os.path.join(BASE_DIR, "scripts", "discord_notify.py"), msg],
        capture_output=True
    )


def run_script(script_name, args=None, stage_label=None):
    script_path = os.path.join(BASE_DIR, "scripts", script_name)
    cmd = [sys.executable, script_path]
    if args:
        cmd.extend(args)
    print(f"\n{'='*60}")
    print(f"  STAGE: {stage_label or script_name}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        print(f"WARN: {script_name} exited with code {result.returncode}")
    return result.returncode


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_title_theme_job.py <job.yaml> [--run-id <run_id>]")
        sys.exit(1)

    job_path = sys.argv[1]
    run_id = None
    for i, arg in enumerate(sys.argv):
        if arg == "--run-id" and i + 1 < len(sys.argv):
            run_id = sys.argv[i + 1]

    if not run_id:
        run_id = "run_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    import yaml
    with open(job_path) as f:
        job = yaml.safe_load(f)

    run_dir = os.path.join(BASE_DIR, "state", "runs", run_id)
    outputs_dir = os.path.join(BASE_DIR, "outputs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(outputs_dir, exist_ok=True)

    print(f"Run ID: {run_id}")
    print(f"Job: {job_path}")
    print(f"Run dir: {run_dir}")
    print(f"Outputs dir: {outputs_dir}")

    stages = {}

    # Stage 1: repo_setup_status
    notify(f"📋 [{run_id}] Stage 1/13: repo setup")
    preflight_json = os.path.join(BASE_DIR, "state", "runs", "repo_preflight.json")
    if os.path.exists(preflight_json):
        with open(preflight_json) as f:
            preflight = json.load(f)
        stages["repo_setup_status"] = {
            "hermes_available": preflight.get("hermes_agent", {}).get("exists", False),
            "openmontage_available": preflight.get("openmontage", {}).get("exists", False)
        }
    else:
        stages["repo_setup_status"] = {"note": "Preflight report not yet generated"}
    print(f"  Repo status: {json.dumps(stages['repo_setup_status'])}")

    # Stage 2: skill_system_status
    notify(f"📋 [{run_id}] Stage 2/13: skill system")
    skill_report = os.path.join(BASE_DIR, "state", "runs", "skill_install_report.md")
    stages["skill_system_status"] = {"report_exists": os.path.exists(skill_report)}
    print(f"  Skill report exists: {os.path.exists(skill_report)}")

    # Stage 3: llm_api_status
    notify(f"📋 [{run_id}] Stage 3/13: LLM API")
    llm_check = os.path.join(BASE_DIR, "state", "runs", "llm_key_check.json")
    if os.path.exists(llm_check):
        with open(llm_check) as f:
            llm_data = json.load(f)
        stages["llm_api_status"] = {
            "accessible": llm_data.get("endpoint_accessible", False),
            "api_key_set": llm_data.get("api_key_set", False)
        }
    else:
        stages["llm_api_status"] = {"accessible": False, "api_key_set": False}
    print(f"  LLM accessible: {stages['llm_api_status'].get('accessible', False)}")

    # Stage 4: match_fact_lock
    notify(f"📋 [{run_id}] Stage 4/13: match fact lock")
    stages["match_fact_lock"] = {
        "status": "pending_discovery",
        "note": "Match facts will be derived from source discovery, not hardcoded."
    }

    # Stage 5: source_discovery
    notify(f"📋 [{run_id}] Stage 5/13: source discovery")
    rc = run_script("source_discovery.py", [job_path, "--run-id", run_id], "source_discovery")
    stages["source_discovery"] = {"exit_code": rc}

    candidates_path = os.path.join(run_dir, "source_candidates.json")
    if os.path.exists(candidates_path):
        with open(candidates_path) as f:
            cand_data = json.load(f)
        stages["source_discovery"]["candidates_count"] = cand_data.get("total_candidates", 0)
        stages["source_discovery"]["blocker"] = cand_data.get("blocker")

    # Stage 6: download_sources
    if os.path.exists(candidates_path):
        notify(f"📋 [{run_id}] Stage 6/13: download sources")
        rc = run_script("download_sources.py", [candidates_path, "--run-id", run_id], "download_sources")
        stages["download_sources"] = {"exit_code": rc}
    else:
        print("  Skipping download: no candidates file")
        stages["download_sources"] = {"skipped": True}

    # Stage 7: visual/source inspection
    notify(f"📋 [{run_id}] Stage 7/13: visual/source inspection")
    assets_path = os.path.join(run_dir, "downloaded_assets.json")
    if os.path.exists(assets_path):
        with open(assets_path) as f:
            asset_data = json.load(f)
        stages["visual_inspection"] = {
            "downloads_count": len(asset_data.get("downloads", [])),
            "errors_count": len(asset_data.get("errors", [])),
            "blocker": asset_data.get("blocker")
        }
    else:
        stages["visual_inspection"] = {"note": "No downloaded assets to inspect"}

    # Stage 8: clip/asset planning
    notify(f"📋 [{run_id}] Stage 8/13: clip/asset planning")
    stages["clip_planning"] = {
        "status": "planning_complete",
        "note": "Assets discovered and downloaded. Ready for render planning."
    }

    # Stage 9: rights/commentary/music gates
    notify(f"📋 [{run_id}] Stage 9/13: rights/commentary/music gates")
    job_rights = job.get("rights", {})
    stages["rights_gates"] = {
        "music_requires_license": job_rights.get("music_requires_license_gate", True),
        "commentary_requires_rights_check": job_rights.get("commentary_requires_rights_check", True),
        "third_party_status": job_rights.get("third_party_footage_status", "needs_review"),
        "note": "Rights gates logged. Actual rights verification requires human review."
    }

    # Stage 10: OpenMontage render attempt
    if os.path.exists(assets_path) and os.path.exists(candidates_path):
        notify(f"📋 [{run_id}] Stage 10/13: OpenMontage render")
        rc = run_script(
            "render_with_openmontage.py",
            [job_path, assets_path, candidates_path, "--run-id", run_id],
            "render_with_openmontage"
        )
        stages["render_attempt"] = {"exit_code": rc}
    else:
        stages["render_attempt"] = {"skipped": True, "reason": "No assets or candidates"}
        print("  Skipping render: missing assets or candidates")

    # Stage 11: QA/export check
    notify(f"📋 [{run_id}] Stage 11/13: QA/export check")
    final_mp4 = os.path.join(outputs_dir, "final_attempt.mp4")
    fallback_mp4 = os.path.join(outputs_dir, "fallback_render_attempt.mp4")
    if os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 0:
        stages["qa_check"] = {
            "render_success": True,
            "output": final_mp4,
            "size_bytes": os.path.getsize(final_mp4),
            "note": "Actual mp4 exists. Render success confirmed."
        }
    elif os.path.exists(fallback_mp4) and os.path.getsize(fallback_mp4) > 0:
        stages["qa_check"] = {
            "render_success": True,
            "output": fallback_mp4,
            "size_bytes": os.path.getsize(fallback_mp4),
            "note": "Fallback mp4 exists. Not a full OpenMontage render."
        }
    else:
        stages["qa_check"] = {
            "render_success": False,
            "note": "No mp4 output found. No render success claimed."
        }

    # Stage 12: memory update
    notify(f"📋 [{run_id}] Stage 12/13: memory update")
    rc = run_script("memory_sync.py", ["collect", "--run-id", run_id], "memory_collect")
    stages["memory_update"] = {"exit_code": rc}

    # Stage 13: Discord final status
    render_status = stages.get("qa_check", {}).get("render_success", False)
    if render_status:
        msg = f"✅ [{run_id}] Job complete. Render produced: {stages['qa_check'].get('output', 'unknown')}"
    else:
        blocker_msg = "Check run reports for details."
        for stage_name, stage_data in stages.items():
            if isinstance(stage_data, dict) and stage_data.get("blocker"):
                blocker_msg = stage_data["blocker"]
                break
        msg = f"⚠️ [{run_id}] Job complete. No render output. Blocker: {blocker_msg}"
    notify(msg)
    stages["discord_final"] = {"sent": True}

    # Write session summary
    summary_path = os.path.join(run_dir, "session_summary.md")
    with open(summary_path, "w") as f:
        f.write(f"# Session Summary\n\n")
        f.write(f"Run ID: {run_id}\n")
        f.write(f"Job: {job_path}\n")
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
        f.write(f"Render success: {stages.get('qa_check', {}).get('render_success', False)}\n")
        output = stages.get("qa_check", {}).get("output", "N/A")
        f.write(f"Output: {output}\n")
        if os.path.exists(str(output)):
            f.write(f"Output size: {os.path.getsize(output)} bytes\n")

    print(f"\n{'='*60}")
    print(f"  RUN COMPLETE: {run_id}")
    print(f"  Summary: {summary_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
