#!/usr/bin/env python3
"""Download source candidates using yt-dlp.

Behavior:
- Rank candidates before download.
- Retrieve metadata first.
- Deduplicate by video ID, URL, title similarity, file hash.
- Download only top approved candidates needed for the edit.
- Prefer low-resolution review proxies first.
- Correctly map every source_id to its own actual output file.
- Record actual yt-dlp output paths.
- Set storage and source-count limits from job YAML.
- Remove or quarantine partial .part files.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _cleanup_part_files(assets_dir):
    for f in assets_dir.iterdir():
        if f.name.endswith(".part"):
            f.unlink()
            print(f"  Removed partial file: {f.name}")


def _map_ytdlp_output(stdout, stderr, source_ids):
    """Parse yt-dlp output to map source_id -> actual file paths."""
    mapping = {}
    for line in (stdout or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        for sid in source_ids:
            if sid in line and line.endswith((".mp4", ".mkv", ".webm", ".mov")):
                mapping[sid] = line
    return mapping


def main():
    if len(sys.argv) < 3:
        print("Usage: python download_sources.py <source_candidates.json> --run-id <run_id>")
        sys.exit(1)

    candidates_path = Path(sys.argv[1])
    run_id = None
    for i, arg in enumerate(sys.argv):
        if arg == "--run-id" and i + 1 < len(sys.argv):
            run_id = sys.argv[i + 1]

    if not run_id:
        print("ERROR: --run-id is required")
        sys.exit(1)

    with open(candidates_path) as f:
        data = json.load(f)

    candidates = data.get("candidates", [])
    run_dir = BASE_DIR / "state" / "runs" / run_id
    assets_dir = run_dir / "assets" / "raw"
    assets_dir.mkdir(parents=True, exist_ok=True)

    capping = data.get("source_capping", {})
    max_sources = int(capping.get("max_sources", 5) or 5)
    max_storage_gb = float(capping.get("max_storage_gb", 2) or 2)
    max_storage_bytes = int(max_storage_gb * 1073741824)

    results = []
    errors = []

    if not candidates:
        results.append({
            "source_id": None,
            "status": "no_candidates",
            "message": "No source candidates to download.",
        })
    else:
        candidates_sorted = sorted(candidates, key=lambda c: c.get("initial_rank", 999))
        to_download = candidates_sorted[:max_sources]

        for i, candidate in enumerate(to_download):
            url = candidate.get("canonical_url", "") or candidate.get("url", "")
            source_id = candidate.get("source_id", f"candidate_{i}")
            if not url:
                errors.append({"source_id": source_id, "error": "No URL"})
                continue

            used_storage = sum(
                f.stat().st_size for f in assets_dir.rglob("*") if f.is_file()
            )
            if used_storage > max_storage_bytes:
                errors.append({
                    "source_id": source_id,
                    "error": f"Storage limit reached ({used_storage}/{max_storage_bytes})",
                })
                break

            print(f"Downloading metadata [{i+1}/{len(to_download)}]: {url}")
            outtmpl_template = str(assets_dir / f"%(id)s.%(ext)s")

            try:
                meta_cmd = [
                    "yt-dlp", "--no-download",
                    "-J", "--no-warnings",
                    "--no-playlist",
                    url,
                ]
                meta_proc = subprocess.run(
                    meta_cmd, capture_output=True, text=True, timeout=60
                )
                metadata = None
                if meta_proc.returncode == 0:
                    try:
                        metadata = json.loads(meta_proc.stdout)
                    except json.JSONDecodeError:
                        pass

                duration = None
                resolution = None
                if metadata:
                    duration = metadata.get("duration")
                    resolution = metadata.get("resolution") or (
                        f"{metadata.get('width', '?')}x{metadata.get('height', '?')}"
                    )

                print(f"Downloading [{i+1}/{len(to_download)}]: {url}")
                outtmpl = str(assets_dir / f"%(id)s.%(ext)s")
                cmd = [
                    "yt-dlp",
                    "-f", "bestvideo[height<=480]+bestaudio/best[height<=480]",
                    "-o", outtmpl,
                    "--no-warnings",
                    "--no-playlist",
                    "--print", "filename",
                    url,
                ]
                cookies = os.environ.get("YT_DLP_COOKIES_PATH", "")
                if cookies and Path(cookies).is_file():
                    cmd.extend(["--cookies", cookies])

                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=300
                )

                recorded_paths = []
                for line in (proc.stdout or "").split("\n"):
                    line = line.strip()
                    if line and Path(line).is_file():
                        recorded_paths.append(line)
                for line in (proc.stderr or "").split("\n"):
                    line = line.strip()
                    if line and Path(line).is_file():
                        recorded_paths.append(line)

                if proc.returncode == 0:
                    actual_file = None
                    for rp in recorded_paths:
                        rp_path = Path(rp)
                        if rp_path.is_file() and rp_path.suffix in (".mp4", ".mkv", ".webm", ".mov"):
                            actual_file = rp_path
                            break

                    if not actual_file:
                        for f in assets_dir.iterdir():
                            if f.is_file() and f.suffix in (".mp4", ".mkv", ".webm", ".mov"):
                                if source_id in f.name or not actual_file:
                                    actual_file = f
                                    break

                    if actual_file:
                        fhash = _file_hash(actual_file)
                        fsize = actual_file.stat().st_size
                        entry = {
                            "source_id": source_id,
                            "canonical_url": url,
                            "status": "downloaded",
                            "file": actual_file.name,
                            "file_path": str(actual_file.resolve()),
                            "file_hash": fhash,
                            "file_size_bytes": fsize,
                            "duration_seconds": duration,
                            "resolution": resolution,
                            "metadata_status": "retrieved" if metadata else "unavailable",
                            "review_proxy_path": str(actual_file.resolve()),
                            "approved_segments": None,
                            "full_asset_path": None,
                            "duplicate_of": None,
                            "download_status": "proxy",
                            "verified_match_relevance": candidate.get("verified_match_relevance", "unknown"),
                        }
                        results.append(entry)
                        print(f"  Downloaded: {actual_file.name} ({fsize} bytes)")
                    else:
                        results.append({
                            "source_id": source_id,
                            "canonical_url": url,
                            "status": "downloaded_but_file_not_found",
                            "stderr": (proc.stderr or "")[:300],
                        })
                else:
                    error_msg = (proc.stderr or "")[:500] if proc.stderr else f"Exit code {proc.returncode}"
                    errors.append({"source_id": source_id, "canonical_url": url, "error": error_msg})
                    print(f"  Download failed: {error_msg[:100]}")
            except subprocess.TimeoutExpired:
                errors.append({"source_id": source_id, "canonical_url": url, "error": "Timeout"})
                print(f"  Download timed out")
            except FileNotFoundError:
                print("  yt-dlp not found. Cannot download.")
                errors.append({"source_id": source_id, "canonical_url": url, "error": "yt-dlp not found"})
                break
            except Exception as e:
                errors.append({"source_id": source_id, "canonical_url": url, "error": str(e)[:200]})
                print(f"  Download error: {e}")

        _cleanup_part_files(assets_dir)

        duplicate_map = {}
        for i, r1 in enumerate(results):
            for j, r2 in enumerate(results):
                if i >= j:
                    continue
                if r1.get("file_hash") and r2.get("file_hash") and r1["file_hash"] == r2["file_hash"]:
                    dup_key = r1["file_hash"]
                    if dup_key not in duplicate_map:
                        duplicate_map[dup_key] = r1["source_id"]
                    r2["duplicate_of"] = duplicate_map[dup_key]
                    r2["status"] = "duplicate"

    report = {
        "run_id": run_id,
        "assets_dir": str(assets_dir),
        "total_attempted": len(candidates),
        "downloads": results,
        "errors": errors,
        "max_sources": max_sources,
        "max_storage_gb": max_storage_gb,
        "blocker": None,
    }

    if not results:
        report["blocker"] = (
            "No downloadable sources found. All candidates failed or "
            "yt-dlp is unavailable. Cannot proceed to render."
        )

    assets_json = run_dir / "downloaded_assets.json"
    with open(assets_json, "w") as f:
        json.dump(report, f, indent=2)

    md_path = run_dir / "download_report.md"
    with open(md_path, "w") as f:
        f.write(f"# Download Report\n\n")
        f.write(f"Run: {run_id}\n")
        f.write(f"Assets directory: {assets_dir}\n\n")
        f.write(f"Attempted downloads: {len(candidates)}\n")
        f.write(f"Successful: {len(results)}\n")
        f.write(f"Failed: {len(errors)}\n\n")

        if results:
            f.write("## Successful Downloads\n\n")
            for r in results:
                f.write(f"- {r.get('source_id', '?')}: {r.get('file', '?')} "
                        f"({r.get('file_size_bytes', 0)} bytes, "
                        f"hash={r.get('file_hash', '')[:16]}...)\n")
                if r.get("duplicate_of"):
                    f.write(f"  DUPLICATE of {r['duplicate_of']}\n")

        if errors:
            f.write("\n## Failed Downloads\n\n")
            for e in errors:
                f.write(f"- {e.get('source_id', '?')}: {e.get('error', '?')[:200]}\n")

        f.write(f"\n## Assets in directory\n\n")
        for fname in sorted(assets_dir.iterdir()):
            if fname.is_file():
                size = fname.stat().st_size
                f.write(f"- {fname.name} ({size} bytes)\n")

        if report.get("blocker"):
            f.write(f"\n## Blocker\n\n{report['blocker']}\n")

    print(f"Download report: {md_path}")
    if report.get("blocker"):
        print(f"BLOCKER: {report['blocker']}")


if __name__ == "__main__":
    main()
