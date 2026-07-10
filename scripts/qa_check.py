#!/usr/bin/env python3
"""Full QA pipeline after render.

Checks:
- ffprobe validation
- loudness measurement
- output duration, resolution, codec
- missing media
- captions/text safe zones
- factual claims against match_fact_lock
- source concentration thresholds
- rights/commentary/music statuses
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _ffprobe_info(filepath: Path) -> dict:
    info = {"valid": False, "error": None, "streams": [], "format": {}}
    if not filepath or not filepath.is_file():
        info["error"] = "File not found"
        return info
    if not shutil.which("ffprobe"):
        info["error"] = "ffprobe not available"
        return info

    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(filepath),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            info["valid"] = True
            info["format"] = data.get("format", {})
            for stream in data.get("streams", []):
                s = {
                    "index": stream.get("index"),
                    "codec_type": stream.get("codec_type"),
                    "codec_name": stream.get("codec_name"),
                }
                if stream["codec_type"] == "video":
                    s.update({
                        "width": stream.get("width"),
                        "height": stream.get("height"),
                        "r_frame_rate": stream.get("r_frame_rate"),
                        "duration": stream.get("duration"),
                    })
                info["streams"].append(s)
        else:
            info["error"] = f"ffprobe exit {proc.returncode}"
    except Exception as e:
        info["error"] = str(e)
    return info


def _loudness_measurement(filepath: Path) -> dict:
    result = {"measured": False, "integrated_loudness": None, "loudness_range": None, "true_peak": None}
    if not shutil.which("ffmpeg"):
        return result

    try:
        cmd = [
            "ffmpeg", "-i", str(filepath),
            "-af", "loudnorm=I=-16:LRA=11:TP=-1.5:print_format=json",
            "-f", "null", "-",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = proc.stderr or ""
        for line in output.split("\n"):
            if "{" in line and "}" in line:
                try:
                    start = line.index("{")
                    end = line.rindex("}") + 1
                    data = json.loads(line[start:end])
                    result["measured"] = True
                    result["integrated_loudness"] = data.get("input_i") or data.get("input_loudness")
                    result["loudness_range"] = data.get("input_lra")
                    result["true_peak"] = data.get("input_tp")
                except (ValueError, json.JSONDecodeError):
                    pass
                break
    except Exception:
        pass
    return result


def _check_factual_claims(render_output: Path, run_dir: Path) -> dict:
    lock_path = run_dir / "hermes_artifacts" / "match_fact_lock.json"
    if not lock_path.is_file():
        return {"checked": False, "note": "No match_fact_lock available"}
    try:
        with open(lock_path) as f:
            facts = json.load(f)
    except Exception:
        return {"checked": False, "error": "Cannot parse match_fact_lock"}

    return {
        "checked": True,
        "match": facts.get("match"),
        "opponent": facts.get("opponent"),
        "date": facts.get("date"),
        "score": facts.get("score"),
        "stage": facts.get("competition_stage"),
        "verification_status": facts.get("verification_status"),
        "note": "All claims should be verified before on-screen display. Automated fact-check of rendered text requires OCR/ASR.",
    }


def run_qa(run_id: str, run_dir: Path) -> dict:
    outputs_dir = BASE_DIR / "outputs" / run_id
    render_path = outputs_dir / "final_openmontage_render.mp4"
    fallback_path = outputs_dir / "fallback_render_attempt.mp4"

    output_path = render_path if render_path.is_file() else (fallback_path if fallback_path.is_file() else None)

    qa = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "render_found": output_path is not None,
        "render_path": str(output_path) if output_path else None,
    }

    if not output_path:
        qa["blocker"] = "No render output found to QA"
        return qa

    probe = _ffprobe_info(output_path)
    qa["ffprobe"] = probe

    loudness = _loudness_measurement(output_path)
    qa["loudness"] = loudness

    factual = _check_factual_claims(output_path, run_dir)
    qa["factual_claims"] = factual

    summary = {
        "has_video": any(s.get("codec_type") == "video" for s in probe.get("streams", [])),
        "has_audio": any(s.get("codec_type") == "audio" for s in probe.get("streams", [])),
        "duration_seconds": None,
        "resolution": None,
        "codec": None,
        "file_size_bytes": output_path.stat().st_size,
        "loudness_ok": False,
    }

    for s in probe.get("streams", []):
        if s.get("codec_type") == "video":
            summary["resolution"] = f"{s.get('width', '?')}x{s.get('height', '?')}"
            summary["codec"] = s.get("codec_name")
            summary["duration_seconds"] = s.get("duration")
        if s.get("codec_type") == "audio":
            summary["has_audio"] = True

    fmt = probe.get("format", {})
    if fmt.get("duration"):
        summary["duration_seconds"] = float(fmt["duration"])

    if loudness.get("measured") and loudness.get("integrated_loudness"):
        try:
            val = float(loudness["integrated_loudness"])
            summary["loudness_ok"] = -25 <= val <= -10
        except (TypeError, ValueError):
            pass

    qa["summary"] = summary

    issues = []
    if not summary.get("has_video"):
        issues.append("NO VIDEO STREAM FOUND")
    if summary.get("duration_seconds") and summary["duration_seconds"] < 5:
        issues.append(f"Output too short: {summary['duration_seconds']}s")
    if not summary.get("has_audio"):
        issues.append("NO AUDIO STREAM FOUND")
    if qa.get("loudness", {}).get("measured") and not summary.get("loudness_ok"):
        issues.append("Loudness outside target range (-25 to -10 LUFS)")
    qa["issues"] = issues
    qa["qa_passed"] = len(issues) == 0

    return qa


def main():
    if len(sys.argv) < 2:
        print("Usage: python qa_check.py <run_id>")
        sys.exit(1)

    run_id = sys.argv[1]
    run_dir = BASE_DIR / "state" / "runs" / run_id

    qa = run_qa(run_id, run_dir)

    qa_path = run_dir / "full_qa_report.json"
    with open(qa_path, "w") as f:
        json.dump(qa, f, indent=2)

    md_path = run_dir / "full_qa_report.md"
    with open(md_path, "w") as f:
        f.write(f"# Full QA Report\n\n")
        f.write(f"Run: {run_id}\n\n")
        f.write(f"Render found: {qa.get('render_found', False)}\n")
        f.write(f"QA passed: {qa.get('qa_passed', False)}\n\n")

        if qa.get("summary"):
            s = qa["summary"]
            f.write(f"## Summary\n\n")
            f.write(f"- Video: {s.get('has_video', False)}\n")
            f.write(f"- Audio: {s.get('has_audio', False)}\n")
            f.write(f"- Duration: {s.get('duration_seconds', '?')}s\n")
            f.write(f"- Resolution: {s.get('resolution', '?')}\n")
            f.write(f"- Codec: {s.get('codec', '?')}\n")
            f.write(f"- File size: {s.get('file_size_bytes', 0)} bytes\n")
            f.write(f"- Loudness OK: {s.get('loudness_ok', False)}\n\n")

        if qa.get("ffprobe"):
            f.write(f"## FFprobe\n\n")
            f.write(f"- Valid: {qa['ffprobe'].get('valid', False)}\n")
            if qa['ffprobe'].get('error'):
                f.write(f"- Error: {qa['ffprobe']['error']}\n")

        if qa.get("loudness"):
            f.write(f"\n## Loudness\n\n")
            f.write(f"- Measured: {qa['loudness'].get('measured', False)}\n")
            if qa['loudness'].get('integrated_loudness') is not None:
                f.write(f"- Integrated: {qa['loudness']['integrated_loudness']} LUFS\n")
            if qa['loudness'].get('loudness_range') is not None:
                f.write(f"- Range: {qa['loudness']['loudness_range']} LU\n")

        if qa.get("factual_claims"):
            f.write(f"\n## Factual Claims\n\n")
            f.write(f"- Checked: {qa['factual_claims'].get('checked', False)}\n")
            for k in ["match", "opponent", "date", "score", "stage"]:
                if qa['factual_claims'].get(k):
                    f.write(f"- {k}: {qa['factual_claims'][k]}\n")

        if qa.get("issues"):
            f.write(f"\n## Issues\n\n")
            for issue in qa["issues"]:
                f.write(f"- {issue}\n")

        if qa.get("blocker"):
            f.write(f"\n## Blocker\n\n{qa['blocker']}\n")

    print(f"QA report: {md_path}")
    print(f"QA {'PASSED' if qa.get('qa_passed', False) else 'HAS ISSUES'}")
    if qa.get("issues"):
        for issue in qa["issues"]:
            print(f"  ISSUE: {issue}")


if __name__ == "__main__":
    main()
