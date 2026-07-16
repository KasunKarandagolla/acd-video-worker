#!/usr/bin/env python3
"""Apply audited compatibility changes to exactly one pinned OpenMontage commit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


PIN = "f633b5f428b9be9a2afecba851dfddd101619756"
PATCH_ID = "cinematic-cut-props-v1"


def run(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, payload: dict) -> None:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openmontage-root", type=Path, required=True)
    parser.add_argument("--worker-root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    root = args.openmontage_root.expanduser().resolve()
    worker = args.worker_root.expanduser().resolve()

    head = run(root, ["rev-parse", "HEAD"])
    if head.returncode != 0 or head.stdout.strip() != PIN:
        raise SystemExit(f"Refusing compatibility patch: expected OpenMontage {PIN}, found {head.stdout.strip() or 'unknown'}")

    patch = worker / "patches" / "openmontage" / "f633b5f-cinematic-cut-props-v1.patch"
    check = run(root, ["apply", "--check", str(patch)])
    if check.returncode == 0:
        applied = run(root, ["apply", str(patch)])
        if applied.returncode != 0:
            raise SystemExit(applied.stderr or "OpenMontage compatibility patch failed")
    else:
        reverse = run(root, ["apply", "--reverse", "--check", str(patch)])
        if reverse.returncode != 0:
            raise SystemExit(
                "OpenMontage files do not match either the pinned source or the audited compatibility patch; "
                "preserving the checkout and refusing to overwrite it."
            )

    overlay_root = worker / "patches" / "openmontage" / "overlay"
    installed: dict[str, str] = {}
    for source in sorted(overlay_root.rglob("*")):
        if not source.is_file() or source.suffix == ".pyc" or "__pycache__" in source.parts:
            continue
        relative = source.relative_to(overlay_root)
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or digest(target) != digest(source):
            shutil.copy2(source, target)
        installed[str(relative)] = digest(source)

    marker = {
        "schema_version": "1.0",
        "openmontage_commit": PIN,
        "patches": [PATCH_ID],
        "patch_sha256": digest(patch),
        "overlay_sha256": installed,
    }
    atomic_json(root / ".acd-compatibility-patches.json", marker)
    print(json.dumps(marker, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
