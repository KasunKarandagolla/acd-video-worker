"""Worker-owned source manifest and sequential acquisition boundary."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def _atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


SENSITIVE_QUERY_PARTS = ("token", "key", "auth", "signature", "sig", "credential", "password", "secret")


def sanitize_reference(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        query = urlencode([
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not any(part in key.lower() for part in SENSITIVE_QUERY_PARTS)
        ])
        return urlunparse((parsed.scheme, host, parsed.path, parsed.params, query, ""))
    return str(Path(value).expanduser().resolve())


class SourceService:
    """Prepare user inputs and expose existing replacement acquisition."""

    def prepare_manifest(self, path: Path, references: Iterable[str]) -> dict:
        entries = []
        for index, raw in enumerate(references):
            reference = sanitize_reference(raw)
            parsed = urlparse(reference)
            if parsed.scheme in {"http", "https"}:
                entries.append({
                    "source_id": f"input_url_{index + 1}",
                    "kind": "url",
                    "original_url": reference,
                    "availability_status": "candidate_url",
                    "technical_verification_status": "not_acquired",
                    "rights_status": "unverified",
                    "rights_evidence": [],
                    "license": "unknown",
                    "provenance": {"origin": "user_reference"},
                })
                continue
            local = Path(reference)
            entry = {
                "source_id": f"input_file_{index + 1}",
                "kind": "local_file",
                "path": str(local),
                "availability_status": "available" if local.is_file() else "missing",
                "technical_verification_status": "not_probed",
                "rights_status": "user_supplied_unverified",
                "rights_evidence": [],
                "license": "unknown",
                "provenance": {"origin": "user_supplied_file"},
            }
            if local.is_file():
                digest = hashlib.sha256()
                with local.open("rb") as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(block)
                entry.update({"size_bytes": local.stat().st_size, "sha256": digest.hexdigest()})
            entries.append(entry)
        manifest = {
            "schema_version": "1.0",
            "policy": {
                "free_only": True,
                "no_access_control_bypass": True,
                "rights_verification_required": True,
            },
            "sources": entries,
            "acquisition_attempts": [],
        }
        _atomic_json(Path(path), manifest)
        return manifest

    def acquire(self, manifest_path: Path, urls: list[str], story_slot: str, output_dir: Path) -> dict:
        """Try ranked URLs sequentially using the existing acquisition engine."""
        if not urls:
            raise ValueError("At least one candidate URL is required")
        if any(urlparse(url).scheme not in {"http", "https"} for url in urls):
            raise ValueError("Only http(s) source candidates are accepted")
        urls = [sanitize_reference(url) for url in urls]

        # Lazy imports keep intake usable when optional yt-dlp is not installed.
        from acd_worker.source.acquisition import AcquisitionEngine
        from acd_worker.source.discovery import SourceCandidate

        candidates = [
            SourceCandidate(
                candidate_id=f"{story_slot}_{index + 1}_{uuid.uuid4().hex[:6]}",
                url=url,
                video_id="",
                title=f"Agent candidate {index + 1}",
                channel="unknown",
                duration=0,
                upload_date="",
                thumbnail="",
                query="agent-selected candidate",
                story_slot=story_slot,
                verification_status="unverified",
                discovery_method="hermes_request",
                metadata_confidence="low",
                deep_analysis_candidate="yes",
            )
            for index, url in enumerate(urls)
        ]
        engine = AcquisitionEngine(str(output_dir), max_attempts_per_slot=len(candidates))
        acquired, attempts = engine.acquire_for_slot(candidates, story_slot, f"{story_slot}_clip")

        manifest_path = Path(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.setdefault("acquisition_attempts", []).extend(attempt.to_dict() for attempt in attempts)
        if acquired:
            manifest.setdefault("sources", []).append(acquired.to_dict())
        _atomic_json(manifest_path, manifest)
        return {"acquired": acquired.to_dict() if acquired else None, "attempts": [a.to_dict() for a in attempts]}
