#!/usr/bin/env python3
"""Render the real 12-second native bridge canary without Hermes.

This is a production-contract probe, not a fixture renderer. It authors a
small canonical OpenMontage project, generates only original local source
clips, invokes the same NativeExecutionBridge/ToolRegistry/video_compose path
as production, and runs the worker's independent delivery validators.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKER_ROOT / "src"))

from acd_worker.media_validation import FinalMediaValidator, OpenMontageArtifactValidator  # noqa: E402
from acd_worker.native_bridge import NativeExecutionBridge  # noqa: E402


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def make_clip(path: Path, text: str, accent: str, motion: int, font_size: int) -> None:
    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if not font.is_file():
        raise RuntimeError(f"Canary font is unavailable: {font}")
    path.parent.mkdir(parents=True, exist_ok=True)
    video_filter = ",".join((
        "color=c=0x041712:s=1280x720:r=30:d=4",
        "drawgrid=w=160:h=90:t=2:c=white@0.10",
        f"drawbox=x='mod(t*{motion}\\,1180)':y=80:w=100:h=560:color=0x{accent}@0.55:t=fill",
        "drawbox=x=80:y=70:w=1120:h=580:color=white@0.22:t=3",
        f"drawtext=fontfile={font}:text='{text}':fontcolor=white:fontsize={font_size}:x=(w-text_w)/2:y=(h-text_h)/2",
    ))
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", video_filter,
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0 or not path.is_file():
        raise RuntimeError(f"Canary source generation failed: {(result.stderr or result.stdout)[-2000:]}")


def proposal_packet() -> dict:
    concepts = []
    for concept_id, title, hook in (
        ("c1", "The Countdown", "Ninety minutes compress into one decisive dream."),
        ("c2", "Pitch Pulse", "Geometry becomes pressure, then purpose."),
        ("c3", "One Dream", "A restrained build resolves in one collective promise."),
    ):
        concepts.append({
            "id": concept_id,
            "title": title,
            "hook": hook,
            "narrative_structure": "journey",
            "visual_approach": "Original kinetic typography and animated football-pitch geometry.",
            "target_duration_seconds": 12,
            "key_points": ["Pressure accumulates", "Purpose resolves"],
            "why_this_works": "It creates a clear emotional escalation without borrowed footage.",
        })
    return {
        "version": "1.0",
        "concept_options": concepts,
        "selected_concept": {"concept_id": "c1", "rationale": "The cleanest tension-to-release structure."},
        "production_plan": {
            "pipeline": "cinematic",
            "stages": [],
            "renderer_family": "cinematic-trailer",
            "render_runtime": "remotion",
            "composition_mode": "templated",
            "delivery_promise": {
                "promise_type": "motion_led",
                "motion_required": True,
                "source_required": False,
                "tone_mode": "cinematic",
                "quality_floor": "presentable",
                "approved_fallback": None,
            },
        },
        "cost_estimate": {
            "total_estimated_usd": 0,
            "line_items": [{"tool": "video_compose", "operation": "offline Remotion render", "quantity": 1, "estimated_usd": 0}],
            "budget_cap_usd": 0,
            "budget_verdict": "within_budget",
        },
        "approval": {"status": "approved", "approved_budget_usd": 0},
    }


def author_project(project: Path) -> dict[str, Path]:
    if project.exists() and any(project.iterdir()):
        raise RuntimeError(f"Canary project must be absent or empty: {project}")
    artifacts = project / "artifacts"
    assets = project / "assets" / "video"
    renders = project / "renders"
    for directory in (artifacts, assets, renders, project / "football_emotion"):
        directory.mkdir(parents=True, exist_ok=True)
    write_json(project / "project.json", {
        "version": "1.0",
        "project_id": project.name,
        "title": "90 MINUTES. ONE DREAM.",
        "pipeline_type": "cinematic",
    })

    clip_specs = (
        ("opening", "90 MINUTES", "27E879", 230, 86),
        ("build", "ONE DREAM", "E8C547", 310, 86),
        ("resolve", "90 MINUTES. ONE DREAM.", "FFFFFF", 390, 58),
    )
    manifest_assets = []
    scenes = []
    cuts = []
    for index, (asset_id, text, accent, motion, font_size) in enumerate(clip_specs):
        path = assets / f"{asset_id}.mp4"
        make_clip(path, text, accent, motion, font_size)
        start = index * 4
        manifest_assets.append({
            "id": asset_id,
            "type": "video",
            "path": str(path),
            "source_tool": "offline_ffmpeg_asset_generator",
            "scene_id": f"s{index + 1}",
            "cost_usd": 0,
            "duration_seconds": 4,
            "resolution": "1280x720",
            "format": "mp4",
            "license": "Original generated geometry and typography",
        })
        scenes.append({
            "id": f"s{index + 1}",
            "type": "animation",
            "description": text,
            "start_seconds": start,
            "end_seconds": start + 4,
            "shot_intent": "Escalate from pressure to collective purpose.",
            "narrative_role": ("build_tension", "emotional_beat", "resolution")[index],
            "information_role": text,
            "hero_moment": index == 2,
            "shot_language": {
                "shot_size": ("wide", "medium", "close_up")[index],
                "camera_movement": ("dolly_in", "tracking_right", "zoom_in")[index],
                "lighting_key": "low_key",
                "depth_of_field": "deep",
                "color_temperature": "cool",
            },
        })
        cuts.append({
            "id": f"c{index + 1}",
            "source": asset_id,
            "in_seconds": 0,
            "out_seconds": 4,
            "speed": 1,
            "layer": "primary",
            "transition_in": "cut" if index == 0 else "fade",
            "transition_out": "cut" if index == 2 else "fade",
            "transition_duration": 0.25,
            "reason": "Authored football-emotion beat.",
        })

    payloads = {
        "proposal_packet": proposal_packet(),
        "scene_plan": {"version": "1.0", "scenes": scenes, "metadata": {"target_duration_seconds": 12}},
        "asset_manifest": {"version": "1.0", "assets": manifest_assets, "total_cost_usd": 0},
        "edit_decisions": {
            "version": "1.0",
            "cuts": cuts,
            "renderer_family": "cinematic-trailer",
            "render_runtime": "remotion",
            "composition_mode": "templated",
            "subtitles": {"enabled": False},
            "metadata": {
                "target_duration_seconds": 12,
                "proposal_render_runtime": "remotion",
                "acd_silence_plan": {
                    "intentional": True,
                    "rationale": "The contract canary explicitly approves silence to isolate native visual execution.",
                },
            },
        },
    }
    paths = {}
    for kind, payload in payloads.items():
        path = artifacts / f"{kind}.json"
        write_json(path, payload)
        paths[kind] = path
    stage_by_artifact = {
        "proposal_packet": "proposal",
        "scene_plan": "scene_plan",
        "asset_manifest": "assets",
        "edit_decisions": "edit",
    }
    approval_stages = {"proposal", "scene_plan", "assets"}
    for kind, stage in stage_by_artifact.items():
        write_json(project / f"checkpoint_{stage}.json", {
            "version": "1.0",
            "project_id": project.name,
            "pipeline_type": "cinematic",
            "stage": stage,
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checkpoint_policy": "guided",
            "human_approval_required": stage in approval_stages,
            "human_approved": stage in approval_stages,
            "artifacts": {kind: payloads[kind]},
        })
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the exact pinned OpenMontage native delivery canary")
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--openmontage-root", type=Path, default=WORKER_ROOT / "external" / "OpenMontage")
    parser.add_argument("--openmontage-python", type=Path)
    args = parser.parse_args()
    project = args.project_dir.expanduser().resolve()
    openmontage = args.openmontage_root.expanduser().resolve()
    if args.openmontage_python:
        os.environ["OPENMONTAGE_PYTHON"] = str(args.openmontage_python.expanduser().absolute())

    paths = author_project(project)
    request = {
        "pipeline": "cinematic",
        "artifacts": {kind: str(path) for kind, path in paths.items()},
        "output_path": str(project / "renders" / "final.mp4"),
        "output_profile": "generic_720p",
        "remotion_timeout_ms": 180000,
        "approved_silence": True,
        "approved_checkpoints": ["proposal", "scene_plan", "assets"],
    }
    bridge = NativeExecutionBridge(WORKER_ROOT, openmontage, project, timeout=480)
    result = bridge.execute(request)
    artifact_validation = OpenMontageArtifactValidator(
        project, openmontage, project / "football_emotion" / "acd_agent_result.json",
    ).validate(result.openmontage_artifacts, result.output_media)
    media_validation = [FinalMediaValidator(project, timeout=90).validate(item) for item in result.output_media]
    certificate = {
        "schema_version": "1.0",
        "valid": bool(artifact_validation.get("valid")) and any(item.get("valid") for item in media_validation),
        "fingerprint": result.fingerprint,
        "compatibility": result.compatibility,
        "output_media": result.output_media,
        "artifact_validation": artifact_validation,
        "media_validation": media_validation,
    }
    write_json(project / "football_emotion" / "native_canary_certificate.json", certificate)
    print(json.dumps(certificate, indent=2, sort_keys=True))
    return 0 if certificate["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
