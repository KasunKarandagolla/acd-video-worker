#!/usr/bin/env python3
"""Discover video sources from job title/theme using yt-dlp search."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_job(job_path):
    import yaml
    with open(job_path) as f:
        return yaml.safe_load(f)


def search_ytdlp(query, max_results=10):
    results = []
    try:
        cmd = [
            "yt-dlp", "--flat-playlist",
            "-J", "--no-warnings",
            f"ytsearch{max_results}:{query}"
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            entries = data.get("entries", [])
            for entry in entries:
                results.append({
                    "source_id": entry.get("id", ""),
                    "url": f"https://youtube.com/watch?v={entry.get('id', '')}",
                    "title": entry.get("title", ""),
                    "platform": "youtube",
                    "source_type": "unknown",
                    "query_used": query,
                    "downloadable": "yes",
                    "rights_risk": "needs_review",
                    "verification_status": "unverified",
                    "reason_to_consider": f"yt-dlp search result for: {query}"
                })
    except FileNotFoundError:
        print("WARN: yt-dlp not installed. Cannot perform YouTube search.")
    except subprocess.TimeoutExpired:
        print("WARN: yt-dlp search timed out.")
    except Exception as e:
        print(f"WARN: yt-dlp search error: {e}")
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python source_discovery.py <job.yaml> --run-id <run_id>")
        sys.exit(1)

    job_path = sys.argv[1]
    run_id = None
    for i, arg in enumerate(sys.argv):
        if arg == "--run-id" and i + 1 < len(sys.argv):
            run_id = sys.argv[i + 1]

    if not run_id:
        run_id = "run_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    job = load_job(job_path)
    run_dir = os.path.join(BASE_DIR, "state", "runs", run_id)
    os.makedirs(run_dir, exist_ok=True)

    title = job.get("title", "")
    theme = job.get("theme", "")
    print(f"Job title: {title}")
    print(f"Job theme: {theme}")

    all_candidates = []
    queries = []

    if title:
        queries.append(title)
    if theme:
        queries.append(theme)

    if not queries:
        queries = ["sports highlights"]

    for query in queries:
        print(f"Searching: {query}")
        results = search_ytdlp(query)
        all_candidates.extend(results)

    # Deduplicate by source_id
    seen = set()
    candidates = []
    for c in all_candidates:
        sid = c.get("source_id", "")
        if sid and sid not in seen:
            seen.add(sid)
            candidates.append(c)

    report = {
        "run_id": run_id,
        "job_title": title,
        "job_theme": theme,
        "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
        "total_candidates": len(candidates),
        "sources_queried": queries,
        "candidates": candidates,
        "title_claim_status": "unverified",
        "title_claim_evidence": None,
        "blocker": None
    }

    # Title claim check
    if "nobody expected" in title.lower() or "hardest" in title.lower():
        report["title_claim_status"] = "creative_hypothesis"
        report["title_claim_evidence"] = (
            "Title contains subjective claims ('Nobody Expected', 'Hardest'). "
            "Actual public expectation data not verified. "
            "Recommend softening wording if factual support is missing."
        )

    if not candidates:
        report["blocker"] = (
            "No source candidates found. yt-dlp may be unavailable, "
            "or search queries returned no results."
        )

    candidates_path = os.path.join(run_dir, "source_candidates.json")
    with open(candidates_path, "w") as f:
        json.dump(report, f, indent=2)

    md_path = os.path.join(run_dir, "source_discovery_report.md")
    with open(md_path, "w") as f:
        f.write(f"# Source Discovery Report\n\n")
        f.write(f"Run: {run_id}\n")
        f.write(f"Title: {title}\n")
        f.write(f"Theme: {theme}\n\n")

        f.write(f"## Queries Used\n\n")
        for q in queries:
            f.write(f"- {q}\n")

        f.write(f"\n## Candidates ({len(candidates)})\n\n")
        for c in candidates[:20]:
            f.write(f"### {c.get('source_id', '?')}\n")
            f.write(f"- URL: {c.get('url', '?')}\n")
            f.write(f"- Title: {c.get('title', '?')}\n")
            f.write(f"- Platform: {c.get('platform', '?')}\n")
            f.write(f"- Downloadable: {c.get('downloadable', '?')}\n")
            f.write(f"- Rights Risk: {c.get('rights_risk', '?')}\n")
            f.write(f"- Verification: {c.get('verification_status', '?')}\n\n")

        f.write(f"\n## Title Claim Status\n\n")
        f.write(f"Status: {report['title_claim_status']}\n")
        if report.get("title_claim_evidence"):
            f.write(f"Note: {report['title_claim_evidence']}\n")

        if report.get("blocker"):
            f.write(f"\n## Blocker\n\n{report['blocker']}\n")

    print(f"Source candidates: {candidates_path}")
    print(f"Source discovery report: {md_path}")

    if report.get("blocker"):
        print(f"BLOCKER: {report['blocker']}")


if __name__ == "__main__":
    main()
