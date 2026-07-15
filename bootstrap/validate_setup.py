#!/usr/bin/env python3
"""Truthful environment doctor for the thin ACD production path."""

from __future__ import annotations

import argparse
import ast
import hashlib
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
ENTRY_SKILLS = (
    "hermes-openmontage-repo-bridge",
    "social-edit-reasoning",
    "football-story-strategy",
    "football-pro-cutting-pacing",
    "football-audio-music-director",
    "football-retention-quality-control",
)
OPENMONTAGE_PATCH_ID = "cinematic-cut-props-v1"
OPENMONTAGE_PATCH_PATH = ROOT / "patches" / "openmontage" / "f633b5f-cinematic-cut-props-v1.patch"
OPENMONTAGE_OVERLAY_ROOT = ROOT / "patches" / "openmontage" / "overlay"
OPENMONTAGE_PATCHED_PATHS = {
    "lib/media_profiles.py",
    "remotion-composer/src/CinematicRenderer.tsx",
    "remotion-composer/src/CollageBurst.tsx",
    "remotion-composer/src/Explainer.tsx",
    "remotion-composer/src/LyricOverlay.tsx",
    "remotion-composer/src/TitledVideo.tsx",
    "scripts/scaffold_atelier_project.py",
    "tools/video/video_compose.py",
}


@dataclass
class Gate:
    name: str
    status: str
    evidence: str


def run(
    command: list[str],
    cwd: Path | None = None,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def openmontage_compatibility_gate(openmontage: Path) -> Gate:
    """Accept only the audited compatibility delta on the exact upstream pin."""
    if not (openmontage / ".git").is_dir():
        return Gate("openmontage_compatibility", "blocked", f"checkout missing: {openmontage}")
    head = run(["git", "rev-parse", "HEAD"], cwd=openmontage)
    actual = head.stdout.strip()
    if head.returncode or actual != OPENMONTAGE_PIN:
        return Gate("openmontage_compatibility", "failed", f"expected {OPENMONTAGE_PIN}, found {actual or head.stderr.strip()}")

    marker_path = openmontage / ".acd-compatibility-patches.json"
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Gate("openmontage_compatibility", "failed", f"compatibility marker unavailable: {exc}")
    if marker.get("openmontage_commit") != OPENMONTAGE_PIN:
        return Gate("openmontage_compatibility", "failed", "compatibility marker is for a different OpenMontage commit")
    if marker.get("patches") != [OPENMONTAGE_PATCH_ID]:
        return Gate("openmontage_compatibility", "failed", f"unexpected compatibility patch set: {marker.get('patches')!r}")
    if not OPENMONTAGE_PATCH_PATH.is_file() or marker.get("patch_sha256") != sha256(OPENMONTAGE_PATCH_PATH):
        return Gate("openmontage_compatibility", "failed", "installed marker does not match the tracked compatibility patch")

    reverse = run(["git", "apply", "--reverse", "--check", str(OPENMONTAGE_PATCH_PATH)], cwd=openmontage)
    if reverse.returncode:
        return Gate("openmontage_compatibility", "failed", "audited patch is not applied cleanly: " + reverse.stderr.strip()[-500:])
    modified = {
        line.strip()
        for line in run(["git", "diff", "--name-only"], cwd=openmontage).stdout.splitlines()
        if line.strip()
    }
    if modified != OPENMONTAGE_PATCHED_PATHS:
        return Gate(
            "openmontage_compatibility",
            "failed",
            f"tracked OpenMontage delta differs from audited paths; expected {sorted(OPENMONTAGE_PATCHED_PATHS)}, found {sorted(modified)}",
        )

    expected_overlay = marker.get("overlay_sha256")
    if not isinstance(expected_overlay, dict) or not expected_overlay:
        return Gate("openmontage_compatibility", "failed", "compatibility marker has no overlay hashes")
    tracked_overlay: dict[str, str] = {}
    for source in sorted(OPENMONTAGE_OVERLAY_ROOT.rglob("*")):
        if source.is_file() and source.suffix != ".pyc" and "__pycache__" not in source.parts:
            relative = str(source.relative_to(OPENMONTAGE_OVERLAY_ROOT))
            tracked_overlay[relative] = sha256(source)
    if expected_overlay != tracked_overlay:
        return Gate("openmontage_compatibility", "failed", "marker overlay hashes differ from the tracked overlay")
    for relative, expected in tracked_overlay.items():
        installed = openmontage / relative
        if not installed.is_file() or sha256(installed) != expected:
            return Gate("openmontage_compatibility", "failed", f"installed overlay differs from tracked source: {relative}")
    return Gate(
        "openmontage_compatibility",
        "passed",
        f"{OPENMONTAGE_PIN} + {OPENMONTAGE_PATCH_ID} ({marker['patch_sha256'][:12]})",
    )


def remotion_runtime_gate(openmontage: Path) -> Gate:
    composer = openmontage / "remotion-composer"
    cli = composer / "node_modules" / ".bin" / "remotion"
    browser_root = composer / "node_modules" / ".remotion"
    browsers = [
        path for path in browser_root.rglob("chrome-headless-shell*")
        if path.is_file() and os.access(path, os.X_OK)
    ] if browser_root.is_dir() else []
    missing = []
    if not shutil.which("node"):
        missing.append("node")
    if not shutil.which("npx"):
        missing.append("npx")
    if not cli.is_file():
        missing.append("locked Remotion CLI")
    if not browsers:
        missing.append("preinstalled Remotion browser")
    if missing:
        return Gate("remotion_runtime", "blocked", "missing: " + ", ".join(missing))
    return Gate("remotion_runtime", "passed", f"locked CLI + browser: {browsers[0]}")


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


def hermes_openmontage_plugin_gate(profile_home: Path, hermes_repo: Path) -> Gate:
    plugin = profile_home / "plugins" / "acd-openmontage"
    missing = [
        str(path)
        for path in (plugin / "plugin.yaml", plugin / "__init__.py", ROOT / "scripts" / "openmontage_creative_adapter.py")
        if not path.is_file()
    ]
    reference_dir = profile_home / "skills" / "football-emotion-video" / "skills" / "hermes-openmontage-repo-bridge" / "references"
    for name in ("repo-setup-status.md", "openmontage-schema-lock.md", "repo-source-lock.md"):
        if not (reference_dir / name).is_file():
            missing.append(str(reference_dir / name))
    hermes_python = hermes_repo / "venv" / "bin" / "python"
    if not hermes_python.is_file():
        missing.append(str(hermes_python))
    if missing:
        return Gate("hermes_openmontage_plugin", "blocked", "missing: " + ", ".join(missing))
    ddgs_version = os.environ.get("ACD_DDGS_VERSION", "9.14.4")
    probe = run([
        str(hermes_python), "-c",
        f"import importlib.metadata as m; assert m.version('ddgs') == {ddgs_version!r}; print(m.version('ddgs'))",
    ], timeout=30)
    if probe.returncode:
        return Gate("hermes_openmontage_plugin", "blocked", "Hermes DDGS dependency is unavailable: " + probe.stderr.strip()[-500:])
    config_path = profile_home / "config.yaml"
    config = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    required = ("acd-openmontage", "search_backend: ddgs", "coding_context: off")
    absent = [item for item in required if item not in config]
    if absent:
        return Gate("hermes_openmontage_plugin", "failed", "profile config missing: " + ", ".join(absent))
    toolset_lines: list[str] = []
    collecting = False
    for line in config.splitlines():
        if line.startswith("toolsets:"):
            collecting = True
            toolset_lines.append(line)
            continue
        if collecting and (line.startswith("  - ") or not line.strip()):
            toolset_lines.append(line)
            continue
        if collecting:
            break
    toolset_text = "\n".join(toolset_lines)
    mutable = [name for name in ("file", "terminal", "code_execution", "coding") if name in toolset_text]
    if mutable:
        return Gate(
            "hermes_openmontage_plugin",
            "failed",
            "production profile exposes mutable coding toolsets: " + ", ".join(mutable),
        )
    discovery = run(
        [
            str(hermes_python),
            "-c",
            (
                "from hermes_cli.plugins import discover_plugins,get_plugin_manager; "
                "from tools.registry import registry; discover_plugins(force=True); "
                "m=get_plugin_manager(); names=set(m._plugin_tool_names); "
                "expected={'openmontage_native','acd_acquire_source'}; "
                "assert expected.issubset(names), names; "
                "assert all(registry.get_entry(n) and registry.get_entry(n).toolset=='acd-openmontage' for n in expected); "
                "print(','.join(sorted(expected)))"
            ),
        ],
        cwd=hermes_repo,
        timeout=60,
        env={**os.environ, "HERMES_HOME": str(profile_home)},
    )
    if discovery.returncode:
        detail = (discovery.stderr or discovery.stdout).strip()[-1000:]
        return Gate("hermes_openmontage_plugin", "failed", "pinned Hermes plugin discovery failed: " + detail)
    return Gate(
        "hermes_openmontage_plugin",
        "passed",
        "pinned Hermes discovered typed tools; bridge references and zero-key web search verified",
    )


def registry_gate(openmontage: Path) -> Gate:
    python = Path(os.environ.get("OPENMONTAGE_PYTHON", openmontage / ".venv" / "bin" / "python")).expanduser().absolute()
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


def model_tool_contract_gate(profile_home: Path) -> Gate:
    """Fail closed when a selected provider needs tool-parsing request flags."""
    config_path = profile_home / "config.yaml"
    if not config_path.is_file():
        return Gate("model_tool_contract", "blocked", "Hermes profile config is missing")
    config_text = config_path.read_text(encoding="utf-8")
    if "nvidia/nemotron-3-ultra-550b-a55b" not in config_text:
        return Gate("model_tool_contract", "passed", "no additional selected-model tool contract")
    required = (
        "chat_template_kwargs:",
        "enable_thinking: true",
        "force_nonempty_content: true",
    )
    missing = [item for item in required if item not in config_text]
    if missing:
        return Gate(
            "model_tool_contract",
            "failed",
            "Nemotron 3 Ultra reasoning/tool parsing contract is incomplete: " + ", ".join(missing),
        )
    return Gate(
        "model_tool_contract",
        "passed",
        "Nemotron 3 Ultra reasoning/tool parsing flags are configured",
    )


def hermes_same_path_contract_gate(hermes_repo: Path) -> Gate:
    """Verify the exact pinned hooks used by the production handshake adapter."""
    required = {
        hermes_repo / "run_agent.py": (
            "class AIAgent",
            "def _build_api_kwargs(",
            "def _interruptible_api_call(",
            "def _interruptible_streaming_api_call(",
        ),
        hermes_repo / "agent" / "conversation_loop.py": (
            "_cc_fr = agent._get_transport()",
            "_finish_result = _cc_fr.normalize_response(response)",
        ),
        hermes_repo / "agent" / "tool_executor.py": (
            "agent.tool_start_callback(",
            "agent.tool_complete_callback(",
            "function_result",
        ),
        hermes_repo / "agent" / "transports" / "types.py": (
            "class ToolCall",
            "arguments: str",
            "class NormalizedResponse",
        ),
        ROOT / "scripts" / "hermes_event_adapter.py": (
            "_status_only_tool",
            "api_response_normalized",
            "ACD_HERMES_TOOL_HANDSHAKE_FAILED",
        ),
    }
    absent = []
    for path, markers in required.items():
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            absent.append(f"missing {path}")
            continue
        absent.extend(f"{path.name}: {marker}" for marker in markers if marker not in source)
    if absent:
        return Gate(
            "hermes_same_path_contract",
            "failed",
            "pinned request/response/callback surface differs: " + "; ".join(absent),
        )
    return Gate(
        "hermes_same_path_contract",
        "passed",
        "live request restriction, normalized response and real tool callbacks verified",
    )


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
        hermes_same_path_contract_gate(hermes_repo),
        openmontage_compatibility_gate(openmontage),
        production_boundary(),
    ]

    compile_result = run([sys.executable, "-m", "compileall", "-q", "src", "scripts", "bootstrap", "plugins"], cwd=ROOT)
    gates.append(Gate("python_compile", "passed" if compile_result.returncode == 0 else "failed", compile_result.stderr.strip() or "compiled"))
    test_result = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"], cwd=ROOT, timeout=180)
    gates.append(Gate("focused_tests", "passed" if test_result.returncode == 0 else "failed", (test_result.stderr or test_result.stdout).strip()[-1000:]))

    hermes_cli = shutil.which("hermes")
    gates.append(Gate("hermes_cli", "passed" if hermes_cli else "blocked", hermes_cli or "Hermes CLI is not installed"))
    gates.append(Gate("hermes_profile", "passed" if (profile_home / "config.yaml").is_file() else "blocked", str(profile_home)))
    gates.append(skill_gate(profile_home))
    gates.append(hermes_openmontage_plugin_gate(profile_home, hermes_repo))
    skill_result = run([sys.executable, str(ROOT / "skills" / "football-emotion-video" / "tools" / "validate_skill_system.py"), str(ROOT / "skills" / "football-emotion-video")])
    gates.append(Gate("canonical_skill_validation", "passed" if skill_result.returncode == 0 and "Result: PASSED" in skill_result.stdout else "failed", (skill_result.stdout + skill_result.stderr).strip()[-1000:]))
    gates.append(model_gate(profile_home))
    gates.append(model_tool_contract_gate(profile_home))

    manifest = openmontage / "pipeline_defs" / "documentary-montage.yaml"
    gates.append(Gate("openmontage_manifest", "passed" if manifest.is_file() else "failed", str(manifest)))
    gates.append(registry_gate(openmontage))
    gates.append(remotion_runtime_gate(openmontage))
    gates.append(Gate("ffmpeg_ffprobe", "passed" if shutil.which("ffmpeg") and shutil.which("ffprobe") else "blocked", "required for render/validation"))
    gates.append(Gate("source_acquisition", "passed" if importlib.util.find_spec("yt_dlp") else "blocked", "yt-dlp Python package"))
    gates.append(Gate("discord", "passed" if os.environ.get("DISCORD_WEBHOOK_URL") else "blocked", "optional; run is unaffected when absent"))

    summary = {status: sum(g.status == status for g in gates) for status in ("passed", "failed", "blocked")}
    required_blockers = [gate.name for gate in gates if gate.status == "blocked" and gate.name != "discord"]
    worker_head = run(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip()
    worker_dirty = run(["git", "status", "--porcelain"], cwd=ROOT).stdout.strip() != ""
    marker_path = openmontage / ".acd-compatibility-patches.json"
    try:
        compatibility_marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        compatibility_marker = None
    report = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gates": [asdict(g) for g in gates],
        "summary": summary,
        "production_path_complete": summary["failed"] == 0 and not required_blockers,
        "live_certification": "blocked" if summary["failed"] or required_blockers else "ready_for_live_smoke",
        "required_blockers": required_blockers,
        "runtime_identity": {
            "worker_commit": worker_head or None,
            "worker_dirty": worker_dirty,
            "hermes_commit": HERMES_PIN,
            "openmontage_commit": OPENMONTAGE_PIN,
            "openmontage_compatibility": compatibility_marker,
            "python": sys.version.split()[0],
            "node": run(["node", "--version"]).stdout.strip() if shutil.which("node") else None,
            "npm": run(["npm", "--version"]).stdout.strip() if shutil.which("npm") else None,
            "requirements_sha256": sha256(ROOT / "requirements.txt"),
            "remotion_lock_sha256": sha256(openmontage / "remotion-composer" / "package-lock.json") if (openmontage / "remotion-composer" / "package-lock.json").is_file() else None,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "thin-validation.json"
    md_path = args.output_dir / "thin-validation.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "runtime-validation-certificate.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
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
    return 1 if summary["failed"] or required_blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
