#!/usr/bin/env python3
"""Discover video sources from job title/theme using yt-dlp search.

Behavior:
1. Load match fact lock if available for verified search terms.
2. Search using verified opponent, date, stage, key events.
3. Rank candidates before accepting.
4. Deduplicate by video ID and title similarity.
5. Reject sources unrelated to verified match.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_job(job_path):
    import yaml
    with open(job_path) as f:
        return yaml.safe_load(f)


def load_match_fact_lock(run_dir):
    lock_path = run_dir / "hermes_artifacts" / "match_fact_lock.json"
    if lock_path.is_file():
        try:
            with open(lock_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return None
    return None


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
                source_id = entry.get("id", "")
                results.append({
                    "source_id": source_id,
                    "canonical_url": f"https://youtube.com/watch?v={source_id}",
                    "title": entry.get("title", ""),
                    "channel": entry.get("channel", "") or entry.get("uploader", ""),
                    "platform": "youtube",
                    "source_type": "unknown",
                    "query_used": query,
                    "provider": "yt_dlp_search",
                    "downloadable": "yes",
                    "rights_risk": "needs_review",
                    "verification_status": "unverified",
                    "reason_to_consider": f"yt-dlp search result for: {query}",
                    "title_lower": (entry.get("title", "") or "").lower(),
                })
    except FileNotFoundError:
        print("WARN: yt-dlp not installed. Cannot perform YouTube search.")
    except subprocess.TimeoutExpired:
        print("WARN: yt-dlp search timed out.")
    except Exception as e:
        print(f"WARN: yt-dlp search error: {e}")
    return results


def search_tavily(query, max_results=10):
    """Search using Tavily API for YouTube and credible web sources."""
    results = []
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        print("WARN: TAVILY_API_KEY not set. Cannot perform Tavily search.")
        return results
    try:
        import requests as req
        resp = req.post(
            "https://api.tavily.com/search",
            json={"query": query, "max_results": max_results, "include_domains": ["youtube.com"]},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            tavily_results = data.get("results", [])
            for r in tavily_results:
                url = r.get("url", "")
                title = r.get("title", "")
                if not url:
                    continue
                source_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
                platform = "youtube" if "youtube.com" in url.lower() or "youtu.be" in url.lower() else "web"
                results.append({
                    "source_id": source_id,
                    "canonical_url": url,
                    "title": title,
                    "channel": r.get("source", ""),
                    "platform": platform,
                    "source_type": "unknown",
                    "query_used": query,
                    "provider": "tavily_search",
                    "downloadable": "yes" if platform == "youtube" else "unknown",
                    "rights_risk": "needs_review",
                    "verification_status": "unverified",
                    "reason_to_consider": f"Tavily search result for: {query}",
                    "title_lower": (title or "").lower(),
                })
        else:
            print(f"WARN: Tavily search returned status {resp.status_code}")
    except ImportError:
        print("WARN: requests module not available for Tavily search.")
    except Exception as e:
        print(f"WARN: Tavily search error: {e}")
    return results


def _title_similarity(t1, t2):
    t1 = re.sub(r'[^a-z0-9\s]', '', t1.lower()).strip()
    t2 = re.sub(r'[^a-z0-9\s]', '', t2.lower()).strip()
    words1 = set(t1.split())
    words2 = set(t2.split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    return len(intersection) / max(len(words1), len(words2))


def deduplicate(candidates):
    seen_ids = {}
    seen_urls = {}
    unique = []
    for c in candidates:
        sid = c.get("source_id", "")
        url = c.get("canonical_url", "")
        if sid and sid in seen_ids:
            seen_ids[sid]["duplicate_count"] = seen_ids[sid].get("duplicate_count", 1) + 1
            continue
        if url and url in seen_urls:
            seen_urls[url]["duplicate_count"] = seen_urls[url].get("duplicate_count", 1) + 1
            continue
        seen_ids[sid] = c
        seen_urls[url] = c
        c["_dedup_key"] = sid
        unique.append(c)

    title_deduped = []
    for i, c in enumerate(unique):
        is_dup = False
        for j, other in enumerate(unique):
            if i >= j:
                continue
            sim = _title_similarity(c.get("title", ""), other.get("title", ""))
            if sim > 0.85:
                is_dup = True
                break
        if not is_dup:
            title_deduped.append(c)
        else:
            pass
    return title_deduped


def filter_by_match_relevance(candidates, match_facts):
    if not match_facts:
        return candidates
    opponent = (match_facts.get("opponent") or "").lower().strip()
    date_str = (match_facts.get("date") or "").lower().strip()
    score = (match_facts.get("score") or "").lower().strip()
    match_name = (match_facts.get("match") or "").lower().strip()

    kept = []
    rejected = []
    for c in candidates:
        title = c.get("title_lower", "")
        keywords = [opponent, date_str, score, match_name]
        keywords = [k for k in keywords if k and len(k) > 2]
        match_score = 0
        for kw in keywords:
            if kw in title:
                match_score += 1
        c["match_relevance_score"] = match_score
        if match_score > 0 or not keywords:
            c["verified_match_relevance"] = "relevant" if match_score > 0 else "unknown"
            kept.append(c)
        else:
            c["verified_match_relevance"] = "irrelevant"
            rejected.append(c)

    return kept


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
    run_dir = BASE_DIR / "state" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    title = job.get("title", "")
    theme = job.get("theme", "")

    match_facts = load_match_fact_lock(run_dir)

    print(f"Job title: {title}")
    print(f"Job theme: {theme}")
    if match_facts:
        print(f"Match facts loaded: {match_facts.get('match', 'unknown')} vs {match_facts.get('opponent', '?')}")
    else:
        print("No match fact lock found. Using raw title/theme search.")

    all_candidates = []
    queries = []

    if match_facts:
        opponent = match_facts.get("opponent", "")
        date_str = match_facts.get("date", "")
        stage = match_facts.get("competition_stage", "")
        match_name = match_facts.get("match", "")
        if opponent and date_str:
            queries.append(f"{opponent} {date_str} highlights")
            queries.append(f"{opponent} {date_str} full match")
        if stage:
            queries.append(f"{opponent} {stage} highlights")
        if match_name:
            queries.append(match_name)
    if title:
        queries.append(title)
    if theme:
        queries.append(theme)
    if not queries:
        queries = ["sports highlights"]

    queries = list(dict.fromkeys(queries))

    yt_dlp_failed = False
    for query in queries:
        print(f"Searching (yt-dlp): {query}")
        results = search_ytdlp(query, max_results=8)
        all_candidates.extend(results)
        if not results:
            yt_dlp_failed = True

    if not all_candidates and yt_dlp_failed:
        tavily_queries = queries
        if match_facts:
            opponent = match_facts.get("opponent", "")
            date_str = match_facts.get("date", "")
            stage = match_facts.get("competition_stage", "") or match_facts.get("stage_or_round", "")
            match_name = match_facts.get("match", "")
            tavily_queries = []
            if opponent and date_str:
                tavily_queries.append(f"{opponent} vs Egypt 2026 FIFA World Cup {stage} {date_str}")
                tavily_queries.append(f"{opponent} Egypt World Cup 2026 highlights")
                tavily_queries.append(f"{opponent} vs Egypt 2026 {stage} highlights")
            if match_name:
                tavily_queries.append(match_name)
            tavily_queries = list(dict.fromkeys(tavily_queries))
            if not tavily_queries:
                tavily_queries = queries
        print("yt-dlp returned no results. Falling back to Tavily search...")
        for query in tavily_queries:
            print(f"Searching (Tavily): {query}")
            results = search_tavily(query, max_results=10)
            all_candidates.extend(results)

    candidates = deduplicate(all_candidates)

    if match_facts:
        candidates = filter_by_match_relevance(candidates, match_facts)

    for rank, c in enumerate(candidates, 1):
        c["initial_rank"] = rank

    report = {
        "run_id": run_id,
        "job_title": title,
        "job_theme": theme,
        "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
        "total_candidates": len(candidates),
        "sources_queried": queries,
        "match_facts_loaded": match_facts is not None,
        "candidates": candidates,
        "title_claim_status": "unverified",
        "title_claim_evidence": None,
        "blocker": None,
    }

    if "nobody expected" in title.lower() or "hardest" in title.lower():
        report["title_claim_status"] = "creative_hypothesis"
        report["title_claim_evidence"] = (
            "Title contains subjective claims ('Nobody Expected', 'Hardest'). "
            "Actual public expectation data not verified. "
            "Recommend softening wording if factual support is missing."
        )
        print(f"  Title claim: {report['title_claim_status']}")

    if not candidates:
        report["blocker"] = (
            "No source candidates found. yt-dlp may be unavailable, "
            "or search queries returned no results."
        )

    candidates_path = run_dir / "source_candidates.json"
    with open(candidates_path, "w") as f:
        json.dump(report, f, indent=2)

    md_path = run_dir / "source_discovery_report.md"
    with open(md_path, "w") as f:
        f.write(f"# Source Discovery Report\n\n")
        f.write(f"Run: {run_id}\n")
        f.write(f"Title: {title}\n")
        f.write(f"Theme: {theme}\n\n")
        f.write(f"Match facts loaded: {match_facts is not None}\n")
        if match_facts:
            f.write(f"Verified match: {match_facts.get('match', '?')} vs {match_facts.get('opponent', '?')}\n")
            f.write(f"Date: {match_facts.get('date', '?')}\n")

        f.write(f"\n## Queries Used\n\n")
        for q in queries:
            f.write(f"- {q}\n")

        f.write(f"\n## Candidates ({len(candidates)})\n\n")
        for c in candidates[:20]:
            f.write(f"### {c.get('source_id', '?')}\n")
            f.write(f"- URL: {c.get('canonical_url', '?')}\n")
            f.write(f"- Title: {c.get('title', '?')}\n")
            f.write(f"- Match Relevance: {c.get('verified_match_relevance', 'unknown')}\n")
            f.write(f"- Initial Rank: {c.get('initial_rank', '?')}\n")
            f.write(f"- Platform: {c.get('platform', '?')}\n\n")

        f.write(f"\n## Title Claim Status\n\n")
        f.write(f"Status: {report['title_claim_status']}\n")
        if report.get("title_claim_evidence"):
            f.write(f"Note: {report['title_claim_evidence']}\n")

        if report.get("blocker"):
            f.write(f"\n## Blocker\n\n{report['blocker']}\n")

    print(f"Source candidates: {candidates_path}")
    print(f"Total candidates (deduplicated): {len(candidates)}")

    if report.get("blocker"):
        print(f"BLOCKER: {report['blocker']}")


if __name__ == "__main__":
    main()
