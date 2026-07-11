"""
Quality Loopback System — Automatic quality review and targeted loopbacks.

Runs football QA skills, detects failures, and routes back to the correct
pipeline stage rather than restarting from the beginning.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class QualityGate(Enum):
    """Quality gates that can trigger loopbacks."""
    RETENTION = "retention"           # football-retention-quality-control
    AUDIO = "audio"                   # football-audio-quality-control
    PLATFORM_EXPORT = "platform_export"  # football-platform-export-validator
    SCHEMA = "schema"                 # OpenMontage schema validation
    SOURCE_MEDIA = "source_media"     # source_media_review verification


class FailureCategory(Enum):
    """Categories of quality failures for loopback routing."""
    MISSING_FOOTAGE = "missing_footage"
    INSUFFICIENT_COVERAGE = "insufficient_coverage"
    WEAK_CLIP = "weak_clip"
    DUPLICATE_CLIPS = "duplicate_clips"
    INVALID_TIMESTAMPS = "invalid_timestamps"
    BLACK_FRAMES = "black_frames"
    FROZEN_FRAMES = "frozen_frames"
    BROKEN_VIDEO = "broken_video"
    BAD_ASPECT_RATIO = "bad_aspect_ratio"
    AUDIO_CLIPPING = "audio_clipping"
    EXCESSIVE_SILENCE = "excessive_silence"
    MISSING_NARRATION = "missing_narration"
    MISSING_MUSIC = "missing_music"
    BAD_DUCKING = "bad_ducking"
    UNREADABLE_CAPTIONS = "unreadable_captions"
    MISSING_STORY_SECTION = "missing_story_section"
    WEAK_EMOTIONAL_PROGRESSION = "weak_emotional_progression"
    INVALID_EDIT_ARTIFACT = "invalid_edit_artifact"
    RENDER_FAILURE = "render_failure"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    REUSED_CONTENT_RISK = "reused_content_risk"
    VIBE_CHECK_FAILED = "vibe_check_failed"


# Mapping from failure category to target stage for loopback
LOOPBACK_TARGETS = {
    # Footage discovery/acquisition issues
    FailureCategory.MISSING_FOOTAGE: "footage_discovery",
    FailureCategory.INSUFFICIENT_COVERAGE: "footage_discovery",
    FailureCategory.BLACK_FRAMES: "footage_acquisition",
    FailureCategory.FROZEN_FRAMES: "footage_acquisition",
    FailureCategory.BROKEN_VIDEO: "footage_acquisition",
    FailureCategory.BAD_ASPECT_RATIO: "visual_analysis",
    
    # Clip scoring/selection issues
    FailureCategory.WEAK_CLIP: "clip_scoring",
    FailureCategory.DUPLICATE_CLIPS: "clip_scoring",
    FailureCategory.INVALID_TIMESTAMPS: "timestamp_extraction",
    
    # Audio issues
    FailureCategory.AUDIO_CLIPPING: "audio_plan",
    FailureCategory.EXCESSIVE_SILENCE: "audio_plan",
    FailureCategory.MISSING_NARRATION: "narration",
    FailureCategory.MISSING_MUSIC: "audio_plan",
    FailureCategory.BAD_DUCKING: "audio_plan",
    
    # Editorial issues
    FailureCategory.UNREADABLE_CAPTIONS: "edit_plan",
    FailureCategory.MISSING_STORY_SECTION: "edit_plan",
    FailureCategory.WEAK_EMOTIONAL_PROGRESSION: "edit_plan",
    
    # OpenMontage issues
    FailureCategory.INVALID_EDIT_ARTIFACT: "edit_plan",
    FailureCategory.RENDER_FAILURE: "openmontage_compose",
    FailureCategory.SCHEMA_VALIDATION_FAILED: "edit_plan",
    FailureCategory.REUSED_CONTENT_RISK: "footage_discovery",
    FailureCategory.VIBE_CHECK_FAILED: "edit_plan",
}


# Stage name mapping
STAGE_NAME_MAP = {
    "footage_discovery": "FOOTAGE_DISCOVERY",
    "footage_acquisition": "FOOTAGE_ACQUISITION",
    "visual_analysis": "VISUAL_ANALYSIS",
    "timestamp_extraction": "TIMESTAMP_EXTRACTION",
    "clip_scoring": "CLIP_SCORING",
    "narration": "NARRATION",
    "audio_plan": "AUDIO_PLAN",
    "edit_plan": "EDIT_PLAN",
    "openmontage_compose": "OPENMONTAGE_COMPOSE",
}


@dataclass
class LoopbackDecision:
    """Decision to loop back to a previous stage."""
    failure_category: FailureCategory
    target_stage: str
    reason: str
    severity: str  # low, medium, high, blocking
    attempt_number: int
    max_attempts: int
    should_continue: bool


@dataclass
class QAReport:
    """Aggregated QA report from all quality gates."""
    retention_pass: bool
    audio_pass: bool
    platform_pass: bool
    schema_pass: bool
    source_media_pass: bool
    overall_pass: bool
    findings: list[dict] = field(default_factory=list)
    loopback_decisions: list[LoopbackDecision] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class LoopbackController:
    """
    Controls automatic loopbacks with configurable limits.
    
    Prevents infinite loops by tracking attempt counts per failure category.
    """
    
    def __init__(self, max_loopbacks_per_category: int = 3):
        self.max_loopbacks = max_loopbacks_per_category
        self.attempt_counts: dict[FailureCategory, int] = {}
        self.loopback_history: list[LoopbackDecision] = []
    
    def can_loopback(self, category: FailureCategory) -> bool:
        """Check if we can attempt another loopback for this category."""
        return self.attempt_counts.get(category, 0) < self.max_loopbacks
    
    def get_target_stage(self, category: FailureCategory) -> Optional[str]:
        """Get the pipeline stage to loop back to for a failure category."""
        target = LOOPBACK_TARGETS.get(category)
        if target:
            return STAGE_NAME_MAP.get(target, target)
        return None
    
    def create_loopback(
        self,
        category: FailureCategory,
        reason: str,
        severity: str = "medium"
    ) -> LoopbackDecision:
        """Create a loopback decision."""
        attempt = self.attempt_counts.get(category, 0) + 1
        self.attempt_counts[category] = attempt
        
        target = self.get_target_stage(category)
        should_continue = attempt <= self.max_loopbacks
        
        decision = LoopbackDecision(
            failure_category=category,
            target_stage=target or "EDIT_PLAN",
            reason=reason,
            severity=severity,
            attempt_number=attempt,
            max_attempts=self.max_loopbacks,
            should_continue=should_continue
        )
        
        self.loopback_history.append(decision)
        return decision
    
    def reset_category(self, category: FailureCategory) -> None:
        """Reset attempt count for a category (e.g., after successful retry)."""
        if category in self.attempt_counts:
            del self.attempt_counts[category]
    
    def get_stats(self) -> dict:
        """Get loopback statistics."""
        return {
            "total_loopbacks": len(self.loopback_history),
            "by_category": {cat.value: count for cat, count in self.attempt_counts.items()},
            "history": [
                {
                    "category": d.failure_category.value,
                    "target_stage": d.target_stage,
                    "attempt": d.attempt_number,
                    "reason": d.reason
                }
                for d in self.loopback_history
            ]
        }


class QualityGateRunner:
    """
    Runs the football QA skills and aggregates results.
    
    Integrates with the orchestrator to execute quality checks at the
    QUALITY_REVIEW stage and produce loopback decisions.
    """
    
    def __init__(
        self,
        hermes_runner,
        project_dir: Path,
        loopback_controller: Optional[LoopbackController] = None
    ):
        self.hermes_runner = hermes_runner
        self.project_dir = project_dir
        self.football_emotion_dir = project_dir / "football_emotion"
        self.loopback = loopback_controller or LoopbackController()
    
    def run_all_gates(self, context: dict) -> QAReport:
        """Run all three football QA gates and aggregate results."""
        
        # Gate 1: Retention Quality Control
        retention_result = self._run_retention_qa(context)
        
        # Gate 2: Audio Quality Control
        audio_result = self._run_audio_qa(context)
        
        # Gate 3: Platform Export Validator
        platform_result = self._run_platform_validator(context)
        
        # Aggregate findings
        all_findings = []
        loopback_decisions = []
        
        for result in [retention_result, audio_result, platform_result]:
            if result.get("findings"):
                for finding in result["findings"]:
                    finding["gate"] = result.get("gate", "unknown")
                    all_findings.append(finding)
                    
                    # Check if this finding triggers a loopback
                    loopback = self._check_finding_for_loopback(finding)
                    if loopback:
                        loopback_decisions.append(loopback)
        
        overall_pass = (
            retention_result.get("pass", False) and
            audio_result.get("pass", False) and
            platform_result.get("pass", False)
        )
        
        return QAReport(
            retention_pass=retention_result.get("pass", False),
            audio_pass=audio_result.get("pass", False),
            platform_pass=platform_result.get("pass", False),
            schema_pass=True,  # Checked separately
            source_media_pass=True,  # Checked separately
            overall_pass=overall_pass,
            findings=all_findings,
            loopback_decisions=loopback_decisions
        )
    
    def _run_retention_qa(self, context: dict) -> dict:
        """Run football-retention-quality-control skill."""
        prompt = f"""
Run the football-retention-quality-control skill for this project.

Project directory: {self.project_dir}
Football emotion artifacts: {self.football_emotion_dir}

Required input artifacts (already generated):
- full_qa_report.json (will be created)
- story_plan.json
- clip_scores.json
- openmontage_edit_plan.json
- edit_decisions.json (if available)
- render_report.json (if available)

The skill checks:
1. Technical QA: black frames, frozen frames, broken video, aspect ratio, resolution
2. Editorial QA: missing story sections, insufficient clip coverage, duplicate clips, 
   invalid timestamps, weak emotional progression
3. Platform QA: aspect ratio, resolution, codec, safe zones for target platform
4. Reused Content Gate: Content ID risk, transformative use, source diversity
5. Vibe Check: overall emotional coherence, hook effectiveness, ending impact

Output: full_qa_report.json with pass/fail and detailed findings including
required_loopbacks with target_stage, target_skill, reason, severity.
"""
        
        result = self.hermes_runner.run_session(
            prompt=prompt,
            context=context,
            expected_skills=["football-retention-quality-control"]
        )
        
        if result.success:
            # Load generated report
            report_path = self.football_emotion_dir / "full_qa_report.json"
            if report_path.exists():
                return {
                    "gate": "retention",
                    "pass": json.loads(report_path.read_text()).get("pass", False),
                    "findings": json.loads(report_path.read_text()).get("findings", [])
                }
        
        return {"gate": "retention", "pass": False, "findings": []}
    
    def _run_audio_qa(self, context: dict) -> dict:
        """Run football-audio-quality-control skill."""
        prompt = f"""
Run the football-audio-quality-control skill for this project.

Project directory: {self.project_dir}
Football emotion artifacts: {self.football_emotion_dir}

Required input artifacts:
- audio_qc_report.json (will be created)
- audio_plan.json
- render_report.json (for measured audio)
- edit_decisions.json (for audio config)

The skill checks:
1. Loudness: Integrated LUFS target -14 LUFS (±1 LU)
2. True Peak: ≤ -1 dBTP
3. Loudness Range: LRA appropriate for content
4. Ducking: Commentary/narration properly ducked under music
5. Silence: No excessive silent gaps (>2s unintended)
6. Clipping: No digital clipping in final mix
7. Balance: Music vs commentary vs SFX levels appropriate

Output: audio_qc_report.json with pass/fail and qc_report findings.
"""
        
        result = self.hermes_runner.run_session(
            prompt=prompt,
            context=context,
            expected_skills=["football-audio-quality-control"]
        )
        
        if result.success:
            report_path = self.football_emotion_dir / "audio_qc_report.json"
            if report_path.exists():
                return {
                    "gate": "audio",
                    "pass": json.loads(report_path.read_text()).get("pass", False),
                    "findings": json.loads(report_path.read_text()).get("findings", [])
                }
        
        return {"gate": "audio", "pass": False, "findings": []}
    
    def _run_platform_validator(self, context: dict) -> dict:
        """Run football-platform-export-validator skill."""
        prompt = f"""
Run the football-platform-export-validator skill for this project.

Project directory: {self.project_dir}
Football emotion artifacts: {self.football_emotion_dir}

Required input artifacts:
- export_profile.json (will be created)
- render_report.json
- Platform from user request (YouTube longform, Shorts, TikTok, etc.)

The skill validates:
1. Aspect ratio matches platform (16:9 longform, 9:16 vertical)
2. Resolution meets platform minimums
3. Codec is platform-compatible (H.264/AAC for YouTube)
4. Audio loudness meets platform spec (YouTube: -14 LUFS)
5. True peak ≤ -1 dBTP
6. Duration within platform limits
7. File container format (MP4 for YouTube)
8. HDR metadata handling if applicable
9. Caption/subtitle format compliance

Output: export_profile.json with pass/fail and export_profile details.
"""
        
        result = self.hermes_runner.run_session(
            prompt=prompt,
            context=context,
            expected_skills=["football-platform-export-validator"]
        )
        
        if result.success:
            report_path = self.football_emotion_dir / "export_profile.json"
            if report_path.exists():
                return {
                    "gate": "platform_export",
                    "pass": json.loads(report_path.read_text()).get("pass", False),
                    "findings": json.loads(report_path.read_text()).get("findings", [])
                }
        
        return {"gate": "platform_export", "pass": False, "findings": []}
    
    def _check_finding_for_loopback(self, finding: dict) -> Optional[LoopbackDecision]:
        """Analyze a QA finding and create loopback if needed."""
        finding_text = finding.get("finding", "").lower()
        severity = finding.get("severity", "medium")
        
        # Map findings to failure categories
        category = None
        
        # Technical findings
        if "black frame" in finding_text or "frozen frame" in finding_text:
            category = FailureCategory.BLACK_FRAMES
        elif "broken video" in finding_text or "corrupt" in finding_text:
            category = FailureCategory.BROKEN_VIDEO
        elif "aspect ratio" in finding_text:
            category = FailureCategory.BAD_ASPECT_RATIO
        
        # Footage coverage
        elif "missing" in finding_text and ("footage" in finding_text or "clip" in finding_text):
            category = FailureCategory.MISSING_FOOTAGE
        elif "insufficient" in finding_text and "coverage" in finding_text:
            category = FailureCategory.INSUFFICIENT_COVERAGE
        elif "duplicate" in finding_text and "clip" in finding_text:
            category = FailureCategory.DUPLICATE_CLIPS
        elif "invalid timestamp" in finding_text or "timestamp" in finding_text and "invalid" in finding_text:
            category = FailureCategory.INVALID_TIMESTAMPS
        
        # Clip quality
        elif "weak clip" in finding_text or "low score" in finding_text:
            category = FailureCategory.WEAK_CLIP
        
        # Audio
        elif "clipping" in finding_text or "peak" in finding_text and "high" in finding_text:
            category = FailureCategory.AUDIO_CLIPPING
        elif "silence" in finding_text and ("excessive" in finding_text or "long" in finding_text):
            category = FailureCategory.EXCESSIVE_SILENCE
        elif "narration" in finding_text and "missing" in finding_text:
            category = FailureCategory.MISSING_NARRATION
        elif "music" in finding_text and "missing" in finding_text:
            category = FailureCategory.MISSING_MUSIC
        elif "ducking" in finding_text and ("bad" in finding_text or "fail" in finding_text):
            category = FailureCategory.BAD_DUCKING
        
        # Editorial
        elif "caption" in finding_text and "unreadable" in finding_text:
            category = FailureCategory.UNREADABLE_CAPTIONS
        elif "story section" in finding_text and "missing" in finding_text:
            category = FailureCategory.MISSING_STORY_SECTION
        elif "emotional progression" in finding_text and "weak" in finding_text:
            category = FailureCategory.WEAK_EMOTIONAL_PROGRESSION
        
        # OpenMontage
        elif "edit_decisions" in finding_text and ("invalid" in finding_text or "schema" in finding_text):
            category = FailureCategory.INVALID_EDIT_ARTIFACT
        elif "render" in finding_text and "fail" in finding_text:
            category = FailureCategory.RENDER_FAILURE
        elif "schema" in finding_text and "validation" in finding_text:
            category = FailureCategory.SCHEMA_VALIDATION_FAILED
        elif "reused content" in finding_text or "content id" in finding_text:
            category = FailureCategory.REUSED_CONTENT_RISK
        elif "vibe" in finding_text and "fail" in finding_text:
            category = FailureCategory.VIBE_CHECK_FAILED
        
        if category and self.loopback.can_loopback(category):
            return self.loopback.create_loopback(
                category=category,
                reason=finding.get("finding", "Quality gate failure"),
                severity=severity
            )
        
        return None


def create_quality_gate_runner(hermes_runner, project_dir: Path, config: dict) -> QualityGateRunner:
    """Factory function to create QA runner with config."""
    loopback = LoopbackController(
        max_loopbacks_per_category=config.get("max_loopbacks_per_category", 3)
    )
    return QualityGateRunner(hermes_runner, project_dir, loopback)


# Thresholds and policies for quality gates
QUALITY_POLICIES = {
    "retention": {
        "min_clip_coverage_per_section": 1,
        "max_duplicate_clips": 0,
        "max_black_frames_percent": 0.5,
        "require_hook_within_seconds": 10,
        "require_reaction_for_action": True,
        "min_emotional_reversals": 2,
    },
    "audio": {
        "target_lufs": -14.0,
        "lufs_tolerance": 1.0,
        "max_true_peak_db": -1.0,
        "max_silence_seconds": 2.0,
        "require_ducking_for_commentary": True,
        "ducking_reduction_db_min": 6,
    },
    "platform": {
        "youtube_longform": {
            "aspect_ratio": "16:9",
            "min_resolution": "1920x1080",
            "max_duration_seconds": 43200,  # 12 hours
            "codec": "h264",
            "audio_codec": "aac",
            "container": "mp4",
        },
        "youtube_shorts": {
            "aspect_ratio": "9:16",
            "min_resolution": "1080x1920",
            "max_duration_seconds": 60,
            "codec": "h264",
            "audio_codec": "aac",
            "container": "mp4",
        },
        "tiktok": {
            "aspect_ratio": "9:16",
            "min_resolution": "1080x1920",
            "max_duration_seconds": 180,
            "codec": "h264",
            "audio_codec": "aac",
            "container": "mp4",
        },
        "instagram_reels": {
            "aspect_ratio": "9:16",
            "min_resolution": "1080x1920",
            "max_duration_seconds": 90,
            "codec": "h264",
            "audio_codec": "aac",
            "container": "mp4",
        }
    }
}


if __name__ == "__main__":
    # Test loopback controller
    controller = LoopbackController(max_loopbacks_per_category=3)
    
    # Test some loopbacks
    cat = FailureCategory.MISSING_FOOTAGE
    for i in range(4):
        decision = controller.create_loopback(cat, f"Missing footage in section {i}", "high")
        print(f"Loopback {i+1}: target={decision.target_stage}, continue={decision.should_continue}")
    
    print(f"\nStats: {controller.get_stats()}")
    
    # Test category mapping
    print(f"\nMissing footage -> {controller.get_target_stage(FailureCategory.MISSING_FOOTAGE)}")
    print(f"Weak clip -> {controller.get_target_stage(FailureCategory.WEAK_CLIP)}")
    print(f"Audio clipping -> {controller.get_target_stage(FailureCategory.AUDIO_CLIPPING)}")
    print(f"Render failure -> {controller.get_target_stage(FailureCategory.RENDER_FAILURE)}")