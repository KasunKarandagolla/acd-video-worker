# OpenMontage Artifact Bridge Contract

This contract maps football-emotion planning outputs into OpenMontage canonical artifacts.

## Principle

Football skills should not invent private artifacts that OpenMontage cannot consume. They must either:

1. enrich an OpenMontage canonical artifact, or
2. write an auxiliary file under `projects/<project-id>/football_emotion/` and reference it from the canonical artifact.

## Recommended project subfolder

```text
projects/<project-id>/football_emotion/
├── brief_interpretation.json
├── source_candidates.json
├── clip_scores.json
├── story_plan.json
├── audio_music_plan.json
├── visual_cohesion_plan.json
├── graphics_text_plan.json
├── assembly_plan.json
├── rights_and_license_report.json
├── qa_report.json
└── hermes_memory_update.json
```

## Canonical artifact enrichment

| Football file | OpenMontage artifact to enrich |
|---|---|
| `brief_interpretation.json` | proposal / brief |
| `source_candidates.json` | research brief, asset manifest |
| `clip_scores.json` | scene_plan, edit_decisions |
| `story_plan.json` | script, scene_plan |
| `audio_music_plan.json` | proposal, asset_manifest, edit_decisions |
| `visual_cohesion_plan.json` | scene_plan, edit_decisions |
| `graphics_text_plan.json` | scene_plan, edit_decisions |
| `assembly_plan.json` | edit_decisions |
| `rights_and_license_report.json` | asset_manifest, QA/checkpoint notes |
| `qa_report.json` | render_report/checkpoint |
| `hermes_memory_update.json` | Hermes memory, not OpenMontage core |

## Verification fields required

Every source/media/music item must include:

```json
{
  "source_url": "",
  "local_path": "",
  "rights_status": "unverified | candidate | verified | rejected",
  "verification_notes": "",
  "last_checked_at": "",
  "allowed_use_summary": ""
}
```

## Execution field rule

`openmontage_edit_operations` must remain adapter-facing until the local OpenMontage schema is read. If a field is not in the selected pipeline's schema, store it as auxiliary `football_emotion` metadata instead of forcing it into canonical JSON.

## V5 schema-lock rule

The bridge now has two modes:

```yaml
bridge_mode: adapter_facing_plan | openmontage_native_operations
```

Use `adapter_facing_plan` until `openmontage_schema_lock.bridge_status: passed`.

Only after schema lock passes may the agent write real OpenMontage-native field names for `edit_decisions`, `asset_manifest`, `scene_plan`, `script`, or `render_report`.
