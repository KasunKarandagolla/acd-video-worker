"""Pinned OpenMontage production compatibility, separate from creative choice."""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


PINNED_OPENMONTAGE_COMMIT = "f633b5f428b9be9a2afecba851dfddd101619756"
COMPATIBILITY_MARKER = ".acd-compatibility-patches.json"
CINEMATIC_PROPS_PATCH = "cinematic-cut-props-v1"
AUDITED_OPENMONTAGE_PATHS = {
    "lib/media_profiles.py",
    "remotion-composer/src/CinematicRenderer.tsx",
    "remotion-composer/src/CollageBurst.tsx",
    "remotion-composer/src/Explainer.tsx",
    "remotion-composer/src/LyricOverlay.tsx",
    "remotion-composer/src/TitledVideo.tsx",
    "scripts/scaffold_atelier_project.py",
    "tools/video/video_compose.py",
}


@dataclass(frozen=True)
class RuntimeTuple:
    pipeline: str
    composition_mode: str
    renderer_family: str
    render_runtime: str

    @classmethod
    def from_edit_decisions(cls, pipeline: str, payload: dict[str, Any]) -> "RuntimeTuple":
        return cls(
            pipeline=str(pipeline or "").strip(),
            composition_mode=str(payload.get("composition_mode") or "").strip(),
            renderer_family=str(payload.get("renderer_family") or "").strip(),
            render_runtime=str(payload.get("render_runtime") or "").strip(),
        )


@dataclass(frozen=True)
class CompatibilityDecision:
    supported: bool
    code: str
    reason: str
    runtime: RuntimeTuple
    openmontage_commit: Optional[str] = None
    required_patch: Optional[str] = None
    missing_capabilities: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OpenMontageCompatibilityRegistry:
    """Fail closed on runtime tuples not certified at the pinned commit.

    The registry is deliberately technical. Hermes may choose the creative
    pipeline and renderer, but native execution cannot begin until this gate
    accepts the resulting typed tuple.
    """

    _EXPLAINER_FAMILIES = {
        "explainer-data",
        "explainer-teacher",
        "product-reveal",
        "screen-demo",
        "animation-first",
    }
    _CINEMATIC_FAMILIES = {"cinematic-trailer", "documentary-montage"}

    def __init__(self, openmontage_root: Path, worker_root: Optional[Path] = None):
        self.root = Path(openmontage_root).expanduser().resolve()
        self.worker_root = Path(worker_root).expanduser().resolve() if worker_root else None

    def evaluate(self, runtime: RuntimeTuple) -> CompatibilityDecision:
        commit = self._commit()
        if commit != PINNED_OPENMONTAGE_COMMIT:
            return self._no(
                runtime,
                "OPENMONTAGE_PIN_MISMATCH",
                f"Expected OpenMontage {PINNED_OPENMONTAGE_COMMIT}, found {commit or 'unknown'}.",
                commit=commit,
            )

        missing = self._missing_runtime_capabilities(runtime)
        if missing:
            return self._no(
                runtime,
                "OPENMONTAGE_RUNTIME_UNAVAILABLE",
                "The selected native runtime is not completely installed.",
                commit=commit,
                missing=missing,
            )

        if runtime.composition_mode == "atelier":
            if runtime.render_runtime != "remotion":
                return self._no(runtime, "UNSUPPORTED_RUNTIME_TUPLE", "Atelier is a Remotion-only native path at this pin.", commit=commit)
            return self._yes(runtime, "Native atelier execution is available.", commit)

        if runtime.composition_mode != "templated":
            return self._no(runtime, "UNSUPPORTED_RUNTIME_TUPLE", "composition_mode must be templated or atelier.", commit=commit)

        if runtime.render_runtime == "ffmpeg":
            return self._yes(runtime, "Native cut-schema FFmpeg execution is available.", commit)
        if runtime.render_runtime == "hyperframes":
            return self._yes(runtime, "Native HyperFrames execution is available.", commit)
        if runtime.render_runtime != "remotion":
            return self._no(runtime, "UNSUPPORTED_RUNTIME_TUPLE", "Unknown render_runtime.", commit=commit)

        if runtime.renderer_family in self._EXPLAINER_FAMILIES:
            return self._yes(runtime, "The pinned Explainer composition consumes canonical cuts directly.", commit)
        if runtime.renderer_family in self._CINEMATIC_FAMILIES:
            if CINEMATIC_PROPS_PATCH not in self._patches():
                return self._no(
                    runtime,
                    "OPENMONTAGE_COMPATIBILITY_PATCH_MISSING",
                    "The pinned CinematicRenderer requires the certified cuts-to-scenes compatibility patch.",
                    commit=commit,
                    required_patch=CINEMATIC_PROPS_PATCH,
                )
            return self._yes(runtime, "Certified native cuts-to-scenes adapter is installed.", commit, CINEMATIC_PROPS_PATCH)
        return self._no(runtime, "UNSUPPORTED_RUNTIME_TUPLE", "Renderer family has no certified Remotion handoff at this pin.", commit=commit)

    def _missing_runtime_capabilities(self, runtime: RuntimeTuple) -> tuple[str, ...]:
        missing: list[str] = []
        python = Path(os.environ.get("OPENMONTAGE_PYTHON", self.root / ".venv" / "bin" / "python")).expanduser()
        if not python.is_file():
            missing.append("openmontage_python")
        if runtime.render_runtime in {"remotion", "hyperframes"}:
            if not shutil.which("npx"):
                missing.append("npx")
            if runtime.render_runtime == "remotion":
                composer = self.root / "remotion-composer"
                cli = composer / "node_modules" / ".bin" / "remotion"
                if not cli.is_file():
                    missing.append("remotion_cli")
                browser_root = composer / "node_modules" / ".remotion"
                browser = any(
                    path.is_file() and os.access(path, os.X_OK)
                    for path in browser_root.rglob("chrome-headless-shell*")
                ) if browser_root.is_dir() else False
                if not browser:
                    missing.append("remotion_browser")
        if runtime.render_runtime == "ffmpeg" and not shutil.which("ffmpeg"):
            missing.append("ffmpeg")
        return tuple(missing)

    def _commit(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return result.stdout.strip() if result.returncode == 0 else None

    def _patches(self) -> set[str]:
        path = self.root / COMPATIBILITY_MARKER
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        if payload.get("openmontage_commit") != PINNED_OPENMONTAGE_COMMIT:
            return set()
        overlays = payload.get("overlay_sha256")
        if not isinstance(overlays, dict) or not overlays:
            return set()
        for relative, expected in overlays.items():
            try:
                installed = (self.root / str(relative)).resolve()
                installed.relative_to(self.root)
                actual = hashlib.sha256(installed.read_bytes()).hexdigest()
            except (OSError, ValueError):
                return set()
            if actual != expected:
                return set()
        if self.worker_root:
            patch = self.worker_root / "patches" / "openmontage" / "f633b5f-cinematic-cut-props-v1.patch"
            try:
                patch_hash = hashlib.sha256(patch.read_bytes()).hexdigest()
            except OSError:
                return set()
            if payload.get("patch_sha256") != patch_hash:
                return set()
            reverse = subprocess.run(
                ["git", "-C", str(self.root), "apply", "--reverse", "--check", str(patch)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if reverse.returncode != 0:
                return set()
            modified = subprocess.run(
                ["git", "-C", str(self.root), "diff", "--name-only"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if modified.returncode != 0 or set(modified.stdout.splitlines()) != AUDITED_OPENMONTAGE_PATHS:
                return set()
        return {str(item) for item in payload.get("patches") or []}

    @staticmethod
    def _yes(runtime: RuntimeTuple, reason: str, commit: str, patch: Optional[str] = None) -> CompatibilityDecision:
        return CompatibilityDecision(True, "SUPPORTED", reason, runtime, commit, patch)

    @staticmethod
    def _no(
        runtime: RuntimeTuple,
        code: str,
        reason: str,
        *,
        commit: Optional[str],
        required_patch: Optional[str] = None,
        missing: tuple[str, ...] = (),
    ) -> CompatibilityDecision:
        return CompatibilityDecision(False, code, reason, runtime, commit, required_patch, missing)
