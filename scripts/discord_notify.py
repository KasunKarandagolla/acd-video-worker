#!/usr/bin/env python3
"""Send a Discord webhook notification."""
import os
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python discord_notify.py <message>")
        sys.exit(1)

    message = " ".join(sys.argv[1:])
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

    if not webhook_url:
        print("WARN: DISCORD_WEBHOOK_URL not set. Skipping notification.")
        print(f"Would have sent: {message}")
        return

    try:
        import requests
        payload = {"content": message[:2000]}
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code not in (200, 204):
            print(f"WARN: Discord returned {resp.status_code}")
    except Exception as e:
        print(f"WARN: Discord notification failed: {e}")

if __name__ == "__main__":
    main()
