#!/usr/bin/env python3
"""Isolated process boundary for the pinned OpenMontage delivery API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


def atomic_json(path: Path, payload: dict) -> None:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openmontage-root", type=Path, required=True)
    parser.add_argument("--command", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()

    root = args.openmontage_root.expanduser().resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    payload = json.loads(args.command.read_text(encoding="utf-8"))
    try:
        from lib.acd_native_delivery import execute_delivery

        result = execute_delivery(payload)
        status = 0 if result.get("status") == "delivered" else 1
    except Exception as exc:  # final isolated-process protocol boundary
        result = {
            "schema_version": "1.0",
            "status": "failed",
            "code": "OPENMONTAGE_NATIVE_EXCEPTION",
            "message": str(exc),
        }
        status = 1
    atomic_json(args.result.expanduser().resolve(), result)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
