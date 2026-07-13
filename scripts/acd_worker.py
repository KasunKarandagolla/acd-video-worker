#!/usr/bin/env python3
"""Single production entrypoint for the thin ACD control plane."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acd_worker.run_state import RunStatus  # noqa: E402
from acd_worker.thin_controller import ThinControllerConfig, ThinRunController  # noqa: E402


@dataclass
class ACDConfig:
    project_root: Path
    hermes_home: Path
    hermes_profile: str
    hermes_cli: Optional[str]
    openmontage_root: Path
    openmontage_projects_dir: Path
    state_dir: Path
    hermes_timeout: int
    hermes_max_turns: int
    hermes_recovery_max_turns: int
    hermes_headless_auto_approve: bool
    discord_webhook_url: str
    dry_run: bool = False

    @classmethod
    def from_env(cls) -> "ACDConfig":
        openmontage_root = Path(os.environ.get("OPENMONTAGE_ROOT", PROJECT_ROOT / "external" / "OpenMontage")).expanduser()
        return cls(
            project_root=PROJECT_ROOT,
            hermes_home=Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser(),
            hermes_profile=os.environ.get("HERMES_PROFILE", "football-emotion"),
            hermes_cli=os.environ.get("HERMES_CLI") or None,
            openmontage_root=openmontage_root,
            openmontage_projects_dir=Path(os.environ.get("OPENMONTAGE_PROJECTS_DIR", openmontage_root / "projects")).expanduser(),
            state_dir=Path(os.environ.get("ACD_STATE_DIR", PROJECT_ROOT / "state" / "runs")).expanduser(),
            hermes_timeout=int(os.environ.get("ACD_HERMES_TIMEOUT", "3600")),
            hermes_max_turns=int(os.environ.get("ACD_HERMES_MAX_TURNS", "60")),
            hermes_recovery_max_turns=int(os.environ.get("ACD_HERMES_RECOVERY_MAX_TURNS", "30")),
            hermes_headless_auto_approve=os.environ.get("ACD_HERMES_YOLO", "true").lower() == "true",
            discord_webhook_url=os.environ.get("DISCORD_WEBHOOK_URL", ""),
            dry_run=os.environ.get("ACD_DRY_RUN", "false").lower() == "true",
        )

    def controller_config(self) -> ThinControllerConfig:
        return ThinControllerConfig(
            worker_root=self.project_root,
            hermes_home=self.hermes_home,
            hermes_profile=self.hermes_profile,
            hermes_cli=self.hermes_cli,
            openmontage_root=self.openmontage_root,
            projects_dir=self.openmontage_projects_dir,
            state_dir=self.state_dir,
            hermes_timeout=self.hermes_timeout,
            hermes_max_turns=self.hermes_max_turns,
            hermes_recovery_max_turns=self.hermes_recovery_max_turns,
            hermes_headless_auto_approve=self.hermes_headless_auto_approve,
            discord_webhook_url=self.discord_webhook_url,
            dry_run=self.dry_run,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Thin AI Creative Director control plane")
    parser.add_argument("request", nargs="?", help="Creative video request")
    parser.add_argument("--input", action="append", default=[], help="Local file or URL; repeat for mixed inputs")
    parser.add_argument("--run-id", help="Resume an existing non-terminal run")
    parser.add_argument(
        "--retry-blocked",
        action="store_true",
        help="Explicitly retry a HERMES_RUNTIME_UNAVAILABLE blocked run using its existing Hermes session",
    )
    parser.add_argument("--dry-run", action="store_true", help="Prepare intake and Hermes prompt, then report BLOCKED without executing")
    parser.add_argument("--json", action="store_true", help="Print only the final run-state JSON")
    args = parser.parse_args()
    if args.retry_blocked and not args.run_id:
        parser.error("--retry-blocked requires --run-id")

    logging.basicConfig(
        level=getattr(logging, os.environ.get("ACD_LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    config = ACDConfig.from_env()
    if args.dry_run:
        config.dry_run = True
    controller = ThinRunController(config.controller_config())

    if args.run_id:
        state = controller.resume(args.run_id, retry_blocked=args.retry_blocked)
    else:
        if not args.request:
            parser.error("request is required unless --run-id is used")
        state = controller.start(args.request, args.input)

    payload = json.dumps(state.to_dict(), indent=2, sort_keys=True)
    if args.json:
        print(payload)
    else:
        print(f"Run {state.run_id}: {state.status.value}")
        print(f"State: {controller.store.path_for(state.run_id)}")
        if state.status == RunStatus.DELIVERED:
            valid = [item["path"] for item in state.validation if item.get("valid")]
            print(f"Output: {valid[0]}")
        elif state.blocker:
            print(f"Blocked [{state.blocker.code}]: {state.blocker.message}")
        elif state.error:
            print(f"Failed [{state.error.code}]: {state.error.message}")

    if state.status == RunStatus.DELIVERED:
        return 0
    if state.status == RunStatus.BLOCKED:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
