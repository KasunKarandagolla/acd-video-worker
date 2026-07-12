#!/usr/bin/env python3
"""Hydrate/export durable ACD state without copying credentials."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


EXCLUDED_NAMES = {".env", "secrets", "secrets.json", "credentials", "credentials.json", "tokens.json"}


def _allowed(path: Path) -> bool:
    return not path.is_symlink() and path.name.lower() not in EXCLUDED_NAMES


def copy_tree(source: Path, destination: Path) -> int:
    if not source.is_dir():
        return 0
    copied = 0
    for item in source.rglob("*"):
        if not _allowed(item) or any(parent.name.lower() in EXCLUDED_NAMES for parent in item.parents if parent != source):
            continue
        relative = item.relative_to(source)
        target = destination / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            copied += 1
    return copied


def roots() -> dict[str, Path]:
    hermes_root = Path(os.environ.get("HERMES_HOME", "/kaggle/working/.hermes")).expanduser().resolve()
    profile = os.environ.get("HERMES_PROFILE", "football-emotion")
    state_dir = Path(os.environ.get("ACD_STATE_DIR", "/kaggle/working/acd-state/runs")).expanduser().resolve()
    projects = Path(os.environ.get("OPENMONTAGE_PROJECTS_DIR", "/kaggle/working/projects")).expanduser().resolve()
    return {"hermes-profile": hermes_root / "profiles" / profile, "acd-state": state_dir.parent, "projects": projects}


def hydrate(source: Path) -> int:
    total = 0
    for name, destination in roots().items():
        total += copy_tree(source / name, destination)
    return total


def export(destination: Path) -> int:
    total = 0
    destination.mkdir(parents=True, exist_ok=True)
    for name, source in roots().items():
        total += copy_tree(source, destination / name)
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="Hydrate or export non-secret ACD runtime state")
    sub = parser.add_subparsers(dest="command", required=True)
    hydrate_parser = sub.add_parser("hydrate")
    hydrate_parser.add_argument("--source", type=Path, default=os.environ.get("ACD_PERSIST_SOURCE"))
    export_parser = sub.add_parser("export")
    export_parser.add_argument("--destination", type=Path, default=os.environ.get("ACD_PERSIST_EXPORT", "/kaggle/working/acd-persist-export"))
    args = parser.parse_args()

    if args.command == "hydrate":
        if args.source is None:
            print("No persistence source configured; starting with empty durable state.")
            return 0
        source = args.source.expanduser().resolve()
        if not source.is_dir():
            print(f"Persistence source does not exist: {source}")
            return 2
        print(f"Hydrated {hydrate(source)} non-secret files from {source}")
        return 0

    destination = args.destination.expanduser().resolve()
    print(f"Exported {export(destination)} non-secret files to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
