#!/usr/bin/env python3
"""Callable worker-owned source acquisition/replacement boundary for Hermes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acd_worker.source_service import SourceService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire ranked source candidates sequentially")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--slot", required=True)
    parser.add_argument("--url", action="append", required=True)
    args = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.slot):
        parser.error("--slot must contain only letters, digits, underscores or hyphens")
    manifest = args.manifest.expanduser().resolve()
    if not manifest.is_file():
        parser.error(f"manifest does not exist: {manifest}")
    # The manifest's football_emotion parent defines the project boundary.
    project_dir = manifest.parent.parent.resolve()
    output_dir = args.output_dir.expanduser().resolve()
    try:
        output_dir.relative_to(project_dir)
    except ValueError:
        parser.error("--output-dir must stay inside the OpenMontage project workspace")

    try:
        result = SourceService().acquire(manifest, args.url, args.slot, output_dir)
    except ImportError as exc:
        print(json.dumps({"status": "blocked", "code": "ACQUISITION_DEPENDENCY_MISSING", "message": str(exc)}))
        return 2
    except Exception as exc:
        print(json.dumps({"status": "failed", "code": "ACQUISITION_FAILED", "message": str(exc)}))
        return 1
    print(json.dumps({"status": "acquired" if result["acquired"] else "blocked", **result}, indent=2))
    return 0 if result["acquired"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
