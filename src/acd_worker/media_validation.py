"""Independent final-media validation owned by the ACD worker."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


class FinalMediaValidator:
    def __init__(self, allowed_root: Path, ffprobe: str = "ffprobe", timeout: int = 30):
        self.allowed_root = Path(allowed_root).expanduser().resolve()
        self.ffprobe = ffprobe
        self.timeout = timeout

    def validate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        raw_path = candidate.get("path")
        evidence: dict[str, Any] = {"path": str(raw_path or ""), "valid": False}
        if not isinstance(raw_path, str) or not raw_path.strip():
            evidence["error"] = "Output candidate has no path"
            return evidence

        path = Path(raw_path).expanduser().resolve()
        evidence["path"] = str(path)
        try:
            path.relative_to(self.allowed_root)
        except ValueError:
            evidence["error"] = "Output path is outside the approved OpenMontage project directory"
            return evidence
        if not path.is_file():
            evidence["error"] = "Output file does not exist"
            return evidence
        evidence["size_bytes"] = path.stat().st_size
        if evidence["size_bytes"] <= 0:
            evidence["error"] = "Output file is empty"
            return evidence

        try:
            result = subprocess.run(
                [self.ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except FileNotFoundError:
            evidence["error"] = "ffprobe is not installed"
            evidence["blocker_code"] = "FFPROBE_UNAVAILABLE"
            return evidence
        except subprocess.TimeoutExpired:
            evidence["error"] = "ffprobe timed out"
            return evidence

        if result.returncode != 0:
            evidence["error"] = "ffprobe rejected the output media"
            evidence["ffprobe_returncode"] = result.returncode
            return evidence
        try:
            probe = json.loads(result.stdout)
        except json.JSONDecodeError:
            evidence["error"] = "ffprobe returned malformed JSON"
            return evidence

        streams = probe.get("streams") or []
        video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        if not video:
            evidence["error"] = "Output has no video stream"
            return evidence
        try:
            duration = float((probe.get("format") or {}).get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0
        if duration <= 0:
            evidence["error"] = "Output duration is not positive"
            return evidence

        evidence.update({
            "valid": True,
            "duration_seconds": duration,
            "width": int(video.get("width") or 0),
            "height": int(video.get("height") or 0),
            "video_codec": video.get("codec_name"),
            "has_audio": any(stream.get("codec_type") == "audio" for stream in streams),
        })
        return evidence
