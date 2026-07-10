#!/usr/bin/env python3
"""Install dependencies for Hermes-Agent and OpenMontage integration.

Does NOT clone repositories — that is done exclusively by
bootstrap/clone_repos.sh. This script installs dependencies only from
the already cloned and pinned paths:
  external/Hermes-Agent
  external/OpenMontage

If either repo is missing, exits with a clear blocker.
"""
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HERMES_REPO = BASE_DIR / "external" / "Hermes-Agent"
OM_REPO = BASE_DIR / "external" / "OpenMontage"
HERMES_VENV = Path("/kaggle/working/.venvs/hermes")


def main():
    blockers = []

    if not HERMES_REPO.is_dir() or not (HERMES_REPO / "run_agent.py").is_file():
        blockers.append(
            f"Hermes-Agent not found at {HERMES_REPO}. "
            f"Run bootstrap/clone_repos.sh first."
        )
    else:
        print(f"Hermes-Agent repo: {HERMES_REPO}")

    if not OM_REPO.is_dir() or not (OM_REPO / "pipeline_defs").is_dir():
        blockers.append(
            f"OpenMontage not found at {OM_REPO}. "
            f"Run bootstrap/clone_repos.sh first."
        )
    else:
        print(f"OpenMontage repo: {OM_REPO}")

    if blockers:
        for b in blockers:
            print(f"BLOCKER: {b}")
            sys.exit(1)

    if not HERMES_VENV.exists():
        print("Creating Hermes virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(HERMES_VENV)], check=True)
    else:
        print(f"Hermes venv: {HERMES_VENV}")

    pip = HERMES_VENV / "bin" / "pip"
    if pip.is_file():
        print("Installing Hermes dependencies...")
        subprocess.run([str(pip), "install", "--upgrade", "pip"], check=True)
        req_file = HERMES_REPO / "requirements.txt"
        if req_file.is_file():
            subprocess.run([str(pip), "install", "-r", str(req_file)], check=True)
        subprocess.run(
            [str(pip), "install", "openai", "pydantic", "pyyaml", "requests", "jsonschema"],
            check=True,
        )

    print("Dependencies ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
