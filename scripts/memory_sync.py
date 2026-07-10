#!/usr/bin/env python3
"""Memory sync: hydrate, collect, and push to GitHub."""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(BASE_DIR, "state", "hermes_memory")
RUNS_DIR = os.path.join(BASE_DIR, "state", "runs")


def ensure_memory_dir():
    os.makedirs(MEMORY_DIR, exist_ok=True)
    for fname in ["MEMORY.md", "USER.md", "learned_patterns.jsonl"]:
        fpath = os.path.join(MEMORY_DIR, fname)
        if not os.path.exists(fpath):
            with open(fpath, "w") as f:
                if fname == "MEMORY.md":
                    f.write("# Hermes Memory\n\nInitialized by acd-video-worker memory_sync\n")
                elif fname == "USER.md":
                    f.write("# User Profile\n\nInitialized by acd-video-worker\n")
                elif fname == "learned_patterns.jsonl":
                    f.write("")


def hydrate():
    ensure_memory_dir()

    hermes_memory_path = os.path.join(BASE_DIR, "external", "Hermes-Agent")
    if os.path.isdir(hermes_memory_path):
        hermes_memory_targets = [
            os.path.join(hermes_memory_path, "memory"),
            os.path.join(hermes_memory_path, "data", "memory"),
            os.path.join(hermes_memory_path, "agent", "memory"),
        ]
        linked = False
        for target in hermes_memory_targets:
            if os.path.isdir(target) or not os.path.exists(target):
                os.makedirs(target, exist_ok=True)
                for fname in ["MEMORY.md", "USER.md", "learned_patterns.jsonl"]:
                    src = os.path.join(MEMORY_DIR, fname)
                    dst = os.path.join(target, fname)
                    if not os.path.exists(dst):
                        shutil.copy2(src, dst)
                linked = True
                print(f"Synced memory to Hermes location: {target}")
                break
        if not linked:
            print("Hermes-Agent found but no standard memory directory detected.")
            print("Keeping memory in state/hermes_memory/ (adapter-facing mode).")
    else:
        print("Hermes-Agent not cloned yet. Memory stays in state/hermes_memory/.")
        print("Adapter-facing mode: external tools should read from state/hermes_memory/.")

    print(f"Memory directory: {MEMORY_DIR}")
    for fname in os.listdir(MEMORY_DIR):
        fpath = os.path.join(MEMORY_DIR, fname)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            print(f"  {fname} ({size} bytes)")


def collect(run_id):
    if not run_id:
        print("ERROR: --run-id is required for collect")
        sys.exit(1)

    run_dir = os.path.join(RUNS_DIR, run_id)
    if not os.path.isdir(run_dir):
        print(f"ERROR: run directory not found: {run_dir}")
        sys.exit(1)

    ensure_memory_dir()
    now = datetime.now(timezone.utc).isoformat()

    memory_update = {
        "timestamp": now,
        "run_id": run_id,
        "summary": {},
        "learned_patterns": []
    }

    session_summary = os.path.join(run_dir, "session_summary.md")
    if os.path.exists(session_summary):
        with open(session_summary) as f:
            content = f.read()
        memory_update["summary"]["session_summary_length"] = len(content)
        memory_update["summary"]["session_summary_preview"] = content[:500]

    for report_file in ["source_discovery_report.md", "download_report.md", "render_report.md"]:
        rpath = os.path.join(run_dir, report_file)
        if os.path.exists(rpath):
            with open(rpath) as f:
                content = f.read()
            memory_update["summary"][report_file.replace(".md", "")] = content[:300]

    patterns_file = os.path.join(MEMORY_DIR, "learned_patterns.jsonl")
    with open(patterns_file, "a") as f:
        f.write(json.dumps(memory_update) + "\n")

    mem_update = os.path.join(run_dir, "memory_update_report.md")
    with open(mem_update, "w") as f:
        f.write(f"# Memory Update Report\n\nRun: {run_id}\nTimestamp: {now}\n\n")
        f.write("## Summary\n\n")
        for key, val in memory_update["summary"].items():
            f.write(f"- **{key}**: {val}\n")
        f.write("\nPattern appended to learned_patterns.jsonl\n")

    print(f"Memory collected for run {run_id}")
    print(f"Update report: {mem_update}")


def push(run_id=None):
    token = os.environ.get("GITHUB_TOKEN", "")
    repo_url = os.environ.get("PRIVATE_REPO_URL", "")

    if not token or not repo_url:
        print("WARN: GITHUB_TOKEN or PRIVATE_REPO_URL not set. Cannot push.")
        return

    paths_to_add = ["state/hermes_memory/"]
    if run_id:
        run_dir = os.path.join(RUNS_DIR, run_id)
        if os.path.isdir(run_dir):
            paths_to_add.append(f"state/runs/{run_id}/")
    paths_to_add.append("locks/")

    try:
        authenticated_url = repo_url.replace("https://", f"https://{token}@")
        result = subprocess.run(
            ["git", "remote", "set-url", "origin", authenticated_url],
            capture_output=True, text=True, cwd=BASE_DIR
        )
        if result.returncode != 0:
            print("WARN: Could not set git remote URL (not a git repo yet?)")
            return

        for path in paths_to_add:
            subprocess.run(["git", "add", path], capture_output=True, cwd=BASE_DIR)

        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            capture_output=True, cwd=BASE_DIR
        )
        if diff.returncode == 0:
            print("No changes to commit.")
            return

        commit_msg = f"memory-sync: updates for run {run_id}" if run_id else "memory-sync: periodic update"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            capture_output=True, cwd=BASE_DIR
        )
        push_result = subprocess.run(
            ["git", "push", "origin", "HEAD"],
            capture_output=True, text=True, cwd=BASE_DIR
        )
        if push_result.returncode == 0:
            print(f"Memory pushed to GitHub for run {run_id}")
        else:
            blocker_msg = f"Git push failed: {push_result.stderr[:500]}"
            print(f"BLOCKER: {blocker_msg}")
            blocker_path = os.path.join(RUNS_DIR, run_id or "unknown", "git_push_blocker.md")
            os.makedirs(os.path.dirname(blocker_path), exist_ok=True)
            with open(blocker_path, "w") as f:
                f.write(f"# Git Push Blocker\n\n{blocker_msg}\n")
    except Exception as e:
        print(f"WARN: Git push failed: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python memory_sync.py hydrate")
        print("  python memory_sync.py collect --run-id <run_id>")
        print("  python memory_sync.py push --run-id <run_id>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "hydrate":
        hydrate()
    elif command == "collect":
        run_id = None
        for i, arg in enumerate(sys.argv):
            if arg == "--run-id" and i + 1 < len(sys.argv):
                run_id = sys.argv[i + 1]
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
