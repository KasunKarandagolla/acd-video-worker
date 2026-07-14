#!/usr/bin/env python3
"""Hydrate/export durable ACD state without copying credentials."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
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
            _copy_file(item, target)
            copied += 1
    return copied


def _copy_file(source: Path, target: Path) -> None:
    """Copy ordinary files; snapshot live SQLite databases through its API."""
    try:
        with source.open("rb") as handle:
            sqlite_header = handle.read(16) == b"SQLite format 3\x00"
    except OSError:
        sqlite_header = False
    if not sqlite_header:
        shutil.copy2(source, target)
        return

    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    os.close(fd)
    try:
        os.unlink(temporary)
        source_uri = f"file:{source}?mode=ro"
        with sqlite3.connect(source_uri, uri=True, timeout=30) as source_db:
            with sqlite3.connect(temporary) as target_db:
                source_db.backup(target_db)
                target_db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        os.replace(temporary, target)
        shutil.copystat(source, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def roots() -> dict[str, Path]:
    hermes_root = Path(os.environ.get("HERMES_HOME", "/kaggle/working/.hermes")).expanduser().resolve()
    profile = os.environ.get("HERMES_PROFILE", "football-emotion")
    state_dir = Path(os.environ.get("ACD_STATE_DIR", "/kaggle/working/acd-state/runs")).expanduser().resolve()
    projects = Path(os.environ.get("OPENMONTAGE_PROJECTS_DIR", "/kaggle/working/projects")).expanduser().resolve()
    return {"hermes-profile": hermes_root / "profiles" / profile, "acd-state": state_dir.parent, "projects": projects}


def hydrate(source: Path) -> int:
    _validate_snapshot(source)
    total = 0
    for name, destination in roots().items():
        total += copy_tree(source / name, destination)
    return total


def _validate_snapshot(source: Path) -> None:
    manifest_path = source / "snapshot-manifest.json"
    if not manifest_path.is_file():
        return  # backward-compatible import of pre-manifest snapshots
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative, expected in (payload.get("files") or {}).items():
        path = (source / relative).resolve()
        try:
            path.relative_to(source.resolve())
        except ValueError as exc:
            raise ValueError(f"Persistence manifest contains an unsafe path: {relative}") from exc
        if not path.is_file():
            raise ValueError(f"Persistence snapshot is incomplete: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected.get("sha256"):
            raise ValueError(f"Persistence snapshot hash mismatch: {relative}")


def export(destination: Path) -> int:
    total = 0
    destination.mkdir(parents=True, exist_ok=True)
    for name, source in roots().items():
        total += copy_tree(source, destination / name)
    manifest = {
        "schema_version": "1.0",
        "files": {},
    }
    for path in sorted(destination.rglob("*")):
        if not path.is_file() or path.name == "snapshot-manifest.json":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest["files"][str(path.relative_to(destination))] = {"sha256": digest, "size_bytes": path.stat().st_size}
    _atomic_json(destination / "snapshot-manifest.json", manifest)
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
        try:
            count = hydrate(source)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Persistence snapshot validation failed: {exc}")
            return 2
        print(f"Hydrated {count} non-secret files from {source}")
        return 0

    destination = args.destination.expanduser().resolve()
    print(f"Exported {export(destination)} non-secret files to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
