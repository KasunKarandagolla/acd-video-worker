#!/usr/bin/env python3
"""Inspect cloned Hermes-Agent and OpenMontage repos."""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_JSON = os.path.join(BASE_DIR, "state", "runs", "repo_preflight.json")
REPORT_MD = os.path.join(BASE_DIR, "state", "runs", "repo_preflight.md")


def inspect_repo(path, label):
    result = {
        "path": path,
        "exists": os.path.isdir(path),
        "is_git_repo": os.path.isdir(os.path.join(path, ".git")),
        "high_level_files": [],
        "subdirs": [],
        "python_files": [],
        "config_files": [],
        "notable_structures": {}
    }

    if not result["exists"]:
        return result

    try:
        entries = sorted(os.listdir(path))
        for entry in entries:
            full = os.path.join(path, entry)
            if os.path.isfile(full):
                result["high_level_files"].append(entry)
                if entry.endswith(".py"):
                    result["python_files"].append(entry)
                elif entry in ("package.json", "setup.py", "setup.cfg", "pyproject.toml",
                               "requirements.txt", "Cargo.toml", "Makefile"):
                    result["config_files"].append(entry)
            elif os.path.isdir(full):
                result["subdirs"].append(entry)
                sub_entries = os.listdir(full) if os.path.isdir(full) else []
                for se in sub_entries:
                    se_full = os.path.join(full, se)
                    if os.path.isfile(se_full) and se.endswith(".py"):
                        result["python_files"].append(f"{entry}/{se}")
                # Detect specific structures
                if entry in ("skills", "memory", "tools", "data", "config", "schemas",
                             "pipeline_defs", "pipeline", "render", "runtime", "agent"):
                    result["notable_structures"][entry] = [e for e in sub_entries if not e.startswith(".")]

    except PermissionError:
        result["error"] = "Permission denied reading directory"

    return result


def safe_import_check(path):
    result = {"can_import": False, "import_attempts": []}
    if not os.path.isdir(path):
        return result

    sys.path.insert(0, path)
    for candidate in os.listdir(path):
        if candidate.endswith(".py") and not candidate.startswith("_"):
            mod_name = candidate[:-3]
            try:
                __import__(mod_name)
                result["import_attempts"].append({"module": mod_name, "success": True})
                result["can_import"] = True
            except Exception as e:
                result["import_attempts"].append({
                    "module": mod_name,
                    "success": False,
                    "error": type(e).__name__
                })
    sys.path.pop(0)
    return result


def main():
    os.makedirs(os.path.dirname(REPORT_JSON), exist_ok=True)

    hermes = inspect_repo(
        os.path.join(BASE_DIR, "external", "Hermes-Agent"),
        "Hermes-Agent"
    )
    openmontage = inspect_repo(
        os.path.join(BASE_DIR, "external", "OpenMontage"),
        "OpenMontage"
    )

    if hermes["exists"]:
        hermes["import_check"] = safe_import_check(
            os.path.join(BASE_DIR, "external", "Hermes-Agent")
        )
    if openmontage["exists"]:
        openmontage["import_check"] = safe_import_check(
            os.path.join(BASE_DIR, "external", "OpenMontage")
        )

    data = {
        "timestamp_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "hermes_agent": hermes,
        "openmontage": openmontage
    }

    with open(REPORT_JSON, "w") as f:
        json.dump(data, f, indent=2)

    with open(REPORT_MD, "w") as f:
        f.write(f"# Repo Preflight Report\n\n")
        f.write(f"Timestamp: {data['timestamp_utc']}\n\n")

        f.write("## Hermes-Agent\n\n")
        f.write(f"- Exists: {hermes['exists']}\n")
        f.write(f"- Git repo: {hermes['is_git_repo']}\n")
        f.write(f"- High-level files ({len(hermes['high_level_files'])}): ")
        f.write(", ".join(hermes['high_level_files'][:20]))
        f.write("\n")
        f.write(f"- Subdirs: {', '.join(hermes['subdirs'][:20])}\n")
        if hermes.get("notable_structures"):
            f.write(f"- Notable structures: {json.dumps(hermes['notable_structures'])}\n")

        f.write("\n## OpenMontage\n\n")
        f.write(f"- Exists: {openmontage['exists']}\n")
        f.write(f"- Git repo: {openmontage['is_git_repo']}\n")
        f.write(f"- High-level files ({len(openmontage['high_level_files'])}): ")
        f.write(", ".join(openmontage['high_level_files'][:20]))
        f.write("\n")
        f.write(f"- Subdirs: {', '.join(openmontage['subdirs'][:20])}\n")
        if openmontage.get("notable_structures"):
            f.write(f"- Notable structures: {json.dumps(openmontage['notable_structures'])}\n")

        if openmontage["python_files"]:
            f.write(f"\nPython files: {', '.join(openmontage['python_files'][:30])}\n")

        f.write("\n## Summary\n\n")
        f.write(f"Hermes-Agent: {'AVAILABLE' if hermes['exists'] else 'MISSING'}\n")
        f.write(f"OpenMontage: {'AVAILABLE' if openmontage['exists'] else 'MISSING'}\n")

        for repo_name, repo in [("Hermes-Agent", hermes), ("OpenMontage", openmontage)]:
            if repo.get("import_check", {}).get("can_import"):
                f.write(f"- {repo_name}: Python imports possible\n")
            else:
                f.write(f"- {repo_name}: Python import not attempted/not possible directly\n")

    print(f"Reports written to:")
    print(f"  {REPORT_JSON}")
    print(f"  {REPORT_MD}")

    if not hermes["exists"]:
        print("WARN: Hermes-Agent not cloned yet")
    if not openmontage["exists"]:
        print("WARN: OpenMontage not cloned yet")


if __name__ == "__main__":
    main()
