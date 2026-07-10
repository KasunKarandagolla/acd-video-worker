#!/usr/bin/env python3
"""
Validates the football-emotion-skill-system package structure.

Checks:
- Every skill has SKILL.md
- Every SKILL.md has strict YAML frontmatter parsed by PyYAML
- Required name/description fields exist
- Frontmatter name matches folder name
- Referenced local/shared/cross-skill reference files exist
- Required shared contracts/references exist
- evals.json is valid JSON

Usage:
    python3 tools/validate_skill_system.py [package_root]
"""

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("ERROR: PyYAML is required. Install with: python3 -m pip install pyyaml", file=sys.stderr)
    sys.exit(1)

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
REQUIRED_FRONTMATTER_FIELDS = ["name", "description"]
REQUIRED_SHARED_CONTRACTS = ["shared/contracts/pipeline-artifacts.md", "shared/contracts/openmontage-artifact-bridge.md"]
REQUIRED_SHARED_REFERENCES = [
    "shared/references/verification-standard.md",
    "shared/references/emotion-pattern-library.md",
    "shared/references/pro-editing-methodology.md",
    "shared/references/audio-emotion-playbook.md",
    "shared/references/pipeline-routing-guide.md",
    "shared/references/editorial-journey/social-edit-reasoning-router.md",
    "shared/references/editorial-journey/brief-interpretation.md",
    "shared/references/editorial-journey/sourcing-strategy.md",
    "shared/references/editorial-journey/clip-selection.md",
    "shared/references/editorial-journey/narrative-structure.md",
    "shared/references/editorial-journey/pacing-rhythm-cuts.md",
    "shared/references/editorial-journey/audio-music.md",
    "shared/references/editorial-journey/visual-cohesion.md",
    "shared/references/editorial-journey/graphics-typography.md",
    "shared/references/editorial-journey/assembly-workflow.md",
    "shared/references/editorial-journey/quality-assurance.md",
    "shared/references/editorial-journey/genre-playbooks.md",
    "shared/references/repo-bridge/repo-source-lock.md",
    "shared/references/repo-bridge/hermes-agent-contract.md",
    "shared/references/repo-bridge/openmontage-agent-contract.md",
    "shared/references/repo-bridge/openmontage-tool-registry-preflight.md",
    "shared/references/repo-bridge/openmontage-stage-skill-map.md",
    "shared/references/repo-bridge/install-layout.md",

    "shared/references/current-event-fact-lock.md",
    "shared/references/fact-provenance-standard.md",
    "shared/references/live-tournament-sourcing.md",
    "shared/references/dynamic-arc-revision.md",
    "shared/references/football-playbooks-defending-champion.md",
    "shared/references/penalty-shootout-subarc.md",
    "shared/references/native-language-commentary.md",
    "shared/references/commentary-crowd-clarity.md",
    "shared/references/hdr-sdr-handling.md",
    "shared/references/platform-export-optimization.md",
    "shared/references/social-sentiment-story-evidence.md",
    "shared/references/backlot-checkpoint-governance.md",
    "shared/references/broadcast-overlay-map.md",
    "shared/references/repo-bridge/repo-setup-status.md",
    "shared/references/repo-bridge/openmontage-schema-lock.md",
    "shared/references/user-supplied-footage-rights.md",
    "shared/references/reused-content-thresholds.md",
    "shared/references/repo-bridge/openmontage-zero-key-capability-envelope.md",
    "shared/references/repo-bridge/openmontage-pipeline-manifest-preflight.md",
    "shared/references/repo-bridge/hermes-runtime-skill-install.md",
    "shared/references/llm-decision-boundaries.md",
]

REF_PATH_RE = re.compile(
    r"`([a-zA-Z0-9\-_]+/references/[a-zA-Z0-9\-_./]+\.md|"
    r"references/[a-zA-Z0-9\-_./]+\.md|"
    r"shared/(?:references|contracts)/[a-zA-Z0-9\-_./]+\.md)`"
)

class Result:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = []

    def ok(self, msg): self.passed.append(msg)
    def fail(self, msg): self.errors.append(msg)
    def warn(self, msg): self.warnings.append(msg)
    @property
    def success(self): return not self.errors


def parse_frontmatter(text: str):
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, "No YAML frontmatter block found (must start with '---' on line 1)"
    raw = match.group(1)
    try:
        fields = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return None, f"Invalid YAML frontmatter: {exc}"
    if not isinstance(fields, dict):
        return None, "YAML frontmatter must parse to a mapping/object"
    return fields, None


def validate_skill(skill_dir: Path, result: Result, package_root: Path):
    skill_name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        result.fail(f"[{skill_name}] Missing SKILL.md")
        return

    text = skill_md.read_text(encoding="utf-8")
    if len(text.strip()) < 200:
        result.fail(f"[{skill_name}] SKILL.md is too small/empty for a functional skill")

    fields, err = parse_frontmatter(text)
    if err:
        result.fail(f"[{skill_name}] {err}")
        return

    for req in REQUIRED_FRONTMATTER_FIELDS:
        val = fields.get(req)
        if not isinstance(val, str) or not val.strip():
            result.fail(f"[{skill_name}] Missing or invalid required frontmatter field: '{req}'")
        else:
            result.ok(f"[{skill_name}] Has required field '{req}'")

    fm_name = fields.get("name")
    if isinstance(fm_name, str):
        if fm_name.strip() != skill_name:
            result.fail(f"[{skill_name}] Frontmatter name '{fm_name}' does not match folder name '{skill_name}'")
        else:
            result.ok(f"[{skill_name}] Frontmatter name matches folder name")
        if not re.match(r"^[a-z0-9][a-z0-9\-]*$", fm_name.strip()):
            result.warn(f"[{skill_name}] name '{fm_name}' should be lowercase with hyphens only")

    desc = fields.get("description")
    if isinstance(desc, str) and len(desc) < 40:
        result.warn(f"[{skill_name}] description is quite short ({len(desc)} chars)")

    referenced_paths = set(REF_PATH_RE.findall(text))
    for ref in referenced_paths:
        if ref.startswith("shared/"):
            candidate = package_root / ref
        elif ref.startswith("references/"):
            candidate = skill_dir / ref
        else:
            candidate = package_root / "skills" / ref
        if not candidate.exists():
            result.fail(f"[{skill_name}] References missing file: {ref} (expected at {candidate})")
        else:
            result.ok(f"[{skill_name}] Reference exists: {ref}")


def validate_shared(package_root: Path, result: Result):
    for rel in REQUIRED_SHARED_CONTRACTS + REQUIRED_SHARED_REFERENCES:
        p = package_root / rel
        if not p.exists():
            result.fail(f"Missing required shared file: {rel}")
        else:
            result.ok(f"Required shared file exists: {rel}")


def validate_evals(package_root: Path, result: Result):
    path = package_root / "evals" / "evals.json"
    if not path.exists():
        result.fail("Missing evals/evals.json")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        result.fail(f"evals/evals.json is not valid JSON: {exc}")
        return
    if not isinstance(data, dict) or not isinstance(data.get("evals"), list) or not data["evals"]:
        result.fail("evals/evals.json has no non-empty 'evals' array")
        return
    result.ok(f"evals/evals.json is valid JSON with {len(data['evals'])} evals")
    for i, ev in enumerate(data["evals"]):
        for field in ["id", "prompt", "assertions"]:
            if field not in ev:
                result.fail(f"evals/evals.json eval index {i} missing field '{field}'")



def validate_tools(package_root: Path, result: Result):
    required_tools = [
        "tools/validate_skill_system.py",
        "tools/validate_packaged_zip.py",
        "tools/bridge_preflight.py",
        "tools/openmontage_schema_probe.py",
        "tools/ffmpeg_loudness_check.py",
        "tools/fact_provenance_lint.py",
        "tools/memory_claim_lint.py",
        "tools/current_event_gate_lint.py",
    ]
    for rel in required_tools:
        p = package_root / rel
        if not p.exists():
            result.fail(f"Missing required tool: {rel}")
        elif p.stat().st_size < 200:
            result.fail(f"Required tool too small/empty: {rel}")
        else:
            result.ok(f"Required tool exists: {rel}")


def main():
    package_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    result = Result()
    skills_dir = package_root / "skills"
    if not skills_dir.exists():
        result.fail("Missing skills/ directory")
    else:
        for skill_dir in sorted([p for p in skills_dir.iterdir() if p.is_dir()]):
            validate_skill(skill_dir, result, package_root)
    validate_shared(package_root, result)
    validate_evals(package_root, result)
    validate_tools(package_root, result)

    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Passed checks:   {len(result.passed)}")
    print(f"Warnings:        {len(result.warnings)}")
    print(f"Errors:          {len(result.errors)}")
    if result.warnings:
        print("\nWARNINGS:")
        for w in result.warnings: print(f"  - {w}")
    if result.errors:
        print("\nERRORS:")
        for e in result.errors: print(f"  - {e}")
    print(f"\nResult: {'PASSED' if result.success else 'FAILED'}")
    return 0 if result.success else 1

if __name__ == "__main__":
    raise SystemExit(main())
