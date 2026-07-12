#!/usr/bin/env python3
"""Truthful environment doctor for the thin ACD production path."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HERMES_PIN = "5ecc07986f46463ca3096679b03a46402eb19cee"
OPENMONTAGE_PIN = "f633b5f428b9be9a2afecba851dfddd101619756"
ENTRY_SKILLS = ("hermes-openmontage-repo-bridge", "social-edit-reasoning", "football-story-strategy")


@dataclass
class Gate:
    name: str
    status: str
    evidence: str


def run(command: list[str], cwd: Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)


def git_pin(name: str, path: Path, expected: str) -> Gate:
    if not (path / ".git").is_dir():
        return Gate(name, "blocked", f"checkout missing: {path}")
    result = run(["git", "rev-parse", "HEAD"], cwd=path)
    actual = result.stdout.strip()
    if actual != expected:
        return Gate(name, "failed", f"expected {expected}, found {actual or result.stderr.strip()}")
    # LFS/sandbox smudge differences can change a checked-out binary without
    # changing upstream source. Fail only on tracked text/source differences.
    numstat = run(["git", "diff", "--numstat"], cwd=path).stdout.splitlines()
    text_differences = [line for line in numstat if line and not line.startswith("-\t-\t")]
    if text_differences:
        return Gate(name, "failed", "pinned checkout has tracked source modifications")
    binary_note = "; binary smudge difference ignored" if numstat else ""
    return Gate(name, "passed", expected + binary_note)


def production_boundary() -> Gate:
    path = ROOT / "scripts" / "acd_worker.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return Gate("production_boundary", "failed", str(exc))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    forbidden = [name for name in imports if name in {"acd_worker.orchestrator", "acd_worker.openmontage_runner", "acd_worker.quality_loop", "acd_worker.footage_requirements"}]
    return Gate("production_boundary", "failed" if forbidden else "passed", f"forbidden imports: {forbidden}" if forbidden else "thin controller only")


def skill_gate(profile_home: Path) -> Gate:
    root = profile_home / "skills"
    if not root.is_dir():
        return Gate("football_skills", "blocked", f"profile skills missing: {root}")
    found = {path.parent.name for path in root.rglob("SKILL.md")}
    missing = sorted(set(ENTRY_SKILLS) - found)
    if missing:
        return Gate("football_skills", "failed", f"missing entry skills: {', '.join(missing)}")
    return Gate("football_skills", "passed", f"{len(found)} SKILL.md packages discovered")


def registry_gate(openmontage: Path) -> Gate:
    python = openmontage / ".venv" / "bin" / "python"
    if not python.is_file():
        return Gate("openmontage_registry", "blocked", "OpenMontage virtual environment is not installed")
    command = [str(python), "-c", "from tools.tool_registry import registry; registry.discover(); print(len(registry._tools))"]
    result = run(command, cwd=openmontage)
    if result.returncode:
        error = result.stderr.strip()[-1000:]
        return Gate("openmontage_registry", "blocked" if "ModuleNotFoundError" in error else "failed", error)
    return Gate("openmontage_registry", "passed", f"{result.stdout.strip()} tools discovered")


def model_gate(profile_home: Path) -> Gate:
    config_path = profile_home / "config.yaml"
    if not config_path.is_file():
        return Gate("free_model_endpoint", "blocked", "Hermes profile config is missing")
    config_text = config_path.read_text(encoding="utf-8")
    configured_model = any(
        line.strip().startswith("default:") and line.split(":", 1)[1].strip().strip("\"'")
        for line in config_text.splitlines()
    )
    if not configured_model:
        return Gate("free_model_endpoint", "blocked", "select a model in the named Hermes profile")
    env_keys = ("LLM_API_KEY", "OPENAI_API_KEY", "NVIDIA_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY")
    if any(os.environ.get(key) for key in env_keys):
        return Gate("free_model_endpoint", "passed", "model configured; credential present in environment (value not inspected)")
    env_file = profile_home / ".env"
    if env_file.is_file():
        try:
            configured = any(
                line.split("=", 1)[0].strip() in env_keys and line.split("=", 1)[1].strip()
                for line in env_file.read_text(encoding="utf-8").splitlines()
                if "=" in line and not line.lstrip().startswith("#")
            )
        except OSError:
            configured = False
        if configured:
            return Gate("free_model_endpoint", "passed", "model configured; credential present in profile .env (value not reported)")
    return Gate("free_model_endpoint", "blocked", "model configured but its endpoint credential is unavailable")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the thin ACD runtime")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "state" / "setup")
    args = parser.parse_args()

    hermes_root = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser().resolve()
    profile = os.environ.get("HERMES_PROFILE", "football-emotion")
    profile_home = hermes_root if hermes_root.parent.name == "profiles" else hermes_root / "profiles" / profile
    hermes_repo = Path(os.environ.get("HERMES_AGENT_PATH", ROOT / "external" / "Hermes-Agent")).expanduser().resolve()
    openmontage = Path(os.environ.get("OPENMONTAGE_ROOT", ROOT / "external" / "OpenMontage")).expanduser().resolve()

    gates = [
        git_pin("hermes_pin", hermes_repo, HERMES_PIN),
        git_pin("openmontage_pin", openmontage, OPENMONTAGE_PIN),
        production_boundary(),
    ]

    compile_result = run([sys.executable, "-m", "compileall", "-q", "src", "scripts", "bootstrap"], cwd=ROOT)
    gates.append(Gate("python_compile", "passed" if compile_result.returncode == 0 else "failed", compile_result.stderr.strip() or "compiled"))
    test_result = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"], cwd=ROOT, timeout=180)
    gates.append(Gate("focused_tests", "passed" if test_result.returncode == 0 else "failed", (test_result.stderr or test_result.stdout).strip()[-1000:]))

    hermes_cli = shutil.which("hermes")
    gates.append(Gate("hermes_cli", "passed" if hermes_cli else "blocked", hermes_cli or "Hermes CLI is not installed"))
    gates.append(Gate("hermes_profile", "passed" if (profile_home / "config.yaml").is_file() else "blocked", str(profile_home)))
    gates.append(skill_gate(profile_home))
    skill_result = run([sys.executable, str(ROOT / "skills" / "football-emotion-video" / "tools" / "validate_skill_system.py"), str(ROOT / "skills" / "football-emotion-video")])
    gates.append(Gate("canonical_skill_validation", "passed" if skill_result.returncode == 0 and "Result: PASSED" in skill_result.stdout else "failed", (skill_result.stdout + skill_result.stderr).strip()[-1000:]))
    gates.append(model_gate(profile_home))

    manifest = openmontage / "pipeline_defs" / "documentary-montage.yaml"
    gates.append(Gate("openmontage_manifest", "passed" if manifest.is_file() else "failed", str(manifest)))
    gates.append(registry_gate(openmontage))
    remotion = openmontage / "remotion-composer" / "node_modules"
    gates.append(Gate("remotion_runtime", "passed" if remotion.is_dir() and shutil.which("node") and shutil.which("npx") else "blocked", "node+npx+remotion node_modules"))
    gates.append(Gate("ffmpeg_ffprobe", "passed" if shutil.which("ffmpeg") and shutil.which("ffprobe") else "blocked", "required for render/validation"))
    gates.append(Gate("source_acquisition", "passed" if importlib.util.find_spec("yt_dlp") else "blocked", "yt-dlp Python package"))
    gates.append(Gate("discord", "passed" if os.environ.get("DISCORD_WEBHOOK_URL") else "blocked", "optional; run is unaffected when absent"))

    summary = {status: sum(g.status == status for g in gates) for status in ("passed", "failed", "blocked")}
    report = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gates": [asdict(g) for g in gates],
        "summary": summary,
        "production_path_complete": summary["failed"] == 0,
        "live_certification": "blocked" if summary["blocked"] else "ready_for_live_smoke",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "thin-validation.json"
    md_path = args.output_dir / "thin-validation.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    rows = "\n".join(f"| {g.name} | {g.status} | {g.evidence.replace('|', '/')} |" for g in gates)
    md_path.write_text(
        "# Thin Runtime Validation\n\n| Gate | Status | Evidence |\n|---|---|---|\n" + rows +
        f"\n\nPassed: {summary['passed']}  Failed: {summary['failed']}  Blocked: {summary['blocked']}\n",
        encoding="utf-8",
    )
    for gate in gates:
        marker = {"passed": "✓", "failed": "✗", "blocked": "!"}[gate.status]
        print(f"{marker} {gate.name}: {gate.status} — {gate.evidence}")
    print(f"Summary: {summary}; reports: {json_path}, {md_path}")
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
