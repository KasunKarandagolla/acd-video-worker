#!/usr/bin/env python3
"""Search capability preflight.

Before current-event match identification, prove that Hermes has a
functioning search/retrieval route. Generic webpage access (curl, wget,
requests hitting google.com) is NOT search capability.

Classification:
  available  — a real text search query was executed, results returned,
               at least one result URL was retrieved.
  limited    — normal webpages can be retrieved but no real search-query
               capability is available.
  blocked    — neither search nor retrieval works.

For current-event jobs, limited blocks match_fact_lock.
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _try_execute_search(query: str, provider_name: str, config: dict) -> dict:
    """Try executing a real search query and returning results.

    Returns dict with search_provider, test_query, result_count,
    retrieved_result_url(s), and HTTP status.
    """
    out = {
        "search_provider": provider_name,
        "search_tool": config.get("tool", provider_name),
        "test_query": query,
        "result_count": 0,
        "retrieved_result_urls": [],
        "http_status": None,
        "error": None,
    }

    if provider_name == "googlesearch":
        try:
            from googlesearch import search
            urls = list(search(query, num_results=5))
            out["result_count"] = len(urls)
            out["retrieved_result_urls"] = urls[:3]
            out["http_status"] = 200 if urls else 204
        except Exception as e:
            out["error"] = str(e)[:200]
        return out

    if provider_name == "serper":
        api_key = os.environ.get("SERPER_API_KEY", "")
        if not api_key:
            out["error"] = "SERPER_API_KEY not set"
            return out
        try:
            import requests as req
            resp = req.post(
                "https://google.serper.dev/search",
                json={"q": query, "num": 5},
                headers={"X-API-KEY": api_key},
                timeout=15,
            )
            out["http_status"] = resp.status_code
            if resp.status_code == 200:
                data = resp.json()
                organic = data.get("organic", [])
                out["result_count"] = len(organic)
                out["retrieved_result_urls"] = [r.get("link", "") for r in organic[:3]]
        except Exception as e:
            out["error"] = str(e)[:200]
        return out

    if provider_name == "tavily":
        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            out["error"] = "TAVILY_API_KEY not set"
            return out
        try:
            import requests as req
            resp = req.post(
                "https://api.tavily.com/search",
                json={"query": query, "max_results": 5},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15,
            )
            out["http_status"] = resp.status_code
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                out["result_count"] = len(results)
                out["retrieved_result_urls"] = [r.get("url", "") for r in results[:3]]
        except Exception as e:
            out["error"] = str(e)[:200]
        return out

    if provider_name == "brave":
        api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
        if not api_key:
            out["error"] = "BRAVE_SEARCH_API_KEY not set"
            return out
        try:
            import requests as req
            resp = req.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 5},
                headers={"Accept": "application/json", "X-Subscription-Token": api_key},
                timeout=15,
            )
            out["http_status"] = resp.status_code
            if resp.status_code == 200:
                web = resp.json().get("web", {})
                results = web.get("results", [])
                out["result_count"] = len(results)
                out["retrieved_result_urls"] = [r.get("url", "") for r in results[:3]]
        except Exception as e:
            out["error"] = str(e)[:200]
        return out

    out["error"] = f"Unknown provider: {provider_name}"
    return out


def _detect_search_providers() -> list:
    """Detect available search providers without running a query."""
    providers = []

    try:
        import googlesearch
        providers.append({
            "name": "googlesearch",
            "module": "googlesearch",
            "type": "python_module",
            "config": {"tool": "googlesearch.search"},
            "needs_api_key": False,
        })
    except ImportError:
        pass

    serper_key = os.environ.get("SERPER_API_KEY", "")
    if serper_key:
        providers.append({
            "name": "serper",
            "module": "requests",
            "type": "api",
            "config": {"tool": "serper.dev"},
            "needs_api_key": True,
        })

    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    if tavily_key:
        providers.append({
            "name": "tavily",
            "module": "requests",
            "type": "api",
            "config": {"tool": "tavily.com"},
            "needs_api_key": True,
        })

    brave_key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
    if brave_key:
        providers.append({
            "name": "brave",
            "module": "requests",
            "type": "api",
            "config": {"tool": "search.brave.com"},
            "needs_api_key": True,
        })

    return providers


def check_retrieval() -> dict:
    """Check if generic webpage retrieval works. NOT search capability."""
    result = {
        "authoritative_retrieval_status": "blocked",
        "test_urls_tried": [],
        "last_error": None,
        "fetched_content_length": 0,
    }
    import urllib.request
    import urllib.error

    test_urls = [
        "https://en.wikipedia.org",
        "https://api.github.com",
    ]
    for url in test_urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read()
                result["authoritative_retrieval_status"] = "available"
                result["test_urls_tried"].append({
                    "url": url, "status": resp.status, "bytes": len(content),
                })
                result["fetched_content_length"] = len(content)
                break
        except Exception as e:
            result["test_urls_tried"].append({"url": url, "error": str(e)[:100]})
            result["last_error"] = str(e)[:200]

    return result


def main():
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
        "current_event_fact_verification": "blocked",
        "search_providers_detected": [],
        "search_results": [],
        "retrieval": None,
        "blocker": None,
        "recommendations": [],
    }

    providers = _detect_search_providers()
    result["search_providers_detected"] = [
        {"name": p["name"], "module": p["module"], "needs_api_key": p["needs_api_key"]}
        for p in providers
    ]

    test_query = "Argentina football latest news 2026"
    search_success = False
    for p in providers:
        sr = _try_execute_search(test_query, p["name"], p.get("config", {}))
        result["search_results"].append(sr)
        if sr["result_count"] > 0 and sr["retrieved_result_urls"]:
            search_success = True
            break

    retrieval = check_retrieval()
    result["retrieval"] = retrieval

    if search_success:
        result["current_event_fact_verification"] = "available"
    elif retrieval.get("authoritative_retrieval_status") == "available":
        result["current_event_fact_verification"] = "limited"
        result["blocker"] = (
            "Webpage retrieval works but no real search-query capability is available. "
            "Cannot verify current-event match facts using YouTube titles only. "
            "Install googlesearch-python or set SERPER_API_KEY / TAVILY_API_KEY / BRAVE_SEARCH_API_KEY."
        )
        result["recommendations"].append(
            "Install googlesearch-python (pip install googlesearch-python) or set a "
            "search API key env var (SERPER_API_KEY, TAVILY_API_KEY, BRAVE_SEARCH_API_KEY)."
        )
    else:
        result["current_event_fact_verification"] = "blocked"
        result["blocker"] = (
            "No search or retrieval capability is available. "
            "Cannot verify current-event match facts."
        )
        result["recommendations"].append(
            "Install googlesearch-python or set a search API key env var, and "
            "ensure outbound internet access."
        )

    report_path = BASE_DIR / "state" / "runs" / "search_capability_preflight.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2)

    md_path = BASE_DIR / "state" / "runs" / "search_capability_preflight.md"
    with open(md_path, "w") as f:
        f.write(f"# Search Capability Preflight\n\n")
        f.write(f"Timestamp: {result['timestamp_utc']}\n\n")
        f.write(f"## Current-Event Fact Verification\n\n{result['current_event_fact_verification']}\n\n")
        f.write(f"## Search Providers Detected\n\n")
        for sp in result["search_providers_detected"]:
            f.write(f"- {sp['name']} (module={sp['module']}, needs_api_key={sp['needs_api_key']})\n")
        f.write(f"\n## Search Results\n\n")
        for sr in result["search_results"]:
            f.write(f"- Provider: {sr.get('search_provider')}\n")
            f.write(f"  Query: {sr.get('test_query')}\n")
            f.write(f"  Result count: {sr.get('result_count')}\n")
            f.write(f"  URLs: {sr.get('retrieved_result_urls')}\n")
            f.write(f"  HTTP status: {sr.get('http_status')}\n")
            if sr.get("error"):
                f.write(f"  Error: {sr['error']}\n")
        f.write(f"\n## Retrieval\n\n")
        f.write(f"- Status: {retrieval.get('authoritative_retrieval_status')}\n")
        f.write(f"- Fetchable bytes: {retrieval.get('fetched_content_length')}\n")
        if result.get("recommendations"):
            f.write(f"\n## Recommendations\n\n")
            for r in result["recommendations"]:
                f.write(f"- {r}\n")
        if result.get("blocker"):
            f.write(f"\n## Blocker\n\n{result['blocker']}\n")

    print(f"Search capability preflight: {report_path}")
    print(f"Fact verification status: {result['current_event_fact_verification']}")
    print(f"Search providers detected: {len(result['search_providers_detected'])}")

    if result["current_event_fact_verification"] != "available":
        print(f"\nBLOCKER: {result['blocker']}")
        sys.exit(1)

    print("Proceeding: search capability sufficient.")


if __name__ == "__main__":
    main()
