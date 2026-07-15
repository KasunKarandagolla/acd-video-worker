"""Independent final-media validation owned by the ACD worker."""

from __future__ import annotations

import json
import hashlib
import math
import os
import subprocess
from pathlib import Path
from typing import Any

REQUIRED_OPENMONTAGE_ARTIFACTS = (
    "scene_plan",
    "asset_manifest",
    "edit_decisions",
    "render_report",
    "final_review",
)
OPENMONTAGE_PLANNING_ARTIFACTS = ("brief", "proposal_packet")


class OpenMontageArtifactValidator:
    """Verify native OpenMontage delivery evidence without owning its pipeline."""

    def __init__(self, project_root: Path, openmontage_root: Path, agent_result_path: Path):
        self.project_root = Path(project_root).expanduser().resolve()
        self.openmontage_root = Path(openmontage_root).expanduser().resolve()
        self.agent_result_path = Path(agent_result_path).expanduser().resolve()

    def validate(self, artifacts: list[dict[str, Any]], output_candidates: list[dict[str, Any]]) -> dict[str, Any]:
        evidence: dict[str, Any] = {"valid": False, "artifacts": [], "errors": []}
        if not isinstance(artifacts, list):
            evidence["errors"].append("openmontage_artifacts must be a list")
            return evidence

        by_kind: dict[str, Path] = {}
        for item in artifacts:
            kind = str(item.get("kind") or "") if isinstance(item, dict) else ""
            raw_path = item.get("path") if isinstance(item, dict) else None
            entry = {"kind": kind, "path": str(raw_path or ""), "valid": False}
            schema_path = self.openmontage_root / "schemas" / "artifacts" / f"{kind}.schema.json"
            if not isinstance(raw_path, str) or not raw_path.strip():
                entry["error"] = "artifact path is missing"
                evidence["artifacts"].append(entry)
                continue
            path = Path(raw_path).expanduser().resolve()
            entry["path"] = str(path)
            if path == self.agent_result_path:
                entry["error"] = "worker agent result cannot be claimed as an OpenMontage artifact"
                evidence["artifacts"].append(entry)
                continue
            if not kind or not schema_path.is_file():
                entry["error"] = "unsupported or non-canonical OpenMontage artifact kind"
                evidence["artifacts"].append(entry)
                continue
            if kind in by_kind:
                entry["error"] = "duplicate canonical artifact kind"
                evidence["artifacts"].append(entry)
                continue
            try:
                relative = path.relative_to(self.project_root)
            except ValueError:
                entry["error"] = "artifact is outside the approved project workspace"
                evidence["artifacts"].append(entry)
                continue
            if not relative.parts or relative.parts[0] != "artifacts":
                entry["error"] = "canonical OpenMontage artifacts must be under project artifacts/"
                evidence["artifacts"].append(entry)
                continue
            if not path.is_file():
                entry["error"] = "artifact file does not exist"
                evidence["artifacts"].append(entry)
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                entry["error"] = f"artifact/schema could not be read: {exc}"
                evidence["artifacts"].append(entry)
                continue
            schema_error = self._schema_error(schema_path, path)
            if schema_error:
                entry["error"] = f"native schema validation failed: {schema_error}"
                evidence["artifacts"].append(entry)
                continue
            entry["valid"] = True
            evidence["artifacts"].append(entry)
            by_kind[kind] = path

        missing = [kind for kind in REQUIRED_OPENMONTAGE_ARTIFACTS if kind not in by_kind]
        invalid_declared = [item for item in evidence["artifacts"] if not item.get("valid")]
        if invalid_declared:
            evidence["errors"].append("one or more declared OpenMontage artifacts are invalid")
        if missing:
            evidence["errors"].append("missing schema-valid native artifacts: " + ", ".join(missing))
            return evidence
        if not any(kind in by_kind for kind in OPENMONTAGE_PLANNING_ARTIFACTS):
            evidence["errors"].append("missing schema-valid native planning artifact: brief or proposal_packet")
            return evidence

        # Native JSON-schema validation is intentionally artifact-local. It
        # does not prove that edit_decisions references resolve through the
        # asset_manifest or that the declared media exists. Delivery must fail
        # closed on that cross-artifact handoff instead of allowing a renderer
        # crash (or a visually incomplete render) to masquerade as valid state.
        evidence["errors"].extend(self.cross_artifact_errors(by_kind))
        if evidence["errors"]:
            return evidence

        candidate_paths = {
            str(Path(item["path"]).expanduser().resolve())
            for item in output_candidates
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        }
        if not candidate_paths:
            evidence["errors"].append("no output candidate paths were declared")
            return evidence
        for candidate in candidate_paths:
            try:
                relative = Path(candidate).relative_to(self.project_root)
            except ValueError:
                evidence["errors"].append("output candidate is outside the OpenMontage project")
                return evidence
            if not relative.parts or relative.parts[0] != "renders":
                evidence["errors"].append("native deliverables must be under project renders/")
                return evidence

        render_report = json.loads(by_kind["render_report"].read_text(encoding="utf-8"))
        report_outputs = {
            str(self._resolve_artifact_reference(item.get("path"), by_kind["render_report"]))
            for item in render_report.get("outputs", [])
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        }
        if not candidate_paths.issubset(report_outputs):
            evidence["errors"].append("render_report does not reference every delivered output")
            return evidence

        report_hash = str((render_report.get("metadata") or {}).get("output_sha256") or "")
        if not report_hash:
            evidence["errors"].append("render_report lacks exact output SHA-256 lineage")
        for candidate in candidate_paths:
            actual_hash = self._sha256(Path(candidate)) if Path(candidate).is_file() else ""
            declared = next(
                (str(item.get("sha256") or "") for item in output_candidates if isinstance(item, dict) and str(Path(str(item.get("path") or "")).expanduser().resolve()) == candidate),
                "",
            )
            if not declared or declared != actual_hash or report_hash != actual_hash:
                evidence["errors"].append("candidate, render_report and rendered bytes do not share one SHA-256")

        final_review = json.loads(by_kind["final_review"].read_text(encoding="utf-8"))
        review_hash = str((final_review.get("metadata") or {}).get("output_sha256") or "")
        if not report_hash or review_hash != report_hash:
            evidence["errors"].append("final_review does not preserve the rendered output SHA-256")
        review_ref = render_report.get("final_review_ref")
        if not review_ref or self._resolve_artifact_reference(review_ref, by_kind["render_report"]) != by_kind["final_review"]:
            evidence["errors"].append("render_report does not link the declared final_review")
        reviewed_path = str(self._resolve_artifact_reference(final_review.get("output_path"), by_kind["final_review"]))
        checks = final_review.get("checks") or {}
        visual = checks.get("visual_spotcheck") or {}
        promise = checks.get("promise_preservation") or {}
        edit_decisions = json.loads(by_kind["edit_decisions"].read_text(encoding="utf-8"))
        if reviewed_path not in candidate_paths:
            evidence["errors"].append("final_review does not reference a delivered output")
        if final_review.get("status") != "pass" or final_review.get("recommended_action") != "present_to_user":
            evidence["errors"].append("final_review did not approve presentation")
        if int(visual.get("frames_sampled") or 0) < 4:
            evidence["errors"].append("final_review lacks the required four-frame visual spotcheck")
        if any(visual.get(key) is True for key in ("black_frames_detected", "broken_overlays", "missing_assets", "unreadable_text")):
            evidence["errors"].append("final_review reports a visual defect")
        if promise.get("delivery_promise_honored") is not True:
            evidence["errors"].append("final_review does not confirm delivery-promise preservation")
        if promise.get("runtime_swap_detected") is True or promise.get("silent_downgrade_detected") is True:
            evidence["errors"].append("final_review reports a runtime swap or silent downgrade")
        if promise.get("render_runtime_used") != edit_decisions.get("render_runtime"):
            evidence["errors"].append("final_review runtime does not match edit_decisions")
        if render_report.get("render_grammar") != edit_decisions.get("renderer_family"):
            evidence["errors"].append("render_report grammar does not match edit_decisions renderer family")

        evidence["valid"] = not evidence["errors"]
        return evidence

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def cross_artifact_errors(self, by_kind: dict[str, Path]) -> list[str]:
        manifest_path = by_kind["asset_manifest"]
        edit_path = by_kind["edit_decisions"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        edit = json.loads(edit_path.read_text(encoding="utf-8"))
        errors: list[str] = []
        asset_paths: dict[str, Path] = {}

        for asset in manifest.get("assets") or []:
            asset_id = str(asset.get("id") or "")
            if asset_id in asset_paths:
                errors.append(f"asset_manifest contains duplicate asset ID: {asset_id}")
                continue
            resolved = self._resolve_artifact_reference(asset.get("path"), manifest_path)
            asset_paths[asset_id] = resolved
            try:
                resolved.relative_to(self.project_root)
            except ValueError:
                errors.append(f"asset_manifest path is outside the project: {asset_id}")
                continue
            if not resolved.is_file() or resolved.stat().st_size <= 0:
                errors.append(f"asset_manifest media is missing or empty: {asset_id}")

        references: list[tuple[str, str]] = []
        for cut in edit.get("cuts") or []:
            references.append((f"cut {cut.get('id') or '<unknown>'}", str(cut.get("source") or "")))
        for overlay in edit.get("overlays") or []:
            references.append(("overlay", str(overlay.get("asset_id") or "")))
        audio = edit.get("audio") or {}
        for segment in (audio.get("narration") or {}).get("segments") or []:
            references.append(("narration", str(segment.get("asset_id") or "")))
        music = audio.get("music") or edit.get("music") or {}
        if music.get("asset_id"):
            references.append(("music", str(music["asset_id"])))
        for sfx in audio.get("sfx") or []:
            if sfx.get("asset_id"):
                references.append(("sfx", str(sfx["asset_id"])))
        subtitles = edit.get("subtitles") or {}
        if subtitles.get("enabled") and subtitles.get("source"):
            references.append(("subtitles", str(subtitles["source"])))

        for label, reference in references:
            if not reference:
                errors.append(f"edit_decisions {label} has an empty asset reference")
                continue
            if reference in asset_paths:
                if not asset_paths[reference].is_file():
                    errors.append(f"edit_decisions {label} references missing manifest media: {reference}")
                continue
            resolved = self._resolve_artifact_reference(reference, edit_path)
            try:
                resolved.relative_to(self.project_root)
            except ValueError:
                errors.append(f"edit_decisions {label} references a path outside the project: {reference}")
                continue
            if not resolved.is_file() or resolved.stat().st_size <= 0:
                errors.append(f"edit_decisions {label} references unknown asset ID or missing media: {reference}")

        return list(dict.fromkeys(errors))

    # Backward-compatible private alias for callers from the pre-bridge path.
    _cross_artifact_errors = cross_artifact_errors

    def _schema_error(self, schema_path: Path, artifact_path: Path) -> str:
        # Preserve the venv launcher path: resolving its symlink selects the
        # base interpreter and silently drops the environment's packages.
        python = Path(os.environ.get("OPENMONTAGE_PYTHON", self.openmontage_root / ".venv" / "bin" / "python")).expanduser().absolute()
        if not python.is_file():
            return "pinned OpenMontage Python environment is unavailable"
        script = (
            "import json,sys; from jsonschema import Draft202012Validator; "
            "schema=json.load(open(sys.argv[1], encoding='utf-8')); "
            "payload=json.load(open(sys.argv[2], encoding='utf-8')); "
            "errors=sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e:list(e.path)); "
            "print(errors[0].message if errors else ''); sys.exit(1 if errors else 0)"
        )
        try:
            result = subprocess.run(
                [str(python), "-c", script, str(schema_path), str(artifact_path)],
                capture_output=True,
                text=True,
                timeout=self.timeout if hasattr(self, "timeout") else 30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return str(exc)
        return "" if result.returncode == 0 else (result.stdout.strip() or result.stderr.strip() or "unknown schema error")[-1000:]

    def _resolve_artifact_reference(self, raw_path: Any, artifact_path: Path) -> Path:
        path = Path(str(raw_path or "")).expanduser()
        if path.is_absolute():
            return path.resolve()
        # Native schemas often store project-relative paths such as
        # renders/final.mp4 or projects/<id>/renders/final.mp4.
        direct = (self.project_root / path).resolve()
        if direct.exists():
            return direct
        parts = path.parts
        if self.project_root.name in parts:
            index = parts.index(self.project_root.name)
            return (self.project_root.joinpath(*parts[index + 1:])).resolve()
        for anchor in ("renders", "artifacts", "assets"):
            if anchor in parts:
                index = parts.index(anchor)
                return (self.project_root.joinpath(*parts[index:])).resolve()
        return (artifact_path.parent / path).resolve()


class FinalMediaValidator:
    def __init__(self, allowed_root: Path, ffprobe: str = "ffprobe", ffmpeg: str = "ffmpeg", timeout: int = 30):
        self.allowed_root = Path(allowed_root).expanduser().resolve()
        self.ffprobe = ffprobe
        self.ffmpeg = ffmpeg
        self.timeout = timeout

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

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
        actual_hash = self._sha256(path)
        evidence["sha256"] = actual_hash
        declared_hash = str(candidate.get("sha256") or "")
        if not declared_hash or declared_hash != actual_hash:
            evidence["error"] = "Output SHA-256 is missing or does not match the rendered bytes"
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

        visual = self._visual_probe(path, duration)
        evidence.update(visual)
        if visual.get("blocker_code"):
            return evidence
        if visual.get("visually_blank"):
            evidence["error"] = "Sampled frames contain no meaningful visual detail"
            return evidence
        if visual.get("visually_frozen"):
            evidence["error"] = "Sampled frames show no temporal change"
            return evidence

        has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
        if not has_audio and candidate.get("approved_silence") is not True:
            evidence["error"] = "Output has no audio and no explicit approved silence plan"
            return evidence

        evidence.update({
            "valid": True,
            "duration_seconds": duration,
            "width": int(video.get("width") or 0),
            "height": int(video.get("height") or 0),
            "video_codec": video.get("codec_name"),
            "has_audio": has_audio,
            "approved_silence": candidate.get("approved_silence") is True,
        })
        return evidence

    def _visual_probe(self, path: Path, duration: float) -> dict[str, Any]:
        # Five frames plus a maximum-delta test allowed a static or mostly
        # frozen render to pass when only one sampled transition changed. Use
        # a denser, whole-timeline distribution check instead.
        frame_count = 11
        interval = max(duration / max(frame_count - 1, 1), 0.1)
        width, height = 64, 36
        try:
            result = subprocess.run(
                [
                    self.ffmpeg, "-v", "error", "-i", str(path),
                    "-vf", f"fps=1/{interval},scale={width}:{height},format=gray",
                    "-frames:v", str(frame_count), "-f", "rawvideo", "pipe:1",
                ],
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
        except FileNotFoundError:
            return {"blocker_code": "FFMPEG_UNAVAILABLE", "error": "ffmpeg is required for visual validation"}
        except subprocess.TimeoutExpired:
            return {"error": "ffmpeg visual validation timed out"}
        if result.returncode != 0:
            return {"error": "ffmpeg could not sample output frames"}
        frame_size = width * height
        frames = [result.stdout[offset:offset + frame_size] for offset in range(0, len(result.stdout), frame_size)]
        frames = [frame for frame in frames if len(frame) == frame_size]
        return self._analyze_frames(frames)

    @staticmethod
    def _analyze_frames(frames: list[bytes]) -> dict[str, Any]:
        """Analyze uniformly sampled 8-bit grayscale frames.

        This pure function makes the validator failure-injectable: tests can
        prove that a detailed still, an animated intro followed by a freeze,
        and a frozen ending are rejected without invoking ffmpeg.
        """
        if not frames:
            return {
                "visually_blank": True,
                "visually_frozen": True,
                "sampled_frames": 0,
                "visual_detail_score": 0.0,
                "temporal_change_score": 0.0,
                "temporal_change_distribution": [],
            }
        frame_size = len(frames[0])
        if frame_size <= 0 or any(len(frame) != frame_size for frame in frames):
            return {
                "visually_blank": True,
                "visually_frozen": True,
                "sampled_frames": 0,
                "visual_detail_score": 0.0,
                "temporal_change_score": 0.0,
                "temporal_change_distribution": [],
                "error": "Visual samples have inconsistent frame sizes",
            }
        deviations = []
        ranges = []
        for frame in frames:
            mean = sum(frame) / len(frame)
            deviations.append(math.sqrt(sum((pixel - mean) ** 2 for pixel in frame) / len(frame)))
            ranges.append(max(frame) - min(frame))
        detail = max(deviations)
        changes = []
        for previous, current in zip(frames, frames[1:]):
            changes.append(sum(abs(a - b) for a, b in zip(previous, current)) / frame_size)
        change_threshold = 0.5
        changed = [value >= change_threshold for value in changes]
        required_changes = max(2, math.ceil(len(changes) * 0.35)) if changes else 0
        changing_intervals = sum(changed)
        segment_coverage = []
        if changes:
            for segment in range(3):
                start = math.floor(segment * len(changes) / 3)
                end = math.floor((segment + 1) * len(changes) / 3)
                if segment == 2:
                    end = len(changes)
                segment_coverage.append(any(changed[start:end]))
        temporal = sum(changes) / len(changes) if changes else 0.0
        frozen_ending = len(changes) >= 2 and not any(changed[-2:])
        frozen = (
            len(frames) > 1
            and (
                changing_intervals < required_changes
                or not all(segment_coverage)
                or frozen_ending
            )
        )
        return {
            "sampled_frames": len(frames),
            "visual_detail_score": round(detail, 3),
            "visual_luma_range": max(ranges),
            "temporal_change_score": round(temporal, 3),
            "temporal_change_peak": round(max(changes), 3) if changes else 0.0,
            "temporal_change_distribution": [round(value, 3) for value in changes],
            "changing_intervals": changing_intervals,
            "required_changing_intervals": required_changes,
            "temporal_segment_coverage": segment_coverage,
            "frozen_ending": frozen_ending,
            "visually_blank": detail < 2.0 or max(ranges) < 12,
            "visually_frozen": frozen,
        }
