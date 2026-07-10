#!/usr/bin/env python3
"""Orchestrator: runs the full title/theme job pipeline.

Real order:
1. repo_setup_status
2. skill_system_status
3. llm_api_status
4. Hermes runtime start
5. match_fact_lock
6. source discovery and verification
7. proxy download
8. visual/audio analysis
9. timestamp extraction and clip scoring
10. arc revision
11. story/audio/visual/graphics plans
12. artifact gate
13. OpenMontage artifact conversion
14. OpenMontage render
15. QA
16. session summary
17. one memory update
18. one GitHub push
19. Discord final status
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

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

    stages = {}

    # Stage 1: repo_setup_status
    notify(f"[{run_id}] Stage 1/19: repo setup")
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
    notify(f"[{run_id}] Stage 2/19: skill system")
    skill_report = BASE_DIR / "state" / "runs" / "skill_install_report.md"
    stages["skill_system_status"] = {"report_exists": skill_report.is_file()}
    print(f"  Skill report exists: {skill_report.is_file()}")

    # Stage 3: llm_api_status
    notify(f"[{run_id}] Stage 3/19: LLM API")
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

    # Stage 4: Hermes runtime start
    notify(f"[{run_id}] Stage 4/19: Hermes runtime")
    rc = run_script("hermes_runtime.py", [title, theme, run_id], "hermes_runtime")
    stages["hermes_runtime"] = {"exit_code": rc}
    hermes_report = run_dir / "hermes_run_report.json"
    if hermes_report.is_file():
        with open(hermes_report) as f:
            hr = json.load(f)
        stages["hermes_runtime"]["hermes_invoked"] = hr.get("hermes_invoked", False)
        stages["hermes_runtime"]["session_id"] = hr.get("session_id")
        stages["hermes_runtime"]["blocker"] = hr.get("blocker")

    # Stage 5: match_fact_lock (created by Hermes, verify it exists)
    notify(f"[{run_id}] Stage 5/19: match fact lock")
    match_fact = run_dir / "hermes_artifacts" / "match_fact_lock.json"
    if match_fact.is_file():
        with open(match_fact) as f:
            mf = json.load(f)
        stages["match_fact_lock"] = {
            "status": mf.get("verification_status", "unknown"),
            "match": mf.get("match"),
            "opponent": mf.get("opponent"),
            "date": mf.get("date"),
        }
        print(f"  Match facts: {mf.get('match')} vs {mf.get('opponent')} ({mf.get('verification_status')})")
    else:
        stages["match_fact_lock"] = {"status": "missing", "note": "Match facts not produced by Hermes"}
        print("  WARN: match_fact_lock.json not found")

    # Stage 6: source discovery and verification
    notify(f"[{run_id}] Stage 6/19: source discovery")
    rc = run_script("source_discovery.py", [job_path, "--run-id", run_id], "source_discovery")
    stages["source_discovery"] = {"exit_code": rc}
    candidates_path = run_dir / "source_candidates.json"
    if candidates_path.is_file():
        with open(candidates_path) as f:
            cand_data = json.load(f)
        stages["source_discovery"]["candidates_count"] = cand_data.get("total_candidates", 0)
        stages["source_discovery"]["blocker"] = cand_data.get("blocker")

    # Stage 7: proxy download
    if candidates_path.is_file():
        notify(f"[{run_id}] Stage 7/19: proxy download")
        rc = run_script("download_sources.py", [str(candidates_path), "--run-id", run_id], "download_sources")
        stages["download_sources"] = {"exit_code": rc}
    else:
        print("  Skipping download: no candidates file")
        stages["download_sources"] = {"skipped": True}

    # Stage 8: visual/audio analysis
    notify(f"[{run_id}] Stage 8/19: visual/audio analysis")
    rc = run_script("media_analysis.py", [run_id], "media_analysis")
    stages["media_analysis"] = {"exit_code": rc}

    # Stage 9: timestamp extraction and clip scoring
    notify(f"[{run_id}] Stage 9/19: timestamp/clip scoring")
    stages["timestamp_clip_scoring"] = {
        "status": "pending",
        "note": "Timestamp and clip scoring requires media inspection results from analysis stage.",
    }

    # Stage 10: arc revision
    notify(f"[{run_id}] Stage 10/19: arc revision")
    stages["arc_revision"] = {"status": "pending", "note": "Arc revision gated on full media analysis."}

    # Stage 11: story/audio/visual/graphics plans
    notify(f"[{run_id}] Stage 11/19: story/audio/visual/graphics plans")
    stages["editorial_plans"] = {"status": "pending", "note": "Editorial plans pending artifact gate."}

    # Stage 12: artifact gate
    notify(f"[{run_id}] Stage 12/19: artifact gate")
    rc = run_script("editorial_artifact_gate.py", [run_id], "artifact_gate")
    stages["artifact_gate"] = {"exit_code": rc}
    gate_result = run_dir / "artifact_gate_result.json"
    if gate_result.is_file():
        with open(gate_result) as f:
            gr = json.load(f)
        stages["artifact_gate"]["gate_passed"] = gr.get("gate_passed", False)
        stages["artifact_gate"]["blocker"] = gr.get("blocker")
        print(f"  Artifact gate: {'PASSED' if gr.get('gate_passed') else 'BLOCKED'}")

    # Stage 13: OpenMontage artifact conversion (inside render step)
    notify(f"[{run_id}] Stage 13/19: OpenMontage artifact conversion")

    # Stage 14: OpenMontage render
    assets_path = run_dir / "downloaded_assets.json"
    if assets_path.is_file() and candidates_path.is_file():
        notify(f"[{run_id}] Stage 14/19: OpenMontage render")
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
    notify(f"[{run_id}] Stage 15/19: QA")
    rc = run_script("qa_check.py", [run_id], "qa_check")
    stages["qa_check"] = {"exit_code": rc}
    qa_report = run_dir / "full_qa_report.json"
    if qa_report.is_file():
        with open(qa_report) as f:
            qa = json.load(f)
        stages["qa_check"]["qa_passed"] = qa.get("qa_passed", False)
        stages["qa_check"]["issues"] = qa.get("issues", [])

    final_mp4 = outputs_dir / "final_openmontage_render.mp4"
    fallback_mp4 = outputs_dir / "fallback_render_attempt.mp4"
    if final_mp4.is_file() and final_mp4.stat().st_size > 0:
        stages["render_output"] = {
            "render_success": True,
            "output": str(final_mp4),
            "size_bytes": final_mp4.stat().st_size,
            "note": "OpenMontage/final mp4 exists.",
        }
    elif fallback_mp4.is_file() and fallback_mp4.stat().st_size > 0:
        stages["render_output"] = {
            "render_success": True,
            "output": str(fallback_mp4),
            "size_bytes": fallback_mp4.stat().st_size,
            "note": "Fallback mp4 exists. Not a full OpenMontage render.",
        }
    else:
        stages["render_output"] = {"render_success": False, "note": "No mp4 output found."}

    # Stage 16: session summary
    notify(f"[{run_id}] Stage 16/19: session summary")
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

    # Stage 17: one memory update
    notify(f"[{run_id}] Stage 17/19: memory update")
    rc = run_script("memory_sync.py", ["collect", "--run-id", run_id], "memory_collect")
    stages["memory_update"] = {"exit_code": rc}

    # Stage 18: one GitHub push
    notify(f"[{run_id}] Stage 18/19: GitHub push")
    rc = run_script("memory_sync.py", ["push", "--run-id", run_id], "memory_push")
    stages["github_push"] = {"exit_code": rc}

    # Stage 19: Discord final status
    render_status = stages.get("render_output", {}).get("render_success", False)
    if render_status:
        msg = f"[{run_id}] Job complete. Render: {stages['render_output'].get('output', 'unknown')}"
    else:
        blocker_msg = "Check run reports for details."
        for stage_name, stage_data in stages.items():
            if isinstance(stage_data, dict) and stage_data.get("blocker"):
                blocker_msg = stage_data["blocker"]
                break
        msg = f"[{run_id}] Job complete. No render output. Blocker: {blocker_msg}"
    notify(msg)
    stages["discord_final"] = {"sent": True}

    print(f"\n{'='*60}")
    print(f"  RUN COMPLETE: {run_id}")
    print(f"  Summary: {summary_path}")
    print(f"  Render success: {render_status}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
