"""
Hermes Runner — Invokes Hermes Agent sessions for skill execution.

Provides a clean interface for running Hermes sessions with the football-emotion profile,
passing prompts that activate specific skills, and capturing structured outputs.
"""

import json
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List, Dict


@dataclass
class HermesSessionResult:
    """Result of a Hermes session execution."""
    success: bool
    session_id: Optional[str] = None
    output: str = ""
    error: Optional[str] = None
    returncode: int = -1
    artifacts: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)


class HermesRunner:
    """
    Runs Hermes Agent sessions for the football-emotion skill system.

    Handles session management, skill activation via description matching,
    artifact extraction, and error handling.
    """

    def __init__(
        self,
        hermes_home: str,
        profile: str = "football-emotion",
        dry_run: bool = False,
        timeout: int = 600,
        hermes_cli: Optional[str] = None
    ):
        self.hermes_home = Path(hermes_home).expanduser().resolve()
        self.profile = profile
        self.dry_run = dry_run
        self.timeout = timeout
        self.profile_dir = self.hermes_home / "profiles" / profile

        # Resolve hermes CLI - use provided path, or find in PATH, or use bundled
        if hermes_cli:
            self.hermes_cli = Path(hermes_cli).expanduser().resolve()
        else:
            # Try to find hermes in PATH
            import shutil
            hermes_in_path = shutil.which("hermes")
            if hermes_in_path:
                self.hermes_cli = Path(hermes_in_path)
            else:
                # Fallback to common install location
                self.hermes_cli = Path.home() / ".local" / "bin" / "hermes"

        # Verify profile exists
        if not self.profile_dir.exists():
            raise ValueError(f"Hermes profile not found: {self.profile_dir}")

        # Session tracking
        self.session_history: List[Dict] = []

    def run_session(
        self,
        prompt: str,
        context: Dict = None,
        session_id: Optional[str] = None,
        parent_session_id: Optional[str] = None,
        expected_skills: List[str] = None
    ) -> HermesSessionResult:
        """
        Execute a Hermes chat session with the given prompt.

        Args:
            prompt: The prompt to send to Hermes (should trigger skills via description matching)
            context: Additional context to include in the prompt
            session_id: Optional existing session ID to continue
            parent_session_id: Optional parent session for sub-agent tracking
            expected_skills: Skills we expect to be activated (for validation)

        Returns:
            HermesSessionResult with output and any extracted artifacts
        """
        if self.dry_run:
            return self._dry_run_result(prompt, expected_skills)

        # Build environment
        env = os.environ.copy()
        env["HERMES_HOME"] = str(self.profile_dir)

        # Build command - use -q for single query mode, -Q for quiet (programmatic)
        cmd = [
            str(self.hermes_cli),
            "-p", self.profile,
            "chat",
            "-q", prompt,
            "-Q",  # Quiet mode for programmatic use
        ]

        if session_id:
            cmd.extend(["--resume", session_id])
        if parent_session_id:
            cmd.extend(["--parent-session", parent_session_id])

        print(f"[HermesRunner] Running session with profile '{self.profile}'")
        print(f"[HermesRunner] Prompt length: {len(prompt)} chars")
        if expected_skills:
            print(f"[HermesRunner] Expected skills: {expected_skills}")

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            session_result = HermesSessionResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
                returncode=result.returncode
            )

            # Try to extract session ID from output
            session_result.session_id = self._extract_session_id(result.stdout)

            # Parse artifacts from output
            session_result.artifacts = self._extract_artifacts(result.stdout)

            # Record in history
            self.session_history.append({
                "session_id": session_result.session_id,
                "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt,
                "success": session_result.success,
                "timestamp": datetime.utcnow().isoformat(),
                "expected_skills": expected_skills or [],
                "activated_skills": self._detect_activated_skills(result.stdout)
            })

            return session_result

        except subprocess.TimeoutExpired:
            return HermesSessionResult(
                success=False,
                error=f"Hermes session timed out after {self.timeout}s"
            )
        except Exception as e:
            return HermesSessionResult(
                success=False,
                error=f"Hermes execution failed: {e}"
            )

    def run_skill_sequence(
        self,
        stages: List[Dict],
        context: Dict = None
    ) -> List[HermesSessionResult]:
        """
        Run a sequence of Hermes sessions for multiple stages.

        Each stage dict should have:
        - name: stage name
        - prompt: prompt for this stage
        - expected_skills: list of expected skill names
        - depends_on: optional previous stage output keys
        """
        results = []
        accumulated_context = context or {}

        for stage in stages:
            # Build prompt with accumulated context
            prompt = self._build_contextual_prompt(stage["prompt"], accumulated_context)

            result = self.run_session(
                prompt=prompt,
                context=accumulated_context,
                expected_skills=stage.get("expected_skills", [])
            )
            results.append(result)

            if not result.success:
                break

            # Update accumulated context with new artifacts
            accumulated_context.update(result.artifacts)
            accumulated_context[f"{stage['name']}_output"] = result.output

        return results

    def _build_contextual_prompt(self, base_prompt: str, context: Dict) -> str:
        """Enhance prompt with relevant context from previous stages."""
        if not context:
            return base_prompt

        context_parts = ["Previous stage outputs (use as input):"]
        for key, value in context.items():
            if key.endswith("_output"):
                continue
            if isinstance(value, dict):
                context_parts.append(f"\n{key}:")
                context_parts.append(json.dumps(value, indent=2)[:3000])

        return "\n".join(context_parts) + "\n\n" + base_prompt

    def _dry_run_result(self, prompt: str, expected_skills: List[str] = None) -> HermesSessionResult:
        """Generate a mock result for dry-run mode."""
        return HermesSessionResult(
            success=True,
            session_id=f"dry_run_{uuid.uuid4().hex[:8]}",
            output=f"[DRY RUN] Would execute Hermes with prompt ({len(prompt)} chars). Expected skills: {expected_skills or 'any'}",
            artifacts={}
        )

    def _extract_session_id(self, output: str) -> Optional[str]:
        """Extract session ID from Hermes output."""
        import re
        patterns = [
            r"session[_\s]?id[:\s]+([a-f0-9-]{8,})",
            r"Session[:\s]+([a-f0-9-]{8,})",
            r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
        ]
        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_artifacts(self, output: str) -> Dict:
        """Extract structured artifacts from Hermes output."""
        artifacts = {}

        import re
        json_blocks = re.findall(r"```json\n(.*?)\n```", output, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block)
                if isinstance(data, dict):
                    if "source_video_candidate" in str(data):
                        artifacts["source_candidates"] = data
                    elif "video_scene_analysis" in str(data):
                        artifacts["video_scene_analysis"] = data
                    elif "clip_candidate" in str(data):
                        artifacts["clip_candidates"] = data
                    elif "clip_score" in str(data) or "scorecard" in str(data):
                        artifacts["clip_scores"] = data
                    elif "narration_script" in str(data) or "script" in str(data):
                        artifacts["narration_script"] = data
                    elif "audio_plan" in str(data):
                        artifacts["audio_plan"] = data
                    elif "openmontage_edit_plan" in str(data):
                        artifacts["openmontage_edit_plan"] = data
                    elif "edit_decisions" in str(data):
                        artifacts["edit_decisions"] = data
                    elif "render_report" in str(data):
                        artifacts["render_report"] = data
                    elif "full_qa_report" in str(data):
                        artifacts["qa_report"] = data
                    elif "hermes_memory_update" in str(data):
                        artifacts["memory_update"] = data
                    else:
                        artifacts.setdefault("raw_artifacts", []).append(data)
            except json.JSONDecodeError:
                pass

        return artifacts

    def _detect_activated_skills(self, output: str) -> List[str]:
        """Detect which skills were activated based on output content."""
        skills = []
        skill_indicators = {
            "social-edit-reasoning": ["editorial_journey_state", "brief_interpretation"],
            "football-story-strategy": ["story_plan", "user_instruction_profile", "footage_requirements"],
            "football-source-discovery": ["source_video_candidate", "deep_analysis_candidate"],
            "football-footage-acquisition": ["source_media_review", "asset_manifest"],
            "football-visual-scene-analysis": ["video_scene_analysis", "scene_candidate"],
            "football-timestamp-extraction": ["clip_candidate", "source_range"],
            "football-clip-scoring": ["clip_scorecard", "scorecard", "total_10"],
            "football-narration-scriptwriting": ["narration_script", "script_segment"],
            "football-music-library-selector": ["music_sfx_candidate", "suitability_score"],
            "football-audio-music-director": ["audio_plan_segment", "music_action"],
            "football-commentary-ducking-mixer": ["ducking", "commentary_rights_check"],
            "football-pro-cutting-pacing": ["cut_style", "transition", "pacing"],
            "football-caption-thumbnail-direction": ["caption_plan", "thumbnail_candidate"],
            "openmontage-edit-planning": ["openmontage_edit_plan", "edit_decisions"],
            "openmontage-audio-operation-mapper": ["audio_operations", "track_id"],
            "football-retention-quality-control": ["full_qa_report", "editorial_qa"],
            "football-audio-quality-control": ["qc_report", "loudness", "true_peak"],
            "football-platform-export-validator": ["export_profile", "platform"],
            "hermes-football-memory-learning": ["hermes_memory_update", "short_lessons"],
            "football-fact-provenance-gate": ["match_fact_lock", "fact_provenance_report"],
            "football-footage-rights-transformative-risk-assessor": ["footage_rights_risk_record"],
            "football-rights-safe-audio-license-checker": ["license_verification_record"],
        }

        for skill, indicators in skill_indicators.items():
            if any(ind in output for ind in indicators):
                skills.append(skill)

        return skills

    def get_session_history(self) -> List[Dict]:
        """Get history of all sessions run."""
        return self.session_history


def build_skill_prompt(skill_name: str, task: str, inputs: Dict) -> str:
    """Build a prompt that will activate a specific skill via description matching."""

    skill_descriptions = {
        "social-edit-reasoning": "Guide editorial reasoning for reusable emotional sourced-footage videos",
        "football-story-strategy": "Turn a football-emotion request into a concrete story arc",
        "football-source-discovery": "Find source videos or footage for a football emotional storytelling video",
        "football-footage-acquisition": "Download, verify, and prepare source video candidates for OpenMontage",
        "football-visual-scene-analysis": "Analyze actual visual/audio content of source videos",
        "football-timestamp-extraction": "Extract bounded clips with handles and role labels from scene analysis",
        "football-clip-scoring": "Score clip candidates against story plan using editorial rubric",
        "football-narration-scriptwriting": "Write narration script tied to selected clips",
        "football-music-library-selector": "Select music/SFX candidates from free libraries",
        "football-audio-music-director": "Create section-by-section audio plan from clips and music",
        "football-commentary-ducking-mixer": "Plan commentary ducking and audio hierarchy",
        "football-pro-cutting-pacing": "Determine cut rhythm, transitions, effects per section",
        "football-caption-thumbnail-direction": "Plan captions and thumbnail frames",
        "openmontage-edit-planning": "Assemble story + clips + audio into OpenMontage edit plan",
        "openmontage-audio-operation-mapper": "Map audio plan to OpenMontage edit_decisions.audio",
        "football-retention-quality-control": "Full editorial/technical/platform QA review",
        "football-audio-quality-control": "Audio loudness, ducking, peak measurement",
        "football-platform-export-validator": "Validate export profile for target platform",
        "hermes-football-memory-learning": "Distill lessons into Hermes memory update",
        "football-fact-provenance-gate": "Verify match facts before claiming",
        "football-footage-rights-transformative-risk-assessor": "Assess transformative use risk",
        "football-rights-safe-audio-license-checker": "Verify audio license status",
    }

    desc = skill_descriptions.get(skill_name, skill_name)

    prompt = f"""As the AI Creative Director, you need to {desc}.

TASK: {task}

INPUTS:
{json.dumps(inputs, indent=2)}

Execute the appropriate skill(s) and produce the required output artifacts.
"""
    return prompt


if __name__ == "__main__":
    import sys

    hermes_home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    runner = HermesRunner(hermes_home, dry_run=True)

    result = runner.run_session(
        prompt="Test prompt for football-story-strategy skill",
        expected_skills=["football-story-strategy"]
    )

    print(f"Success: {result.success}")
    print(f"Session ID: {result.session_id}")
    print(f"Output: {result.output}")