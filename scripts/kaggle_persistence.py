#!/usr/bin/env python3
"""Hydrate/export durable ACD state without copying credentials."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


EXCLUDED_NAMES = {".env", "secrets", "secrets.json", "credentials", "credentials.json", "tokens.json"}
SECRET_PATTERNS = (
    re.compile(rb"(?:nvapi|sk)-[A-Za-z0-9_-]{16,}"),
    re.compile(rb"gh[oprsu]_[A-Za-z0-9_]{20,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def _fsync_dir(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _allowed(path: Path) -> bool:
    name = path.name.lower()
    return (
        not path.is_symlink()
        and name not in EXCLUDED_NAMES
        and not name.startswith(".env.")
    )


def copy_tree(source: Path, destination: Path) -> int:
    if not source.is_dir():
        return 0
    copied = 0
    for item in source.rglob("*"):
        if not _allowed(item) or any(parent.name.lower() in EXCLUDED_NAMES for parent in item.parents if parent != source):
            continue
        relative = item.relative_to(source)
        if ".leases" in relative.parts or ".persistence.lock" in relative.parts:
            continue
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
        _fsync_dir(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def roots() -> dict[str, Path]:
    hermes_root = Path(os.environ.get("HERMES_HOME", "/kaggle/working/.hermes")).expanduser().resolve()
    profile = os.environ.get("HERMES_PROFILE", "football-emotion")
    state_dir = Path(os.environ.get("ACD_STATE_DIR", "/kaggle/working/acd-state/runs")).expanduser().resolve()
    projects = Path(os.environ.get("OPENMONTAGE_PROJECTS_DIR", "/kaggle/working/projects")).expanduser().resolve()
    return {"hermes-profile": hermes_root / "profiles" / profile, "acd-state": state_dir.parent, "projects": projects}


def _hydration_marker() -> Path:
    override = os.environ.get("ACD_HYDRATION_MARKER")
    if override:
        return Path(override).expanduser().resolve()
    state_root = roots()["acd-state"]
    return state_root.parent / ".acd-persistence-hydration.json"


def _runtime_has_content() -> bool:
    for root in roots().values():
        if not root.is_dir():
            continue
        if any(
            path.is_file()
            and ".leases" not in path.relative_to(root).parts
            and ".persistence.lock" not in path.relative_to(root).parts
            for path in root.rglob("*")
        ):
            return True
    return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_snapshot(source: Path, *, allow_legacy: bool = False) -> Path:
    pointer_path = source / "current.json"
    if pointer_path.is_file():
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        generation_id = str(pointer.get("generation_id") or "")
        if not generation_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in generation_id):
            raise ValueError("Persistence current pointer has an invalid generation ID")
        snapshot = (source / "generations" / generation_id).resolve()
        try:
            snapshot.relative_to(source.resolve())
        except ValueError as exc:
            raise ValueError("Persistence current pointer escapes its root") from exc
        manifest_path = snapshot / "snapshot-manifest.json"
        if not manifest_path.is_file():
            raise ValueError("Persistence current generation has no manifest")
        if _sha256(manifest_path) != pointer.get("manifest_sha256"):
            raise ValueError("Persistence current pointer does not match its generation manifest")
        return snapshot
    if (source / "snapshot-manifest.json").is_file() and allow_legacy:
        return source
    if (source / "snapshot-manifest.json").is_file():
        raise ValueError("Flat persistence snapshots require explicit --allow-legacy")
    raise ValueError("Persistence source has no committed generation pointer")


def hydrate(source: Path, *, allow_legacy: bool = False) -> int:
    snapshot = _resolve_snapshot(source, allow_legacy=allow_legacy)
    _validate_snapshot(snapshot, allow_legacy=allow_legacy)
    manifest = json.loads((snapshot / "snapshot-manifest.json").read_text(encoding="utf-8"))
    generation_id = str(manifest.get("generation_id") or "legacy")
    manifest_sha256 = _sha256(snapshot / "snapshot-manifest.json")
    marker_path = _hydration_marker()
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        marker = None
    if (
        isinstance(marker, dict)
        and marker.get("generation_id") == generation_id
        and marker.get("manifest_sha256") == manifest_sha256
    ):
        return 0
    if _runtime_has_content():
        raise ValueError(
            "Refusing to merge a persistence snapshot into non-empty runtime roots; restart the Kaggle session or use the already hydrated generation"
        )
    total = 0
    for name, destination in roots().items():
        total += copy_tree(snapshot / name, destination)
    _atomic_json(marker_path, {
        "schema_version": "1.0",
        "generation_id": generation_id,
        "manifest_sha256": manifest_sha256,
    })
    return total


def _validate_snapshot(source: Path, *, allow_legacy: bool = False) -> None:
    manifest_path = source / "snapshot-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Persistence snapshot has no manifest")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "2.0" and not allow_legacy:
        raise ValueError("Persistence snapshot does not use generation schema 2.0")
    declared_files = payload.get("files") or {}
    if not isinstance(declared_files, dict):
        raise ValueError("Persistence snapshot manifest files must be an object")
    actual_files = {
        str(path.relative_to(source))
        for path in source.rglob("*")
        if path.is_file() and path.name != "snapshot-manifest.json"
    }
    if actual_files != set(declared_files):
        missing = sorted(set(declared_files) - actual_files)
        extra = sorted(actual_files - set(declared_files))
        raise ValueError(f"Persistence snapshot file set mismatch; missing={missing}, extra={extra}")
    for relative, expected in declared_files.items():
        path = (source / relative).resolve()
        try:
            path.relative_to(source.resolve())
        except ValueError as exc:
            raise ValueError(f"Persistence manifest contains an unsafe path: {relative}") from exc
        if not path.is_file():
            raise ValueError(f"Persistence snapshot is incomplete: {relative}")
        actual = _sha256(path)
        if actual != expected.get("sha256"):
            raise ValueError(f"Persistence snapshot hash mismatch: {relative}")
        if path.stat().st_size != expected.get("size_bytes"):
            raise ValueError(f"Persistence snapshot size mismatch: {relative}")


@contextmanager
def _quiescent_state():
    """Freeze run acquisition and refuse export while any run lease is active."""
    handles = []
    runs_dir = roots()["acd-state"] / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    barrier = (runs_dir / ".persistence.lock").open("a+b")
    handles.append(barrier)
    try:
        try:
            fcntl.flock(barrier.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Persistence export refused while a run is active") from exc
        lease_dir = runs_dir / ".leases"
        if lease_dir.is_dir():
            for lock in sorted(lease_dir.glob("*.lock")):
                handle = lock.open("a+b")
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    handle.close()
                    raise RuntimeError(f"Persistence export refused while a run is active: {lock.name}") from exc
                handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()


def _reject_secrets(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        tail = b""
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                data = tail + chunk
                if any(pattern.search(data) for pattern in SECRET_PATTERNS):
                    raise ValueError(
                        f"Persistence export contains credential-like material: {path.relative_to(root)}"
                    )
                # All credential patterns are far shorter than this overlap;
                # retain it so a token split across chunks is still detected.
                tail = data[-512:]


def _fsync_tree(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
    for directory in sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        _fsync_dir(directory)
    _fsync_dir(root)


def export(destination: Path) -> int:
    """Publish one immutable generation and then atomically advance current."""
    destination = destination.expanduser().resolve()
    for label, source in roots().items():
        source = source.resolve()
        overlaps = False
        try:
            destination.relative_to(source)
            overlaps = True
        except ValueError:
            pass
        try:
            source.relative_to(destination)
            overlaps = True
        except ValueError:
            pass
        if overlaps:
            raise ValueError(
                f"Persistence destination must not overlap runtime root {label}: {source}"
            )
    destination.mkdir(parents=True, exist_ok=True)
    generations = destination / "generations"
    generations.mkdir(parents=True, exist_ok=True)
    generation_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12]
    staging = destination / f".generation-{generation_id}.tmp"
    published = generations / generation_id
    if staging.exists() or published.exists():
        raise RuntimeError("Persistence generation ID collision")
    staging.mkdir()
    total = 0
    try:
        with _quiescent_state():
            for name, source in roots().items():
                total += copy_tree(source, staging / name)
        _reject_secrets(staging)
        manifest = {
            "schema_version": "2.0",
            "generation_id": generation_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": {},
        }
        for path in sorted(staging.rglob("*")):
            if not path.is_file() or path.name == "snapshot-manifest.json":
                continue
            manifest["files"][str(path.relative_to(staging))] = {
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        _atomic_json(staging / "snapshot-manifest.json", manifest)
        _fsync_tree(staging)
        os.replace(staging, published)
        _fsync_dir(generations)
        pointer = {
            "schema_version": "2.0",
            "generation_id": generation_id,
            "manifest_sha256": _sha256(published / "snapshot-manifest.json"),
        }
        _atomic_json(destination / "current.json", pointer)
        return total
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main() -> int:
    parser = argparse.ArgumentParser(description="Hydrate or export non-secret ACD runtime state")
    sub = parser.add_subparsers(dest="command", required=True)
    hydrate_parser = sub.add_parser("hydrate")
    hydrate_parser.add_argument("--source", type=Path, default=os.environ.get("ACD_PERSIST_SOURCE"))
    hydrate_parser.add_argument("--fresh", action="store_true", default=os.environ.get("ACD_FRESH_START") == "1")
    hydrate_parser.add_argument("--allow-legacy", action="store_true", default=os.environ.get("ACD_ALLOW_LEGACY_PERSISTENCE") == "1")
    export_parser = sub.add_parser("export")
    export_parser.add_argument("--destination", type=Path, default=os.environ.get("ACD_PERSIST_EXPORT", "/kaggle/working/acd-persist-export"))
    args = parser.parse_args()

    if args.command == "hydrate":
        if args.source is not None and args.fresh:
            print("Choose exactly one startup mode: persistence source or explicit fresh start, not both.")
            return 2
        if args.source is None:
            if args.fresh:
                print("Explicit fresh start selected; durable state begins empty.")
                return 0
            print("Persistence source is required. Set ACD_PERSIST_SOURCE or explicitly select ACD_FRESH_START=1.")
            return 2
        source = args.source.expanduser().resolve()
        if not source.is_dir():
            print(f"Persistence source does not exist: {source}")
            return 2
        try:
            count = hydrate(source, allow_legacy=args.allow_legacy)
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
