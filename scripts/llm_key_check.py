#!/usr/bin/env python3
"""Check LLM API key connectivity using OpenAI-compatible endpoint."""
import json
import os
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

REPORT_PATH = "state/runs/llm_key_check.json"


def main():
    api_key = os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "")
    model = os.environ.get("LLM_MODEL", "")

    endpoint_host = ""
    if base_url:
        try:
            endpoint_host = urlparse(base_url).hostname or ""
        except Exception:
            endpoint_host = base_url

    result = {
        "api_key_set": bool(api_key),
        "base_url_set": bool(base_url),
        "model_set": bool(model),
        "endpoint_accessible": False,
        "error": None,
        "llm_status": "unknown",
        "model": model or "",
        "endpoint_host": endpoint_host,
        "attempts": [],
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }

    if not api_key:
        result["error"] = "LLM_API_KEY not set"
        print("WARN: LLM_API_KEY not set")
    if not base_url:
        result["error"] = result.get("error") or "LLM_BASE_URL not set"
        print("WARN: LLM_BASE_URL not set")
    if not model:
        result["error"] = result.get("error") or "LLM_MODEL not set"
        print("WARN: LLM_MODEL not set")

    if api_key and base_url:
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model or "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are a connectivity test."},
                {"role": "user", "content": "Reply OK only."}
            ],
            "temperature": 0.2,
            "max_tokens": 64,
            "stream": False
        }

        max_retries = 3
        retryable_codes = {429, 500, 502, 503, 504}

        for attempt in range(1, max_retries + 1):
            attempt_record = {"attempt": attempt, "status_code": None, "error": None}
            try:
                import requests
                resp = requests.post(url, headers=headers, json=payload, timeout=30)
                attempt_record["status_code"] = resp.status_code

                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        reply = choices[0].get("message", {}).get("content", "").strip()
                        if reply:
                            result["endpoint_accessible"] = True
                            result["llm_status"] = "available"
                            attempt_record["reply_length"] = len(reply)
                            print(f"LLM endpoint accessible. Reply received ({len(reply)} chars).")
                            result["attempts"].append(attempt_record)
                            break
                        else:
                            attempt_record["error"] = "empty assistant reply"
                            result["error"] = "empty assistant reply"
                    else:
                        attempt_record["error"] = "no choices in response"
                        result["error"] = "no choices in response"
                elif resp.status_code in retryable_codes and attempt < max_retries:
                    wait = 2 ** attempt
                    attempt_record["error"] = f"HTTP {resp.status_code} (retrying in {wait}s)"
                    print(f"  Attempt {attempt}: HTTP {resp.status_code}, retrying in {wait}s...")
                    result["attempts"].append(attempt_record)
                    time.sleep(wait)
                    continue
                elif resp.status_code in retryable_codes:
                    attempt_record["error"] = f"HTTP {resp.status_code}"
                    result["error"] = f"HTTP {resp.status_code} after {max_retries} retries"
                else:
                    attempt_record["error"] = f"HTTP {resp.status_code}"
                    result["error"] = f"HTTP {resp.status_code}"
            except Exception as e:
                attempt_record["error"] = type(e).__name__
                if attempt < max_retries:
                    wait = 2 ** attempt
                    print(f"  Attempt {attempt}: {type(e).__name__}, retrying in {wait}s...")
                    result["attempts"].append(attempt_record)
                    time.sleep(wait)
                    continue
                result["error"] = f"{type(e).__name__} after {max_retries} retries"

            result["attempts"].append(attempt_record)

        if not result["endpoint_accessible"]:
            result["llm_status"] = "blocked"
            print(f"WARN: LLM endpoint not accessible after {max_retries} attempts. Status: blocked")

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
