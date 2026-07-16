"""Optional best-effort macro-state notifications."""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Optional

from .run_state import RunState


class DiscordNotifier:
    def __init__(self, webhook_url: str = "", timeout: int = 10):
        self.webhook_url = webhook_url.strip()
        self.timeout = timeout
        self.log = logging.getLogger("acd_worker.notifications")

    @property
    def enabled(self) -> bool:
        return self.webhook_url.startswith("https://")

    def started(self, state: RunState) -> None:
        self._send("ACD run started", f"Project: `{state.project_id}`\nRun: `{state.run_id}`", 0x3498DB)

    def terminal(self, state: RunState) -> None:
        details = ""
        if state.blocker:
            details = f"\nBlocker: `{state.blocker.code}` — {state.blocker.message[:350]}"
        elif state.error:
            details = f"\nError: `{state.error.code}` — {state.error.message[:350]}"
        elif state.validation:
            valid = next((item.get("path") for item in state.validation if item.get("valid")), None)
            if valid:
                details = f"\nOutput: `{valid}`"
        colors = {"DELIVERED": 0x2ECC71, "BLOCKED": 0xF39C12, "FAILED": 0xE74C3C}
        self._send(f"ACD run {state.status.value.lower()}", f"Project: `{state.project_id}`\nRun: `{state.run_id}`{details}", colors.get(state.status.value, 0x3498DB))

    def _send(self, title: str, description: str, color: int) -> None:
        if not self.enabled:
            return
        payload = {"embeds": [{"title": title, "description": description, "color": color}]}
        try:
            request = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response.read(1)
        except Exception as exc:
            # Notifications are observability only and never affect production.
            self.log.warning("Discord notification failed: %s", exc)
