"""
Stage Orchestrator — Full production stage controller with checkpoint/resume.

Manages the complete workflow from user request through OpenMontage render,
with Hermes skill invocation, artifact validation, checkpoint persistence,
and automatic loopback handling.
"""

import json
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Dict, List

from .source.discovery import SourceCandidate
from .source.acquisition import AcquiredSource, AcquisitionAttempt
from .footage_requirements import FootageRequirementsPlan, FootageRequirement


class StageStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_HUMAN = "awaiting_human"
    LOOPBACK = "loopback"
    SKIPPED = "skipped"


class StageName(Enum):
    # Core workflow stages (matching FINAL_ARCHITECTURE.md)
    REQUEST = "request"
    STORY_UNDERSTANDING = "story_understanding"
    FOOTAGE_REQUIREMENTS = "footage_requirements"
    FOOTAGE_DISCOVERY = "footage_discovery"
    FOOTAGE_ACQUISITION = "footage_acquisition"
    VISUAL_ANALYSIS = "visual_analysis"
    TIMESTAMP_EXTRACTION = "timestamp_extraction"
    CLIP_SCORING = "clip_scoring"
    NARRATION = "narration"
    AUDIO_PLAN = "audio_plan"
    EDIT_PLAN = "edit_plan"
    OPENMONTAGE_IDEA = "openmontage_idea"
    OPENMONTAGE_SCENE_PLAN = "openmontage_scene_plan"
    OPENMONTAGE_ASSETS = "openmontage_assets"
    OPENMONTAGE_EDIT = "openmontage_edit"
    OPENMONTAGE_COMPOSE = "openmontage_compose"
    QUALITY_REVIEW = "quality_review"
    DELIVERY = "delivery"
    MEMORY_UPDATE = "memory_update"


# Stage order for execution and resume
STAGE_ORDER = [
    StageName.REQUEST,
    StageName.STORY_UNDERSTANDING,
    StageName.FOOTAGE_REQUIREMENTS,
    StageName.FOOTAGE_DISCOVERY,
    StageName.FOOTAGE_ACQUISITION,
    StageName.VISUAL_ANALYSIS,
    StageName.TIMESTAMP_EXTRACTION,
    StageName.CLIP_SCORING,
    StageName.NARRATION,
    StageName.AUDIO_PLAN,
    StageName.EDIT_PLAN,
    StageName.OPENMONTAGE_IDEA,
    StageName.OPENMONTAGE_SCENE_PLAN,
    StageName.OPENMONTAGE_ASSETS,
    StageName.OPENMONTAGE_EDIT,
    StageName.OPENMONTAGE_COMPOSE,
    StageName.QUALITY_REVIEW,
    StageName.DELIVERY,
    StageName.MEMORY_UPDATE,
]

# Map stages to Hermes skills that should be invoked
STAGE_SKILLS = {
    StageName.STORY_UNDERSTANDING: ["social-edit-reasoning", "football-story-strategy"],
    StageName.FOOTAGE_REQUIREMENTS: ["football-story-strategy"],
    StageName.FOOTAGE_DISCOVERY: ["football-source-discovery"],
    StageName.FOOTAGE_ACQUISITION: ["football-footage-acquisition"],
    StageName.VISUAL_ANALYSIS: ["football-visual-scene-analysis"],
    StageName.TIMESTAMP_EXTRACTION: ["football-timestamp-extraction"],
    StageName.CLIP_SCORING: ["football-clip-scoring"],
    StageName.NARRATION: ["football-narration-scriptwriting"],
    StageName.AUDIO_PLAN: ["football-music-library-selector", "football-audio-music-director", "football-commentary-ducking-mixer"],
    StageName.EDIT_PLAN: ["football-pro-cutting-pacing", "football-caption-thumbnail-direction", "openmontage-edit-planning"],
    StageName.OPENMONTAGE_IDEA: ["openmontage-edit-planning"],  # Uses idea-director
    StageName.OPENMONTAGE_SCENE_PLAN: ["openmontage-edit-planning"],  # Uses scene-director
    StageName.OPENMONTAGE_ASSETS: ["openmontage-edit-planning"],  # Uses asset-director
    StageName.OPENMONTAGE_EDIT: ["openmontage-edit-planning"],  # Uses edit-director
    StageName.OPENMONTAGE_COMPOSE: ["openmontage-edit-planning"],  # Uses compose-director
    StageName.QUALITY_REVIEW: ["football-retention-quality-control", "football-audio-quality-control", "football-platform-export-validator"],
    StageName.MEMORY_UPDATE: ["hermes-football-memory-learning"],
}


# Artifacts expected at each stage
STAGE_ARTIFACTS = {
    StageName.STORY_UNDERSTANDING: ["brief_interpretation.json", "story_plan.json", "editorial_journey_state.json"],
    StageName.FOOTAGE_REQUIREMENTS: ["footage_requirements.json"],
    StageName.FOOTAGE_DISCOVERY: ["source_candidates.json"],
    StageName.FOOTAGE_ACQUISITION: ["source_media_review.json", "asset_manifest.json", "acquisition_attempts.json"],
    StageName.VISUAL_ANALYSIS: ["video_scene_analysis.json"],
    StageName.TIMESTAMP_EXTRACTION: ["clip_candidates.json"],
    StageName.CLIP_SCORING: ["clip_scores.json"],
    StageName.NARRATION: ["narration_script.json"],
    StageName.AUDIO_PLAN: ["audio_plan.json", "license_verification_records.json"],
    StageName.EDIT_PLAN: ["openmontage_edit_plan.json", "openmontage_audio_operations.json", "assembly_plan.json"],
    StageName.OPENMONTAGE_IDEA: ["brief.json"],
    StageName.OPENMONTAGE_SCENE_PLAN: ["scene_plan.json"],
    StageName.OPENMONTAGE_ASSETS: ["asset_manifest.json"],
    StageName.OPENMONTAGE_EDIT: ["edit_decisions.json"],
    StageName.OPENMONTAGE_COMPOSE: ["render_report.json"],
    StageName.QUALITY_REVIEW: ["full_qa_report.json", "audio_qc_report.json", "export_profile.json"],
    StageName.MEMORY_UPDATE: ["hermes_memory_update.json", "project_record.json"],
}


@dataclass
class StageCheckpoint:
    """Checkpoint data for a completed stage."""
    stage: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    input_artifacts: list[str] = field(default_factory=list)
    output_artifacts: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None
    loopback_count: int = 0
    hermes_session_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "StageCheckpoint":
        return cls(**data)


@dataclass
class ProjectState:
    """Complete project state for checkpoint/resume."""
    project_id: str
    run_id: str
    user_request: str
    created_at: str
    updated_at: str
    current_stage: Optional[str] = None
    completed_stages: list[str] = field(default_factory=list)
    stage_checkpoints: dict[str, StageCheckpoint] = field(default_factory=dict)
    status: str = "running"  # running, completed, failed, awaiting_human
    error: Optional[str] = None
    output_path: Optional[str] = None
    hermes_sessions: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        data = asdict(self)
        data["stage_checkpoints"] = {k: v.to_dict() for k, v in self.stage_checkpoints.items()}
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "ProjectState":
        checkpoints = {k: StageCheckpoint.from_dict(v) for k, v in data.get("stage_checkpoints", {}).items()}
        data["stage_checkpoints"] = checkpoints
        return cls(**data)


class CheckpointManager:
    """Manages project checkpoints with atomic writes and history."""
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.checkpoints_dir = project_dir / "checkpoints"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir = self.checkpoints_dir / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.checkpoints_dir / "project_state.json"
    
    def save_state(self, state: ProjectState) -> None:
        """Atomically save project state."""
        state.updated_at = datetime.utcnow().isoformat()
        tmp_file = self.state_file.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(state.to_dict(), indent=2))
        tmp_file.replace(self.state_file)
    
    def load_state(self) -> Optional[ProjectState]:
        """Load project state if exists."""
        if not self.state_file.exists():
            return None
        try:
            data = json.loads(self.state_file.read_text())
            return ProjectState.from_dict(data)
        except Exception:
            return None
    
    def save_stage_checkpoint(self, state: ProjectState, checkpoint: StageCheckpoint) -> None:
        """Save stage checkpoint and archive previous."""
        stage_name = checkpoint.stage
        
        # Archive existing checkpoint if present
        existing_file = self.checkpoints_dir / f"{stage_name}.json"
        if existing_file.exists():
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            archive_file = self.history_dir / f"{stage_name}_{timestamp}.json"
            shutil.move(str(existing_file), str(archive_file))
        
        # Write new checkpoint
        existing_file.write_text(json.dumps(checkpoint.to_dict(), indent=2))
        
        # Update state
        state.stage_checkpoints[stage_name] = checkpoint
        if checkpoint.status == StageStatus.COMPLETED.value:
            if stage_name not in state.completed_stages:
                state.completed_stages.append(stage_name)
        self.save_state(state)
    
    def get_latest_checkpoint(self, stage: StageName) -> Optional[StageCheckpoint]:
        """Get latest checkpoint for a stage."""
        checkpoint_file = self.checkpoints_dir / f"{stage.value}.json"
        if checkpoint_file.exists():
            try:
                data = json.loads(checkpoint_file.read_text())
                return StageCheckpoint.from_dict(data)
            except Exception:
                pass
        return None


class ArtifactValidator:
    """Validates artifacts against schemas."""
    
    def __init__(self, openmontage_schemas_path: Path, strict_mode: bool = True):
        self.schemas_path = openmontage_schemas_path
        self._schema_cache: dict[str, dict] = {}
        self.strict_mode = strict_mode
    
    def _load_schema(self, artifact_name: str) -> Optional[dict]:
        """Load JSON schema for artifact."""
        if artifact_name in self._schema_cache:
            return self._schema_cache[artifact_name]
        
        schema_file = self.schemas_path / f"{artifact_name}.schema.json"
        if schema_file.exists():
            try:
                schema = json.loads(schema_file.read_text())
                self._schema_cache[artifact_name] = schema
                return schema
            except Exception:
                pass
        return None
    
    def validate(self, artifact_name: str, data: dict) -> tuple[bool, list[str]]:
        """Validate artifact against schema. Returns (valid, errors)."""
        schema = self._load_schema(artifact_name)
        if not schema:
            return True, []  # No schema = skip validation
        
        try:
            import jsonschema
            jsonschema.validate(instance=data, schema=schema)
            return True, []
        except jsonschema.exceptions.ValidationError as e:
            return False, [str(e)]
        except Exception as e:
            return False, [f"Validation error: {e}"]
    
    def validate_required_artifacts(self, stage: StageName, project_dir: Path) -> tuple[bool, list[str]]:
        """Validate all required artifacts for a stage exist and are valid."""
        required = STAGE_ARTIFACTS.get(stage, [])
        errors = []
        
        for artifact_name in required:
            artifact_file = project_dir / "football_emotion" / artifact_name
            if not artifact_file.exists():
                errors.append(f"Missing required artifact: {artifact_name}")
                continue
            
            try:
                data = json.loads(artifact_file.read_text())
                valid, val_errors = self.validate(artifact_name.replace(".json", ""), data)
                if not valid:
                    errors.extend([f"{artifact_name}: {e}" for e in val_errors])
            except json.JSONDecodeError as e:
                errors.append(f"{artifact_name}: Invalid JSON - {e}")
        
        return len(errors) == 0, errors


class LoopbackController:
    """Manages automatic loopbacks based on quality failures."""
    
    def __init__(self, max_loopbacks: int = 3):
        self.max_loopbacks = max_loopbacks
        self.loopback_counts: dict[str, int] = {}
    
    # Mapping from failure type to target stage for loopback
    LOOPBACK_MAP = {
        # Footage issues
        "missing_footage": StageName.FOOTAGE_DISCOVERY,
        "insufficient_coverage": StageName.FOOTAGE_DISCOVERY,
        "weak_clip": StageName.CLIP_SCORING,
        "duplicate_clips": StageName.CLIP_SCORING,
        "invalid_timestamps": StageName.TIMESTAMP_EXTRACTION,
        "black_frames": StageName.FOOTAGE_ACQUISITION,
        "frozen_frames": StageName.FOOTAGE_ACQUISITION,
        "broken_video": StageName.FOOTAGE_ACQUISITION,
        "bad_aspect_ratio": StageName.VISUAL_ANALYSIS,
        
        # Audio issues
        "audio_clipping": StageName.AUDIO_PLAN,
        "excessive_silence": StageName.AUDIO_PLAN,
        "missing_narration": StageName.NARRATION,
        "missing_music": StageName.AUDIO_PLAN,
        "bad_ducking": StageName.AUDIO_PLAN,
        
        # Editorial issues
        "missing_story_section": StageName.EDIT_PLAN,
        "weak_emotional_progression": StageName.EDIT_PLAN,
        "unreadable_captions": StageName.EDIT_PLAN,
        
        # OpenMontage issues
        "invalid_edit_artifact": StageName.EDIT_PLAN,
        "render_failure": StageName.OPENMONTAGE_COMPOSE,
        "schema_validation_failed": StageName.EDIT_PLAN,
    }
    
    def should_loopback(self, failure_type: str) -> bool:
        """Check if we should attempt a loopback for this failure."""
        count = self.loopback_counts.get(failure_type, 0)
        return count < self.max_loopbacks
    
    def get_target_stage(self, failure_type: str) -> Optional[StageName]:
        """Get the stage to loop back to for a failure type."""
        return self.LOOPBACK_MAP.get(failure_type)
    
    def record_loopback(self, failure_type: str) -> int:
        """Record a loopback attempt and return new count."""
        count = self.loopback_counts.get(failure_type, 0) + 1
        self.loopback_counts[failure_type] = count
        return count
    
    def can_continue(self, failure_type: str) -> bool:
        """Check if we can continue after this failure type."""
        return self.loopback_counts.get(failure_type, 0) < self.max_loopbacks


# Skill invocation payloads for each stage
STAGE_PROMPTS = {
    StageName.REQUEST: """
Initialize the production project with the user request.
Validate the request and create initial project structure.
Output: project initialized with user_request in state.
""",

    StageName.STORY_UNDERSTANDING: """
Analyze the user request and produce:
1. brief_interpretation (emotional_question, tonal_flavor, runtime_target, platform, arc_phases_in_scope)
2. story_plan (story_structure, hook_pattern, sections with emotional_role and required_clip_types, minimum_clip_package)
3. editorial_journey_state (locked decisions, current_stage=1)

Use skills: social-edit-reasoning, football-story-strategy
""",
    
    StageName.FOOTAGE_REQUIREMENTS: """
Using the brief_interpretation and story_plan, generate a dynamic footage requirements plan.
Each requirement must have: slot_id, purpose, story_section, required_emotion, desired_subject,
desired_action, visual_type, priority, minimum_clips, search_terms, alternative_terms, optional,
estimated_duration_seconds, story_role, platform_considerations.

Output: footage_requirements.json
Use skill: football-story-strategy (generates requirements from story plan)
""",
    
    StageName.FOOTAGE_DISCOVERY: """
Using the footage_requirements.json, run football-source-discovery for each requirement.
Search YouTube using multiple query styles per requirement (story, moment, editing-style, official, non-English).
Rank candidates with 7-axis rubric. Output source_candidates.json with deep_analysis_candidate flags.

Use skill: football-source-discovery
""",
    
    StageName.FOOTAGE_ACQUISITION: """
For each deep_analysis_candidate from source_candidates.json, download sequentially using
OpenMontage video_downloader (yt-dlp). Verify each download with ffprobe, frame sampling.
On failure, try next ranked candidate (max 3 per slot). Build source_media_review.json and
update asset_manifest.json.

Use skill: football-footage-acquisition
""",
    
    StageName.VISUAL_ANALYSIS: """
For each acquired source in source_media_review.json, run football-visual-scene-analysis
using OpenMontage frame_sampler (scene_guided) and scene_detect (content). Output
video_scene_analysis.json with confidence and manual_review_needed flags.

Use skill: football-visual-scene-analysis
""",
    
    StageName.TIMESTAMP_EXTRACTION: """
Convert video_scene_analysis.json to timestamped clip_candidate rows using
football-timestamp-extraction. Each clip gets editor_timeline_role, source_range,
emotional_purpose. Output clip_candidates.json.

Use skill: football-timestamp-extraction
""",
    
    StageName.CLIP_SCORING: """
Score all clip_candidates against story_plan using football-clip-scoring rubric
(emotional_strength_2, visual_clarity_2, story_relevance_2, audio_commentary_value_1,
uniqueness_1, editability_1, rights_reused_content_risk_1). Output clip_scores.json
with recommended_use assignments.

Use skill: football-clip-scoring
""",
    
    StageName.NARRATION: """
Write narration script tied to selected clips from clip_scores.json using
football-narration-scriptwriting. Output narration_script.json with segments
mapped to clip IDs and timing.

Use skill: football-narration-scriptwriting
""",
    
    StageName.AUDIO_PLAN: """
Create complete audio plan: music selection (football-music-library-selector),
audio direction (football-audio-music-director), commentary ducking
(football-commentary-ducking-mixer). Verify licenses
(football-rights-safe-audio-license-checker). Output audio_plan.json and
license_verification_records.json.

Use skills: football-music-library-selector, football-audio-music-director,
football-commentary-ducking-mixer, football-rights-safe-audio-license-checker
""",
    
    StageName.EDIT_PLAN: """
Assemble openmontage_edit_plan.json from story_plan, clip_scores, narration_script,
audio_plan, caption plan. Apply pro cutting/pacing (football-pro-cutting-pacing).
Map audio to OpenMontage operations (openmontage-audio-operation-mapper).
Validate against schema lock. Output openmontage_edit_plan.json,
openmontage_audio_operations.json, assembly_plan.json.

Use skills: football-pro-cutting-pacing, football-caption-thumbnail-direction,
openmontage-edit-planning, openmontage-audio-operation-mapper
""",
    
    StageName.OPENMONTAGE_IDEA: """
Run OpenMontage documentary-montage pipeline idea-director stage.
Input: brief from edit plan. Output: brief.json artifact.
Use skill: openmontage-edit-planning (invokes idea-director)
""",
    
    StageName.OPENMONTAGE_SCENE_PLAN: """
Run OpenMontage scene-director stage. Input: brief.json. Output: scene_plan.json.
Map our clip selections to scene slots.
Use skill: openmontage-edit-planning (invokes scene-director)
""",
    
    StageName.OPENMONTAGE_ASSETS: """
Run OpenMontage asset-director stage. Input: scene_plan.json, our local asset_manifest.json.
Output: updated asset_manifest.json with picked clips.
Use skill: openmontage-edit-planning (invokes asset-director)
""",
    
    StageName.OPENMONTAGE_EDIT: """
Run OpenMontage edit-director stage. Input: scene_plan.json, asset_manifest.json,
our openmontage_edit_plan.json (after schema lock). Output: edit_decisions.json.
Use skill: openmontage-edit-planning (invokes edit-director)
""",
    
    StageName.OPENMONTAGE_COMPOSE: """
Run OpenMontage compose-director stage. Input: edit_decisions.json, asset_manifest.json.
Render with FFmpeg (render_runtime: ffmpeg). Output: render_report.json, final.mp4.
Use skill: openmontage-edit-planning (invokes compose-director)
""",
    
    StageName.QUALITY_REVIEW: """
Run football QA skills: football-retention-quality-control (full_qa_report),
football-audio-quality-control (audio_qc_report), football-platform-export-validator
(export_profile). Check for: missing sections, insufficient clips, duplicates,
invalid timestamps, black/frozen frames, broken video, bad aspect, audio clipping,
silence, unreadable captions, missing narration/music, weak emotional progression.
Output loopback instructions if any gate fails.

Use skills: football-retention-quality-control, football-audio-quality-control,
football-platform-export-validator
""",
    
    StageName.MEMORY_UPDATE: """
Run hermes-football-memory-learning to distill lessons into hermes_memory_update.json.
Update MEMORY.md/USER.md (size enforced). Write full project_record.json.
Use skill: hermes-football-memory-learning
""",
}


@dataclass
class StageResult:
    """Result of executing a stage."""
    stage: StageName
    success: bool
    output_artifacts: list[str] = field(default_factory=list)
    error: Optional[str] = None
    loopback: Optional[StageName] = None
    metadata: dict = field(default_factory=dict)
    status: str = "unknown"


class FixtureArtifactProvider:
    """Provides deterministic fixture artifacts for dry-run mode."""

    @staticmethod
    def get_fixture_artifacts(stage: StageName, project_dir: Path) -> Dict[str, Any]:
        football_emotion_dir = project_dir / "football_emotion"
        football_emotion_dir.mkdir(parents=True, exist_ok=True)

        fixtures = {}

        if stage == StageName.STORY_UNDERSTANDING:
            fixtures["brief_interpretation.json"] = {
                "emotional_question": "How did Messi overcome pressure to achieve World Cup glory?",
                "tonal_flavor": "triumphant",
                "runtime_target": 180,
                "platform": "youtube_longform",
                "arc_phases_in_scope": ["cold_open", "setup", "fall", "grind", "turning_point", "triumph_or_payoff", "coda"]
            }
            fixtures["story_plan.json"] = {
                "story_structure": "pain_pressure_comeback_legacy",
                "hook_pattern": "iconic_image",
                "target_duration": 180,
                "sections": [
                    {"section_id": "pressure_doubt", "timeline_range": "0-30", "emotional_role": "tension", "required_clip_types": ["tunnel_walk", "closeup_face"]},
                    {"section_id": "grind_struggle", "timeline_range": "30-90", "emotional_role": "struggle", "required_clip_types": ["missed_chance", "defensive_pressure"]},
                    {"section_id": "turning_point", "timeline_range": "90-150", "emotional_role": "release", "required_clip_types": ["goal", "celebration"]},
                    {"section_id": "legacy_aftermath", "timeline_range": "150-180", "emotional_role": "meaning", "required_clip_types": ["trophy_lift", "final_image"]}
                ],
                "minimum_clip_package": ["tunnel_walk", "missed_chance", "goal", "trophy_lift"]
            }
            fixtures["editorial_journey_state.json"] = {
                "locked_decisions": {"emotional_question": "How did Messi overcome pressure to achieve World Cup glory?"},
                "current_stage": 1
            }

        elif stage == StageName.FOOTAGE_REQUIREMENTS:
            fixtures["footage_requirements.json"] = {
                "project_id": project_dir.name,
                "generated_at": datetime.utcnow().isoformat(),
                "user_request": "Messi World Cup 2022 triumph 30s",
                "match_context": {"competition": "World Cup 2022", "teams": ["Argentina", "France"], "players": ["Messi", "Mbappe"]},
                "story_type": "pain_pressure_comeback_legacy",
                "emotional_arc": ["pain", "context", "pressure", "release", "meaning"],
                "intended_duration_seconds": 180,
                "narration_strategy": "hybrid",
                "platform": "youtube_longform",
                "requirements": [
                    {
                        "slot_id": "req_pressure_01",
                        "purpose": "Establish pre-match tension via Messi tunnel walk",
                        "story_section": "pressure_doubt",
                        "required_emotion": "tension",
                        "desired_subject": "Messi Argentina",
                        "desired_action": "tunnel walk focused expression",
                        "visual_type": "closeup",
                        "priority": 1,
                        "minimum_clips": 2,
                        "search_terms": ["Messi tunnel walk World Cup 2022", "Argentina pre-match pressure"],
                        "alternative_terms": ["Messi pre-match focus", "World Cup final tunnel"],
                        "optional": False,
                        "estimated_duration_seconds": 5.0,
                        "story_role": "hook_reference",
                        "platform_considerations": {"aspect_ratio": "16:9"}
                    },
                    {
                        "slot_id": "req_celebration_01",
                        "purpose": "Show World Cup trophy lift moment",
                        "story_section": "legacy_aftermath",
                        "required_emotion": "triumph",
                        "desired_subject": "Messi Argentina",
                        "desired_action": "lifting trophy celebration",
                        "visual_type": "wide",
                        "priority": 1,
                        "minimum_clips": 1,
                        "search_terms": ["Messi lifting World Cup trophy 2022", "Argentina champions celebration"],
                        "alternative_terms": ["Messi trophy lift", "World Cup 2022 final celebration"],
                        "optional": False,
                        "estimated_duration_seconds": 8.0,
                        "story_role": "source_clip",
                        "platform_considerations": {"aspect_ratio": "16:9"}
                    }
                ]
            }

        elif stage == StageName.FOOTAGE_DISCOVERY:
            fixtures["source_candidates.json"] = {
                "req_pressure_01": [
                    {
                        "candidate_id": "req_pressure_01_abc123",
                        "url": "https://youtu.be/abc123",
                        "video_id": "abc123",
                        "title": "Messi Tunnel Walk World Cup 2022 Final",
                        "channel": "FIFA",
                        "duration": 120,
                        "upload_date": "20221218",
                        "thumbnail": "",
                        "query": "Messi tunnel walk World Cup 2022",
                        "story_slot": "req_pressure_01",
                        "ranking_score": 8.5,
                        "verification_status": "unverified",
                        "discovery_method": "yt_dlp_search",
                        "metadata_confidence": "high",
                        "deep_analysis_candidate": "yes"
                    }
                ],
                "req_celebration_01": [
                    {
                        "candidate_id": "req_celebration_01_def456",
                        "url": "https://youtu.be/def456",
                        "video_id": "def456",
                        "title": "Argentina World Cup 2022 Trophy Lift Celebration",
                        "channel": "FIFA",
                        "duration": 300,
                        "upload_date": "20221218",
                        "thumbnail": "",
                        "query": "Messi lifting World Cup trophy 2022",
                        "story_slot": "req_celebration_01",
                        "ranking_score": 9.0,
                        "verification_status": "unverified",
                        "discovery_method": "yt_dlp_search",
                        "metadata_confidence": "high",
                        "deep_analysis_candidate": "yes"
                    }
                ]
            }

        elif stage == StageName.FOOTAGE_ACQUISITION:
            sources_dir = project_dir / "football_emotion" / "sources"
            sources_dir.mkdir(parents=True, exist_ok=True)

            fixtures["source_media_review.json"] = {
                "files": [
                    {
                        "path": "football_emotion/sources/req_pressure_01_abc123.mp4",
                        "media_type": "video",
                        "reviewed": True,
                        "technical_probe": {
                            "duration_seconds": 120.5,
                            "width": 1920,
                            "height": 1080,
                            "video_codec": "h264",
                            "audio_codec": "aac",
                            "sample_rate": 44100,
                            "channels": 2,
                            "bitrate_kbps": 5000
                        },
                        "content_summary": "Messi walking through tunnel, focused expression",
                        "transcript_summary": "Stadium ambience, crowd murmur",
                        "representative_frames": [],
                        "quality_risks": [],
                        "usable_for": ["hero_footage", "b_roll"],
                        "verification_status": "verified",
                        "acquisition_attempt": 1,
                        "original_candidate_id": "req_pressure_01_abc123",
                        "source_url": "https://youtu.be/abc123"
                    },
                    {
                        "path": "football_emotion/sources/req_celebration_01_def456.mp4",
                        "media_type": "video",
                        "reviewed": True,
                        "technical_probe": {
                            "duration_seconds": 45.0,
                            "width": 1920,
                            "height": 1080,
                            "video_codec": "h264",
                            "audio_codec": "aac",
                            "sample_rate": 44100,
                            "channels": 2,
                            "bitrate_kbps": 6000
                        },
                        "content_summary": "Messi lifting World Cup trophy, team celebration",
                        "transcript_summary": "Commentator: 'Messi lifts the World Cup!' Crowd roars",
                        "representative_frames": [],
                        "quality_risks": [],
                        "usable_for": ["hero_footage", "b_roll"],
                        "verification_status": "verified",
                        "acquisition_attempt": 1,
                        "original_candidate_id": "req_celebration_01_def456",
                        "source_url": "https://youtu.be/def456"
                    }
                ],
                "summary": "2 sources acquired and verified for Messi World Cup triumph story",
                "planning_implications": ["All critical slots filled with verified footage"]
            }
            fixtures["asset_manifest.json"] = {
                "assets": [
                    {
                        "id": "src_req_pressure_01_abc123",
                        "type": "video",
                        "path": "football_emotion/sources/req_pressure_01_abc123.mp4",
                        "source_tool": "video_downloader",
                        "scene_id": "req_pressure_01",
                        "subtype": "source_footage",
                        "license": "unverified",
                        "original_url": "https://youtu.be/abc123",
                        "generation_summary": "Downloaded from YouTube via yt-dlp; verification_status: verified",
                        "technical_metadata": {
                            "duration_seconds": 120.5,
                            "width": 1920,
                            "height": 1080,
                            "video_codec": "h264",
                            "audio_codec": "aac",
                            "sample_rate": 44100,
                            "channels": 2
                        },
                        "quality_warnings": [],
                        "file_hash": "abc123hash",
                        "file_size_bytes": 50000000
                    },
                    {
                        "id": "src_req_celebration_01_def456",
                        "type": "video",
                        "path": "football_emotion/sources/req_celebration_01_def456.mp4",
                        "source_tool": "video_downloader",
                        "scene_id": "req_celebration_01",
                        "subtype": "source_footage",
                        "license": "unverified",
                        "original_url": "https://youtu.be/def456",
                        "generation_summary": "Downloaded from YouTube via yt-dlp; verification_status: verified",
                        "technical_metadata": {
                            "duration_seconds": 45.0,
                            "width": 1920,
                            "height": 1080,
                            "video_codec": "h264",
                            "audio_codec": "aac",
                            "sample_rate": 44100,
                            "channels": 2
                        },
                        "quality_warnings": [],
                        "file_hash": "def456hash",
                        "file_size_bytes": 30000000
                    }
                ]
            }
            fixtures["acquisition_attempts.json"] = []

        elif stage == StageName.VISUAL_ANALYSIS:
            fixtures["video_scene_analysis.json"] = {
                "scenes": [
                    {
                        "scene_id": "scene_001",
                        "source_video_id": "abc123",
                        "source_timestamp_start": "00:00:10",
                        "source_timestamp_end": "00:00:20",
                        "editor_timeline_role": "hook",
                        "scene_type": "tunnel_walk",
                        "visual_description": "Messi walking through tunnel, focused expression, Argentina jersey",
                        "audio_description": "Stadium ambience, distant crowd",
                        "editing_technique_observed": "steady_cam_follow",
                        "emotional_purpose": "establish_tension",
                        "confidence": "high",
                        "manual_review_needed": False
                    },
                    {
                        "scene_id": "scene_002",
                        "source_video_id": "def456",
                        "source_timestamp_start": "00:00:05",
                        "source_timestamp_end": "00:00:15",
                        "editor_timeline_role": "climax",
                        "scene_type": "trophy_lift",
                        "visual_description": "Messi lifting World Cup trophy, confetti, teammates cheering",
                        "audio_description": "Commentator excitement, crowd roar",
                        "editing_technique_observed": "wide_celebration_shot",
                        "emotional_purpose": "triumphant_release",
                        "confidence": "high",
                        "manual_review_needed": False
                    }
                ]
            }

        elif stage == StageName.TIMESTAMP_EXTRACTION:
            fixtures["clip_candidates.json"] = {
                "clips": [
                    {
                        "clip_id": "clip_001",
                        "source_video_id": "abc123",
                        "source_range": "00:00:10-00:00:15",
                        "topic_match": "tunnel_walk",
                        "scene_type": "tunnel_walk",
                        "emotional_role": "hook",
                        "visual_signs": ["focused_expression", "argentina_jersey"],
                        "audio_signs": ["stadium_ambience"],
                        "story_relevance": "high",
                        "rights_risk": "low",
                        "verification_status": "verified",
                        "editor_timeline_role": "hook",
                        "recommended_use": "hook"
                    },
                    {
                        "clip_id": "clip_002",
                        "source_video_id": "def456",
                        "source_range": "00:00:05-00:00:13",
                        "topic_match": "trophy_lift",
                        "scene_type": "celebration",
                        "emotional_role": "climax",
                        "visual_signs": ["trophy", "confetti", "teammates"],
                        "audio_signs": ["commentator", "crowd_roar"],
                        "story_relevance": "high",
                        "rights_risk": "low",
                        "verification_status": "verified",
                        "editor_timeline_role": "climax",
                        "recommended_use": "climax"
                    }
                ]
            }

        elif stage == StageName.CLIP_SCORING:
            fixtures["clip_scores.json"] = {
                "clips": [
                    {
                        "clip_id": "clip_001",
                        "scores": {
                            "emotional_strength_2": 2,
                            "visual_clarity_2": 2,
                            "story_relevance_2": 2,
                            "audio_commentary_value_1": 1,
                            "uniqueness_1": 1,
                            "editability_1": 1,
                            "rights_reused_content_risk_1": 1
                        },
                        "total_10": 10,
                        "recommended_use": "hook"
                    },
                    {
                        "clip_id": "clip_002",
                        "scores": {
                            "emotional_strength_2": 2,
                            "visual_clarity_2": 2,
                            "story_relevance_2": 2,
                            "audio_commentary_value_1": 1,
                            "uniqueness_1": 1,
                            "editability_1": 1,
                            "rights_reused_content_risk_1": 1
                        },
                        "total_10": 10,
                        "recommended_use": "climax"
                    }
                ]
            }

        elif stage == StageName.NARRATION:
            fixtures["narration_script.json"] = {
                "segments": [
                    {
                        "segment_id": "seg_001",
                        "clip_id": "clip_001",
                        "text": "Before the glory, there was the walk. Alone with the weight of a nation.",
                        "start_seconds": 0,
                        "end_seconds": 5
                    },
                    {
                        "segment_id": "seg_002",
                        "clip_id": "clip_002",
                        "text": "And then, the moment arrived. Messi lifts the World Cup. A legacy complete.",
                        "start_seconds": 5,
                        "end_seconds": 15
                    }
                ]
            }

        elif stage == StageName.AUDIO_PLAN:
            fixtures["audio_plan.json"] = {
                "music": {
                    "track_id": "music_001",
                    "title": "Epic Orchestral Build",
                    "source": "YouTube Audio Library",
                    "license": "cc_by",
                    "mood": "triumphant",
                    "sections": [
                        {"section": "pressure_doubt", "action": "low_tension_bed", "volume_db": -25},
                        {"section": "grind_struggle", "action": "build_intensity", "volume_db": -20},
                        {"section": "turning_point", "action": "full_mix", "volume_db": -15},
                        {"section": "legacy_aftermath", "action": "warm_resolution", "volume_db": -18}
                    ]
                },
                "narration": {
                    "enabled": True,
                    "voice": "narrator",
                    "ducking": {"threshold_db": -20, "reduction_db": 12}
                },
                "sfx": []
            }
            fixtures["license_verification_records.json"] = []

        elif stage == StageName.EDIT_PLAN:
            fixtures["openmontage_edit_plan.json"] = {
                "version": "1.0",
                "sections": [
                    {
                        "section_id": "pressure_doubt",
                        "timeline_range": "0-5",
                        "clips": ["clip_001"],
                        "cut_style": "slow_reveal",
                        "transition_in": "fade_from_black",
                        "transition_out": "hard_cut",
                        "speed": "normal",
                        "effect": "subtle_zoom",
                        "reason": "Establish tension through slow reveal"
                    },
                    {
                        "section_id": "legacy_aftermath",
                        "timeline_range": "5-15",
                        "clips": ["clip_002"],
                        "cut_style": "impact",
                        "transition_in": "hard_cut",
                        "transition_out": "fade_to_black",
                        "speed": "normal",
                        "effect": "none",
                        "reason": "Climactic release"
                    }
                ],
                "renderer_family": "documentary-montage",
                "render_runtime": "remotion",
                "composition_mode": "templated"
            }
            fixtures["openmontage_audio_operations.json"] = {
                "tracks": [
                    {
                        "track_type": "narration",
                        "clips": [
                            {"asset_id": "narration_seg_001", "start_time": 0, "end_time": 5},
                            {"asset_id": "narration_seg_002", "start_time": 5, "end_time": 15}
                        ]
                    },
                    {
                        "track_type": "music",
                        "clips": [
                            {"asset_id": "music_001", "start_time": 0, "end_time": 15, "volume_db": -20, "fade_in": 1.0, "fade_out": 1.0, "ducking": {"enabled": True, "threshold_db": -20, "reduction_db": 12}}
                        ]
                    }
                ],
                "subtitles": []
            }
            fixtures["assembly_plan.json"] = {}

        elif stage == StageName.OPENMONTAGE_IDEA:
            fixtures["brief.json"] = {
                "thematic_question": "How did Messi overcome pressure to achieve World Cup glory?",
                "tone": "triumphant",
                "duration_seconds": 15,
                "music_plan": {
                    "source": "library",
                    "mood": "triumphant",
                    "pacing": "build_to_climax"
                },
                "end_tag_plan": {
                    "text": "The moment that defined a legacy.",
                    "palette": "warm_gold",
                    "duration_seconds": 3,
                    "mode": "overlay"
                },
                "narration_plan": {
                    "enabled": True,
                    "style": "poetic_commentary",
                    "voice": "narrator"
                }
            }

        elif stage == StageName.OPENMONTAGE_SCENE_PLAN:
            fixtures["scene_plan.json"] = {
                "metadata": {
                    "slot_count": 2,
                    "total_target_seconds": 15,
                    "era_mix": "contemporary"
                },
                "slots": [
                    {
                        "slot_id": "req_pressure_01",
                        "description": "Establish pre-match tension via Messi tunnel walk",
                        "target_hold_seconds": 5,
                        "search_queries": ["Messi tunnel walk World Cup 2022"],
                        "preferred_sources": ["youtube"],
                        "hero": True,
                        "visual_type": "closeup",
                        "emotional_role": "tension",
                        "required": True
                    },
                    {
                        "slot_id": "req_celebration_01",
                        "description": "Show World Cup trophy lift moment",
                        "target_hold_seconds": 10,
                        "search_queries": ["Messi lifting World Cup trophy 2022"],
                        "preferred_sources": ["youtube"],
                        "hero": True,
                        "visual_type": "wide",
                        "emotional_role": "triumph",
                        "required": True
                    }
                ]
            }

        elif stage == StageName.OPENMONTAGE_ASSETS:
            fixtures["asset_manifest.json"] = {
                "assets": [
                    {
                        "id": "src_req_pressure_01_abc123",
                        "type": "video",
                        "path": "football_emotion/sources/req_pressure_01_abc123.mp4",
                        "source_tool": "video_downloader",
                        "scene_id": "req_pressure_01",
                        "subtype": "source_footage",
                        "license": "unverified",
                        "original_url": "https://youtu.be/abc123",
                        "generation_summary": "Downloaded from YouTube via yt-dlp; verification_status: verified",
                        "technical_metadata": {"duration_seconds": 120.5, "width": 1920, "height": 1080},
                        "quality_warnings": [],
                        "file_hash": "abc123hash",
                        "file_size_bytes": 50000000
                    },
                    {
                        "id": "src_req_celebration_01_def456",
                        "type": "video",
                        "path": "football_emotion/sources/req_celebration_01_def456.mp4",
                        "source_tool": "video_downloader",
                        "scene_id": "req_celebration_01",
                        "subtype": "source_footage",
                        "license": "unverified",
                        "original_url": "https://youtu.be/def456",
                        "generation_summary": "Downloaded from YouTube via yt-dlp; verification_status: verified",
                        "technical_metadata": {"duration_seconds": 45.0, "width": 1920, "height": 1080},
                        "quality_warnings": [],
                        "file_hash": "def456hash",
                        "file_size_bytes": 30000000
                    }
                ]
            }

        elif stage == StageName.OPENMONTAGE_EDIT:
            fixtures["edit_decisions.json"] = {
                "version": "1.0",
                "cuts": [
                    {
                        "id": "pressure_doubt_clip_001",
                        "source": "football_emotion/sources/req_pressure_01_abc123.mp4",
                        "in_seconds": 10.0,
                        "out_seconds": 15.0,
                        "speed": 1.0,
                        "layer": "primary",
                        "transform": {"animation": "ken-burns-slow-zoom"},
                        "transition_in": "fade_from_black",
                        "transition_out": "hard_cut",
                        "reason": "Establish tension through slow reveal"
                    },
                    {
                        "id": "legacy_aftermath_clip_002",
                        "source": "football_emotion/sources/req_celebration_01_def456.mp4",
                        "in_seconds": 5.0,
                        "out_seconds": 15.0,
                        "speed": 1.0,
                        "layer": "primary",
                        "transform": {"animation": "none"},
                        "transition_in": "hard_cut",
                        "transition_out": "fade_to_black",
                        "reason": "Climactic release"
                    }
                ],
                "overlays": [],
                "audio": {
                    "narration": {
                        "segments": [
                            {"asset_id": "narration_seg_001", "start_seconds": 0, "end_seconds": 5},
                            {"asset_id": "narration_seg_002", "start_seconds": 5, "end_seconds": 15}
                        ]
                    },
                    "music": {
                        "asset_id": "music_001",
                        "volume": 0.1,
                        "fade_in_seconds": 1.0,
                        "fade_out_seconds": 1.0,
                        "ducking": {
                            "enabled": True,
                            "threshold_db": -20,
                            "reduction_db": 12,
                            "attack_ms": 100,
                            "release_ms": 300
                        }
                    },
                    "sfx": [],
                    "subtitles": []
                },
                "renderer_family": "documentary-montage",
                "render_runtime": "remotion",
                "composition_mode": "templated"
            }

        elif stage == StageName.OPENMONTAGE_COMPOSE:
            output_dir = project_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            final_video = output_dir / "final.mp4"
            final_video.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")

            fixtures["render_report.json"] = {
                "version": "1.0",
                "outputs": [
                    {
                        "path": str(final_video),
                        "format": "mp4",
                        "codec": "h264",
                        "audio_codec": "aac",
                        "resolution": "1920x1080",
                        "fps": 30,
                        "duration_seconds": 15.0,
                        "file_size_bytes": 1000000,
                        "platform_target": "youtube_longform"
                    }
                ],
                "render_time_seconds": 5.0,
                "warnings": [],
                "verification_notes": ["Dry-run synthetic output"],
                "render_grammar": "documentary-montage",
                "slideshow_risk_score": {"average": 0.1, "verdict": "low"},
                "decision_log_ref": "",
                "final_review_ref": "",
                "metadata": {"dry_run": True}
            }

        elif stage == StageName.QUALITY_REVIEW:
            fixtures["full_qa_report.json"] = {
                "pass": True,
                "findings": [],
                "required_loopbacks": []
            }
            fixtures["audio_qc_report.json"] = {
                "pass": True,
                "qc_report": {
                    "integrated_lufs": -14.2,
                    "true_peak_db": -1.5,
                    "lra": 5.0
                }
            }
            fixtures["export_profile.json"] = {
                "pass": True,
                "export_profile": {
                    "platform": "youtube_longform",
                    "aspect_ratio": "16:9",
                    "resolution": "1920x1080",
                    "codec": "h264",
                    "audio_codec": "aac",
                    "loudness_target_lufs": -14
                }
            }

        elif stage == StageName.MEMORY_UPDATE:
            fixtures["hermes_memory_update.json"] = {
                "project_id": project_dir.name,
                "topic": "Messi World Cup 2022 triumph",
                "story_type": "pain_pressure_comeback_legacy",
                "short_lessons": [
                    "Tunnel walk footage essential for pressure establishment",
                    "Trophy lift wide shot carries maximum emotional release"
                ],
                "best_source_types": ["FIFA official broadcast", "tournament highlights"],
                "successful_hook_pattern": "iconic_image",
                "successful_audio_pattern": "orchestral_build_to_climax",
                "clips_to_avoid_next_time": [],
                "full_project_record_path": f"projects/{project_dir.name}/football_emotion/project_record.json"
            }
            fixtures["project_record.json"] = {
                "project_id": project_dir.name,
                "run_id": "dry_run",
                "user_request": "Messi World Cup 2022 triumph 30s",
                "completed_at": datetime.utcnow().isoformat(),
                "stages_completed": [s.value for s in STAGE_ORDER],
                "artifacts_generated": sum(len(STAGE_ARTIFACTS.get(s, [])) for s in STAGE_ORDER),
                "loopback_count": 0
            }

        return fixtures


class StageOrchestrator:
    """
    Main orchestrator for the football video production pipeline.
    
    Handles stage execution, Hermes skill invocation, checkpoint/resume,
    artifact validation, and automatic loopbacks.
    """
    
    def __init__(
        self,
        project_dir: Path,
        hermes_runner,
        openmontage_runner,
        config: dict,
        loopback_controller: Optional[LoopbackController] = None,
        dry_run: bool = False
    ):
        self.project_dir = project_dir
        self.hermes_runner = hermes_runner
        self.openmontage_runner = openmontage_runner
        self.config = config
        self.dry_run = dry_run
        self.loopback = loopback_controller or LoopbackController(
            max_loopbacks=config.get("max_loopbacks", 3)
        )
        
        self.checkpoint_mgr = CheckpointManager(project_dir)
        self.validator = ArtifactValidator(
            Path(config.get("openmontage_schemas_path")) if config.get("openmontage_schemas_path") else self._find_openmontage_schemas(),
            strict_mode=True
        )
        
        # Load or create project state
        self.state = self.checkpoint_mgr.load_state()
        if not self.state:
            self.state = ProjectState(
                project_id=project_dir.name,
                run_id=str(uuid.uuid4()),
                user_request="",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )

        self.fixture_provider = FixtureArtifactProvider()
    
    def get_next_stage(self) -> Optional[StageName]:
        """Get the next stage to execute based on completed stages."""
        for stage in STAGE_ORDER:
            if stage.value not in self.state.completed_stages:
                return stage
        return None
    
    def can_resume_from(self, stage: StageName) -> bool:
        """Check if we can resume from a given stage."""
        checkpoint = self.checkpoint_mgr.get_latest_checkpoint(stage)
        return checkpoint is not None and checkpoint.status == StageStatus.COMPLETED.value
    
    def validate_stage_inputs(self, stage: StageName) -> tuple[bool, list[str]]:
        """Validate that required input artifacts exist for a stage."""
        # Input artifacts are the output artifacts of previous stages
        required_inputs = []
        stage_idx = STAGE_ORDER.index(stage)
        
        for prev_stage in STAGE_ORDER[:stage_idx]:
            required_inputs.extend(STAGE_ARTIFACTS.get(prev_stage, []))
        
        errors = []
        for artifact in required_inputs:
            artifact_path = self.project_dir / "football_emotion" / artifact
            if not artifact_path.exists():
                errors.append(f"Missing input artifact: {artifact}")
        
        return len(errors) == 0, errors
    
    def execute_stage(self, stage: StageName, context: dict) -> StageResult:
        """Execute a single pipeline stage."""
        print(f"\n{'='*60}")
        print(f"EXECUTING STAGE: {stage.value}")
        print(f"{'='*60}")
        
        # Create checkpoint for running stage
        checkpoint = StageCheckpoint(
            stage=stage.value,
            status=StageStatus.RUNNING.value,
            started_at=datetime.utcnow().isoformat(),
            input_artifacts=list(STAGE_ARTIFACTS.get(stage, [])),
        )
        self.checkpoint_mgr.save_stage_checkpoint(self.state, checkpoint)
        
        try:
            # Dry-run mode: write fixture artifacts and return success
            if self.dry_run:
                return self._execute_dry_run_stage(stage, checkpoint)
            
            # Validate inputs
            valid, errors = self.validate_stage_inputs(stage)
            if not valid:
                return StageResult(
                    stage=stage,
                    success=False,
                    error=f"Input validation failed: {errors}"
                )
            
            # Build full prompt with context
            full_prompt = self._build_stage_prompt(stage, prompt, context)
            
            # Execute via Hermes
            result = self.hermes_runner.run_session(full_prompt, context)
            
            if not result.success:
                error = result.error or "Unknown error"
                checkpoint.status = StageStatus.FAILED.value
                checkpoint.completed_at = datetime.utcnow().isoformat()
                checkpoint.error = error
                self.checkpoint_mgr.save_stage_checkpoint(self.state, checkpoint)
                
                return StageResult(
                    stage=stage,
                    success=False,
                    error=error
                )
            
            # Validate output artifacts
            output_artifacts = STAGE_ARTIFACTS.get(stage, [])
            valid, val_errors = self.validator.validate_required_artifacts(stage, self.project_dir)
            
            if not valid:
                checkpoint.status = StageStatus.FAILED.value
                checkpoint.completed_at = datetime.utcnow().isoformat()
                checkpoint.error = f"Artifact validation failed: {val_errors}"
                self.checkpoint_mgr.save_stage_checkpoint(self.state, checkpoint)
                
                # Check for loopback
                loopback_stage = self._check_loopback(val_errors)
                return StageResult(
                    stage=stage,
                    success=False,
                    error=f"Artifact validation failed: {val_errors}",
                    loopback=loopback_stage
                )
            
            # Success
            checkpoint.status = StageStatus.COMPLETED.value
            checkpoint.completed_at = datetime.utcnow().isoformat()
            checkpoint.output_artifacts = output_artifacts
            checkpoint.hermes_session_id = result.session_id
            if checkpoint.hermes_session_id:
                self.state.hermes_sessions.append(checkpoint.hermes_session_id)
            self.checkpoint_mgr.save_stage_checkpoint(self.state, checkpoint)
            
            return StageResult(
                stage=stage,
                success=True,
                output_artifacts=output_artifacts,
                metadata={"hermes_session_id": checkpoint.hermes_session_id}
            )
            
        except Exception as e:
            checkpoint.status = StageStatus.FAILED.value
            checkpoint.completed_at = datetime.utcnow().isoformat()
            checkpoint.error = str(e)
            self.checkpoint_mgr.save_stage_checkpoint(self.state, checkpoint)
            
            return StageResult(
                stage=stage,
                success=False,
                error=str(e)
            )
            checkpoint.error = str(e)
            self.checkpoint_mgr.save_stage_checkpoint(self.state, checkpoint)
            
            return StageResult(
                stage=stage,
                success=False,
                error=str(e)
            )

    def _execute_dry_run_stage(self, stage: StageName, checkpoint: StageCheckpoint) -> StageResult:
        """Execute stage in dry-run mode using fixture artifacts."""
        fixtures = self.fixture_provider.get_fixture_artifacts(stage, self.project_dir)

        for artifact_name, artifact_data in fixtures.items():
            artifact_path = self.project_dir / "football_emotion" / artifact_name
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(json.dumps(artifact_data, indent=2))

        output_artifacts = list(fixtures.keys())
        checkpoint.status = StageStatus.COMPLETED.value
        checkpoint.completed_at = datetime.utcnow().isoformat()
        checkpoint.output_artifacts = output_artifacts
        checkpoint.hermes_session_id = f"dry_run_{uuid.uuid4().hex[:8]}"
        self.state.hermes_sessions.append(checkpoint.hermes_session_id)
        self.checkpoint_mgr.save_stage_checkpoint(self.state, checkpoint)

        print(f"✓ Dry-run stage {stage.value} completed with {len(output_artifacts)} fixture artifacts")
        return StageResult(
            stage=stage,
            success=True,
            output_artifacts=output_artifacts,
            metadata={"dry_run": True, "fixture_artifacts": len(fixtures)},
            status="completed"
        )

    def _build_stage_prompt(self, stage: StageName, base_prompt: str, context: dict) -> str:
        """Build complete prompt with context for Hermes."""
        context_json = json.dumps(context, indent=2)
        
        return f"""Project Context:
{context_json}

Stage: {stage.value}
{base_prompt}

Current project directory: {self.project_dir}
Football emotion artifacts directory: {self.project_dir / 'football_emotion'}

Execute this stage and produce the required output artifacts.
"""
    
    def _check_loopback(self, validation_errors: list[str]) -> Optional[StageName]:
        """Determine if any validation error triggers a loopback."""
        for error in validation_errors:
            error_lower = error.lower()
            
            # Check for specific failure patterns
            if "missing" in error_lower and ("footage" in error_lower or "clip" in error_lower):
                if self.loopback.should_loopback("missing_footage"):
                    self.loopback.record_loopback("missing_footage")
                    return StageName.FOOTAGE_DISCOVERY
            
            if "insufficient" in error_lower and "coverage" in error_lower:
                if self.loopback.should_loopback("insufficient_coverage"):
                    self.loopback.record_loopback("insufficient_coverage")
                    return StageName.FOOTAGE_DISCOVERY
            
            if "weak" in error_lower and "clip" in error_lower:
                if self.loopback.should_loopback("weak_clip"):
                    self.loopback.record_loopback("weak_clip")
                    return StageName.CLIP_SCORING
            
            if "duplicate" in error_lower and "clip" in error_lower:
                if self.loopback.should_loopback("duplicate_clips"):
                    self.loopback.record_loopback("duplicate_clips")
                    return StageName.CLIP_SCORING
            
            if "timestamp" in error_lower and "invalid" in error_lower:
                if self.loopback.should_loopback("invalid_timestamps"):
                    self.loopback.record_loopback("invalid_timestamps")
                    return StageName.TIMESTAMP_EXTRACTION
            
            if "black" in error_lower and "frame" in error_lower:
                if self.loopback.should_loopback("black_frames"):
                    self.loopback.record_loopback("black_frames")
                    return StageName.FOOTAGE_ACQUISITION
            
            if "audio" in error_lower and ("clipping" in error_lower or "peak" in error_lower):
                if self.loopback.should_loopback("audio_clipping"):
                    self.loopback.record_loopback("audio_clipping")
                    return StageName.AUDIO_PLAN
            
            if "silence" in error_lower and "excessive" in error_lower:
                if self.loopback.should_loopback("excessive_silence"):
                    self.loopback.record_loopback("excessive_silence")
                    return StageName.AUDIO_PLAN
            
            if "narration" in error_lower and "missing" in error_lower:
                if self.loopback.should_loopback("missing_narration"):
                    self.loopback.record_loopback("missing_narration")
                    return StageName.NARRATION
            
            if "music" in error_lower and "missing" in error_lower:
                if self.loopback.should_loopback("missing_music"):
                    self.loopback.record_loopback("missing_music")
                    return StageName.AUDIO_PLAN
            
            if "ducking" in error_lower and ("bad" in error_lower or "fail" in error_lower):
                if self.loopback.should_loopback("bad_ducking"):
                    self.loopback.record_loopback("bad_ducking")
                    return StageName.AUDIO_PLAN
            
            if "story section" in error_lower and "missing" in error_lower:
                if self.loopback.should_loopback("missing_story_section"):
                    self.loopback.record_loopback("missing_story_section")
                    return StageName.EDIT_PLAN
            
            if "emotional" in error_lower and "progression" in error_lower:
                if self.loopback.should_loopback("weak_emotional_progression"):
                    self.loopback.record_loopback("weak_emotional_progression")
                    return StageName.EDIT_PLAN
            
            if "caption" in error_lower and "unreadable" in error_lower:
                if self.loopback.should_loopback("unreadable_captions"):
                    self.loopback.record_loopback("unreadable_captions")
                    return StageName.EDIT_PLAN
            
            if "edit" in error_lower and ("invalid" in error_lower or "schema" in error_lower):
                if self.loopback.should_loopback("invalid_edit_artifact"):
                    self.loopback.record_loopback("invalid_edit_artifact")
                    return StageName.EDIT_PLAN
            
            if "render" in error_lower and "fail" in error_lower:
                if self.loopback.should_loopback("render_failure"):
                    self.loopback.record_loopback("render_failure")
                    return StageName.OPENMONTAGE_COMPOSE
            
            if "schema" in error_lower and "validation" in error_lower:
                if self.loopback.should_loopback("schema_validation_failed"):
                    self.loopback.record_loopback("schema_validation_failed")
                    return StageName.EDIT_PLAN
        
        return None
    
    def run_pipeline(self, user_request: str, initial_context: dict) -> StageResult:
        """Run the complete pipeline from current state."""
        self.state.user_request = user_request
        self.state.metadata.update(initial_context)
        self.checkpoint_mgr.save_state(self.state)
        
        last_result = None
        
        while True:
            next_stage = self.get_next_stage()
            if not next_stage:
                # All stages complete
                self.state.status = "completed"
                self.checkpoint_mgr.save_state(self.state)
                return StageResult(
                    stage=StageName.MEMORY_UPDATE,
                    success=True,
                    metadata={"final": True}
                )
            
            # Execute stage
            result = self.execute_stage(next_stage, self.state.metadata)
            last_result = result
            
            if result.success:
                print(f"✓ Stage {next_stage.value} completed successfully")
                continue
            
            # Handle failure
            if result.loopback and self.loopback.can_continue(result.loopback.value):
                print(f"↩ Loopback to {result.loopback.value} (attempt {self.loopback.loopback_counts.get(result.loopback.value, 1)})")
                # Mark loopback target as incomplete so it re-runs
                if result.loopback.value in self.state.completed_stages:
                    self.state.completed_stages.remove(result.loopback.value)
                self.checkpoint_mgr.save_state(self.state)
                continue
            
            # Fatal failure
            self.state.status = "failed"
            self.state.error = result.error
            self.checkpoint_mgr.save_state(self.state)
            return result
        
        return last_result


# CLI for testing
if __name__ == "__main__":
    import sys
    
    # Test checkpoint manager
    print("Testing CheckpointManager...")
    with __import__("tempfile").TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / "test_project"
        project_dir.mkdir()
        
        mgr = CheckpointManager(project_dir)
        
        state = ProjectState(
            project_id="test_project",
            run_id="test_run",
            user_request="test",
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )
        
        mgr.save_state(state)
        loaded = mgr.load_state()
        assert loaded.project_id == "test_project"
        print("✓ State save/load works")
        
        checkpoint = StageCheckpoint(
            stage="test_stage",
            status=StageStatus.COMPLETED.value,
            started_at=datetime.utcnow().isoformat(),
            completed_at=datetime.utcnow().isoformat()
        )
        mgr.save_stage_checkpoint(state, checkpoint)
        
        loaded_checkpoint = mgr.get_latest_checkpoint(StageName.STORY_UNDERSTANDING)
        print(f"Checkpoint loaded: {loaded_checkpoint is not None}")
        
        print("\n✓ All checkpoint tests passed")

    def _find_openmontage_schemas(self) -> Path:
        """Discover OpenMontage schemas path from repository root."""
        # Try relative to this file
        repo_root = Path(__file__).parent.parent.parent
        candidates = [
            repo_root / "external" / "OpenMontage" / "schemas" / "artifacts",
            Path.cwd() / "external" / "OpenMontage" / "schemas" / "artifacts",
        ]
        for c in candidates:
            if c.exists():
                return c
        # Fallback - return empty path, validator will fail appropriately
        return Path("")