#!/usr/bin/env python3
"""Visual and audio analysis of downloaded media assets.

Generates:
- media_probe.json (ffprobe results per file)
- contact_sheet_manifest.json (sampled frames)
- visual_scene_analysis.json (scene-level analysis)
- audio_analysis.json (audio stream analysis)
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _ffprobe_media(filepath: Path) -> dict:
    result = {
        "file": filepath.name,
        "path": str(filepath.resolve()),
        "size_bytes": filepath.stat().st_size,
        "streams": [],
        "format": {},
        "error": None,
    }

    if not shutil.which("ffprobe"):
        result["error"] = "ffprobe not available"
        return result

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
            result["format"] = data.get("format", {})
            for stream in data.get("streams", []):
                stream_info = {
                    "index": stream.get("index"),
                    "codec_type": stream.get("codec_type"),
                    "codec_name": stream.get("codec_name"),
                    "codec_long_name": stream.get("codec_long_name"),
                }
                if stream["codec_type"] == "video":
                    stream_info.update({
                        "width": stream.get("width"),
                        "height": stream.get("height"),
                        "r_frame_rate": stream.get("r_frame_rate"),
                        "duration": stream.get("duration"),
                        "bit_rate": stream.get("bit_rate"),
                    })
                elif stream["codec_type"] == "audio":
                    stream_info.update({
                        "sample_rate": stream.get("sample_rate"),
                        "channels": stream.get("channels"),
                        "channel_layout": stream.get("channel_layout"),
                    })
                result["streams"].append(stream_info)
        else:
            result["error"] = f"ffprobe exit {proc.returncode}: {proc.stderr[:200]}"
    except Exception as e:
        result["error"] = str(e)

    return result


def _sample_frames(filepath: Path, output_dir: Path, max_frames: int = 5) -> list:
    frames = []
    if not shutil.which("ffmpeg"):
        return frames

    try:
        duration_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(filepath),
        ]
        dur_proc = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=15)
        duration = float(dur_proc.stdout.strip()) if dur_proc.returncode == 0 else 30

        frame_dir = output_dir / filepath.stem
        frame_dir.mkdir(parents=True, exist_ok=True)

        intervals = [duration * i / (max_frames + 1) for i in range(1, max_frames + 1)]
        for idx, ts in enumerate(intervals):
            outpath = frame_dir / f"frame_{idx:03d}.jpg"
            cmd = [
                "ffmpeg", "-y", "-ss", str(ts),
                "-i", str(filepath),
                "-vframes", "1",
                "-q:v", "2",
                str(outpath),
            ]
            subprocess.run(cmd, capture_output=True, timeout=30)
            if outpath.is_file():
                frames.append({
                    "frame_index": idx,
                    "timestamp_seconds": round(ts, 2),
                    "path": str(outpath.resolve()),
                    "size_bytes": outpath.stat().st_size,
                })

    except Exception as e:
        pass

    return frames


def _analyze_audio(filepath: Path) -> dict:
    audio_info = {
        "file": filepath.name,
        "has_audio": False,
        "streams": [],
        "loudness": None,
        "error": None,
    }

    if not shutil.which("ffprobe"):
        audio_info["error"] = "ffprobe not available"
        return audio_info

    probe = _ffprobe_media(filepath)
    audio_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"]
    if not audio_streams:
        return audio_info

    audio_info["has_audio"] = True
    audio_info["streams"] = audio_streams

    if shutil.which("ffmpeg") and len(audio_streams) > 0:
        try:
            loudness_cmd = [
                "ffmpeg", "-i", str(filepath),
                "-af", "loudnorm=I=-16:LRA=11:TP=-1.5:print_format=json",
                "-f", "null", "-",
            ]
            proc = subprocess.run(loudness_cmd, capture_output=True, text=True, timeout=60)
            for line in (proc.stderr or "").split("\n"):
                if '"input_i"' in line or '"input_loudness"' in line:
                    try:
                        start = line.index("{")
                        end = line.rindex("}") + 1
                        loudness_data = json.loads(line[start:end])
                        audio_info["loudness"] = loudness_data
                    except (ValueError, json.JSONDecodeError):
                        pass
                    break
        except Exception:
            pass

    return audio_info


def main():
    if len(sys.argv) < 2:
        print("Usage: python media_analysis.py <run_id>")
        sys.exit(1)

    run_id = sys.argv[1]
    run_dir = BASE_DIR / "state" / "runs" / run_id
    assets_dir = run_dir / "assets" / "raw"
    analysis_dir = run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = analysis_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    video_files = sorted([
        f for f in assets_dir.iterdir()
        if f.is_file() and f.suffix in (".mp4", ".mkv", ".webm", ".mov")
    ])

    all_probes = []
    all_frames = []
    all_audio = []

    for vf in video_files:
        print(f"Analyzing: {vf.name}")
        probe = _ffprobe_media(vf)
        all_probes.append(probe)

        frames = _sample_frames(vf, frames_dir)
        all_frames.extend(frames)

        audio = _analyze_audio(vf)
        all_audio.append(audio)

    media_probe_path = analysis_dir / "media_probe.json"
    with open(media_probe_path, "w") as f:
        json.dump(all_probes, f, indent=2)

    contact_sheet = {
        "run_id": run_id,
        "total_frames": len(all_frames),
        "frames": all_frames,
        "frame_dir": str(frames_dir),
    }
    contact_path = analysis_dir / "contact_sheet_manifest.json"
    with open(contact_path, "w") as f:
        json.dump(contact_sheet, f, indent=2)

    visual_analysis = {
        "run_id": run_id,
        "files_analyzed": len(video_files),
        "probes": all_probes,
        "total_frames_sampled": len(all_frames),
    }
    visual_path = analysis_dir / "visual_scene_analysis.json"
    with open(visual_path, "w") as f:
        json.dump(visual_analysis, f, indent=2)

    audio_analysis = {
        "run_id": run_id,
        "files_analyzed": len(video_files),
        "audio_streams": all_audio,
    }
    audio_path = analysis_dir / "audio_analysis.json"
    with open(audio_path, "w") as f:
        json.dump(audio_analysis, f, indent=2)

    md_path = analysis_dir / "media_analysis_report.md"
    with open(md_path, "w") as f:
        f.write(f"# Media Analysis Report\n\n")
        f.write(f"Run: {run_id}\n\n")
        f.write(f"## Files Analyzed: {len(video_files)}\n\n")
        for probe in all_probes:
            f.write(f"### {probe['file']}\n")
            f.write(f"- Size: {probe.get('size_bytes', 0)} bytes\n")
            for s in probe.get("streams", []):
                if s.get("codec_type") == "video":
                    f.write(f"- Video: {s.get('codec_name', '?')} "
                            f"{s.get('width', '?')}x{s.get('height', '?')}\n")
                elif s.get("codec_type") == "audio":
                    f.write(f"- Audio: {s.get('codec_name', '?')} "
                            f"{s.get('sample_rate', '?')}Hz {s.get('channels', '?')}ch\n")
            f.write("\n")

        f.write(f"## Contact Sheet\n\n")
        f.write(f"Total sampled frames: {len(all_frames)}\n\n")
        for fr in all_frames[:20]:
            f.write(f"- Frame {fr['frame_index']} at {fr['timestamp_seconds']}s: {fr['path']}\n")

        f.write(f"\n## Audio Analysis\n\n")
        for a in all_audio:
            f.write(f"### {a['file']}\n")
            f.write(f"- Has audio: {a.get('has_audio', False)}\n")
            for s in a.get("streams", []):
                f.write(f"- Stream: {s.get('codec_name', '?')} "
                        f"{s.get('sample_rate', '?')}Hz {s.get('channels', '?')}ch\n")
            if a.get("loudness"):
                f.write(f"- Loudness data available\n")
            f.write("\n")

    print(f"Media analysis complete: {analysis_dir}")
    print(f"  - {len(all_probes)} files probed")
    print(f"  - {len(all_frames)} frames sampled")
    print(f"  - {len(all_audio)} audio analyses")


if __name__ == "__main__":
    main()
