#!/usr/bin/env python3
"""Check LLM API key connectivity using OpenAI-compatible endpoint."""
import json
import os
import sys

REPORT_PATH = "state/runs/llm_key_check.json"

def main():
    api_key = os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "")
    model = os.environ.get("LLM_MODEL", "")

    result = {
        "api_key_set": bool(api_key),
        "base_url_set": bool(base_url),
        "model_set": bool(model),
        "endpoint_accessible": False,
        "error": None,
        "timestamp_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z"
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
            "messages": [{"role": "user", "content": "Reply OK only."}],
            "max_tokens": 10
        }
        try:
            import requests
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                choice = data.get("choices", [{}])[0]
                reply = choice.get("message", {}).get("content", "")
                result["endpoint_accessible"] = True
                result["llm_reply"] = reply.strip()
                print(f"LLM endpoint accessible. Reply: {reply.strip()}")
            else:
                error_detail = resp.text[:500]
                result["error"] = f"HTTP {resp.status_code}: {error_detail}"
                print(f"WARN: LLM endpoint returned {resp.status_code}")
                # Do not expose API key in output
        except Exception as e:
            result["error"] = f"Connection failed: {type(e).__name__}"
            print(f"WARN: LLM endpoint connection failed: {type(e).__name__}")

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Report written to {REPORT_PATH}")

if __name__ == "__main__":
    main()
