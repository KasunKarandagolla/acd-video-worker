#!/usr/bin/env python3
"""Attempt render through OpenMontage or fallback ffmpeg."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def inspect_openmontage():
    om_path = os.path.join(BASE_DIR, "external", "OpenMontage")
    if not os.path.isdir(om_path):
        return {"available": False, "reason": "Not cloned"}
    result = {"available": True, "render_commands": [], "has_pipeline_defs": False, "has_schemas": False}
    for root, dirs, files in os.walk(om_path):
        for fname in files:
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, om_path)
            if fname.endswith(".py"):
                with open(fpath) as f:
                    content = f.read(500).lower()
                if "render" in content or "pipeline" in content:
                    result["render_commands"].append(rel)
            if "pipeline_def" in rel.lower() or "pipeline" in rel.lower():
                if fname.endswith((".json", ".yaml", ".yml")):
                    result["has_pipeline_defs"] = True
            if "schema" in rel.lower():
                result["has_schemas"] = True
        if root == om_path:
            for d in dirs:
                if d in ("bin", "cli", "scripts"):
                    result["render_commands"].append(f"{d}/")
    return result


def try_openmontage_render(job, assets, om_info, run_dir, outputs_dir):
    om_path = os.path.join(BASE_DIR, "external", "OpenMontage")
    render_plan = {
        "openmontage_available": om_info["available"],
        "render_attempted": False,
        "render_success": False,
        "output_path": None,
        "error": None,
        "fallback_used": False
    }

    video_files = [a for a in assets if a.get("file", "").endswith((".mp4", ".mkv", ".webm", ".mov"))]

    if not video_files:
        render_plan["error"] = "No downloaded video files to render."
        return render_plan

    if om_info["available"]:
        # Try to find and run a render command
        if om_info["render_commands"]:
            render_plan["render_attempted"] = True
            print("OpenMontage found. Attempting render...")
            print(f"  Detected render-related files: {om_info['render_commands'][:5]}")

            assets_dir = os.path.join(run_dir, "assets", "raw")
            video_inputs = " ".join([f"--input {os.path.join(assets_dir, a['file'])}" for a in video_files[:5]])

            for cmd_hint in om_info["render_commands"][:3]:
                cmd_path = os.path.join(om_path, cmd_hint)
                if os.path.isfile(cmd_path):
                    cmd = ["python3", cmd_path, video_inputs, "-o", outputs_dir]
                    print(f"  Running: {' '.join(cmd[:4])}...")
                    try:
                        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=om_path)
                        if proc.returncode == 0:
                            # Check for output
                            for fname in os.listdir(outputs_dir):
                                if fname.endswith(".mp4"):
                                    render_plan["render_success"] = True
                                    render_plan["output_path"] = os.path.join(outputs_dir, fname)
                                    print(f"  Render success: {render_plan['output_path']}")
                                    break
                        if render_plan["render_success"]:
                            break
                    except subprocess.TimeoutExpired:
                        print("  Render timed out.")
                    except Exception as e:
                        print(f"  Render error: {e}")

        if not render_plan["render_success"]:
            print("OpenMontage render path not clearly detected or failed.")
    else:
        print("OpenMontage not available.")

    # Fallback ffmpeg if no success yet
    if not render_plan["render_success"] and video_files:
        print("Creating fallback render with ffmpeg...")
        render_plan["fallback_used"] = True
        render_plan["render_attempted"] = True
        fallback_path = os.path.join(outputs_dir, "fallback_render_attempt.mp4")
        os.makedirs(outputs_dir, exist_ok=True)

        first_video = os.path.join(run_dir, "assets", "raw", video_files[0]["file"])
        if os.path.exists(first_video):
            try:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", first_video,
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "23",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-t", "30",
                    fallback_path
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if proc.returncode == 0 and os.path.exists(fallback_path) and os.path.getsize(fallback_path) > 0:
                    render_plan["render_success"] = True
                    render_plan["output_path"] = fallback_path
                    print(f"Fallback render success: {fallback_path}")
                else:
                    error_msg = proc.stderr[-500:] if proc.stderr else str(proc.returncode)
                    render_plan["error"] = f"Fallback ffmpeg failed: {error_msg}"
                    print(f"  Fallback failed.")
            except Exception as e:
                render_plan["error"] = f"Fallback error: {e}"

    return render_plan


def main():
    if len(sys.argv) < 4:
        print("Usage: python render_with_openmontage.py <job.yaml> <downloaded_assets.json> <source_candidates.json> --run-id <run_id>")
        sys.exit(1)

    job_path = sys.argv[1]
    assets_path = sys.argv[2]
    candidates_path = sys.argv[3]
    run_id = None
    for i, arg in enumerate(sys.argv):
        if arg == "--run-id" and i + 1 < len(sys.argv):
            run_id = sys.argv[i + 1]

    if not run_id:
        print("ERROR: --run-id is required")
        sys.exit(1)

    import yaml
    with open(job_path) as f:
        job = yaml.safe_load(f)
    with open(assets_path) as f:
        assets_data = json.load(f)
    with open(candidates_path) as f:
        candidates_data = json.load(f)

    run_dir = os.path.join(BASE_DIR, "state", "runs", run_id)
    outputs_dir = os.path.join(BASE_DIR, "outputs", run_id)
    os.makedirs(outputs_dir, exist_ok=True)

    om_info = inspect_openmontage()

    assets = assets_data.get("downloads", [])
    render_plan = try_openmontage_render(job, assets, om_info, run_dir, outputs_dir)

    report = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
        "openmontage_inspection": om_info,
        "render_result": render_plan,
        "video_files_available": [a.get("file") for a in assets if a.get("file", "").endswith((".mp4", ".mkv", ".webm", ".mov"))],
        "blocker": None
    }

    if not render_plan["render_success"]:
        report["blocker"] = (
            render_plan.get("error") or
            "Render did not produce an output mp4. No render success to claim."
        )

    plan_path = os.path.join(run_dir, "openmontage_render_plan.json")
    with open(plan_path, "w") as f:
        json.dump(report, f, indent=2)

    md_path = os.path.join(run_dir, "render_report.md")
    with open(md_path, "w") as f:
        f.write(f"# Render Report\n\n")
        f.write(f"Run: {run_id}\n\n")
        f.write(f"## OpenMontage Status\n\n")
        f.write(f"- Available: {om_info['available']}\n")
        if om_info["render_commands"]:
            f.write(f"- Render-related files: {', '.join(om_info['render_commands'][:10])}\n")
        f.write(f"- Has pipeline defs: {om_info['has_pipeline_defs']}\n")
        f.write(f"- Has schemas: {om_info['has_schemas']}\n\n")

        f.write(f"## Render Attempt\n\n")
        f.write(f"- Attempted: {render_plan['render_attempted']}\n")
        f.write(f"- Success: {render_plan['render_success']}\n")
        f.write(f"- Fallback used: {render_plan['fallback_used']}\n")
        f.write(f"- Output: {render_plan.get('output_path', 'N/A')}\n")
        if render_plan.get("error"):
            f.write(f"- Error: {render_plan['error']}\n")

        f.write(f"\n## Assets Available\n\n")
        for a in assets:
            f.write(f"- {a.get('file', '?')}\n")

        if report.get("blocker"):
            f.write(f"\n## Blocker\n\n{report['blocker']}\n")

    print(f"Render report: {md_path}")
    print(f"Render plan: {plan_path}")

    if render_plan["render_success"]:
        print(f"✓ Render output: {render_plan.get('output_path', '')}")
    else:
        print(f"✗ Render did not produce output.")
        if report.get("blocker"):
            print(f"BLOCKER: {report['blocker']}")


if __name__ == "__main__":
    main()
