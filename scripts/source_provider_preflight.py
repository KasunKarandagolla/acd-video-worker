#!/usr/bin/env python3
"""Source provider preflight — runs before Hermes.

Checks:
1. yt-dlp import or executable availability (self-healing in Kaggle)
2. Tavily availability when TAVILY_API_KEY is set
3. At least one search provider available

If no provider is available, fails immediately before Hermes with:
  error_type: source_provider_unavailable
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.source_acquisition import ensure_yt_dlp_available, check_ytdlp_availability

BASE_DIR = Path(__file__).resolve().parent.parent


def _check_tavily_availability() -> dict:
    """Check if Tavily API key is set and reachable."""
    result = {
        "available": False,
        "error": None,
    }
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        result["error"] = "TAVILY_API_KEY not set"
        return result
    result["available"] = True
    return result


def main():
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
        "providers": {},
        "any_provider_available": False,
        "error_type": None,
        "error_message": None,
        "blocker": None,
    }

    yt_result = ensure_yt_dlp_available()
    result["providers"]["yt_dlp"] = {
        "available": yt_result.get("available", False),
        "method": yt_result.get("method"),
        "error": yt_result.get("error"),
    }

    tavily_result = _check_tavily_availability()
    result["providers"]["tavily"] = {
        "available": tavily_result.get("available", False),
        "error": tavily_result.get("error"),
    }

    yt_available = yt_result.get("available", False)
    yt_cli = check_ytdlp_availability()
    has_yt = yt_available or yt_cli.get("ytdlp_installed", False)

    has_tavily = tavily_result.get("available", False)

    any_available = has_yt or has_tavily
    result["any_provider_available"] = any_available

    if not any_available:
        result["error_type"] = "source_provider_unavailable"
        result["error_message"] = (
            "No source provider available. "
            "yt-dlp not installed and TAVILY_API_KEY not set. "
            "Install yt-dlp or set TAVILY_API_KEY."
        )
        result["blocker"] = result["error_message"]

    report_path = BASE_DIR / "state" / "runs" / "source_provider_preflight.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Source provider preflight: {report_path}")
    print(f"  yt-dlp available: {yt_result.get('available', False)} (method={yt_result.get('method', 'N/A')})")
    print(f"  Tavily available: {has_tavily}")
    print(f"  Any provider available: {any_available}")

    if result.get("blocker"):
        print(f"  BLOCKER: {result['blocker']}")
        print(f"  error_type: {result['error_type']}")
        sys.exit(1)

    print("  Source provider preflight PASSED — proceeding.")


if __name__ == "__main__":
    main()
