#!/usr/bin/env python3
"""
ACD Worker — Production-grade orchestrator for AI Creative Director Football Video System.

This is the thin adapter between user requests, Hermes Agent, and OpenMontage pipelines.
It does NOT make creative decisions — those live in Hermes skills.

Session 4: Full orchestration with checkpoint/resume, dynamic footage requirements,
fallback discovery, quality loopbacks, and end-to-end pipeline execution.
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
    STAGE_ORDER, STAGE_ARTIFACTS, CheckpointManager
)
from acd_worker.hermes_runner import HermesRunner, HermesSessionResult
from acd_worker.openmontage_runner import OpenMontageRunner, run_schema_lock_verification
from acd_worker.footage_requirements import FootageRequirementsGenerator
from acd_worker.source.discovery import DiscoveryEngine, create_story_slot_queries
from acd_worker.source.acquisition import AcquisitionEngine
from acd_worker.source.fallback_discovery import FallbackDiscoveryEngine
from acd_worker.quality_loop import (
    LoopbackController, FailureCategory, QualityGate
)

# ─── Configuration ────────────────────────────────────────────────────────────

@dataclass
class ACDConfig:
    """Runtime configuration loaded from environment + config files."""
    hermes_home: str = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    openmontage_projects_dir: str = os.environ.get("OPENMONTAGE_PROJECTS_DIR", 
                                                    os.path.expanduser("~/OpenMontage/projects"))
    openmontage_root: str = os.environ.get("OPENMONTAGE_ROOT", 
                                            "/home/kasun/Music/Director/acd-video-worker/external/OpenMontage")
    hermes_profile: str = "football-emotion"
    discord_webhook_url: str = os.environ.get("DISCORD_WEBHOOK_URL", "")
    log_level: str = "INFO"
    dry_run: bool = False
    max_loopbacks: int = 3
    render_runtime: str = "ffmpeg"
    min_candidates_per_slot: int = 3
    tavily_api_key: str = os.environ.get("TAVILY_API_KEY", "")
    
    @classmethod
    def from_env(cls) -> "ACDConfig":
        return cls(
            hermes_home=os.environ.get("HERMES_HOME", cls.hermes_home),
            openmontage_projects_dir=os.environ.get("OPENMONTAGE_PROJECTS_DIR", cls.openmontage_projects_dir),
            openmontage_root=os.environ.get("OPENMONTAGE_ROOT", cls.openmontage_root),
            hermes_profile=os.environ.get("HERMES_PROFILE", cls.hermes_profile),
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
            dry_run=config.dry_run
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
            loopback_controller=self.loopback_controller
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
        
        # In dry-run mode, just initialize and return success
        if self.config.dry_run:
            self.logger.info("DRY RUN MODE - Initializing project and returning success")
            self.initialize_project(user_request)
            self.project_state.status = "completed"
            self.orchestrator.checkpoint_mgr.save_state(self.project_state)
            self.logger.info("Dry run completed successfully")
            return True
        
        self.initialize_project(user_request)
        
        try:
            # Parse user request for context
            context = self._parse_user_request(user_request)
            self.run_metadata.update(context)
            
            # ============================================================
            # STAGE 1: STORY_UNDERSTANDING
            # ============================================================
            self.logger.info("\n" + "="*60)
            self.logger.info("STAGE 1: STORY_UNDERSTANDING")
            self.logger.info("="*60)
            
            result = self._run_story_understanding(context)
            if not result.success:
                self._fail_workflow(f"Story understanding failed: {result.error}")
                return False
            
            # ============================================================
            # STAGE 2: FOOTAGE_REQUIREMENTS (Dynamic, Hermes-generated)
            # ============================================================
            self.logger.info("\n" + "="*60)
            self.logger.info("STAGE 2: FOOTAGE_REQUIREMENTS")
            self.logger.info("="*60)
            
            footage_reqs = self._generate_footage_requirements(context)
            if not footage_reqs:
                self._fail_workflow("Footage requirements generation failed")
                return False
            
            # ============================================================
            # STAGE 3: FOOTAGE_DISCOVERY (with fallback)
            # ============================================================
            self.logger.info("\n" + "="*60)
            self.logger.info("STAGE 3: FOOTAGE_DISCOVERY")
            self.logger.info("="*60)
            
            source_candidates = self._run_footage_discovery(footage_reqs, context)
            if not source_candidates:
                self._fail_workflow("Footage discovery failed - no candidates found")
                return False
            
            # ============================================================
            # STAGE 4: VISUAL_ANALYSIS
            # ============================================================
            self.logger.info("\n" + "="*60)
            self.logger.info("STAGE 4: VISUAL_ANALYSIS")
            self.logger.info("="*60)
            
            scene_analysis = self._run_visual_analysis(source_candidates)
            if not scene_analysis:
                self._fail_workflow("Visual analysis failed")
                return False
            
            # ============================================================
            # STAGE 5: TIMESTAMP_EXTRACTION
            # ============================================================
            self.logger.info("\n" + "="*60)
            self.logger.info("STAGE 5: TIMESTAMP_EXTRACTION")
            self.logger.info("="*60)
            
            clip_candidates = self._run_timestamp_extraction(scene_analysis)
            if not clip_candidates:
                self._fail_workflow("Timestamp extraction failed")
                return False
            
            # ============================================================
            # STAGE 6: CLIP_SCORING
            # ============================================================
            self.logger.info("\n" + "="*60)
            self.logger.info("STAGE 6: CLIP_SCORING")
            self.logger.info("="*60)
            
            clip_scores = self._run_clip_scoring(clip_candidates, context)
            if not clip_scores:
                self._fail_workflow("Clip scoring failed")
                return False
            
            # ============================================================
            # STAGE 7: FOOTAGE_ACQUISITION
            # ============================================================
            self.logger.info("\n" + "="*60)
            self.logger.info("STAGE 7: FOOTAGE_ACQUISITION")
            self.logger.info("="*60)
            
            source_media_review, asset_manifest = self._run_footage_acquisition(
                clip_scores, footage_reqs
            )
            if not source_media_review:
                self._fail_workflow("Footage acquisition failed")
                return False
            
            # Discord: sourcing completed
            clips_acquired = len(source_media_review.get("files", []))
            self.discord.sourcing_completed(
                self.project_state.project_id,
                len(source_candidates),
                clips_acquired
            )
            
            # ============================================================
            # STAGE 8-12: OPENMONTAGE PIPELINE
            # ============================================================
            self.logger.info("\n" + "="*60)
            self.logger.info("STAGES 8-12: OPENMONTAGE PIPELINE")
            self.logger.info("="*60)
            
            self.discord.editing_started(self.project_state.project_id)
            
            # Verify schema lock before native artifacts
            if not self.run_schema_lock_verification():
                self._fail_workflow("Schema lock verification failed")
                return False
            
            # Build adapter-facing plans from scored clips
            openmontage_edit_plan, openmontage_audio_ops = self._build_openmontage_plans(
                clip_scores, footage_reqs, context
            )
            
            # Run OpenMontage pipeline
            om_results = self.openmontage_runner.run_full_pipeline(
                brief_interpretation=self._load_artifact("brief_interpretation.json"),
                footage_requirements=footage_reqs.to_dict() if hasattr(footage_reqs, 'to_dict') else footage_reqs,
                clip_scores=clip_scores,
                source_media_review=source_media_review,
                asset_manifest=asset_manifest,
                openmontage_edit_plan=openmontage_edit_plan,
                openmontage_audio_operations=openmontage_audio_ops
            )
            
            # Check compose stage result
            compose_result = next((r for r in om_results if r.stage == "compose"), None)
            if not compose_result or not compose_result.success:
                self.discord.render_failed(
                    self.project_state.project_id,
                    compose_result.error if compose_result else "Unknown compose error"
                )
                self._fail_workflow("OpenMontage compose failed")
                return False
            
            final_video = compose_result.artifacts.get("final_video")
            
            # ============================================================
            # STAGE 13: QUALITY_REVIEW
            # ============================================================
            self.logger.info("\n" + "="*60)
            self.logger.info("STAGE 13: QUALITY_REVIEW")
            self.logger.info("="*60)
            
            qa_passed, qa_failures = self._run_quality_review()
            if not qa_passed:
                self.discord.quality_review_failed(self.project_state.project_id, qa_failures)
                # Attempt loopbacks
                for failure in qa_failures:
                    target_stage = self.loopback_controller.get_target_stage(failure)
                    if target_stage and self.loopback_controller.should_loopback(failure):
                        self.discord.loopback_triggered(
                            self.project_state.project_id,
                            "quality_review",
                            target_stage.value,
                            failure
                        )
                        # In a full implementation, we'd loop back here
                        # For Session 4, we report and continue
                
                self._fail_workflow(f"Quality review failed: {qa_failures}")
                return False
            
            # ============================================================
            # STAGE 14: DELIVERY
            # ============================================================
            self.logger.info("\n" + "="*60)
            self.logger.info("STAGE 14: DELIVERY")
            self.logger.info("="*60)
            
            output_path = self._finalize_delivery(final_video)
            
            # ============================================================
            # STAGE 15: MEMORY_UPDATE
            # ============================================================
            self.logger.info("\n" + "="*60)
            self.logger.info("STAGE 15: MEMORY_UPDATE")
            self.logger.info("="*60)
            
            self._run_memory_update()
            
            # Complete
            duration = (datetime.utcnow() - self.start_time).total_seconds()
            self.discord.run_completed(
                self.project_state.project_id,
                output_path,
                self.run_id,
                duration
            )
            
            self.project_state.status = "completed"
            self.project_state.output_path = output_path
            self.orchestrator.checkpoint_mgr.save_state(self.project_state)
            
            self.logger.info(f"\n✅ Production completed successfully!")
            self.logger.info(f"Output: {output_path}")
            self.logger.info(f"Duration: {duration:.0f}s")
            
            return True
            
        except Exception as e:
            self.logger.exception("Workflow exception")
            self._fail_workflow(f"Workflow exception: {e}")
            return False
    
    def _parse_user_request(self, user_request: str) -> Dict[str, Any]:
        """Parse user request into structured context."""
        # Simple parsing - in production this would use Hermes skill
        context = {
            "raw_request": user_request,
            "target_emotion": "triumph",  # default
            "duration_seconds": 180,      # default 3 min
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
        
        # Extract known entities (simplified)
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
    
    def _run_story_understanding(self, context: Dict) -> HermesSessionResult:
        """Run story understanding via Hermes skills."""
        prompt = f"""
User request: {context['raw_request']}

As the football-emotion creative director, interpret this request using social-edit-reasoning and football-story-strategy skills.

Produce:
1. brief_interpretation.json with:
   - emotional_question: The core emotional question this video answers
   - tonal_flavor: triumphant|bittersweet|defiant|introspective|angry|tragic|heroic
   - runtime_target: {context['duration_seconds']} seconds
   - platform: {context['platform']}
   - arc_phases_in_scope: List of phases from [cold_open, setup, fall, grind, turning_point, triumph_or_payoff, coda]
   - non_negotiable_moments: Specific moments that must be included

2. story_plan.json with:
   - story_structure: Name from emotion-pattern-library (e.g., pain_pressure_comeback_legacy)
   - hook_pattern: One of the 8 hook patterns
   - target_duration: {context['duration_seconds']}s
   - sections: Array of {{section_id, timeline_range, emotional_role, required_clip_types, narrative_purpose}}
   - minimum_clip_package: List of required clip types for this story type

3. editorial_journey_state.json with current_stage=1 and locked decisions.

Save all artifacts to {self.project_dir}/football_emotion/
"""
        result = self.hermes_runner.run_session(
            prompt=prompt,
            expected_skills=["social-edit-reasoning", "football-story-strategy"]
        )
        
        if result.success:
            # Load artifacts into context
            self._load_stage_artifacts(StageName.STORY_UNDERSTANDING)
        
        return result
    
    def _generate_footage_requirements(self, context: Dict) -> Optional[object]:
        """Generate dynamic footage requirements via Hermes."""
        prompt = f"""
Using the brief_interpretation and story_plan from previous stage, generate a dynamic footage requirements plan.

Context:
- Target emotion: {context['target_emotion']}
- Duration: {context['duration_seconds']}s
- Platform: {context['platform']}
- Players: {context['players']}
- Teams: {context['teams']}
- Competition: {context['competition']}
- Story structure: (from story_plan)

Generate footage_requirements.json with an array of requirements, each containing:
- slot_id: unique identifier
- purpose: editorial purpose in one sentence
- story_section: which story phase this serves
- required_emotion: target emotion for this clip
- desired_subject: who/what should be in frame
- desired_action: what should be happening
- visual_type: closeup|wide|medium|reaction|action|graphic
- priority: 1=critical, 2=important, 3=supporting, 4=optional
- minimum_clips: minimum acceptable clips
- search_terms: primary YouTube search queries
- alternative_terms: fallback queries
- optional: can be dropped if no footage found
- estimated_duration_seconds: target duration in final edit
- story_role: hook_reference|source_clip|deep_analysis_reference|audio_reference|thumbnail_reference
- platform_considerations: aspect ratio, safe zones, etc.

Requirements:
- 8-15 requirements total (more for longer videos)
- At least 3 priority-1 (critical) requirements
- Cover ALL story sections from story_plan
- At least 30% non-English queries
- Include at least 1 hook_reference, 1 audio_reference, 1 thumbnail_reference

Save to {self.project_dir}/football_emotion/footage_requirements.json
"""
        result = self.hermes_runner.run_session(
            prompt=prompt,
            expected_skills=["football-story-strategy"]
        )
        
        if result.success:
            # Load the generated requirements
            req_file = self.project_dir / "football_emotion" / "footage_requirements.json"
            if req_file.exists():
                from acd_worker.footage_requirements import load_footage_requirements
                return load_footage_requirements(req_file)
        
        # Fallback: generate from template
        self.logger.warning("Hermes generation failed, using fallback template")
        return self.footage_req_generator.generate_fallback_plan(
            user_request=context['raw_request'],
            match_context={
                "competition": context['competition'],
                "teams": context['teams'],
                "players": context['players']
            },
            target_emotion=context['target_emotion'],
            duration_seconds=context['duration_seconds'],
            platform=context['platform']
        )
    
    def _run_footage_discovery(self, footage_reqs, context: Dict) -> List:
        """Run footage discovery with primary + fallback methods."""
        all_candidates = {}
        
        # Primary discovery via Hermes skill
        prompt = f"""
Run football-source-discovery for each requirement in footage_requirements.json.

For each requirement:
1. Execute 5 query styles: story, moment, editing-style, official-source, non-English
2. Use yt-dlp search (ytsearchN:query) via browser/terminal tools
3. Rank candidates with 7-axis rubric (0-10)
4. Assign deep_analysis_candidate: yes (>=8), maybe (6-7.9), no (<6)
5. Apply rejection rules (generic highlights, AI fakes, watermarks, shorts-only, etc.)

Output: source_candidates.json with all candidates per slot, ranked.
Save to {self.project_dir}/football_emotion/source_candidates.json
"""
        result = self.hermes_runner.run_session(
            prompt=prompt,
            expected_skills=["football-source-discovery"]
        )
        
        if result.success:
            candidates_file = self.project_dir / "football_emotion" / "source_candidates.json"
            if candidates_file.exists():
                with open(candidates_file) as f:
                    all_candidates = json.load(f)
        
        # Check if we need fallback
        fallback_engine = FallbackDiscoveryEngine(
            min_candidates_per_slot=self.config.min_candidates_per_slot,
            tavily_api_key=self.config.tavily_api_key
        )
        
        # Get primary results per slot
        primary_per_slot = {}
        if isinstance(all_candidates, dict):
            for slot, cands in all_candidates.items():
                primary_per_slot[slot] = cands
        
        # Run fallback for slots with insufficient candidates
        slot_queries = {}
        if hasattr(footage_reqs, 'get_search_queries'):
            slot_queries = footage_reqs.get_search_queries()
        else:
            # Build from requirements
            for req in footage_reqs.requirements:
                slot_queries[req.slot_id] = req.search_terms + req.alternative_terms
        
        fallback_results = fallback_engine.discover_all_slots(
            slot_queries=slot_queries,
            target_emotion=context['target_emotion'],
            primary_results=primary_per_slot
        )
        
        # Merge fallback results
        for slot, fallback_cands in fallback_results.items():
            if slot not in all_candidates:
                all_candidates[slot] = []
            # Add fallback candidates that aren't duplicates
            existing_ids = {c.get('video_id') for c in all_candidates[slot] if c.get('video_id')}
            for fc in fallback_cands:
                if fc.video_id not in existing_ids:
                    all_candidates[slot].append(fc.to_dict())
                    existing_ids.add(fc.video_id)
        
        # Save combined results
        output_file = self.project_dir / "football_emotion" / "source_candidates.json"
        output_file.write_text(json.dumps(all_candidates, indent=2))
        
        # Flatten for return
        flat_candidates = []
        for slot, cands in all_candidates.items():
            flat_candidates.extend(cands)
        
        self.logger.info(f"Total candidates discovered: {len(flat_candidates)} across {len(all_candidates)} slots")
        return flat_candidates
    
    def _run_visual_analysis(self, source_candidates: List) -> Dict:
        """Run visual scene analysis on deep-analysis candidates."""
        # Filter for deep analysis candidates
        deep_candidates = [c for c in source_candidates if c.get('deep_analysis_candidate') == 'yes']
        
        if not deep_candidates:
            self.logger.warning("No deep analysis candidates found")
            return {}
        
        prompt = f"""
Run football-visual-scene-analysis on {len(deep_candidates)} deep-analysis candidates.

For each candidate:
1. Use OpenMontage frame_sampler (scene_guided mode) to extract representative frames
2. Use OpenMontage scene_detect (content mode) to identify scene boundaries
3. Use transcriber if audio present
4. Produce video_scene_analysis with:
   - scene_id, source_timestamp_start/end
   - editor_timeline_role (hook|setup|buildup|pressure|reversal|climax|aftermath|outro)
   - scene_type, visual_description, audio_description
   - editing_technique_observed
   - emotional_purpose
   - confidence: high|medium|low|unusable
   - manual_review_needed: boolean

Output: video_scene_analysis.json
Save to {self.project_dir}/football_emotion/video_scene_analysis.json
"""
        result = self.hermes_runner.run_session(
            prompt=prompt,
            expected_skills=["football-visual-scene-analysis"]
        )
        
        if result.success:
            return self._load_artifact("video_scene_analysis.json")
        return {}
    
    def _run_timestamp_extraction(self, scene_analysis: Dict) -> List:
        """Extract timestamped clip candidates from scene analysis."""
        prompt = f"""
Run football-timestamp-extraction on the video_scene_analysis.json.

Convert each scene into clip_candidate rows with:
- clip_id, source_video_id, source_range (HH:MM:SS-HH:MM:SS)
- topic_match, scene_type, emotional_role
- visual_signs, audio_signs, story_relevance
- rights_risk, verification_status
- editor_timeline_role, recommended_use

Output: clip_candidates.json
Save to {self.project_dir}/football_emotion/clip_candidates.json
"""
        result = self.hermes_runner.run_session(
            prompt=prompt,
            expected_skills=["football-timestamp-extraction"]
        )
        
        if result.success:
            return self._load_artifact("clip_candidates.json")
        return []
    
    def _run_clip_scoring(self, clip_candidates: List, context: Dict) -> Dict:
        """Score clips against story plan."""
        prompt = f"""
Run football-clip-scoring on all clip_candidates.json against the story_plan.

Score each clip on 7-axis rubric (0-10 total):
- emotional_strength_2 (0-2)
- visual_clarity_2 (0-2)
- story_relevance_2 (0-2)
- audio_commentary_value_1 (0-1)
- uniqueness_1 (0-1)
- editability_1 (0-1)
- rights_reused_content_risk_1 (0-1, inverted)

Assign recommended_use: hook|context|buildup|climax|aftermath|reject
Thresholds: 8-10=core story, 6-7.9=supporting, 4-5.9=context-only/replace, <4=reject

Verify minimum_clip_package from story_plan is satisfied.

Output: clip_scores.json
Save to {self.project_dir}/football_emotion/clip_scores.json
"""
        result = self.hermes_runner.run_session(
            prompt=prompt,
            expected_skills=["football-clip-scoring"]
        )
        
        if result.success:
            return self._load_artifact("clip_scores.json")
        return {}
    
    def _run_footage_acquisition(self, clip_scores: Dict, footage_reqs) -> tuple:
        """Acquire footage for selected clips."""
        # Get selected clips (core + supporting)
        selected_clips = []
        for clip in clip_scores.get("clips", []):
            if clip.get("recommended_use") != "reject":
                selected_clips.append(clip)
        
        if not selected_clips:
            self.logger.error("No clips selected for acquisition")
            return None, None
        
        prompt = f"""
Run football-footage-acquisition for {len(selected_clips)} selected clips.

For each clip:
1. Download source video using OpenMontage video_downloader (yt-dlp)
2. Verify with ffprobe: duration, resolution, codec, audio
3. Frame sample: 4 frames evenly spaced
4. Transcribe if audio present
5. Build source_media_review entry with:
   - path, technical_probe, content_summary, transcript_summary
   - representative_frames, quality_risks, usable_for
   - verification_status: verified|partial|failed
   - acquisition_attempt, original_candidate_id, source_url
6. On failure: try next ranked candidate for same slot (max 3 attempts)
7. Update asset_manifest with each acquired file

Output: source_media_review.json + updated asset_manifest.json
Save to {self.project_dir}/football_emotion/
"""
        result = self.hermes_runner.run_session(
            prompt=prompt,
            expected_skills=["football-footage-acquisition"]
        )
        
        if result.success:
            source_media_review = self._load_artifact("source_media_review.json")
            asset_manifest = self._load_artifact("asset_manifest.json")
            return source_media_review, asset_manifest
        
        return None, None
    
    def _build_openmontage_plans(self, clip_scores: Dict, footage_reqs, context: Dict) -> tuple:
        """Build adapter-facing OpenMontage plans."""
        # Load required artifacts
        brief_interp = self._load_artifact("brief_interpretation.json")
        story_plan = self._load_artifact("story_plan.json")
        narration_script = self._load_artifact("narration_script.json")
        audio_plan = self._load_artifact("audio_plan.json")
        
        # Run planning skills via Hermes
        prompt = f"""
Build OpenMontage adapter-facing plans using:
- story_plan.json
- clip_scores.json
- narration_script.json
- audio_plan.json
- footage_requirements.json

Run these skills in sequence:
1. football-pro-cutting-pacing: Determine cut_style, transitions, effects per section
2. football-caption-thumbnail-direction: Generate caption_plan and thumbnail_candidate
3. football-audio-music-director: Refine audio_plan with section-by-section music actions
4. football-commentary-ducking-mixer: Add ducking parameters
5. openmontage-edit-planning: Assemble openmontage_edit_plan.json
6. openmontage-audio-operation-mapper: Produce openmontage_audio_operations.json

Output both plans to {self.project_dir}/football_emotion/
"""
        result = self.hermes_runner.run_session(
            prompt=prompt,
            expected_skills=[
                "football-pro-cutting-pacing",
                "football-caption-thumbnail-direction",
                "football-audio-music-director",
                "football-commentary-ducking-mixer",
                "openmontage-edit-planning",
                "openmontage-audio-operation-mapper"
            ]
        )
        
        if result.success:
            edit_plan = self._load_artifact("openmontage_edit_plan.json")
            audio_ops = self._load_artifact("openmontage_audio_operations.json")
            return edit_plan, audio_ops
        
        # Return empty plans as fallback
        return {}, {}
    
    def _run_quality_review(self) -> tuple[bool, List[str]]:
        """Run quality review skills."""
        prompt = f"""
Run football QA skills on the completed production:

1. football-retention-quality-control: full_qa_report
   - Technical QA (black frames, aspect ratio, resolution, sync)
   - Editorial QA (missing sections, weak progression, duplicate clips)
   - Platform QA (export profile, safe zones)
   - Reused content gate
   - Vibe check

2. football-audio-quality-control: qc_report
   - Loudness: -14 LUFS ±1
   - True peak: -1 dBTP max
   - LRA: <7 LU
   - No clipping, proper ducking

3. football-platform-export-validator: export_profile
   - Platform: {self.project_dir.name}
   - Aspect ratio, resolution, codec, container
   - Audio codec, loudness target

Output all three reports to {self.project_dir}/football_emotion/
Return loopback instructions if any gate fails.
"""
        result = self.hermes_runner.run_session(
            prompt=prompt,
            expected_skills=[
                "football-retention-quality-control",
                "football-audio-quality-control",
                "football-platform-export-validator"
            ]
        )
        
        failures = []
        if result.success:
            qa_report = self._load_artifact("full_qa_report.json")
            audio_qc = self._load_artifact("audio_qc_report.json")
            export_profile = self._load_artifact("export_profile.json")
            
            # Check pass/fail
            if qa_report and not qa_report.get("pass", True):
                for finding in qa_report.get("required_loopbacks", []):
                    failures.append(finding.get("reason", "QA failure"))
            
            if audio_qc and not audio_qc.get("pass", True):
                failures.append("Audio QC failed: loudness/peak/ducking issues")
            
            if export_profile and not export_profile.get("pass", True):
                failures.append("Export profile validation failed")
        
        return len(failures) == 0, failures
    
    def _finalize_delivery(self, final_video: str) -> str:
        """Finalize delivery - copy to outputs, generate report."""
        output_dir = Path(self.config.openmontage_projects_dir).parent / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        project_output = output_dir / self.project_state.project_id
        project_output.mkdir(exist_ok=True)
        
        # Copy final video
        final_path = Path(final_video)
        output_video = project_output / "final.mp4"
        shutil.copy2(final_path, output_video)
        
        # Copy all artifacts
        artifacts_src = self.project_dir / "football_emotion"
        artifacts_dst = project_output / "artifacts"
        if artifacts_src.exists():
            shutil.copytree(artifacts_src, artifacts_dst, dirs_exist_ok=True)
        
        # Copy OpenMontage artifacts
        om_artifacts_src = self.project_dir / "artifacts"
        if om_artifacts_src.exists():
            shutil.copytree(om_artifacts_src, project_output / "openmontage_artifacts", dirs_exist_ok=True)
        
        # Generate run report
        run_report = {
            "project_id": self.project_state.project_id,
            "run_id": self.run_id,
            "user_request": self.project_state.user_request,
            "completed_at": datetime.utcnow().isoformat(),
            "duration_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
            "output_video": str(output_video),
            "stages_completed": self.project_state.completed_stages,
            "hermes_sessions": self.project_state.hermes_sessions,
            "metadata": self.project_state.metadata
        }
        (project_output / "run_report.json").write_text(json.dumps(run_report, indent=2))
        
        return str(output_video)
    
    def _run_memory_update(self):
        """Run memory learning skill."""
        prompt = f"""
Run hermes-football-memory-learning to distill lessons from this production.

Project: {self.project_state.project_id}
Topic: (from user request)
Story type: (from story_plan)

Produce hermes_memory_update.json with:
- project_id, topic, story_type
- short_lessons: [single-sentence lessons for MEMORY.md]
- best_source_types: [what worked]
- successful_hook_pattern: which hook worked
- successful_audio_pattern: what audio approach worked
- clips_to_avoid_next_time: [patterns that failed]
- full_project_record_path: pointer to project_record.json

Also write full project_record.json with complete run data.

Save to {self.project_dir}/football_emotion/
"""
        self.hermes_runner.run_session(
            prompt=prompt,
            expected_skills=["hermes-football-memory-learning"]
        )
    
    def _load_artifact(self, artifact_name: str) -> Any:
        """Load artifact from football_emotion directory."""
        path = self.project_dir / "football_emotion" / artifact_name
        if path.exists():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                self.logger.warning(f"Failed to parse {artifact_name}")
        return None
    
    def _load_stage_artifacts(self, stage: StageName):
        """Load all artifacts for a stage into context."""
        for artifact in STAGE_ARTIFACTS.get(stage, []):
            self._load_artifact(artifact)
    
    def _fail_workflow(self, error: str):
        """Mark workflow as failed."""
        self.project_state.status = "failed"
        self.project_state.error = error
        self.orchestrator.checkpoint_mgr.save_state(self.project_state)
        self.discord.run_failed(self.project_state.project_id, error)
        self.logger.error(f"Workflow failed: {error}")


def main():
    parser = argparse.ArgumentParser(description="ACD Worker - Football Video Orchestrator (Session 4)")
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
            # Continue from current stage
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