#!/usr/bin/env python3
"""Install dependencies for Hermes-Agent and OpenMontage integration.

Does NOT clone repositories — that is done exclusively by
bootstrap/clone_repos.sh. This script installs dependencies only from
the already cloned and pinned paths:
  external/Hermes-Agent
  external/OpenMontage

If either repo is missing, exits with a clear blocker.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HERMES_REPO = BASE_DIR / "external" / "Hermes-Agent"
OM_REPO = BASE_DIR / "external" / "OpenMontage"
REPORT_JSON = BASE_DIR / "state" / "runs" / "runtime_dependency_report.json"


def _is_kaggle() -> bool:
    return bool(os.environ.get("KAGGLE_KERNEL_RUN_TYPE")) or os.path.isdir("/kaggle/working")


def _resolve_venv_path() -> Path:
    env_venv = os.environ.get("ACD_HERMES_VENV")
    if env_venv:
        return Path(env_venv)
    if _is_kaggle():
        return Path("/kaggle/working/.venvs/hermes")
    return BASE_DIR / ".runtime" / "venvs" / "hermes"


def _ensure_virtualenv(report: dict) -> None:
    try:
        import virtualenv  # noqa: F401
        report["virtualenv_install_attempted"] = False
    except ImportError:
        print("Checking virtualenv")
        report["virtualenv_install_attempted"] = True
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "virtualenv"],
            capture_output=True, text=True
        )
        report["virtualenv_install_exit_code"] = result.returncode
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to install virtualenv: {result.stderr.strip()[:300]}"
            )


def _verify_venv(venv_path: Path) -> bool:
    python_bin = venv_path / "bin" / "python"
    pip_bin = venv_path / "bin" / "pip"
    if not python_bin.is_file() or not pip_bin.is_file():
        return False
    result = subprocess.run(
        [str(python_bin), "-m", "pip", "--version"],
        capture_output=True, text=True
    )
    return result.returncode == 0


def _create_venv(venv_path: Path) -> None:
    python_exe = shutil.which("python3") or sys.executable
    if venv_path.exists():
        shutil.rmtree(venv_path)
    venv_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable, "-m", "virtualenv",
            "--clear",
            "--python", python_exe,
            str(venv_path),
        ],
        check=True, capture_output=True, text=True
    )


def _upgrade_packaging_tools(venv_path: Path) -> None:
    python_bin = venv_path / "bin" / "python"
    subprocess.run(
        [str(python_bin), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        check=True, capture_output=True, text=True
    )


def _run_pip(python_bin: Path, args: list) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(python_bin), "-m", "pip"] + args,
        capture_output=True, text=True
    )


def _write_report(report: dict) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_JSON, "w") as f:
        json.dump(report, f, indent=2, default=str)


def _record_venv_state(venv_path: Path, report: dict) -> None:
    python_bin = venv_path / "bin" / "python"
    pip_bin = venv_path / "bin" / "pip"
    report["venv_python_exists"] = python_bin.is_file()
    report["venv_pip_exists"] = pip_bin.is_file()
    if python_bin.is_file() and pip_bin.is_file():
        pip_check = subprocess.run(
            [str(python_bin), "-m", "pip", "--version"],
            capture_output=True, text=True
        )
        report["pip_verification_exit_code"] = pip_check.returncode


def main() -> int:
    report = {
        "base_python": shutil.which("python3") or sys.executable,
        "environment_creator": "virtualenv",
        "virtualenv_install_attempted": False,
        "virtualenv_install_exit_code": None,
        "venv_path": None,
        "venv_recreated": False,
        "venv_python_exists": False,
        "venv_pip_exists": False,
        "pip_verification_exit_code": None,
        "dependency_commands": [],
        "command_exit_codes": [],
        "final_status": None,
        "safe_error_summary": None,
    }

    blockers = []

    if not HERMES_REPO.is_dir() or not (HERMES_REPO / "run_agent.py").is_file():
        blockers.append(
            f"Hermes-Agent not found at {HERMES_REPO}. "
            f"Run bootstrap/clone_repos.sh first."
        )

    if not OM_REPO.is_dir() or not (OM_REPO / "pipeline_defs").is_dir():
        blockers.append(
            f"OpenMontage not found at {OM_REPO}. "
            f"Run bootstrap/clone_repos.sh first."
        )

    if blockers:
        report["final_status"] = "blocked"
        report["safe_error_summary"] = "; ".join(blockers)
        _write_report(report)
        for b in blockers:
            print(f"BLOCKER: {b}")
        return 1

    print(f"Hermes-Agent repo: {HERMES_REPO}")
    print(f"OpenMontage repo: {OM_REPO}")

    venv_path = _resolve_venv_path()
    report["venv_path"] = str(venv_path)

    try:
        _ensure_virtualenv(report)
    except RuntimeError as e:
        report["final_status"] = "failed"
        report["safe_error_summary"] = str(e)
        _write_report(report)
        print(f"ERROR: {e}")
        return 1

    if venv_path.exists() and _verify_venv(venv_path):
        print(f"Hermes venv: {venv_path}")
        report["venv_python_exists"] = True
        report["venv_pip_exists"] = True
        pip_check = subprocess.run(
            [str(venv_path / "bin" / "python"), "-m", "pip", "--version"],
            capture_output=True, text=True
        )
        report["pip_verification_exit_code"] = pip_check.returncode
    else:
        print("Creating Hermes environment")
        _create_venv(venv_path)
        report["venv_recreated"] = True
        _record_venv_state(venv_path, report)

    print("Verifying environment pip")
    python_bin = venv_path / "bin" / "python"
    pip_check = subprocess.run(
        [str(python_bin), "-m", "pip", "--version"],
        capture_output=True, text=True
    )
    report["pip_verification_exit_code"] = pip_check.returncode
    if pip_check.returncode != 0:
        msg = "Venv pip verification failed after creation"
        report["final_status"] = "failed"
        report["safe_error_summary"] = msg
        _write_report(report)
        print(f"ERROR: {msg}")
        return 1

    _upgrade_packaging_tools(venv_path)

    dep_cmds = []
    dep_codes = []

    print("Installing Hermes dependencies")
    req_file = HERMES_REPO / "requirements.txt"
    if req_file.is_file():
        cmd = [str(python_bin), "-m", "pip", "install", "-r", str(req_file)]
        dep_cmds.append(" ".join(cmd))
        r = _run_pip(python_bin, ["install", "-r", str(req_file)])
        dep_codes.append(r.returncode)
        if r.returncode != 0:
            report["safe_error_summary"] = (
                f"Hermes requirements install failed: {r.stderr.strip()[:300]}"
            )

    extra_pkgs = ["openai", "pydantic", "pyyaml", "requests", "jsonschema"]
    cmd = [str(python_bin), "-m", "pip", "install"] + extra_pkgs
    dep_cmds.append(" ".join(cmd))
    r = _run_pip(python_bin, ["install"] + extra_pkgs)
    dep_codes.append(r.returncode)
    if r.returncode != 0:
        report["safe_error_summary"] = (
            f"Extra packages install failed: {r.stderr.strip()[:300]}"
        )

    print("Installing required OpenMontage dependencies")
    om_req = OM_REPO / "requirements.txt"
    if om_req.is_file():
        cmd = [str(python_bin), "-m", "pip", "install", "-r", str(om_req)]
        dep_cmds.append(" ".join(cmd))
        r = _run_pip(python_bin, ["install", "-r", str(om_req)])
        dep_codes.append(r.returncode)
        if r.returncode != 0:
            report["safe_error_summary"] = (
                f"OpenMontage requirements install failed: {r.stderr.strip()[:300]}"
            )

    report["dependency_commands"] = dep_cmds
    report["command_exit_codes"] = dep_codes

    if any(c != 0 for c in dep_codes):
        report["final_status"] = "failed"
        report["safe_error_summary"] = (
            report["safe_error_summary"] or "One or more pip install commands failed"
        )
        _write_report(report)
        print(f"ERROR: {report['safe_error_summary']}")
        return 1

    report["final_status"] = "complete"
    _write_report(report)
    print("Dependency installation complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
