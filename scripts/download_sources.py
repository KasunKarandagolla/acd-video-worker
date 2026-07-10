#!/usr/bin/env python3
"""Download source candidates using yt-dlp."""
import json
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) < 3:
        print("Usage: python download_sources.py <source_candidates.json> --run-id <run_id>")
        sys.exit(1)

    candidates_path = sys.argv[1]
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
    run_dir = os.path.join(BASE_DIR, "state", "runs", run_id)
    assets_dir = os.path.join(run_dir, "assets", "raw")
    os.makedirs(assets_dir, exist_ok=True)

    results = []
    errors = []

    if not candidates:
        results.append({
            "status": "no_candidates",
            "message": "No source candidates to download."
        })
    else:
        for i, candidate in enumerate(candidates):
            url = candidate.get("url", "")
            source_id = candidate.get("source_id", f"candidate_{i}")
            if not url:
                errors.append({"source_id": source_id, "error": "No URL"})
                continue

            print(f"Downloading [{i+1}/{len(candidates)}]: {url}")
            outtmpl = os.path.join(assets_dir, f"%(id)s.%(ext)s")
            try:
                cmd = [
                    "yt-dlp",
                    "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                    "-o", outtmpl,
                    "--no-warnings",
                    "--no-playlist",
                    url
                ]
                cookies = os.environ.get("YT_DLP_COOKIES_PATH", "")
                if cookies and os.path.exists(cookies):
                    cmd.extend(["--cookies", cookies])

                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if proc.returncode == 0:
                    # Find what was downloaded
                    for fname in os.listdir(assets_dir):
                        if fname.startswith(source_id) or fname.endswith(".mp4") or fname.endswith(".mkv"):
                            results.append({
                                "source_id": source_id,
                                "url": url,
                                "status": "downloaded",
                                "file": fname,
                                "path": os.path.join(assets_dir, fname)
                            })
                            break
                    else:
                        results.append({
                            "source_id": source_id,
                            "url": url,
                            "status": "downloaded_but_file_not_found",
                            "stderr": proc.stderr[:300]
                        })
                else:
                    error_msg = proc.stderr[:500] if proc.stderr else f"Exit code {proc.returncode}"
                    errors.append({"source_id": source_id, "url": url, "error": error_msg})
                    print(f"  Download failed: {error_msg[:100]}")
            except subprocess.TimeoutExpired:
                errors.append({"source_id": source_id, "url": url, "error": "Timeout"})
                print(f"  Download timed out")
            except FileNotFoundError:
                print("  yt-dlp not found. Cannot download.")
                errors.append({"source_id": source_id, "url": url, "error": "yt-dlp not found"})
                break
            except Exception as e:
                errors.append({"source_id": source_id, "url": url, "error": str(e)[:200]})
                print(f"  Download error: {e}")

    report = {
        "run_id": run_id,
        "assets_dir": assets_dir,
        "total_attempted": len(candidates),
        "downloads": results,
        "errors": errors,
        "blocker": None
    }

    if not results:
        report["blocker"] = (
            "No downloadable sources found. All candidates failed or "
            "yt-dlp is unavailable. Cannot proceed to render."
        )

    assets_json = os.path.join(run_dir, "downloaded_assets.json")
    with open(assets_json, "w") as f:
        json.dump(report, f, indent=2)

    md_path = os.path.join(run_dir, "download_report.md")
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
                f.write(f"- {r.get('source_id', '?')}: {r.get('file', '?')}\n")

        if errors:
            f.write("\n## Failed Downloads\n\n")
            for e in errors:
                f.write(f"- {e.get('source_id', '?')}: {e.get('error', '?')[:200]}\n")

        f.write(f"\n## Assets in directory\n\n")
        for fname in sorted(os.listdir(assets_dir)):
            fpath = os.path.join(assets_dir, fname)
            if os.path.isfile(fpath):
                size = os.path.getsize(fpath)
                f.write(f"- {fname} ({size} bytes)\n")

        if report.get("blocker"):
            f.write(f"\n## Blocker\n\n{report['blocker']}\n")

    print(f"Download report: {md_path}")
    if report.get("blocker"):
        print(f"BLOCKER: {report['blocker']}")


if __name__ == "__main__":
    main()
