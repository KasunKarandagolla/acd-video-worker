# OpenMontage Schema Lock

Real `edit_decisions` or other OpenMontage-native artifacts may be produced only after local schemas are inspected.

## Artifact

```yaml
openmontage_schema_lock:
  schemas_path: string
  schemas_found:
    - edit_decisions
    - asset_manifest
    - scene_plan
    - render_report
    - script
  schema_version_or_commit: string
  mapped_fields:
    - football_field: string
      openmontage_field: string
      confidence: low | medium | high
  unmapped_fields:
    - string
  forbidden_assumptions:
    - string
  bridge_status: passed | degraded | blocked
```

## Rule

Before `bridge_status: passed`, output `adapter_facing_plan` only.
