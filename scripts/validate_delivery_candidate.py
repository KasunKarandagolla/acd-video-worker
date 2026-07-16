#!/usr/bin/env python3
"""Run the worker-owned final checks while Hermes can still correct its claim."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acd_worker.agent_contract import load_agent_envelope  # noqa: E402
from acd_worker.media_validation import FinalMediaValidator, OpenMontageArtifactValidator  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a delivered ACD candidate without changing it")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--openmontage-root", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    openmontage_root = Path(args.openmontage_root).expanduser().resolve()
    result_path = Path(args.result).expanduser().resolve()
    try:
        envelope = load_agent_envelope(result_path, args.run_id)
    except (ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "contract_error": str(exc)}, indent=2))
        return 1

    if envelope.status != "delivered":
        print(json.dumps({
            "valid": False,
            "contract_error": "candidate validation applies only to status=delivered",
            "status": envelope.status,
        }, indent=2))
        return 1

    artifact_validation = OpenMontageArtifactValidator(
        project_dir, openmontage_root, result_path
    ).validate(envelope.openmontage_artifacts, envelope.output_media)
    media_validation = [
        FinalMediaValidator(project_dir).validate(candidate)
        for candidate in envelope.output_media
    ]
    evidence = {
        "valid": bool(artifact_validation.get("valid")) and any(
            item.get("valid") for item in media_validation
        ),
        "artifact_validation": artifact_validation,
        "media_validation": media_validation,
    }
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
