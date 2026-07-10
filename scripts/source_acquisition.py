"""External source acquisition strategy.

YouTube has previously blocked Kaggle with:
"Sign in to confirm you're not a bot."

This module provides a provider abstraction with explicit statuses and
ordered source strategy.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class SourceStatus:
    AVAILABLE = "available"
    AUTHENTICATION_REQUIRED = "authentication_required"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


class SourceAcquisitionBlocked(Exception):
    pass


def _get_youtube_cookies_path() -> str:
    """Return YouTube cookies path if available, never print the value."""
    cookies = os.environ.get("YOUTUBE_COOKIES_FILE", "") or os.environ.get("YT_DLP_COOKIES_PATH", "")
    if cookies and Path(cookies).is_file():
        return cookies
    return ""


def check_ytdlp_availability() -> dict:
    """Check if yt-dlp is available and what its status is."""
    result = {
        "status": SourceStatus.UNAVAILABLE,
        "ytdlp_installed": False,
        "authentication": "none",
        "blocker": None,
    }
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        result["blocker"] = "yt-dlp not installed"
        return result

    result["ytdlp_installed"] = True

    cookies = _get_youtube_cookies_path()
    if cookies:
        result["authentication"] = "cookies_provided"
    else:
        result["authentication"] = "anonymous"

    try:
        proc = subprocess.run(
            [ytdlp, "--version"],
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode == 0:
            result["status"] = SourceStatus.AVAILABLE
            result["version"] = proc.stdout.strip()
        else:
            result["status"] = SourceStatus.UNAVAILABLE
            result["blocker"] = f"yt-dlp version check failed: {proc.stderr.strip()[:100]}"
    except Exception as e:
        result["status"] = SourceStatus.UNAVAILABLE
        result["blocker"] = str(e)[:200]

    return result


def _check_youtube_block() -> dict:
    """Check if YouTube search is blocked with bot detection."""
    result = {
        "youtube_search_blocked": False,
        "detection_evidence": None,
        "blocker": None,
    }
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        result["blocker"] = "yt-dlp not available"
        return result

    try:
        proc = subprocess.run(
            [ytdlp, "--flat-playlist", "-J", "--no-warnings",
             "ytsearch1:test query that should not match anything real"],
            capture_output=True, text=True, timeout=15
        )
        output = (proc.stdout + proc.stderr).lower()
        if "sign in" in output or "confirm" in output or "bot" in output:
            result["youtube_search_blocked"] = True
            result["detection_evidence"] = output[:300]
            result["blocker"] = "YouTube is blocking search: 'Sign in to confirm you are not a bot'"
    except subprocess.TimeoutExpired:
        result["blocker"] = "yt-dlp search timed out"
    except Exception as e:
        result["blocker"] = str(e)[:200]

    return result


def get_source_strategy() -> dict:
    """Return the ordered source acquisition strategy for the current run."""
    yt_status = check_ytdlp_availability()
    block_check = _check_youtube_block()

    strategy = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
        "ytdlp_status": yt_status,
        "youtube_block_check": block_check,
        "strategy_plan": [],
        "source_acquisition_blocked": False,
        "blocker": None,
    }

    # Preferred source strategy
    if yt_status["status"] == SourceStatus.AVAILABLE and not block_check.get("youtube_search_blocked"):
        strategy["strategy_plan"] = [
            {
                "priority": 1,
                "provider": "yt-dlp",
                "auth": yt_status["authentication"],
                "method": "YouTube search + download",
                "available": True,
            }
        ]
    elif yt_status["status"] == SourceStatus.AVAILABLE and block_check.get("youtube_search_blocked"):
        strategy["strategy_plan"] = [
            {
                "priority": 1,
                "provider": "yt-dlp",
                "auth": "none",
                "method": "YouTube search",
                "available": False,
                "blocker": block_check["blocker"],
            },
            {
                "priority": 2,
                "provider": "yt-dlp (authenticated)",
                "auth": "cookies",
                "method": "YouTube search with cookies",
                "available": bool(_get_youtube_cookies_path()),
                "note": "Requires YOUTUBE_COOKIES_FILE env pointing to valid cookies file",
            },
        ]
    else:
        strategy["strategy_plan"] = [
            {
                "priority": 1,
                "provider": "yt-dlp",
                "auth": "none",
                "method": "YouTube search",
                "available": yt_status["status"] == SourceStatus.AVAILABLE,
                "blocker": yt_status.get("blocker"),
            },
        ]

    # Check if any source is available
    any_available = any(s.get("available") for s in strategy["strategy_plan"])
    if not any_available:
        strategy["source_acquisition_blocked"] = True
        strategy["blocker"] = (
            "No source acquisition strategy available. "
            "YouTube search is blocked and no authenticated cookies are configured. "
            "Set YOUTUBE_COOKIES_FILE env var to a valid cookies.txt file."
        )

    return strategy


def check_and_warn():
    """Run source acquisition check and print warning if blocked."""
    strategy = get_source_strategy()
    if strategy.get("source_acquisition_blocked"):
        print(f"WARN: Source acquisition blocked: {strategy['blocker']}")
        print("Recommendation: Configure YOUTUBE_COOKIES_FILE or use PIPELINE_SYNTHETIC_E2E=1")
        return False
    return True
