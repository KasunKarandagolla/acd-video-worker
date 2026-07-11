#!/usr/bin/env python3
"""Editorial artifact gate.

Prevents rendering unless ALL required V7 editorial artifacts exist
and pass basic schema/status checks. No four-artifact bypass.

Required artifacts derived from:
- OpenMontage pipeline manifest stages
- V7 editorial routing guide
- actual video type (football current-event)

For football current-event workflow, all 16 artifacts are required.
Each artifact may be explicitly not_applicable with a reason and gate validation.
"""
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

REQUIRED_ARTIFACTS = [
    "match_fact_lock.json",
    "brief_interpretation.json",
    "source_candidates.json",
    "source_verification.json",
    "media_probe.json",
    "visual_scene_analysis.json",
    "timestamp_candidates.json",
    "clip_scores.json",
    "arc_revision_gate.json",
    "story_plan.json",
    "audio_music_plan.json",
    "commentary_rights_check.json",
    "visual_cohesion_plan.json",
    "graphics_text_plan.json",
    "assembly_plan.json",
    "fact_provenance_gate.json",
    "editorial_journey_state.json",
]

ARTIFACT_SCHEMAS = {
    "match_fact_lock.json": {
        "required_fields": ["match", "opponent", "date", "score", "verification_status"],
        "status_field": "verification_status",
        "allowed_statuses": ["verified", "partial", "creative_hypothesis"],
        "note": "creative_hypothesis is valid for seed-based fact locks where score is not yet confirmed",
    },
    "brief_interpretation.json": {
        "required_fields": ["title", "theme", "emotional_arc"],
    },
    "source_candidates.json": {
        "required_fields": ["candidates"],
    },
    "source_verification.json": {
        "required_fields": ["verified_sources"],
    },
    "media_probe.json": {
        "required_fields": [],
        "note": "Schema: list of probe dicts (produced by media_analysis.py as JSON array)",
    },
    "visual_scene_analysis.json": {
        "required_fields": ["run_id", "files_analyzed", "probes"],
    },
    "timestamp_candidates.json": {
        "required_fields": ["timestamps"],
    },
    "clip_scores.json": {
        "required_fields": ["scores"],
    },
    "arc_revision_gate.json": {
        "required_fields": ["arc_decision", "status"],
    },
    "story_plan.json": {
        "required_fields": ["structure", "segments"],
    },
    "audio_music_plan.json": {
        "required_fields": ["audio_plan", "music_tracks"],
    },
    "commentary_rights_check.json": {
        "required_fields": ["rights_status", "commentary_status"],
    },
    "visual_cohesion_plan.json": {
        "required_fields": ["style_guide", "grade_decisions"],
    },
    "graphics_text_plan.json": {
        "required_fields": ["text_elements", "graphic_elements"],
    },
    "assembly_plan.json": {
        "required_fields": ["structure", "total_duration_seconds"],
    },
    "fact_provenance_gate.json": {
        "required_fields": ["verification_summary", "provenance_trail"],
    },
    "editorial_journey_state.json": {
        "required_fields": ["current_stage", "artifacts_produced", "artifacts_pending"],
    },
}


def check_artifact_gate(run_dir: Path) -> dict:
    result = {
        "gate_passed": False,
        "blocker": None,
        "artifacts_found": [],
        "artifacts_missing": [],
        "artifacts_explicitly_na": [],
        "artifacts_invalid": [],
        "match_fact_verified": False,
    }

    artifacts_dir = run_dir / "hermes_artifacts"

    for artifact_name in REQUIRED_ARTIFACTS:
        artifact_path = artifacts_dir / artifact_name
        if artifact_path.is_file():
            result["artifacts_found"].append(artifact_name)
            try:
                with open(artifact_path) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                result["artifacts_invalid"].append({
                    "artifact": artifact_name,
                    "error": f"Invalid JSON: {e}",
                })
                continue

            # Check for explicit not_applicable
            if isinstance(data, dict) and data.get("status") == "not_applicable":
                reason = data.get("reason", "No reason provided")
                gate_validation = data.get("gate_validation", False)
                if not gate_validation:
                    result["artifacts_invalid"].append({
                        "artifact": artifact_name,
                        "error": f"Marked not_applicable but gate_validation is False. Reason: {reason}",
                    })
                    continue
                result["artifacts_explicitly_na"].append({
                    "artifact": artifact_name,
                    "reason": reason,
                })
                continue

            schema = ARTIFACT_SCHEMAS.get(artifact_name, {})
            for field in schema.get("required_fields", []):
                if field not in data:
                    result["artifacts_invalid"].append({
                        "artifact": artifact_name,
                        "error": f"Missing required field: {field}",
                    })

            if artifact_name == "match_fact_lock.json":
                status = data.get("verification_status", "")
                if status in ("verified", "partial", "creative_hypothesis"):
                    result["match_fact_verified"] = True
                else:
                    result["artifacts_invalid"].append({
                        "artifact": artifact_name,
                        "error": f"Match fact not verified (status: {status})",
                    })
        else:
            result["artifacts_missing"].append(artifact_name)

    if result["artifacts_missing"]:
        result["blocker"] = (
            f"Missing required artifacts ({len(result['artifacts_missing'])}): "
            f"{', '.join(result['artifacts_missing'][:5])}..."
            if len(result["artifacts_missing"]) > 5
            else f"Missing required artifacts: {', '.join(result['artifacts_missing'])}"
        )
        return result

    if result["artifacts_invalid"]:
        first_invalid = result["artifacts_invalid"][0]
        result["blocker"] = f"Artifact validation failed: {first_invalid['artifact']} - {first_invalid['error']}"
        return result

    if not result["match_fact_verified"]:
        result["blocker"] = "Match facts not verified. Rejecting."
        return result

    result["gate_passed"] = True
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python editorial_artifact_gate.py <run_id>")
        sys.exit(1)

    run_id = sys.argv[1]
    run_dir = BASE_DIR / "state" / "runs" / run_id

    if not run_dir.is_dir():
        print(f"ERROR: Run directory not found: {run_dir}")
        sys.exit(1)

    result = check_artifact_gate(run_dir)

    gate_path = run_dir / "artifact_gate_result.json"
    with open(gate_path, "w") as f:
        json.dump(result, f, indent=2)

    md_path = run_dir / "artifact_gate_result.md"
    with open(md_path, "w") as f:
        f.write(f"# Editorial Artifact Gate\n\n")
        f.write(f"Run: {run_id}\n\n")
        f.write(f"Gate passed: {result['gate_passed']}\n\n")
        f.write(f"## Artifacts Found ({len(result['artifacts_found'])})\n\n")
        for a in result["artifacts_found"]:
            f.write(f"- {a}\n")
        f.write(f"\n## Artifacts Missing ({len(result['artifacts_missing'])})\n\n")
        for a in result["artifacts_missing"]:
            f.write(f"- {a}\n")
        if result["artifacts_explicitly_na"]:
            f.write(f"\n## Explicitly Not Applicable\n\n")
            for na in result["artifacts_explicitly_na"]:
                f.write(f"- {na['artifact']}: {na['reason']}\n")
        if result["artifacts_invalid"]:
            f.write(f"\n## Invalid Artifacts\n\n")
            for inv in result["artifacts_invalid"]:
                f.write(f"- {inv['artifact']}: {inv['error']}\n")
        if result.get("blocker"):
            f.write(f"\n## Blocker\n\n{result['blocker']}\n")

    print(f"Artifact gate: {'PASSED' if result['gate_passed'] else 'BLOCKED'}")
    if result.get("blocker"):
        print(f"BLOCKER: {result['blocker']}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
