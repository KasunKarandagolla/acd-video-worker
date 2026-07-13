"""
Hermes Runner — Invokes Hermes Agent sessions for skill execution.

Provides a clean interface for running Hermes sessions with the football-emotion profile,
passing prompts that activate specific skills, and capturing structured outputs.
"""

import os
import re
import shutil
import subprocess
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
        hermes_cli: Optional[str] = None,
        cwd: Optional[Path] = None,
        max_turns: int = 60,
        headless_auto_approve: bool = True,
        model_override: Optional[str] = None,
    ):
        self.hermes_home = Path(hermes_home).expanduser().resolve()
        self.profile = profile
        self.dry_run = dry_run
        self.timeout = timeout
        self.cwd = Path(cwd).expanduser().resolve() if cwd else None
        self.max_turns = max_turns
        self.headless_auto_approve = headless_auto_approve
        self.model_override = model_override.strip() if model_override else None
        self.profile_dir = self.hermes_home / "profiles" / profile

        # Resolve hermes CLI - use provided path, or find in PATH, or use bundled
        if hermes_cli:
            self.hermes_cli = Path(hermes_cli).expanduser().resolve()
        else:
            # Try to find hermes in PATH
            hermes_in_path = shutil.which("hermes")
            if hermes_in_path:
                self.hermes_cli = Path(hermes_in_path)
            else:
                # Fallback to common install location
                self.hermes_cli = Path.home() / ".local" / "bin" / "hermes"

        # Session tracking
        self.session_history: List[Dict] = []

    def find_skill(self, skill_name: str) -> Optional[Path]:
        """Return an installed SKILL.md by its frontmatter name or folder name."""
        skills_root = self.profile_dir / "skills"
        if not skills_root.is_dir():
            return None
        direct = skills_root / skill_name / "SKILL.md"
        if direct.is_file():
            return direct
        for candidate in skills_root.rglob("SKILL.md"):
            if candidate.parent.name == skill_name:
                return candidate
            try:
                head = candidate.read_text(encoding="utf-8")[:1000]
            except OSError:
                continue
            if re.search(rf"(?m)^name:\s*[\"']?{re.escape(skill_name)}[\"']?\s*$", head):
                return candidate
        return None

    def run_session(
        self,
        prompt: str,
        context: Dict = None,
        session_id: Optional[str] = None,
        parent_session_id: Optional[str] = None,
        expected_skills: List[str] = None,
        max_turns: Optional[int] = None,
    ) -> HermesSessionResult:
        """
        Execute a Hermes chat session with the given prompt.

        Args:
            prompt: The prompt to send to Hermes (should trigger skills via description matching)
            context: Additional context to include in the prompt
            session_id: Optional existing session ID to continue
            parent_session_id: Optional parent session for sub-agent tracking (stored in metadata only)
            expected_skills: Skills we expect to be activated (for validation)

        Returns:
            HermesSessionResult with output and any extracted artifacts
        """
        if self.dry_run:
            return HermesSessionResult(success=False, error="Dry-run mode does not execute Hermes", returncode=2)

        if not self.profile_dir.is_dir():
            return HermesSessionResult(success=False, error=f"Hermes profile not found: {self.profile_dir}", returncode=2)
        if not self.hermes_cli.is_file() and not shutil.which(str(self.hermes_cli)):
            return HermesSessionResult(success=False, error=f"Hermes CLI not found: {self.hermes_cli}", returncode=2)

        # Build environment
        env = os.environ.copy()
        # The supported `-p` selector resolves this root to profiles/<name>.
        # Passing the profile directory here as well creates nested profile paths.
        env["HERMES_HOME"] = str(self.hermes_home)

        # Build command - use -q for single query mode, -Q for quiet (programmatic)
        cmd = [
            str(self.hermes_cli),
            "-p", self.profile,
        ]
        # Pinned Hermes accepts the global model selector before the chat
        # subcommand. On resume this changes only the inference model; Hermes
        # keeps the same session history, memory and workflow state.
        if self.model_override:
            cmd.extend(["-m", self.model_override])
        cmd.extend([
            "chat",
            "-q", prompt,
            "-Q",  # Quiet mode for programmatic use
            "--source", "tool",
            "--max-turns", str(max_turns if max_turns is not None else self.max_turns),
        ])

        # This runner is fully non-interactive. Without Hermes's supported
        # headless approval flag, dangerous-command prompts wait for a TTY that
        # cannot exist and are denied after 60 seconds. This affects terminal
        # execution only; creative/native checkpoint decisions remain governed
        # by the job contract and must still be returned as structured blockers.
        if self.headless_auto_approve:
            cmd.append("--yolo")

        if session_id:
            cmd.extend(["--resume", session_id])
        for skill in expected_skills or []:
            cmd.extend(["--skills", skill])
        # Note: --parent-session is not supported in pinned Hermes CLI (5ecc079)
        # Parent/child relationships tracked in worker metadata instead
        logger = logging.getLogger("acd_worker.hermes_runner")
        logger.info("Running Hermes session with profile %s (prompt chars: %d)", self.profile, len(prompt))
        if self.model_override:
            logger.info("Using explicit Hermes model override: %s", self.model_override)
        if expected_skills:
            logger.info("Preloading skills: %s", ", ".join(expected_skills))

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.cwd) if self.cwd else None,
                check=False,
            )

            session_id = self._extract_session_id(result.stderr) or self._extract_session_id(result.stdout)
            error = self._redact(result.stderr) if result.returncode != 0 else None
            if result.returncode != 0 and session_id:
                diagnostic = self._session_failure_diagnostic(session_id)
                if diagnostic:
                    error = self._redact(f"{error or ''}\n{diagnostic}").strip()

            session_result = HermesSessionResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=error,
                returncode=result.returncode
            )

            # Try to extract session ID from output
            session_result.session_id = session_id

            # Parse artifacts from output
            session_result.artifacts = self._extract_artifacts(result.stdout)

            # Record in history
            self.session_history.append({
                "session_id": session_result.session_id,
                "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt,
                "success": session_result.success,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "requested_skills": expected_skills or [],
            })

            return session_result

        except subprocess.TimeoutExpired:
            return HermesSessionResult(
                success=False,
                error=f"Hermes session timed out after {self.timeout}s",
                returncode=124,
            )
        except Exception as e:
            return HermesSessionResult(
                success=False,
                error=f"Hermes execution failed: {e}",
                returncode=1,
            )

    @staticmethod
    def _redact(value: str) -> str:
        """Redact common credential forms before persisting/reporting stderr."""
        cleaned = value or ""
        patterns = (
            (r"(?i)(api[_-]?key\s*[=:]\s*)\S+", r"\1[REDACTED]"),
            (r"(?i)(authorization:\s*bearer\s+)\S+", r"\1[REDACTED]"),
            (r"\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{8,}\b", "[REDACTED]"),
        )
        for pattern, replacement in patterns:
            cleaned = re.sub(pattern, replacement, cleaned)
        return cleaned[-8000:]

    def _extract_session_id(self, output: str) -> Optional[str]:
        """Extract session ID from Hermes output."""
        import re
        patterns = [
            r"session[_\s]?id:\s*([A-Za-z0-9_-]{8,})",
            r"Session[:\s]+([A-Za-z0-9_-]{8,})",
            r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
        ]
        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _session_failure_diagnostic(self, session_id: str) -> str:
        """Return the final session-specific backend error from Hermes logs."""
        candidates = (
            self.profile_dir / "logs" / "errors.log",
            self.profile_dir / "logs" / "agent.log",
        )
        interesting = []
        for path in candidates:
            if not path.is_file():
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:]
            except OSError:
                continue
            for line in lines:
                lowered = line.lower()
                if session_id in line and any(token in lowered for token in (" error ", "failed", "resourceexhausted", "rate limit", "quota", " 503")):
                    interesting.append(line)
        return interesting[-1] if interesting else ""

    def _extract_artifacts(self, output: str) -> Dict:
        """Native artifacts stay in OpenMontage; stdout is not an artifact bus."""
        return {}

    def get_session_history(self) -> List[Dict]:
        """Get history of all sessions run."""
        return self.session_history
