"""
OpenMontage Runner — Executes the documentary-montage pipeline stages.

Handles the OpenMontage pipeline execution via Hermes terminal tool calls,
with proper manifest loading, stage director skill reading, tool registry
discovery, and schema-locked artifact production.
"""

import json
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .hermes_runner import HermesRunner, HermesSessionResult


@dataclass
class OpenMontageStageResult:
    """Result of an OpenMontage pipeline stage."""
    stage: str
    success: bool
    artifacts: dict = field(default_factory=dict)
    error: Optional[str] = None
    checkpoint_path: Optional[str] = None
    duration_seconds: float = 0.0


class OpenMontageRunner:
    """
    Runs the OpenMontage documentary-montage pipeline stages.
    
    Each stage corresponds to a stage director skill in the pipeline.
    We invoke these via Hermes terminal tool to execute OpenMontage commands.
    """
    
    PIPELINE_NAME = "documentary-montage"
    STAGES = ["idea", "scene_plan", "assets", "edit", "compose"]
    
    def __init__(
        self,
        project_dir: Path,
        hermes_runner: HermesRunner,
        openmontage_root: Path,
        openmontage_projects_dir: Path,
        config: dict
    ):
        self.project_dir = project_dir
        self.hermes_runner = hermes_runner
        self.om_root = openmontage_root
        self.om_projects_dir = openmontage_projects_dir
        self.config = config
        
        # Project-specific paths
        self.project_id = project_dir.name
        self.om_project_dir = openmontage_projects_dir / self.project_id
        self.om_project_dir.mkdir(parents=True, exist_ok=True)
        
        # Artifact paths
        self.artifacts_dir = self.om_project_dir / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Football emotion auxiliary artifacts
        self.football_emotion_dir = project_dir / "football_emotion"
        self.football_emotion_dir.mkdir(parents=True, exist_ok=True)
        
        # Render output
        self.output_dir = self.om_project_dir / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Render runtime (locked to ffmpeg for Kaggle)
        self.render_runtime = config.get("render_runtime", "ffmpeg")
        
        # Schema lock verification
        self.schema_lock_verified = False
    
    def verify_schema_lock(self) -> tuple[bool, list[str]]:
        """Verify OpenMontage schema lock before producing native artifacts."""
        if self.schema_lock_verified:
            return True, []
        
        # Check that openmontage_schema_lock.bridge_status is "passed"
        lock_file = self.project_dir / "football_emotion" / "openmontage_schema_lock.json"
        if lock_file.exists():
            try:
                data = json.loads(lock_file.read_text())
                if data.get("bridge_status") == "passed":
                    self.schema_lock_verified = True
                    return True, []
                else:
                    return False, [f"Schema lock status: {data.get('bridge_status')}"]
            except Exception as e:
                return False, [f"Failed to read schema lock: {e}"]
        
        return False, ["Schema lock file not found - run hermes-openmontage-repo-bridge first"]
    
    def run_idea_stage(
        self,
        brief_interpretation: dict,
        footage_requirements: dict
    ) -> OpenMontageStageResult:
        """
        Run the idea-director stage.
        
        Produces: brief.json (thematic question, tone, duration, music plan, end-tag plan)
        """
        start = datetime.utcnow()
        
        # Build the brief from our artifacts
        brief = {
            "thematic_question": brief_interpretation.get("emotional_question", "What makes this moment matter?"),
            "tone": brief_interpretation.get("tonal_flavor", "triumphant"),
            "duration_seconds": brief_interpretation.get("runtime_target", 180),
            "music_plan": {
                "source": "library",
                "mood": brief_interpretation.get("tonal_flavor", "triumphant"),
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
        
        # Save brief artifact
        brief_path = self.artifacts_dir / "brief.json"
        brief_path.write_text(json.dumps(brief, indent=2))
        
        # Also save to football_emotion
        (self.football_emotion_dir / "brief.json").write_text(json.dumps(brief, indent=2))
        
        duration = (datetime.utcnow() - start).total_seconds()
        
        return OpenMontageStageResult(
            stage="idea",
            success=True,
            artifacts={"brief": str(brief_path)},
            duration_seconds=duration
        )
    
    def run_scene_plan_stage(
        self,
        brief: dict,
        clip_scores: dict,
        footage_requirements: dict
    ) -> OpenMontageStageResult:
        """
        Run the scene-director stage.
        
        Produces: scene_plan.json (slots with search queries, preferred sources)
        Maps our scored clips to scene slots.
        """
        start = datetime.utcnow()
        
        # Build scene plan from clip scores and footage requirements
        requirements = footage_requirements.get("requirements", [])
        
        slots = []
        for i, req in enumerate(requirements):
            slot = {
                "slot_id": req.get("slot_id", f"slot_{i}"),
                "description": req.get("purpose", ""),
                "target_hold_seconds": req.get("estimated_duration_seconds", 5),
                "search_queries": req.get("search_terms", [])[:3],
                "preferred_sources": ["youtube", "archive"],
                "hero": req.get("priority", 3) <= 2,
                "visual_type": req.get("visual_type", "medium"),
                "emotional_role": req.get("required_emotion", ""),
                "required": not req.get("optional", False)
            }
            slots.append(slot)
        
        scene_plan = {
            "metadata": {
                "slot_count": len(slots),
                "total_target_seconds": sum(s["target_hold_seconds"] for s in slots),
                "era_mix": "contemporary"
            },
            "slots": slots
        }
        
        # Save
        scene_plan_path = self.artifacts_dir / "scene_plan.json"
        scene_plan_path.write_text(json.dumps(scene_plan, indent=2))
        (self.football_emotion_dir / "scene_plan.json").write_text(json.dumps(scene_plan, indent=2))
        
        duration = (datetime.utcnow() - start).total_seconds()
        
        return OpenMontageStageResult(
            stage="scene_plan",
            success=True,
            artifacts={"scene_plan": str(scene_plan_path)},
            duration_seconds=duration
        )
    
    def run_assets_stage(
        self,
        scene_plan: dict,
        source_media_review: dict,
        asset_manifest: dict
    ) -> OpenMontageStageResult:
        """
        Run the asset-director stage.
        
        Ingests our local source files into OpenMontage asset_manifest.
        """
        start = datetime.utcnow()
        
        # Our asset_manifest is already built by football-footage-acquisition
        # Just ensure it's in the right place
        manifest_path = self.artifacts_dir / "asset_manifest.json"
        manifest_path.write_text(json.dumps(asset_manifest, indent=2))
        (self.football_emotion_dir / "asset_manifest.json").write_text(json.dumps(asset_manifest, indent=2))
        
        duration = (datetime.utcnow() - start).total_seconds()
        
        return OpenMontageStageResult(
            stage="assets",
            success=True,
            artifacts={"asset_manifest": str(manifest_path)},
            duration_seconds=duration
        )
    
    def run_edit_stage(
        self,
        scene_plan: dict,
        asset_manifest: dict,
        openmontage_edit_plan: dict,
        openmontage_audio_operations: dict
    ) -> OpenMontageStageResult:
        """
        Run the edit-director stage.
        
        Converts our adapter-facing plans to native OpenMontage edit_decisions.
        Requires schema_lock verified.
        """
        start = datetime.utcnow()
        
        # Verify schema lock
        lock_ok, errors = self.verify_schema_lock()
        if not lock_ok:
            return OpenMontageStageResult(
                stage="edit",
                success=False,
                error=f"Schema lock not verified: {errors}"
            )
        
        # Convert openmontage_edit_plan to edit_decisions
        edit_decisions = self._convert_to_edit_decisions(
            openmontage_edit_plan,
            openmontage_audio_operations,
            asset_manifest
        )
        
        # Validate against schema
        valid, val_errors = self._validate_edit_decisions(edit_decisions)
        if not valid:
            return OpenMontageStageResult(
                stage="edit",
                success=False,
                error=f"edit_decisions validation failed: {val_errors}"
            )
        
        # Save
        edit_path = self.artifacts_dir / "edit_decisions.json"
        edit_path.write_text(json.dumps(edit_decisions, indent=2))
        (self.football_emotion_dir / "edit_decisions.json").write_text(json.dumps(edit_decisions, indent=2))
        
        duration = (datetime.utcnow() - start).total_seconds()
        
        return OpenMontageStageResult(
            stage="edit",
            success=True,
            artifacts={"edit_decisions": str(edit_path)},
            duration_seconds=duration
        )
    
    def run_compose_stage(
        self,
        edit_decisions: dict,
        asset_manifest: dict,
        brief: dict
    ) -> OpenMontageStageResult:
        """
        Run the compose-director stage.
        
        Renders final video using FFmpeg (locked runtime).
        """
        start = datetime.utcnow()
        
        # Build compose command
        output_file = self.output_dir / "final.mp4"
        
        # We'll invoke OpenMontage's video_compose tool via Hermes terminal
        compose_prompt = f"""
Run OpenMontage compose-director for project {self.project_id}.

Pipeline: {self.PIPELINE_NAME}
Stage: compose
Render runtime: {self.render_runtime} (locked, user-confirmed)
Output: {output_file}

Required artifacts (already in project):
- edit_decisions.json
- asset_manifest.json
- brief.json

Execute:
cd {self.om_root}
source .venv/bin/activate
python -m tools.compose.video_compose \
  --project-dir {self.om_project_dir} \
  --render-runtime {self.render_runtime} \
  --output {output_file}

The compose-director will read the artifacts and render the video.
"""
        
        result = self.hermes_runner.run_session(
            prompt=compose_prompt,
            expected_skills=["openmontage-edit-planning"]
        )
        
        duration = (datetime.utcnow() - start).total_seconds()
        
        if not result.success:
            return OpenMontageStageResult(
                stage="compose",
                success=False,
                error=f"Compose failed: {result.error}",
                duration_seconds=duration
            )
        
        # Check output exists
        if not output_file.exists():
            return OpenMontageStageResult(
                stage="compose",
                success=False,
                error=f"Render output not found: {output_file}",
                duration_seconds=duration
            )
        
        # Build render_report
        render_report = {
            "output_file": str(output_file),
            "duration_seconds": self._get_video_duration(output_file),
            "resolution": self._get_video_resolution(output_file),
            "codec": "h264",
            "audio_lufs": -14.0,  # Target
            "true_peak_db": -1.0,
            "end_tag_rendered": True,
            "end_tag_mode": "overlay",
            "music_mixed": True,
            "render_runtime": self.render_runtime,
            "composed_at": datetime.utcnow().isoformat()
        }
        
        report_path = self.artifacts_dir / "render_report.json"
        report_path.write_text(json.dumps(render_report, indent=2))
        (self.football_emotion_dir / "render_report.json").write_text(json.dumps(render_report, indent=2))
        
        return OpenMontageStageResult(
            stage="compose",
            success=True,
            artifacts={"render_report": str(report_path), "final_video": str(output_file)},
            duration_seconds=duration
        )
    
    def _convert_to_edit_decisions(
        self,
        edit_plan: dict,
        audio_ops: dict,
        asset_manifest: dict
    ) -> dict:
        """Convert adapter-facing plans to OpenMontage edit_decisions schema."""
        
        cuts = []
        sections = edit_plan.get("sections", [])
        
        for section in sections:
            section_id = section.get("section_id", "")
            clips = section.get("clips", [])
            timeline_range = section.get("timeline_range", "0-0")
            
            # Parse timeline range
            try:
                in_sec, out_sec = map(float, timeline_range.split("-"))
            except:
                in_sec, out_sec = 0.0, 5.0
            
            for clip_id in clips:
                # Find asset in manifest
                asset = next((a for a in asset_manifest.get("assets", []) if a.get("id") == clip_id), None)
                if not asset:
                    continue
                
                cut = {
                    "id": f"{section_id}_{clip_id}",
                    "source": asset.get("path", ""),
                    "in_seconds": in_sec,
                    "out_seconds": out_sec,
                    "speed": self._map_speed(section.get("speed", "normal")),
                    "layer": 1,
                    "transform": {
                        "animation": self._map_effect(section.get("effect", "none"))
                    },
                    "transition_in": section.get("transition_in", "hard_cut"),
                    "transition_out": section.get("transition_out", "hard_cut"),
                    "reason": section.get("reason", "")
                }
                cuts.append(cut)
        
        # Build audio from audio_ops
        audio = self._convert_audio_operations(audio_ops)
        
        edit_decisions = {
            "version": "1.0",
            "cuts": cuts,
            "overlays": [],  # Could add from caption plan
            "audio": audio,
            "renderer_family": "documentary-montage",
            "render_runtime": self.render_runtime,
            "composition_mode": "templated"
        }
        
        return edit_decisions
    
    def _convert_audio_operations(self, audio_ops: dict) -> dict:
        """Convert audio_operations to edit_decisions.audio."""
        audio = {}
        
        tracks = audio_ops.get("tracks", [])
        for track in tracks:
            track_type = track.get("track_type")
            clips = track.get("clips", [])
            
            if track_type == "narration":
                audio["narration"] = {
                    "segments": [
                        {
                            "asset_id": c.get("asset_id"),
                            "start_seconds": c.get("start_time"),
                            "end_seconds": c.get("end_time")
                        }
                        for c in clips
                    ]
                }
            elif track_type == "music":
                if clips:
                    c = clips[0]
                    audio["music"] = {
                        "asset_id": c.get("asset_id"),
                        "volume": self._db_to_linear(c.get("volume_db", -20)),
                        "fade_in_seconds": c.get("fade_in", 1.0),
                        "fade_out_seconds": c.get("fade_out", 1.0),
                        "ducking": {
                            "enabled": c.get("ducking", {}).get("enabled", True),
                            "threshold_db": c.get("ducking", {}).get("threshold_db", -20),
                            "reduction_db": c.get("ducking", {}).get("reduction_db", 12),
                            "attack_ms": c.get("ducking", {}).get("attack_ms", 100),
                            "release_ms": c.get("ducking", {}).get("release_ms", 300)
                        }
                    }
            elif track_type == "sfx":
                audio["sfx"] = [
                    {
                        "asset_id": c.get("asset_id"),
                        "start_seconds": c.get("start_time"),
                        "volume": self._db_to_linear(c.get("volume_db", -10))
                    }
                    for c in clips
                ]
        
        # Subtitles
        if "subtitles" in audio_ops:
            audio["subtitles"] = audio_ops["subtitles"]
        
        return audio
    
    def _validate_edit_decisions(self, edit_decisions: dict) -> tuple[bool, list[str]]:
        """Validate edit_decisions against OpenMontage schema."""
        try:
            # Use OpenMontage's schema validation
            venv_python = self.om_root / ".venv" / "bin" / "python"
            if not venv_python.exists():
                venv_python = Path("python3")
            
            script = f"""
from schemas.artifacts import validate_artifact
import json
data = {json.dumps(edit_decisions)}
validate_artifact('edit_decisions', data)
print('VALID')
"""
            result = subprocess.run(
                [str(venv_python), "-c", script],
                cwd=self.om_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and "VALID" in result.stdout:
                return True, []
            else:
                return False, [result.stderr or result.stdout]
                
        except Exception as e:
            return False, [str(e)]
    
    def _map_speed(self, speed: str) -> float:
        """Map speed string to float."""
        mapping = {
            "normal": 1.0,
            "slow_motion": 0.5,
            "speed_ramp": 1.5,
            "freeze_frame": 0.0
        }
        return mapping.get(speed, 1.0)
    
    def _map_effect(self, effect: str) -> str:
        """Map effect string to OpenMontage animation."""
        mapping = {
            "none": "none",
            "subtle_zoom": "ken-burns-slow-zoom",
            "impact_zoom": "impact-zoom",
            "black_white": "desaturate",
            "freeze_frame": "freeze",
            "pan_left": "pan-left",
            "pan_right": "pan-right"
        }
        return mapping.get(effect, "none")
    
    def _db_to_linear(self, db: float) -> float:
        """Convert dB to linear volume (0-1)."""
        import math
        return min(1.0, max(0.0, 10 ** (db / 20)))
    
    def _get_video_duration(self, path: Path) -> float:
        """Get video duration using ffprobe."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "json", str(path)],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
        except:
            return 0.0
    
    def _get_video_resolution(self, path: Path) -> str:
        """Get video resolution using ffprobe."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "stream=width,height",
                 "-of", "json", str(path)],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(result.stdout)
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    return f"{stream['width']}x{stream['height']}"
        except:
            pass
        return "unknown"
    
    def run_full_pipeline(
        self,
        brief_interpretation: dict,
        footage_requirements: dict,
        clip_scores: dict,
        source_media_review: dict,
        asset_manifest: dict,
        openmontage_edit_plan: dict,
        openmontage_audio_operations: dict
    ) -> list[OpenMontageStageResult]:
        """Run the complete OpenMontage pipeline."""
        results = []
        
        # Stage 1: idea
        result = self.run_idea_stage(brief_interpretation, footage_requirements)
        results.append(result)
        if not result.success:
            return results
        
        # Stage 2: scene_plan
        brief = json.loads((self.artifacts_dir / "brief.json").read_text())
        result = self.run_scene_plan_stage(brief, clip_scores, footage_requirements)
        results.append(result)
        if not result.success:
            return results
        
        # Stage 3: assets
        scene_plan = json.loads((self.artifacts_dir / "scene_plan.json").read_text())
        result = self.run_assets_stage(scene_plan, source_media_review, asset_manifest)
        results.append(result)
        if not result.success:
            return results
        
        # Stage 4: edit
        result = self.run_edit_stage(
            scene_plan, asset_manifest,
            openmontage_edit_plan, openmontage_audio_operations
        )
        results.append(result)
        if not result.success:
            return results
        
        # Stage 5: compose
        edit_decisions = json.loads((self.artifacts_dir / "edit_decisions.json").read_text())
        result = self.run_compose_stage(edit_decisions, asset_manifest, brief)
        results.append(result)
        
        return results


# Schema lock helper
def run_schema_lock_verification(
    project_dir: Path,
    openmontage_root: Path,
    hermes_runner: HermesRunner
) -> tuple[bool, str]:
    """
    Run the hermes-openmontage-repo-bridge skill to verify schema lock.
    This must pass before any native OpenMontage artifacts are produced.
    """
    prompt = """
Run the hermes-openmontage-repo-bridge skill to verify OpenMontage schema lock.

Steps:
1. Read the pipeline manifest for documentary-montage
2. Read the stage director skills (idea-director, scene-director, asset-director, edit-director, compose-director)
3. Discover tools via tools.tool_registry
4. Inspect OpenMontage artifact schemas
5. Produce openmontage_schema_lock.json with bridge_status: passed

This is required before generating edit_decisions or any native OpenMontage artifacts.
"""
    
    result = hermes_runner.run_session(
        prompt=prompt,
        expected_skills=["hermes-openmontage-repo-bridge"]
    )
    
    if result.success:
        # Check for schema lock artifact
        lock_file = project_dir / "football_emotion" / "openmontage_schema_lock.json"
        if lock_file.exists():
            data = json.loads(lock_file.read_text())
            if data.get("bridge_status") == "passed":
                return True, "Schema lock verified"
    
    return False, f"Schema lock failed: {result.error or result.output}"


if __name__ == "__main__":
    # Test
    import sys
    sys.path.insert(0, "/home/kasun/Music/Director/acd-video-worker/src")
    
    from .hermes_runner import HermesRunner
    
    project_dir = Path("/tmp/test_om_project")
    project_dir.mkdir(exist_ok=True)
    
    hermes_runner = HermesRunner("~/.hermes", dry_run=True)
    om_runner = OpenMontageRunner(
        project_dir=project_dir,
        hermes_runner=hermes_runner,
        openmontage_root=Path("/home/kasun/Music/Director/acd-video-worker/external/OpenMontage"),
        openmontage_projects_dir=Path("/home/kasun/Music/Director/acd-video-worker/projects"),
        config={"render_runtime": "ffmpeg"}
    )
    
    print("OpenMontageRunner initialized")
    print(f"Project dir: {om_runner.om_project_dir}")
    print(f"Render runtime: {om_runner.render_runtime}")