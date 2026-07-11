#!/usr/bin/env python3
"""
ACD Worker — Production-grade orchestrator for AI Creative Director Football Video System.

This is the thin adapter between user requests, Hermes Agent, and OpenMontage pipelines.
It does NOT make creative decisions — those live in Hermes skills.
"""

import os
import sys
import json
import uuid
import argparse
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from acd_worker.orchestrator import (
    StageOrchestrator, ProjectState, StageCheckpoint, StageName, StageStatus,
    CANONICAL_STAGE_ORDER, STAGE_ARTIFACTS, CheckpointManager, FixtureArtifactProvider
)
from acd_worker.hermes_runner import HermesRunner, HermesSessionResult
from acd_worker.openmontage_runner import OpenMontageRunner, run_schema_lock_verification
from acd_worker.footage_requirements import FootageRequirementsGenerator, load_footage_requirements
from acd_worker.source.discovery import DiscoveryEngine, create_story_slot_queries
from acd_worker.source.acquisition import AcquisitionEngine
from acd_worker.source.fallback_discovery import FallbackDiscoveryEngine
from acd_worker.quality_loop import (
    LoopbackController, FailureCategory, QualityGateRunner, create_quality_gate_runner
)


# ─── Configuration ────────────────────────────────────────────────────────────

def get_project_root() -> Path:
    """Get project root from __file__ location."""
    return Path(__file__).parent.parent


@dataclass
class ACDConfig:
    """Runtime configuration loaded from environment + config files."""
    # Paths - no hardcoded machine paths
    project_root: Path = field(default_factory=get_project_root)
    hermes_home: str = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
    openmontage_projects_dir: str = os.environ.get("OPENMONTAGE_PROJECTS_DIR", str(Path.home() / "OpenMontage" / "projects"))
    openmontage_root: str = os.environ.get("OPENMONTAGE_ROOT", str(Path.home() / "OpenMontage"))
    hermes_profile: str = os.environ.get("HERMES_PROFILE", "football-emotion")
    hermes_cli: Optional[str] = os.environ.get("HERMES_CLI")

    # Runtime
    discord_webhook_url: str = os.environ.get("DISCORD_WEBHOOK_URL", "")
    log_level: str = os.environ.get("ACD_LOG_LEVEL", "INFO")
    dry_run: bool = os.environ.get("ACD_DRY_RUN", "false").lower() == "true"
    max_loopbacks: int = int(os.environ.get("ACD_MAX_LOOPBACKS", "3"))
    render_runtime: str = os.environ.get("ACD_RENDER_RUNTIME", "ffmpeg")
    min_candidates_per_slot: int = int(os.environ.get("ACD_MIN_CANDIDATES", "3"))
    tavily_api_key: str = os.environ.get("TAVILY_API_KEY", "")

    @classmethod
    def from_env(cls) -> "ACDConfig":
        return cls(
            hermes_home=os.environ.get("HERMES_HOME", cls.hermes_home),
            openmontage_projects_dir=os.environ.get("OPENMONTAGE_PROJECTS_DIR", cls.openmontage_projects_dir),
            openmontage_root=os.environ.get("OPENMONTAGE_ROOT", cls.openmontage_root),
            hermes_profile=os.environ.get("HERMES_PROFILE", cls.hermes_profile),
            hermes_cli=os.environ.get("HERMES_CLI", cls.hermes_cli),
            discord_webhook_url=os.environ.get("DISCORD_WEBHOOK_URL", cls.discord_webhook_url),
            log_level=os.environ.get("ACD_LOG_LEVEL", cls.log_level),
            dry_run=os.environ.get("ACD_DRY_RUN", "false").lower() == "true",
            max_loopbacks=int(os.environ.get("ACD_MAX_LOOPBACKS", cls.max_loopbacks)),
            render_runtime=os.environ.get("ACD_RENDER_RUNTIME", cls.render_runtime),
            min_candidates_per_slot=int(os.environ.get("ACD_MIN_CANDIDATES", cls.min_candidates_per_slot)),
            tavily_api_key=os.environ.get("TAVILY_API_KEY", cls.tavily_api_key),
        )


# ─── Discord Notifier ─────────────────────────────────────────────────────────

class DiscordNotifier:
    """Sends notifications to Discord webhook."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)

    def notify(self, title: str, description: str, color: int = 0x3498db, fields: List[Dict] = None):
        if not self.enabled:
            return

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if fields:
            embed["fields"] = fields

        payload = {"embeds": [embed]}

        try:
            import urllib.request
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            logging.warning(f"Discord notification failed: {e}")

    def run_started(self, project_id: str, user_request: str, run_id: str):
        self.notify(
            "🎬 ACD Run Started",
            f"Project: `{project_id}`\nRequest: {user_request[:200]}",
            color=0x3498db,
            fields=[{"name": "Run ID", "value": run_id[:8], "inline": True}]
        )

    def sourcing_completed(self, project_id: str, candidates_found: int, clips_acquired: int):
        self.notify(
            "📹 Sourcing Completed",
            f"Project: `{project_id}`\nCandidates found: {candidates_found}\nClips acquired: {clips_acquired}",
            color=0x2ecc71
        )

    def editing_started(self, project_id: str):
        self.notify(
            "✂️ Editing Started",
            f"Project: `{project_id}`\nOpenMontage pipeline: documentary-montage",
            color=0xf39c12
        )

    def render_failed(self, project_id: str, error: str):
        self.notify(
            "❌ Render Failed",
            f"Project: `{project_id}`\nError: {error[:500]}",
            color=0xe74c3c
        )

    def quality_review_failed(self, project_id: str, failures: List[str]):
        self.notify(
            "⚠️ Quality Review Failed",
            f"Project: `{project_id}`\nFailures:\n" + "\n".join(f"• {f}" for f in failures[:5]),
            color=0xe74c3c
        )

    def loopback_triggered(self, project_id: str, from_stage: str, to_stage: str, reason: str):
        self.notify(
            "🔄 Quality Loopback",
            f"Project: `{project_id}`\nFrom: {from_stage}\nTo: {to_stage}\nReason: {reason}",
            color=0xf39c12
        )

    def run_completed(self, project_id: str, output_path: str, run_id: str, duration_seconds: float):
        self.notify(
            "🎉 ACD Run Completed",
            f"Project: `{project_id}`\nOutput: {output_path}",
            color=0x2ecc71,
            fields=[
                {"name": "Run ID", "value": run_id[:8], "inline": True},
                {"name": "Duration", "value": f"{duration_seconds:.0f}s", "inline": True}
            ]
        )

    def run_failed(self, project_id: str, error: str):
        self.notify(
            "❌ ACD Run Failed",
            f"Project: `{project_id}`\nError: {error[:500]}",
            color=0xe74c3c
        )


# ─── ACD Worker Core ──────────────────────────────────────────────────────────

class ACDWorker:
    """Main orchestrator for football video production runs."""

    def __init__(self, config: ACDConfig):
        self.config = config
        self.logger = logging.getLogger("acd_worker")
        self.discord = DiscordNotifier(config.discord_webhook_url)

        # Initialize runners
        self.hermes_runner = HermesRunner(
            hermes_home=config.hermes_home,
            profile=config.hermes_profile,
            dry_run=config.dry_run,
            hermes_cli=config.hermes_cli
        )

        self.footage_req_generator = FootageRequirementsGenerator(hermes_runner=self.hermes_runner)

        # Project state
        self.project_dir: Optional[Path] = None
        self.project_state: Optional[ProjectState] = None
        self.orchestrator: Optional[StageOrchestrator] = None
        self.openmontage_runner: Optional[OpenMontageRunner] = None
        self.loopback_controller = LoopbackController(max_loopbacks_per_category=config.max_loopbacks)

        # Run metadata
        self.run_id: Optional[str] = None
        self.start_time: Optional[datetime] = None
        self.run_metadata: Dict[str, Any] = {}

    def initialize_project(self, user_request: str) -> ProjectState:
        """Create or resume a production project."""
        self.run_id = str(uuid.uuid4())
        project_id = f"football-{datetime.utcnow().strftime('%Y%m%d')}-{self.run_id[:8]}"
        self.start_time = datetime.utcnow()

        # Create project workspace
        self.project_dir = Path(self.config.openmontage_projects_dir) / project_id
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # Create football_emotion auxiliary directory
        (self.project_dir / "football_emotion").mkdir(parents=True, exist_ok=True)

        # Initialize OpenMontage runner
        self.openmontage_runner = OpenMontageRunner(
            project_dir=self.project_dir,
            hermes_runner=self.hermes_runner,
            openmontage_root=Path(self.config.openmontage_root),
            openmontage_projects_dir=Path(self.config.openmontage_projects_dir),
            config={
                "render_runtime": self.config.render_runtime,
                "openmontage_schemas_path": str(Path(self.config.openmontage_root) / "schemas" / "artifacts")
            }
        )

        # Initialize orchestrator
        self.orchestrator = StageOrchestrator(
            project_dir=self.project_dir,
            hermes_runner=self.hermes_runner,
            openmontage_runner=self.openmontage_runner,
            config={
                "max_loopbacks": self.config.max_loopbacks,
                "openmontage_schemas_path": str(Path(self.config.openmontage_root) / "schemas" / "artifacts")
            },
            loopback_controller=self.loopback_controller,
            dry_run=self.config.dry_run
        )

        # Create or load project state
        self.project_state = self.orchestrator.checkpoint_mgr.load_state()
        if not self.project_state:
            self.project_state = ProjectState(
                project_id=project_id,
                run_id=self.run_id,
                user_request=user_request,
                created_at=self.start_time.isoformat(),
                updated_at=self.start_time.isoformat()
            )

        self.project_state.user_request = user_request
        self.orchestrator.state = self.project_state
        self.orchestrator.checkpoint_mgr.save_state(self.project_state)

        self.logger.info(f"Initialized project {project_id} (run: {self.run_id})")

        # Discord notification
        self.discord.run_started(project_id, user_request, self.run_id)

        return self.project_state

    def resume_project(self, run_id: str) -> bool:
        """Resume an existing project from its last checkpoint."""
        runs_dir = Path(self.config.openmontage_projects_dir).parent / "state" / "runs"
        state_file = runs_dir / f"{run_id}.json"

        if not state_file.exists():
            self.logger.error(f"Run state not found: {run_id}")
            return False

        try:
            data = json.loads(state_file.read_text())
            self.project_state = ProjectState.from_dict(data)
            self.run_id = self.project_state.run_id
            self.project_dir = Path(self.config.openmontage_projects_dir) / self.project_state.project_id

            # Reinitialize runners
            self.openmontage_runner = OpenMontageRunner(
                project_dir=self.project_dir,
                hermes_runner=self.hermes_runner,
                openmontage_root=Path(self.config.openmontage_root),
                openmontage_projects_dir=Path(self.config.openmontage_projects_dir),
                config={"render_runtime": self.config.render_runtime}
            )

            self.orchestrator = StageOrchestrator(
                project_dir=self.project_dir,
                hermes_runner=self.hermes_runner,
                openmontage_runner=self.openmontage_runner,
                config={"max_loopbacks": self.config.max_loopbacks},
                loopback_controller=self.loopback_controller
            )
            self.orchestrator.state = self.project_state

            self.logger.info(f"Resumed project {self.project_state.project_id} at stage {self.project_state.current_stage}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to resume: {e}")
            return False

    def run_schema_lock_verification(self) -> bool:
        """Verify OpenMontage schema lock before producing native artifacts."""
        self.logger.info("Verifying OpenMontage schema lock...")

        success, message = run_schema_lock_verification(
            project_dir=self.project_dir,
            openmontage_root=Path(self.config.openmontage_root),
            hermes_runner=self.hermes_runner
        )

        if success:
            self.logger.info("✓ Schema lock verified")
            return True
        else:
            self.logger.error(f"Schema lock failed: {message}")
            return False

    def execute_full_workflow(self, user_request: str) -> bool:
        """Execute the complete football video production workflow."""

        # In dry-run mode, run full pipeline with fixture artifacts
        if self.config.dry_run:
            self.logger.info("DRY RUN MODE - Executing full pipeline with fixture artifacts")
            self.initialize_project(user_request)

            # Run the canonical orchestrator pipeline
            context = self._parse_user_request(user_request)
            self.run_metadata.update(context)

            result = self.orchestrator.run_pipeline(user_request, self.run_metadata)

            if result.success:
                self.logger.info("Dry run completed successfully")
                self.project_state.status = "completed"
                self.orchestrator.checkpoint_mgr.save_state(self.project_state)
                return True
            else:
                self.logger.error(f"Dry run failed: {result.error}")
                return False

        # Full production workflow
        self.initialize_project(user_request)

        try:
            # Parse user request for context
            context = self._parse_user_request(user_request)
            self.run_metadata.update(context)

            # Execute via canonical orchestrator
            result = self.orchestrator.run_pipeline(user_request, self.run_metadata)

            if result.success:
                duration = (datetime.utcnow() - self.start_time).total_seconds()
                output_path = self.project_state.output_path or "unknown"

                self.discord.run_completed(
                    self.project_state.project_id,
                    output_path,
                    self.run_id,
                    duration
                )

                self.logger.info(f"\n✅ Production completed successfully!")
                self.logger.info(f"Output: {output_path}")
                self.logger.info(f"Duration: {duration:.0f}s")
                return True
            else:
                self._fail_workflow(f"Pipeline failed: {result.error}")
                return False

        except Exception as e:
            self.logger.exception("Workflow exception")
            self._fail_workflow(f"Workflow exception: {e}")
            return False

    def _parse_user_request(self, user_request: str) -> Dict[str, Any]:
        """Parse user request into structured context."""
        context = {
            "raw_request": user_request,
            "target_emotion": "triumph",
            "duration_seconds": 180,
            "platform": "youtube_longform",
            "players": [],
            "teams": [],
            "competition": ""
        }

        request_lower = user_request.lower()

        # Extract emotion
        emotions = ["comeback", "heartbreak", "revenge", "legacy", "pressure",
                   "underdog", "last_chance", "iconic_skill", "rivalry",
                   "national_pride", "heroic_failure", "humiliation"]
        for emo in emotions:
            if emo in request_lower:
                context["target_emotion"] = emo
                break

        # Extract duration
        import re
        dur_match = re.search(r'(\d+)\s*(sec|second|min|minute)', request_lower)
        if dur_match:
            val = int(dur_match.group(1))
            unit = dur_match.group(2)
            context["duration_seconds"] = val if unit.startswith("sec") else val * 60

        # Extract platform
        platforms = ["shorts", "tiktok", "reels", "youtube"]
        for p in platforms:
            if p in request_lower:
                context["platform"] = f"youtube_{p}" if p != "youtube" else "youtube_longform"
                break

        # Extract known entities
        known_players = ["messi", "ronaldo", "mbappe", "haaland", "neymar", "modric", "kroos"]
        known_teams = ["argentina", "france", "brazil", "germany", "spain", "england", "portugal", "psg", "real madrid", "barcelona", "manchester"]
        known_comps = ["world cup", "champions league", "euro", "copa america", "premier league", "la liga"]

        for p in known_players:
            if p in request_lower:
                context["players"].append(p.title())
        for t in known_teams:
            if t in request_lower:
                context["teams"].append(t.title())
        for c in known_comps:
            if c in request_lower:
                context["competition"] = c.title()

        return context

    def _fail_workflow(self, error: str):
        """Mark workflow as failed."""
        self.project_state.status = "failed"
        self.project_state.error = error
        self.orchestrator.checkpoint_mgr.save_state(self.project_state)
        self.discord.run_failed(self.project_state.project_id, error)
        self.logger.error(f"Workflow failed: {error}")


def main():
    parser = argparse.ArgumentParser(description="ACD Worker - Football Video Orchestrator (Session 4.5)")
    parser.add_argument("request", nargs="?", help="User request for video production")
    parser.add_argument("--run-id", help="Resume existing run by ID")
    parser.add_argument("--dry-run", action="store_true", help="Run without executing Hermes/OpenMontage")
    parser.add_argument("--config", help="Path to config file (JSON)")
    parser.add_argument("--validate-only", action="store_true", help="Only run setup validation")
    args = parser.parse_args()

    # Setup logging
    log_level = os.environ.get("ACD_LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    logger = logging.getLogger("acd_worker")

    # Load config
    config = ACDConfig.from_env()
    if args.dry_run:
        config.dry_run = True
    if args.config:
        with open(args.config) as f:
            config.__dict__.update(json.load(f))

    worker = ACDWorker(config)

    if args.validate_only:
        logger.info("Running setup validation only...")
        # Would call bootstrap/validate_setup.py
        sys.exit(0)

    if args.run_id:
        # Resume existing run
        logger.info(f"Resuming run {args.run_id}")
        if worker.resume_project(args.run_id):
            logger.info(f"Resumed at stage: {worker.project_state.current_stage}")
            success = worker.execute_full_workflow(worker.project_state.user_request)
            sys.exit(0 if success else 1)
        else:
            logger.error(f"Failed to resume run {args.run_id}")
            sys.exit(1)

    if not args.request:
        parser.print_help()
        sys.exit(1)

    # Execute workflow
    logger.info(f"Starting production for: {args.request}")
    success = worker.execute_full_workflow(args.request)

    if success:
        logger.info("Production completed successfully")
        sys.exit(0)
    else:
        logger.error("Production failed")
        sys.exit(1)


if __name__ == "__main__":
    main()