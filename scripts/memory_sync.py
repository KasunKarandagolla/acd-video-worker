#!/usr/bin/env python3
"""Memory sync: hydrate, collect once per run, and push to GitHub.

Idempotency:
- Collect memory exactly once per run (uses state/runs/<run_id>/.memory_collected marker)
- Push to GitHub exactly once per run
- Repeated cleanup calls do not append duplicate patterns
- Saves only verified reusable lessons
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "state" / "hermes_memory"
RUNS_DIR = BASE_DIR / "state" / "runs"


def ensure_memory_dir():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    for fname in ["MEMORY.md", "USER.md", "learned_patterns.jsonl"]:
        fpath = MEMORY_DIR / fname
        if not fpath.exists():
            with open(fpath, "w") as f:
                if fname == "MEMORY.md":
                    f.write("# Hermes Memory\n\nInitialized by acd-video-worker memory_sync\n")
                elif fname == "USER.md":
                    f.write("# User Profile\n\nInitialized by acd-video-worker\n")
                elif fname == "learned_patterns.jsonl":
                    f.write("")


def hydrate():
    ensure_memory_dir()
    hermes_memory_path = BASE_DIR / "external" / "Hermes-Agent"
    if hermes_memory_path.is_dir():
        for target_rel in ["memory", "data/memory", "agent/memory"]:
            target = hermes_memory_path / target_rel
            target.mkdir(parents=True, exist_ok=True)
            for fname in ["MEMORY.md", "USER.md", "learned_patterns.jsonl"]:
                src = MEMORY_DIR / fname
                dst = target / fname
                if src.is_file() and not dst.is_file():
                    shutil.copy2(str(src), str(dst))
            print(f"Synced memory to Hermes location: {target}")
            break
    print(f"Memory directory: {MEMORY_DIR}")


def collect(run_id):
    if not run_id:
        print("ERROR: --run-id is required for collect")
        sys.exit(1)

    run_dir = RUNS_DIR / run_id
    if not run_dir.is_dir():
        print(f"ERROR: run directory not found: {run_dir}")
        sys.exit(1)

    marker = run_dir / ".memory_collected"
    if marker.exists():
        print(f"Memory already collected for run {run_id}. Use --force to override.")
        return

    ensure_memory_dir()
    now = datetime.now(timezone.utc).isoformat()

    memory_update = {
        "timestamp": now,
        "run_id": run_id,
        "learned_patterns": [],
    }

    pattern = {"event": "run_completed", "run_id": run_id, "timestamp": now}

    hermes_report = run_dir / "hermes_run_report.json"
    if hermes_report.is_file():
        try:
            with open(hermes_report) as f:
                hr = json.load(f)
            pattern["hermes_invoked"] = hr.get("hermes_invoked", False)
            pattern["skills_loaded"] = len(hr.get("selected_skills", []))
        except Exception:
            pass

    render_report = run_dir / "openmontage_execution_report.json"
    if render_report.is_file():
        try:
            with open(render_report) as f:
                rr = json.load(f)
            pattern["render_success"] = rr.get("render_result", {}).get("success", False)
            pattern["render_engine"] = rr.get("render_result", {}).get("engine")
        except Exception:
            pass

    qa_report = run_dir / "full_qa_report.json"
    if qa_report.is_file():
        try:
            with open(qa_report) as f:
                qa = json.load(f)
            pattern["qa_passed"] = qa.get("qa_passed", False)
        except Exception:
            pass

    if pattern.get("render_success") and pattern.get("qa_passed"):
        memory_update["learned_patterns"].append({
            "type": "working_command",
            "run_id": run_id,
            "what": "Full pipeline completed: Hermes -> V7 skills -> sources -> OpenMontage render -> QA",
            "status": "verified",
        })

    if pattern.get("hermes_invoked"):
        memory_update["learned_patterns"].append({
            "type": "integration_lesson",
            "run_id": run_id,
            "what": f"Hermes invoked with {pattern.get('skills_loaded', 0)} V7 skills loaded",
            "status": "verified",
        })

    patterns_file = MEMORY_DIR / "learned_patterns.jsonl"
    existing_entries = set()
    if patterns_file.is_file():
        with open(patterns_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        for lp in entry.get("learned_patterns", []):
                            lp_key = f"{lp.get('type', '')}:{lp.get('what', '')}"
                            existing_entries.add(lp_key)
                    except (json.JSONDecodeError, Exception):
                        pass

    with open(patterns_file, "a") as f:
        for lp in memory_update["learned_patterns"]:
            lp_key = f"{lp['type']}:{lp['what']}"
            if lp_key not in existing_entries:
                f.write(json.dumps({"timestamp": now, "run_id": run_id, "learned_patterns": [lp]}) + "\n")
                existing_entries.add(lp_key)

    marker.write_text(now + "\n")

    mem_update = run_dir / "memory_update_report.md"
    with open(mem_update, "w") as f:
        f.write(f"# Memory Update Report\n\nRun: {run_id}\nTimestamp: {now}\n\n")
        f.write("## Patterns Collected\n\n")
        for lp in memory_update["learned_patterns"]:
            f.write(f"- [{lp['type']}] {lp['what']} ({lp['status']})\n")
        f.write(f"\nMarker: {marker}\n")

    print(f"Memory collected for run {run_id}")
    print(f"  Patterns: {len(memory_update['learned_patterns'])}")
    print(f"  Marker: {marker}")


def push(run_id=None):
    token = os.environ.get("GITHUB_TOKEN", "")
    repo_url = os.environ.get("PRIVATE_REPO_URL", "")

    if not token or not repo_url:
        print("WARN: GITHUB_TOKEN or PRIVATE_REPO_URL not set. Cannot push.")
        return

    paths_to_add = ["state/hermes_memory/"]
    if run_id:
        run_dir = RUNS_DIR / run_id
        if run_dir.is_dir():
            paths_to_add.append(f"state/runs/{run_id}/")
    paths_to_add.append("locks/")

    try:
        authenticated_url = repo_url.replace("https://", f"https://{token}@")
        result = subprocess.run(
            ["git", "remote", "set-url", "origin", authenticated_url],
            capture_output=True, text=True, cwd=str(BASE_DIR)
        )
        if result.returncode != 0:
            print("WARN: Could not set git remote URL (not a git repo yet?)")
            return

        for path in paths_to_add:
            subprocess.run(["git", "add", path], capture_output=True, cwd=str(BASE_DIR))

        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            capture_output=True, cwd=str(BASE_DIR)
        )
        if diff.returncode == 0:
            print("No changes to commit.")
            return

        commit_msg = f"memory-sync: updates for run {run_id}" if run_id else "memory-sync: periodic update"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            capture_output=True, cwd=str(BASE_DIR)
        )
        push_result = subprocess.run(
            ["git", "push", "origin", "HEAD"],
            capture_output=True, text=True, cwd=str(BASE_DIR)
        )
        if push_result.returncode == 0:
            print(f"Memory pushed to GitHub for run {run_id}")
        else:
            blocker_msg = f"Git push failed: {push_result.stderr[:500]}"
            print(f"BLOCKER: {blocker_msg}")
    except Exception as e:
        print(f"WARN: Git push failed: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python memory_sync.py hydrate")
        print("  python memory_sync.py collect --run-id <run_id> [--force]")
        print("  python memory_sync.py push --run-id <run_id>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "hydrate":
        hydrate()
    elif command == "collect":
        run_id = None
        force = False
        for i, arg in enumerate(sys.argv):
            if arg == "--run-id" and i + 1 < len(sys.argv):
                run_id = sys.argv[i + 1]
            if arg == "--force":
                force = True
        if force and run_id:
            marker = RUNS_DIR / run_id / ".memory_collected"
            if marker.exists():
                marker.unlink()
                print(f"Removed marker for {run_id}. Will re-collect.")
        collect(run_id)
    elif command == "push":
        run_id = None
        for i, arg in enumerate(sys.argv):
            if arg == "--run-id" and i + 1 < len(sys.argv):
                run_id = sys.argv[i + 1]
        push(run_id)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
