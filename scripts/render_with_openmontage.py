#!/usr/bin/env python3
"""OpenMontage render integration — real pipeline selection + tool invocation.

Based on the actual pinned OpenMontage repo contract:
- Pipeline manifests in pipeline_defs/*.yaml define stages, tools, and skills
- lib/pipeline_loader.load_pipeline(name) loads and validates manifests
- tools/tool_registry.py: ToolRegistry with discover(), support_envelope(), provider_menu()
- tools.video.video_compose: real composition tool with input_schema + execute()
- lib/checkpoint.py: init_project(), write_checkpoint(), validate_checkpoint()
- schemas/artifacts: validate_artifact() for canonical artifacts

For this football current-event workflow:
- Pipeline: clip-factory (multi-clip extraction for social distribution)
- Tool: video_compose (FFmpeg-based composition)
"""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _ensure_openmontage() -> Path:
    om_path = BASE_DIR / "external" / "OpenMontage"
    if not om_path.is_dir():
        raise RuntimeError(f"OpenMontage not found at {om_path}")
    pipeline_defs = om_path / "pipeline_defs"
    if not pipeline_defs.is_dir():
        raise RuntimeError(f"OpenMontage pipeline_defs not found at {pipeline_defs}")
    return om_path


def _select_pipeline(om_path: Path, job: dict) -> dict:
    """Select a real pipeline manifest from OpenMontage's pipeline_defs."""
    result = {
        "candidates": [],
        "selected": None,
        "selection_reason": None,
        "manifest": None,
    }
    pipeline_defs = om_path / "pipeline_defs"
    yamls = sorted(pipeline_defs.glob("*.yaml"))
    result["candidates"] = [p.stem for p in yamls]

    import yaml

    video_type = (job.get("video_type") or "").lower()
    theme = (job.get("theme") or "").lower()

    priority = ["clip-factory", "cinematic", "documentary-montage", "hybrid"]
    if "highlight" in video_type or "football" in theme or "sport" in theme:
        priority = ["clip-factory", "cinematic", "hybrid", "documentary-montage"]

    for name in priority:
        if name in result["candidates"]:
            manifest_path = pipeline_defs / f"{name}.yaml"
            if manifest_path.is_file():
                with open(manifest_path) as f:
                    manifest = yaml.safe_load(f)
                result["selected"] = name
                result["manifest"] = manifest
                result["selection_reason"] = (
                    f"Pipeline '{name}' selected for {video_type or theme} workflow. "
                    f"Description: {manifest.get('description', 'N/A')[:200]}"
                )
                break

    if not result["selected"] and result["candidates"]:
        name = result["candidates"][0]
        manifest_path = pipeline_defs / f"{name}.yaml"
        if manifest_path.is_file():
            with open(manifest_path) as f:
                manifest = yaml.safe_load(f)
            result["selected"] = name
            result["manifest"] = manifest
            result["selection_reason"] = f"First available pipeline: {name}"

    return result


def _load_pipeline_through_loader(om_path: Path, pipeline_name: str) -> dict:
    """Load pipeline through OpenMontage's actual pipeline loader."""
    result = {"loaded": False, "error": None, "manifest": None, "stages": [], "required_tools": set()}
    sys.path.insert(0, str(om_path))
    try:
        from lib.pipeline_loader import load_pipeline, list_pipelines, get_stage_order, get_required_tools, get_stage_skill

        manifest = load_pipeline(pipeline_name)
        result["loaded"] = True
        result["manifest"] = manifest
        result["stages"] = get_stage_order(manifest, include_sub_stages=True)
        result["required_tools"] = list(get_required_tools(manifest))
        result["all_pipelines"] = list_pipelines()

        for stage_name in get_stage_order(manifest):
            skill_ref = get_stage_skill(manifest, stage_name)
            result.setdefault("stage_skills", {})[stage_name] = skill_ref
    except Exception as e:
        result["error"] = str(e)[:300]
    return result


def _run_registry_discovery(om_path: Path, required_tools: list = None) -> dict:
    """Run the actual OpenMontage tool registry discovery.

    Deterministic selection:
    1. Look for registered tool matching a required_tools entry (from manifest)
    2. Look for any tool with 'compose' or 'edit' in its name (prefer exact match)
    3. Look for 'video_compose' by exact name
    4. If none found, block — never select the first arbitrary tool
    """
    result = {
        "discovery_ran": False,
        "registered_tools": [],
        "support_envelope": {},
        "provider_menu": {},
        "selected_compose_tool": None,
        "compose_tool_support_status": None,
    }
    sys.path.insert(0, str(om_path))
    try:
        from tools.base_tool import BaseTool
        from tools.tool_registry import registry

        discovered = registry.discover("tools")
        result["discovery_ran"] = True
        result["registered_tools"] = registry.list_all()

        envelope = registry.support_envelope()
        result["support_envelope"] = envelope

        provider_menu = registry.provider_menu()
        result["provider_menu"] = provider_menu

        required_tools = required_tools or []

        # Priority 1: exact match against manifest-required tools
        for rt in required_tools:
            if rt in result["registered_tools"]:
                result["selected_compose_tool"] = rt
                result["compose_tool_support_status"] = "matched_manifest_required"
                return result

        # Priority 2: compose or edit tool (prefer exact name match)
        compose_tools = [t for t in result["registered_tools"] if "compose" in t.lower() or "edit" in t.lower()]
        if compose_tools:
            result["selected_compose_tool"] = compose_tools[0]
            result["compose_tool_support_status"] = "matched_compose_edit_name"
            return result

        # Priority 3: exact video_compose
        if "video_compose" in result["registered_tools"]:
            result["selected_compose_tool"] = "video_compose"
            result["compose_tool_support_status"] = "matched_video_compose_name"
            return result

        # No compatible tool — block
        result["compose_tool_support_status"] = "blocked_no_compatible_tool"

    except Exception as e:
        result["error"] = str(e)[:300]
        result["compose_tool_support_status"] = "blocked_discovery_error"

    return result


def _use_openmontage_checkpoints(om_path: Path, run_id: str, pipeline_name: str, run_dir: Path) -> dict:
    """Use OpenMontage checkpointing for pipeline stage tracking."""
    result = {"project_initialized": False, "checkpoints_written": [], "checkpoints_read": []}
    sys.path.insert(0, str(om_path))
    try:
        from lib.checkpoint import init_project, write_checkpoint, read_checkpoint, get_completed_stages
        om_path_resolved = om_path.resolve()
        pipeline_dir = om_path_resolved / "projects"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        init_project(
            project_id=run_id,
            title=f"ACD Video Run {run_id}",
            pipeline_type=pipeline_name,
            pipeline_dir=pipeline_dir,
        )
        result["project_initialized"] = True
        result["pipeline_dir"] = str(pipeline_dir)

        cp = write_checkpoint(
            pipeline_dir=pipeline_dir,
            project_id=run_id,
            stage="idea",
            status="completed",
            artifacts={
                "brief": {"title": run_id, "theme": "football current-event", "format": "short-form-video"},
                "decision_log": {"decisions": [{"decision_id": "pipeline_selection", "choice": pipeline_name}]},
            },
            pipeline_type=pipeline_name,
        )
        result["checkpoints_written"].append("idea")
        result["last_checkpoint"] = str(cp)

        completed = get_completed_stages(pipeline_dir, run_id, pipeline_name)
        result["completed_stages"] = completed
    except Exception as e:
        result["error"] = str(e)[:300]

    return result


def _compose_via_registered_tool(om_path: Path, assets_dir: Path, output_dir: Path, compose_tool_name: str = "video_compose") -> dict:
    """Invoke composition through an OpenMontage registered tool."""
    result = {
        "attempted": False,
        "success": False,
        "tool_used": None,
        "output_path": None,
        "error": None,
    }

    sys.path.insert(0, str(om_path))
    try:
        from tools.tool_registry import registry
        registry.ensure_discovered()
    except Exception as e:
        result["error"] = f"Registry discovery: {e}"
        return result

    video_files = sorted([
        f for f in assets_dir.iterdir()
        if f.is_file() and f.suffix in (".mp4", ".mkv", ".webm", ".mov")
    ])

    if not video_files:
        result["error"] = "No video files to compose"
        return result

    output_path = output_dir / "final_openmontage_render.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tool = registry.get(compose_tool_name)
    if tool is None:
        result["error"] = f"Compose tool '{compose_tool_name}' not registered in OpenMontage registry"
        return result

    result["tool_used"] = compose_tool_name
    result["attempted"] = True

    cuts = []
    for vf in video_files[:3]:
        cuts.append({
            "source": str(vf),
            "in_seconds": 0,
            "out_seconds": min(20, 60 // max(len(video_files[:3]), 1)),
            "speed": 1.0,
        })

    edit_decisions = {
        "cuts": cuts,
        "metadata": {"compose_target": {"width": 1920, "height": 1080, "fit": "pad"}},
    }

    try:
        tool_result = tool.execute({
            "operation": "compose",
            "edit_decisions": edit_decisions,
            "output_path": str(output_path),
            "codec": "libx264",
            "crf": 23,
            "preset": "fast",
        })
        result["success"] = tool_result.success
        if tool_result.success:
            result["output_path"] = str(output_path)
        else:
            result["error"] = tool_result.error[:500] if tool_result.error else "Tool execute returned failure"
    except Exception as e:
        result["error"] = f"video_compose.execute() raised: {e}"

    return result


def _ffmpeg_debug_fallback(assets_dir: Path, output_dir: Path) -> dict:
    """Raw FFmpeg concat as debug fallback only."""
    result = {
        "attempted": False,
        "success": False,
        "output_path": None,
        "error": None,
    }

    video_files = sorted([
        f for f in assets_dir.iterdir()
        if f.is_file() and f.suffix in (".mp4", ".mkv", ".webm", ".mov")
    ])
    if not video_files:
        result["error"] = "No video files"
        return result

    output_path = output_dir / "fallback_render_attempt.mp4"
    video_list = video_files[:3]

    concat_inputs = []
    for vf in video_list:
        concat_inputs.extend(["-i", str(vf)])

    cmd = (
        ["ffmpeg", "-y"]
        + concat_inputs
        + ["-filter_complex",
           f"concat=n={len(video_list)}:v=1:a=0 [v]",
           "-map", "[v]",
           "-c:v", "libx264", "-preset", "fast", "-crf", "23",
           "-c:a", "aac", "-b:a", "128k",
           "-t", "60",
           str(output_path)]
    )

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode == 0 and output_path.is_file() and output_path.stat().st_size > 0:
            result["success"] = True
            result["output_path"] = str(output_path)
            result["attempted"] = True
    except Exception as e:
        result["error"] = str(e)

    return result


def _validate_output(output_path: Path) -> dict:
    validation = {
        "file_exists": False,
        "file_size_bytes": 0,
        "ffprobe_valid": False,
        "duration_seconds": None,
        "width": None,
        "height": None,
        "codec": None,
        "error": None,
    }
    if not output_path or not output_path.is_file():
        validation["error"] = "Output file not found"
        return validation

    validation["file_exists"] = True
    validation["file_size_bytes"] = output_path.stat().st_size

    if not shutil.which("ffprobe"):
        validation["error"] = "ffprobe not available"
        return validation

    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(output_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            validation["ffprobe_valid"] = True
            fmt = data.get("format", {})
            validation["duration_seconds"] = float(fmt.get("duration", 0))
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    validation["width"] = stream.get("width")
                    validation["height"] = stream.get("height")
                    validation["codec"] = stream.get("codec_name")
                    break
        else:
            validation["error"] = f"ffprobe exit {proc.returncode}"
    except Exception as e:
        validation["error"] = str(e)

    return validation


def main():
    if len(sys.argv) < 4:
        print("Usage: python render_with_openmontage.py <job.yaml> <downloaded_assets.json> <source_candidates.json> --run-id <run_id>")
        sys.exit(1)

    job_path = Path(sys.argv[1])
    assets_path = Path(sys.argv[2])
    candidates_path = Path(sys.argv[3])
    run_id = None
    for i, arg in enumerate(sys.argv):
        if arg == "--run-id" and i + 1 < len(sys.argv):
            run_id = sys.argv[i + 1]

    if not run_id:
        print("ERROR: --run-id is required")
        sys.exit(1)

    import yaml
    with open(job_path) as f:
        job = yaml.safe_load(f)
    with open(assets_path) as f:
        assets_data = json.load(f)
    with open(candidates_path) as f:
        candidates_data = json.load(f)

    run_dir = BASE_DIR / "state" / "runs" / run_id
    outputs_dir = BASE_DIR / "outputs" / run_id
    outputs_dir.mkdir(parents=True, exist_ok=True)

    om_info = {"available": False}
    try:
        om_path = _ensure_openmontage()
        om_info["available"] = True
        om_info["path"] = str(om_path)
    except RuntimeError as e:
        om_info["error"] = str(e)

    pipeline_selection = None
    pipeline_load = None
    registry_info = None
    checkpoint_info = None
    compose_result = None
    debug_fallback_result = None
    validation = {}
    openmontage_success = False
    pipeline_success = False
    final_success = False

    if om_info.get("available"):
        om_path = Path(om_info["path"])

        pipeline_selection = _select_pipeline(om_path, job)
        om_info["pipeline_selection"] = pipeline_selection

        if pipeline_selection.get("selected"):
            pipeline_load = _load_pipeline_through_loader(om_path, pipeline_selection["selected"])
            om_info["pipeline_load"] = pipeline_load

        required_tools = (pipeline_load.get("required_tools") or []) if pipeline_load else []
        registry_info = _run_registry_discovery(om_path, required_tools=required_tools)
        om_info["registry"] = registry_info

        selected_pipeline = pipeline_selection.get("selected", "clip-factory")
        checkpoint_info = _use_openmontage_checkpoints(om_path, run_id, selected_pipeline, run_dir)
        om_info["checkpoints"] = checkpoint_info

        assets_dir = run_dir / "assets" / "raw"
        compose_tool_name = registry_info.get("selected_compose_tool") if registry_info else None

        if compose_tool_name and registry_info.get("compose_tool_support_status", "").startswith("blocked"):
            om_info["compose_blocker"] = f"No compatible composition tool in registry. Status: {registry_info.get('compose_tool_support_status')}"
        elif compose_tool_name and assets_dir.is_dir() and list(assets_dir.glob("*.mp4")):
            compose_result = _compose_via_registered_tool(om_path, assets_dir, outputs_dir, compose_tool_name=compose_tool_name)
            om_info["compose_result"] = compose_result

            if compose_result.get("success") and compose_result.get("output_path"):
                validation = _validate_output(Path(compose_result["output_path"]))
                openmontage_success = bool(
                    compose_result.get("success")
                    and compose_result.get("tool_used") == compose_tool_name
                    and validation.get("ffprobe_valid")
                )
                pipeline_success = openmontage_success
            else:
                # Fallback: raw FFmpeg (debug only)
                debug_fallback_result = _ffmpeg_debug_fallback(assets_dir, outputs_dir)
                om_info["debug_fallback"] = debug_fallback_result

                if debug_fallback_result.get("success"):
                    validation = _validate_output(Path(debug_fallback_result["output_path"]))
                    openmontage_success = False
                    pipeline_success = False

    if compose_result and compose_result.get("output_path"):
        master_output = outputs_dir / "final_openmontage_render.mp4"
        src = Path(compose_result["output_path"])
        if src != master_output:
            shutil.copy2(src, master_output)
            compose_result["master_output_path"] = str(master_output)

    if openmontage_success:
        final_success = True
    elif debug_fallback_result and debug_fallback_result.get("success"):
        final_success = False

    report = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
        "openmontage_inspection": om_info,
        "compose_result": compose_result,
        "ffprobe_validation": validation,
        "openmontage_success": openmontage_success,
        "pipeline_success": pipeline_success,
        "final_success": final_success,
        "fallback_used": bool(debug_fallback_result and debug_fallback_result.get("success")),
        "blocker": None,
    }

    if not openmontage_success:
        report["blocker"] = (
            "OpenMontage pipeline render did not succeed. "
            "Debug fallback may exist but is NOT counted as OpenMontage/pipeline/final success."
        )

    plan_path = run_dir / "openmontage_render_plan.json"
    with open(plan_path, "w") as f:
        json.dump(report, f, indent=2)

    exec_report_path = run_dir / "openmontage_execution_report.json"
    with open(exec_report_path, "w") as f:
        json.dump(report, f, indent=2)

    md_path = run_dir / "openmontage_execution_report.md"
    with open(md_path, "w") as f:
        f.write(f"# OpenMontage Execution Report\n\n")
        f.write(f"Run: {run_id}\n\n")

        f.write(f"## OpenMontage Status\n\n")
        f.write(f"- Available: {om_info.get('available', False)}\n")

        if pipeline_selection:
            f.write(f"\n## Pipeline Selection\n\n")
            f.write(f"- Selected: {pipeline_selection.get('selected')}\n")
            f.write(f"- Reason: {pipeline_selection.get('selection_reason')}\n")
            f.write(f"- Candidates: {pipeline_selection.get('candidates')}\n")
            if pipeline_selection.get("manifest"):
                f.write(f"- Manifest name: {pipeline_selection['manifest'].get('name', 'N/A')}\n")
                f.write(f"- Manifest version: {pipeline_selection['manifest'].get('version', 'N/A')}\n")

        if pipeline_load:
            f.write(f"\n## Pipeline Load\n\n")
            f.write(f"- Loaded: {pipeline_load.get('loaded')}\n")
            f.write(f"- Stages ({len(pipeline_load.get('stages', []))}): {pipeline_load.get('stages')}\n")
            f.write(f"- Required tools: {pipeline_load.get('required_tools')}\n")

        if registry_info:
            f.write(f"\n## Registry Discovery\n\n")
            f.write(f"- Ran: {registry_info.get('discovery_ran')}\n")
            f.write(f"- Registered tools ({len(registry_info.get('registered_tools', []))}):\n")
            for t in registry_info.get("registered_tools", []):
                f.write(f"  - {t}\n")
            f.write(f"- Selected compose tool: {registry_info.get('selected_compose_tool')}\n")

        if checkpoint_info:
            f.write(f"\n## Checkpoints\n\n")
            f.write(f"- Project initialized: {checkpoint_info.get('project_initialized')}\n")
            f.write(f"- Checkpoints written: {checkpoint_info.get('checkpoints_written')}\n")

        if compose_result:
            f.write(f"\n## Composition\n\n")
            f.write(f"- Attempted: {compose_result.get('attempted')}\n")
            f.write(f"- Tool used: {compose_result.get('tool_used')}\n")
            f.write(f"- Success: {compose_result.get('success')}\n")
            if compose_result.get("error"):
                f.write(f"- Error: {compose_result['error']}\n")

        if validation:
            f.write(f"\n## FFprobe Validation\n\n")
            f.write(f"- Valid: {validation.get('ffprobe_valid', False)}\n")
            f.write(f"- Duration: {validation.get('duration_seconds', '?')}s\n")
            f.write(f"- Resolution: {validation.get('width', '?')}x{validation.get('height', '?')}\n")
            f.write(f"- Codec: {validation.get('codec', '?')}\n")
            f.write(f"- Size: {validation.get('file_size_bytes', 0)} bytes\n")

        f.write(f"\n## Success Flags\n\n")
        f.write(f"- openmontage_success: {openmontage_success}\n")
        f.write(f"- pipeline_success: {pipeline_success}\n")
        f.write(f"- final_success: {final_success}\n")

    artifacts_manifest = run_dir / "openmontage_artifact_manifest.json"
    with open(artifacts_manifest, "w") as f:
        manifest = {
            "run_id": run_id,
            "pipeline": pipeline_selection.get("selected") if pipeline_selection else None,
            "pipeline_manifest_loaded": pipeline_load.get("loaded") if pipeline_load else False,
            "registry_discovery_ran": registry_info.get("discovery_ran") if registry_info else False,
            "registered_tools": registry_info.get("registered_tools") if registry_info else [],
            "compose_tool_used": compose_result.get("tool_used") if compose_result else None,
            "openmontage_success": openmontage_success,
            "pipeline_success": pipeline_success,
            "final_success": final_success,
            "fallback_used": bool(debug_fallback_result and debug_fallback_result.get("success")),
        }
        json.dump(manifest, f, indent=2)

    print(f"Execution report: {md_path}")
    print(f"OpenMontage success: {openmontage_success}")
    print(f"Pipeline success: {pipeline_success}")
    print(f"Final success: {final_success}")

    if compose_result and compose_result.get("error"):
        print(f"Compose error: {compose_result['error']}")


if __name__ == "__main__":
    main()
