#!/usr/bin/env python3
"""Inspect cloned Hermes-Agent and OpenMontage repos. Uses pathlib, safe subprocess imports."""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_JSON = BASE_DIR / "state" / "runs" / "repo_preflight.json"
REPORT_MD = BASE_DIR / "state" / "runs" / "repo_preflight.md"
HERMES_PATH = BASE_DIR / "external" / "Hermes-Agent"
OPENMONTAGE_PATH = BASE_DIR / "external" / "OpenMontage"
LOCKS_DIR = BASE_DIR / "locks"


def read_pinned_commits(repo_key):
    path = LOCKS_DIR / f"{repo_key}_PINNED_COMMIT.txt"
    if path.is_file():
        return path.read_text().strip()[:80]
    return None


def inspect_repo(path, label):
    result = {
        "path": str(path),
        "exists": path.is_dir(),
        "is_git_repo": (path / ".git").is_dir(),
        "high_level_files": [],
        "subdirs": [],
        "python_files": [],
        "config_files": [],
        "notable_structures": {},
        "pinned_commits": {}
    }
    if not result["exists"]:
        return result

    try:
        for entry in sorted(path.iterdir()):
            name = entry.name
            if entry.is_file():
                result["high_level_files"].append(name)
                if name.endswith(".py"):
                    result["python_files"].append(name)
                elif name in ("package.json", "setup.py", "setup.cfg", "pyproject.toml",
                              "requirements.txt", "Cargo.toml", "Makefile"):
                    result["config_files"].append(name)
            elif entry.is_dir():
                result["subdirs"].append(name)
                for child in entry.iterdir():
                    if child.is_file() and child.suffix == ".py":
                        result["python_files"].append(f"{name}/{child.name}")
                if name in ("skills", "memory", "tools", "data", "config", "schemas",
                            "pipeline_defs", "pipeline", "render", "runtime", "agent"):
                    result["notable_structures"][name] = [
                        e.name for e in entry.iterdir() if not e.name.startswith(".")
                    ]

        pinned = read_pinned_commits(label.upper().replace("-", "_"))
        if pinned:
            result["pinned_commits"]["lock_file"] = pinned
        pinned_head = path / ".git" / "HEAD"
        if pinned_head.is_file():
            result["pinned_commits"]["git_head"] = pinned_head.read_text().strip()[:80]

    except PermissionError:
        result["error"] = "Permission denied reading directory"
    return result


def safe_import_check(path):
    """Test imports via subprocess python -c; never loads into this process."""
    result = {"can_import": False, "import_attempts": []}
    p = Path(path)
    if not p.is_dir():
        return result

    for candidate in sorted(p.iterdir()):
        if candidate.is_file() and candidate.suffix == ".py" and not candidate.name.startswith("_"):
            mod_name = candidate.stem
            try:
                proc = subprocess.run(
                    [sys.executable, "-c", f"import {mod_name}"],
                    cwd=str(path),
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                if proc.returncode == 0:
                    result["import_attempts"].append({"module": mod_name, "success": True})
                    result["can_import"] = True
                else:
                    stderr_short = proc.stderr.strip()[:200]
                    result["import_attempts"].append({
                        "module": mod_name,
                        "success": False,
                        "error": stderr_short or f"exit code {proc.returncode}"
                    })
            except subprocess.TimeoutExpired:
                result["import_attempts"].append({
                    "module": mod_name,
                    "success": False,
                    "error": "timeout"
                })
            except Exception as e:
                result["import_attempts"].append({
                    "module": mod_name,
                    "success": False,
                    "error": type(e).__name__
                })
    return result


def detect_openmontage_features(path):
    features = {
        "pipeline_defs": [],
        "schemas": [],
        "tool_registry_files": [],
        "render_entrypoints": [],
        "runtime_entrypoints": []
    }
    p = Path(path)
    if not p.is_dir():
        return features

    for d in [p / "pipeline_defs", p / "pipeline"]:
        if d.is_dir():
            features["pipeline_defs"] = sorted(
                str(f.relative_to(p)) for f in d.iterdir() if f.is_file()
            )

    for d in [p / "schemas", p / "schema"]:
        if d.is_dir():
            features["schemas"] = sorted(
                str(f.relative_to(p)) for f in d.iterdir() if f.is_file()
            )

    for pattern in ("*registry*",):
        for f in p.rglob(pattern):
            if f.is_file():
                features["tool_registry_files"].append(str(f.relative_to(p)))

    for entrypoint_dir in ("render", "runtime"):
        d = p / entrypoint_dir
        if d.is_dir():
            key = f"{entrypoint_dir}_entrypoints"
            features[key] = sorted(
                str(f.relative_to(p)) for f in d.iterdir()
                if f.is_file() and f.suffix in (".py", ".sh", ".js", ".mjs")
            )

    return features


def detect_hermes_features(path):
    features = {
        "skill_directories": [],
        "memory_directories": [],
        "tool_directories": []
    }
    p = Path(path)
    if not p.is_dir():
        return features

    for d in p.iterdir():
        if d.is_dir():
            name = d.name
            if name in ("skills", "skill", "skillsets"):
                features["skill_directories"] = sorted(
                    str(f.relative_to(p)) for f in d.iterdir() if f.is_dir()
                )
            if name in ("memory", "memories"):
                features["memory_directories"] = sorted(
                    str(f.relative_to(p)) for f in d.iterdir() if f.is_dir()
                )
            if name in ("tools", "tool"):
                features["tool_directories"] = sorted(
                    str(f.relative_to(p)) for f in d.iterdir() if f.is_dir()
                )

    return features


def write_reports(data):
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)

    with open(REPORT_JSON, "w") as f:
        json.dump(data, f, indent=2, default=str)

    with open(REPORT_MD, "w") as f:
        f.write("# Repo Preflight Report\n\n")
        f.write(f"Timestamp: {data['timestamp_utc']}\n\n")

        for repo_key, repo_label in [("hermes_agent", "Hermes-Agent"), ("openmontage", "OpenMontage")]:
            r = data[repo_key]
            f.write(f"## {repo_label}\n\n")
            f.write(f"- Exists: {r['exists']}\n")
            f.write(f"- Git repo: {r['is_git_repo']}\n")
            if r.get("pinned_commits"):
                f.write(f"- Pinned commits: {json.dumps(r['pinned_commits'])}\n")
            f.write(f"- High-level files ({len(r['high_level_files'])}): ")
            f.write(", ".join(r['high_level_files'][:20]))
            f.write("\n")
            f.write(f"- Subdirs: {', '.join(r['subdirs'][:20])}\n")
            if r.get("notable_structures"):
                f.write(f"- Notable structures: {json.dumps(r['notable_structures'])}\n")
            if r.get("config_files"):
                f.write(f"- Package manager files: {', '.join(r['config_files'])}\n")
            if r["python_files"]:
                f.write(f"\nPython files: {', '.join(r['python_files'][:30])}\n")

            features = r.get("features", {})
            if features:
                for feat_key, feat_val in features.items():
                    if feat_val:
                        f.write(f"- {feat_key}: {', '.join(feat_val[:20])}\n")

            import_check = r.get("import_check", {})
            if import_check.get("can_import"):
                f.write(f"- Python imports possible\n")
                for attempt in import_check.get("import_attempts", []):
                    status = "OK" if attempt["success"] else f"FAIL ({attempt.get('error', 'unknown')})"
                    f.write(f"  - {attempt['module']}: {status}\n")
            else:
                f.write(f"- Python import not attempted/not possible directly\n")

        f.write("\n## Summary\n\n")
        for repo_key, repo_label in [("hermes_agent", "Hermes-Agent"), ("openmontage", "OpenMontage")]:
            r = data[repo_key]
            f.write(f"{repo_label}: {'AVAILABLE' if r['exists'] else 'MISSING'}\n")

        if data.get("warnings"):
            f.write("\n## Warnings\n\n")
            for w in data["warnings"]:
                f.write(f"- {w}\n")

        if data.get("blockers"):
            f.write("\n## Blockers\n\n")
            for b in data["blockers"]:
                f.write(f"- {b}\n")


def main():
    (REPORT_JSON.parent).mkdir(parents=True, exist_ok=True)

    hermes = inspect_repo(HERMES_PATH, "Hermes-Agent")
    openmontage = inspect_repo(OPENMONTAGE_PATH, "OpenMontage")

    if hermes["exists"]:
        hermes["import_check"] = safe_import_check(HERMES_PATH)
        hermes["features"] = detect_hermes_features(HERMES_PATH)
    if openmontage["exists"]:
        openmontage["import_check"] = safe_import_check(OPENMONTAGE_PATH)
        openmontage["features"] = detect_openmontage_features(OPENMONTAGE_PATH)

    warnings = []
    blockers = []

    if not hermes["exists"]:
        blockers.append("Hermes-Agent not cloned yet")
    if not openmontage["exists"]:
        blockers.append("OpenMontage not cloned yet")

    for repo_name, repo in [("Hermes-Agent", hermes), ("OpenMontage", openmontage)]:
        if repo["exists"]:
            ic = repo.get("import_check", {})
            if not ic.get("can_import"):
                for attempt in ic.get("import_attempts", []):
                    if not attempt["success"]:
                        warnings.append(
                            f"{repo_name}: import '{attempt['module']}' failed: {attempt.get('error', 'unknown')}"
                        )

    if openmontage["exists"]:
        feats = openmontage.get("features", {})
        if not feats.get("pipeline_defs"):
            warnings.append("OpenMontage: no pipeline_defs detected")
        if not feats.get("schemas"):
            warnings.append("OpenMontage: no schemas detected")
        if not feats.get("render_entrypoints") and not feats.get("runtime_entrypoints"):
            warnings.append("OpenMontage: no render/runtime entrypoints detected")

    data = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "hermes_agent": hermes,
        "openmontage": openmontage,
        "warnings": warnings,
        "blockers": blockers
    }

    write_reports(data)

    print(f"Reports written to:")
    print(f"  {REPORT_JSON}")
    print(f"  {REPORT_MD}")

    for w in warnings:
        print(f"WARN: {w}")
    for b in blockers:
        print(f"BLOCKER: {b}")

    if not hermes["exists"] or not openmontage["exists"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
