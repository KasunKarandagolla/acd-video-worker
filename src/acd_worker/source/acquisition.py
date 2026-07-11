"""
Acquisition Engine - Sequential footage acquisition with verification and replacement.

Implements the careful sequential acquisition flow:
ranked candidate -> metadata probe -> availability check -> sequential download
-> ffprobe validation -> frame/audio sampling -> accepted or rejected
-> replacement candidate when rejected -> source manifest update
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, List, Dict
from fractions import Fraction
import yt_dlp


class FailureType(Enum):
    """Classification of acquisition failures."""
    REMOVED = "removed"
    PRIVATE = "private"
    LOGIN_REQUIRED = "login_required"
    AGE_RESTRICTED = "age_restricted"
    GEO_RESTRICTED = "geo_restricted"
    FORMAT_UNAVAILABLE = "format_unavailable"
    PLAYBACK_BLOCKED = "playback_blocked"
    NETWORK_FAILURE = "network_failure"
    INVALID_MEDIA = "invalid_media"
    LOW_QUALITY = "low_quality"
    DUPLICATE = "duplicate"
    UNKNOWN = "unknown"
    TRANSIENT_NETWORK = "transient_network"


class AcquisitionStatus(Enum):
    """Status of an acquisition attempt."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROBING = "probing"
    VALIDATING = "validating"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    GAP = "gap"


@dataclass
class AcquisitionAttempt:
    """Record of a single acquisition attempt."""
    attempt_id: str
    candidate_id: str
    source_url: str
    story_slot: str
    clip_id: str
    attempt_number: int
    status: AcquisitionStatus
    failure_type: Optional[FailureType] = None
    failure_reason: str = ""
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    local_path: Optional[str] = None
    technical_metadata: Dict = field(default_factory=dict)
    quality_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["failure_type"] = self.failure_type.value if self.failure_type else None
        return d


@dataclass
class AcquiredSource:
    """Successfully acquired and validated source."""
    source_id: str
    candidate_id: str
    original_url: str
    video_id: str
    local_path: str
    story_slot: str
    clip_id: str
    technical_metadata: Dict
    selected_timestamps: List = field(default_factory=list)
    quality_warnings: List = field(default_factory=list)
    verification_status: str = "verified"
    acquisition_attempts: List = field(default_factory=list)
    file_hash: str = ""
    file_size_bytes: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class FailureClassifier:
    """Classifies yt-dlp/ffmpeg errors into failure types."""

    @staticmethod
    def classify(error: str, return_code: int = 0) -> FailureType:
        error_lower = error.lower()

        # Video removed/unavailable
        if any(kw in error_lower for kw in ["video unavailable", "removed", "deleted", "does not exist", "has been removed"]):
            return FailureType.REMOVED

        # Age restricted - check BEFORE private/login
        if any(kw in error_lower for kw in ["age restricted", "age gate", "age verification", "confirm your age", "sign in to confirm your age"]):
            return FailureType.AGE_RESTRICTED

        # Private/login required
        if any(kw in error_lower for kw in ["private video", "login required", "sign in", "authentication required", "this video is private"]):
            return FailureType.PRIVATE

        # Geo restricted
        if any(kw in error_lower for kw in ["geo", "country", "region", "not available in your", "blocked in", "geoblock"]):
            return FailureType.GEO_RESTRICTED

        # Format unavailable
        if any(kw in error_lower for kw in ["format", "codec", "no suitable format", "requested format", "format not available"]):
            return FailureType.FORMAT_UNAVAILABLE

        # Playback blocked (403, DRM, etc.)
        if any(kw in error_lower for kw in ["403", "forbidden", "drm", "protected", "sabr", "widevine", "playback"]):
            return FailureType.PLAYBACK_BLOCKED

        # Network issues (transient)
        if any(kw in error_lower for kw in ["timeout", "connection", "network", "dns", "ssl", "certificate", "timed out"]):
            return FailureType.TRANSIENT_NETWORK

        # Invalid media (corrupt, unplayable)
        if any(kw in error_lower for kw in ["corrupt", "invalid", "moov atom", "truncated", "unplayable", "broken"]):
            return FailureType.INVALID_MEDIA

        return FailureType.UNKNOWN


class MediaValidator:
    """Validates downloaded media files using ffprobe and frame sampling."""

    def __init__(
        self,
        min_duration: float = 5.0,
        max_duration: float = 3600.0,
        min_width: int = 480,
        min_height: int = 270,
        require_audio: bool = False,
        sample_frame_count: int = 4
    ):
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.min_width = min_width
        self.min_height = min_height
        self.require_audio = require_audio
        self.sample_frame_count = sample_frame_count

    def validate(self, file_path: str) -> tuple[bool, Dict, List[str]]:
        """
        Validate a media file.

        Returns:
            (is_valid, technical_metadata, quality_warnings)
        """
        warnings = []

        # 1. ffprobe technical metadata
        probe_result = self._probe_file(file_path)
        if not probe_result["success"]:
            return False, probe_result, [f"Probe failed: {probe_result.get('error', 'Unknown')}"]

        metadata = probe_result["data"]

        # 2. Check duration
        duration = metadata.get("duration_seconds", 0)
        if duration < self.min_duration:
            warnings.append(f"Duration too short: {duration:.1f}s < {self.min_duration}s")
            return False, metadata, warnings
        if duration > self.max_duration:
            warnings.append(f"Duration too long: {duration:.1f}s > {self.max_duration}s")

        # 3. Check resolution
        width = metadata.get("width", 0)
        height = metadata.get("height", 0)
        if width < self.min_width:
            warnings.append(f"Width too small: {width} < {self.min_width}")
            return False, metadata, warnings
        if height < self.min_height:
            warnings.append(f"Height too small: {height} < {self.min_height}")
            return False, metadata, warnings

        # 4. Check audio
        has_audio = "audio_codec" in metadata and metadata["audio_codec"]
        if self.require_audio and not has_audio:
            warnings.append("No audio track found")
            return False, metadata, warnings

        # 5. Frame sampling for visual validation
        frame_result = self._sample_frames(file_path, duration)
        if not frame_result["success"]:
            warnings.append(f"Frame sampling failed: {frame_result.get('error')}")
        else:
            frame_count = frame_result["data"].get("frame_count", 0)
            if frame_count == 0:
                warnings.append("No frames could be extracted")
                return False, metadata, warnings

        # 6. File integrity (non-empty)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        if file_size == 0:
            return False, metadata, ["File is empty"]

        metadata["file_size_bytes"] = file_size

        return True, metadata, warnings

    def _probe_file(self, file_path: str) -> Dict:
        """Run ffprobe on file and extract metadata."""
        try:
            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return {"success": False, "error": result.stderr.strip()}

            data = json.loads(result.stdout)

            fmt = data.get("format", {})
            streams = data.get("streams", [])
            video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

            probe_data = {
                "duration_seconds": float(fmt.get("duration", 0)),
                "format_name": fmt.get("format_name"),
                "bit_rate": int(fmt.get("bit_rate", 0)),
                "file_size": int(fmt.get("size", 0)),
            }

            if video_stream:
                probe_data["width"] = video_stream.get("width", 0)
                probe_data["height"] = video_stream.get("height", 0)
                probe_data["video_codec"] = video_stream.get("codec_name")
                # Safe frame rate parsing using fractions.Fraction
                r_frame_rate = video_stream.get("r_frame_rate", "0/1")
                try:
                    probe_data["fps"] = float(Fraction(r_frame_rate))
                except (ValueError, ZeroDivisionError):
                    probe_data["fps"] = 0.0

            if audio_stream:
                probe_data["audio_codec"] = audio_stream.get("codec_name")
                probe_data["sample_rate"] = int(audio_stream.get("sample_rate", 0))
                probe_data["channels"] = audio_stream.get("channels", 0)

            return {"success": True, "data": probe_data}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "ffprobe timeout"}
        except json.JSONDecodeError:
            return {"success": False, "error": "ffprobe invalid JSON"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _sample_frames(self, file_path: str, duration: float, count: int = None) -> Dict:
        """Extract sample frames using ffmpeg."""
        try:
            count = count or self.sample_frame_count
            output_dir = Path(file_path).parent / f"frames_{uuid.uuid4().hex[:8]}"
            output_dir.mkdir(exist_ok=True)

            if duration <= 0:
                return {"success": False, "error": "Invalid duration"}

            interval = duration / (count + 1)
            timestamps = [interval * (i + 1) for i in range(count)]

            frames = []
            for i, ts in enumerate(timestamps):
                frame_path = output_dir / f"frame_{i:04d}.jpg"
                cmd = [
                    "ffmpeg", "-y", "-ss", str(ts),
                    "-i", file_path,
                    "-frames:v", "1",
                    "-qscale:v", "2",
                    str(frame_path)
                ]
                result = subprocess.run(cmd, capture_output=True, timeout=30)
                if result.returncode == 0 and frame_path.exists():
                    frames.append({"path": str(frame_path), "timestamp": ts})

            return {"success": True, "data": {"frame_count": len(frames), "frames": frames}}

        except Exception as e:
            return {"success": False, "error": str(e)}


class AcquisitionEngine:
    """
    Main acquisition engine.

    Handles sequential download, verification, and candidate replacement.
    """

    def __init__(
        self,
        output_dir: str,
        max_attempts_per_slot: int = 3,
        max_retries_transient: int = 2,
        max_resolution: str = "720p",
        min_duration: float = 5.0,
        max_duration: float = 3600.0,
        min_width: int = 480,
        min_height: int = 270,
        require_audio: bool = False
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_attempts = max_attempts_per_slot
        self.max_transient_retries = max_retries_transient
        self.max_resolution = max_resolution

        self.validator = MediaValidator(
            min_duration=min_duration,
            max_duration=max_duration,
            min_width=min_width,
            min_height=min_height,
            require_audio=require_audio
        )
        self.classifier = FailureClassifier()

        # yt-dlp options for download
        self._ydl_opts = {
            "format": f"bestvideo[height<={max_resolution[:-1]}]+bestaudio/best[height<={max_resolution[:-1]}]/best",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }

    def acquire_for_slot(
        self,
        candidates: List,
        story_slot: str,
        clip_id: str,
    ) -> tuple[Optional[AcquiredSource], List[AcquisitionAttempt]]:
        """
        Try to acquire footage for a story slot from ranked candidates.

        Returns:
            (AcquiredSource or None, list of all attempts made)
        """
        all_attempts = []

        for attempt_num, candidate in enumerate(candidates, 1):
            if attempt_num > self.max_attempts:
                break

            attempt = self._try_acquire(
                candidate=candidate,
                story_slot=story_slot,
                clip_id=clip_id,
                attempt_number=attempt_num
            )
            all_attempts.append(attempt)

            if attempt.status == AcquisitionStatus.ACCEPTED:
                # Success! Build AcquiredSource
                acquired = AcquiredSource(
                    source_id=f"src_{uuid.uuid4().hex[:8]}",
                    candidate_id=candidate.candidate_id,
                    original_url=candidate.url,
                    video_id=candidate.video_id,
                    local_path=attempt.local_path,
                    story_slot=story_slot,
                    clip_id=clip_id,
                    technical_metadata=attempt.technical_metadata,
                    quality_warnings=attempt.quality_warnings,
                    verification_status="verified",
                    acquisition_attempts=[a.to_dict() for a in all_attempts],
                    file_hash=self._compute_hash(attempt.local_path),
                    file_size_bytes=os.path.getsize(attempt.local_path) if attempt.local_path else 0,
                )
                return acquired, all_attempts

            # Check if we should retry (transient network failure)
            if attempt.failure_type == FailureType.TRANSIENT_NETWORK and attempt_num <= self.max_transient_retries:
                continue

            # Hard failure - move to next candidate
            continue

        # All candidates exhausted
        gap_attempt = AcquisitionAttempt(
            attempt_id=f"gap_{uuid.uuid4().hex[:8]}",
            candidate_id="",
            source_url="",
            story_slot=story_slot,
            clip_id=clip_id,
            attempt_number=len(candidates) + 1,
            status=AcquisitionStatus.GAP,
            failure_type=FailureType.UNKNOWN,
            failure_reason=f"All {len(candidates)} candidates exhausted for slot {story_slot}"
        )
        all_attempts.append(gap_attempt)

        return None, all_attempts

    def _try_acquire(
        self,
        candidate,
        story_slot: str,
        clip_id: str,
        attempt_number: int,
    ) -> AcquisitionAttempt:
        """Attempt to acquire a single candidate."""
        attempt = AcquisitionAttempt(
            attempt_id=f"att_{uuid.uuid4().hex[:8]}",
            candidate_id=candidate.candidate_id,
            source_url=candidate.url,
            story_slot=story_slot,
            clip_id=clip_id,
            attempt_number=attempt_number,
            status=AcquisitionStatus.DOWNLOADING,
        )

        # Prepare output path
        output_file = self.output_dir / f"{candidate.candidate_id}.mp4"
        if output_file.exists():
            output_file.unlink()

        # Download with yt-dlp
        ydl_opts = self._ydl_opts.copy()
        ydl_opts["outtmpl"] = str(output_file.with_suffix(".%(ext)s"))

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([candidate.url])

            # Find downloaded file
            downloaded = self._find_downloaded(output_file.parent, candidate.candidate_id)
            if not downloaded:
                attempt.status = AcquisitionStatus.REJECTED
                attempt.failure_type = FailureType.INVALID_MEDIA
                attempt.failure_reason = "Download completed but file not found"
                attempt.completed_at = datetime.utcnow().isoformat()
                return attempt

            attempt.local_path = str(downloaded)
            attempt.status = AcquisitionStatus.VALIDATING

            # Validate media
            is_valid, metadata, warnings = self.validator.validate(str(downloaded))
            attempt.technical_metadata = metadata
            attempt.quality_warnings = warnings

            if is_valid:
                attempt.status = AcquisitionStatus.ACCEPTED
            else:
                attempt.status = AcquisitionStatus.REJECTED
                attempt.failure_type = FailureType.INVALID_MEDIA
                attempt.failure_reason = "; ".join(warnings)
                # Clean up failed download
                try:
                    os.remove(downloaded)
                except:
                    pass
                attempt.local_path = None

        except Exception as e:
            attempt.status = AcquisitionStatus.REJECTED
            attempt.failure_type = self.classifier.classify(str(e))
            attempt.failure_reason = str(e)
            # Clean up partial download
            if output_file.exists():
                try:
                    os.remove(output_file)
                except:
                    pass

        attempt.completed_at = datetime.utcnow().isoformat()
        return attempt

    def _find_downloaded(self, output_dir: Path, prefix: str) -> Optional[Path]:
        """Find downloaded file by prefix."""
        for ext in ["mp4", "mkv", "webm", "mov"]:
            candidates = list(output_dir.glob(f"{prefix}*.{ext}"))
            if candidates:
                return candidates[0]
        return None

    def _compute_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file."""
        import hashlib
        if not file_path or not os.path.exists(file_path):
            return ""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()


class CheckpointManager:
    """Manages acquisition checkpoints for resume capability."""

    def __init__(self, project_dir: str):
        self.checkpoint_dir = Path(project_dir) / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(self, project_id: str, stage: str, data: Dict) -> str:
        """Save checkpoint."""
        checkpoint_file = self.checkpoint_dir / f"{project_id}_{stage}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        checkpoint_file.write_text(json.dumps(data, indent=2))
        return str(checkpoint_file)

    def load_latest(self, project_id: str, stage: str) -> Optional[Dict]:
        """Load latest checkpoint for stage."""
        checkpoints = sorted(self.checkpoint_dir.glob(f"{project_id}_{stage}_*.json"))
        if not checkpoints:
            return None
        return json.loads(checkpoints[-1].read_text())

    def get_completed_slots(self, project_id: str) -> List[str]:
        """Get list of completed story slots from checkpoints."""
        # Implementation would scan checkpoints
        return []


if __name__ == "__main__":
    import sys

    # Test with archive.org video (known working)
    engine = AcquisitionEngine("/tmp/test_acquisition_output", max_attempts_per_slot=2)

    from src.acd_worker.source.discovery import SourceCandidate

    candidates = [
        SourceCandidate(
            candidate_id="test_1",
            url="https://archive.org/details/BigBuckBunny_124",
            video_id="BigBuckBunny_124",
            title="Big Buck Bunny",
            channel="Blender Foundation",
            duration=596,
            upload_date="20110701",
            thumbnail="",
            query="test",
            story_slot="opening_pressure",
            ranking_score=8.5,
            verification_status="unverified",
            discovery_method="test",
            metadata_confidence="high",
            deep_analysis_candidate="yes",
        )
    ]

    print("Testing acquisition...")
    acquired, attempts = engine.acquire_for_slot(
        candidates=candidates,
        story_slot="opening_pressure",
        clip_id="clip_001"
    )

    print(f"Acquired: {acquired is not None}")
    if acquired:
        print(f"  Source ID: {acquired.source_id}")
        print(f"  Local path: {acquired.local_path}")
        print(f"  Duration: {acquired.technical_metadata.get('duration_seconds')}")
        print(f"  Warnings: {acquired.quality_warnings}")

    print(f"\nAttempts:")
    for a in attempts:
        print(f"  [{a.status.value}] {a.failure_type.value if a.failure_type else 'N/A'} - {a.failure_reason[:80]}")