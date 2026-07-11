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
    - source_media_review
    - brief
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

---

## Verified Mappings (from pinned OpenMontage commit f633b5f)

### openmontage_edit_plan → edit_decisions

| Football Field | OpenMontage Field | Confidence | Notes |
|----------------|-------------------|------------|-------|
| `project_title` | (not in edit_decisions; in brief/proposal) | N/A | Carried from proposal |
| `target_duration` | (sum of cuts[].out_seconds - cuts[].in_seconds) | high | Derived |
| `story_structure` | (not direct; in brief) | N/A | |
| `render_runtime_decision.recommendation` | `render_runtime` | high | Must be user-confirmed; enum: ffmpeg\|remotion\|hyperframes |
| `sections[].section_id` | `cuts[].id` (prefix with section_) | high | |
| `sections[].timeline_range` | `cuts[].in_seconds` + `cuts[].out_seconds` | high | |
| `sections[].emotional_role` | `cuts[].reason` (embed role) | medium | |
| `sections[].clips[]` | `cuts[].source` (asset_manifest ID or path) | high | |
| `sections[].cut_style` | `cuts[].transition_in` + `transition_out` | medium | Default: hard_cut |
| `sections[].transition_in` | `cuts[].transition_in` | high | enum: hard_cut\|fade\|cross_dissolve\|match_cut\|none |
| `sections[].transition_out` | `cuts[].transition_out` | high | |
| `sections[].speed` | `cuts[].speed` | high | default 1.0 |
| `sections[].effect` | `cuts[].transform.animation` | medium | ken-burns-slow-zoom, pan-left, static, etc. |
| `sections[].caption` | `subtitles.source` + `subtitles.enabled` | high | |
| `sections[].audio_priority` | `audio.narration` vs `audio.music` ducking | high | |
| `sections[].music_action` | `audio.music.volume` + `audio.music.ducking` | high | |
| `sections[].sfx[]` | `audio.sfx[]` | high | |
| `quality_checks[]` | (not in edit_decisions; in render_report/final_review) | N/A | |

### openmontage_audio_operations → edit_decisions.audio

| Football Field | OpenMontage Field | Confidence |
|----------------|-------------------|------------|
| `tracks[].track_id` | (implicit by array index) | high |
| `tracks[].track_type` | `narration`/`music`/`sfx`/`crowd` → separate objects | high |
| `tracks[].clips[].start_time` | `narration.segments[].start_seconds` | high |
| `tracks[].clips[].end_time` | `narration.segments[].end_seconds` | high |
| `tracks[].clips[].asset_id` | `narration.segments[].asset_id` | high |
| `tracks[].clips[].volume_db` | `music.volume` (0-1, convert) | high |
| `tracks[].clips[].fade_in/out` | `music.fade_in_seconds`/`fade_out_seconds` | high |
| `tracks[].ducking` | `music.ducking` (bool or object) | high |
| `silence_cuts[]` | (handled by silence_cutter tool pre-compose) | N/A |
| `master.target_lufs` | (not in edit_decisions; in render_report/final_review) | N/A |

### source_media_review → asset_manifest + supplementary

| Football Field | OpenMontage Field | Confidence |
|----------------|-------------------|------------|
| `files[].path` | `assets[].path` | high |
| `files[].media_type` | `assets[].type` (video/audio/image) | high |
| `files[].technical_probe` | `assets[]` metadata (duration, resolution, format) | high |
| `files[].content_summary` | `assets[].generation_summary` | medium |
| `files[].transcript_summary` | (not in asset_manifest; in source_media_review supplementary) | N/A |
| `files[].quality_risks[]` | `assets[].quality_score` (inverse) | medium |
| `files[].usable_for[]` | `assets[].subtype` | medium |

### scene_plan → edit_decisions (via edit-director)

The `documentary-montage` pipeline's `edit-director` reads `scene_plan` and produces `edit_decisions`.
Our `openmontage-edit-planning` skill produces `openmontage_edit_plan` which maps to what `edit-director` expects.

### render_report → football QA artifacts

| Football Field | OpenMontage Field | Confidence |
|----------------|-------------------|------------|
| `output_path` | `render_report.output_file` | high |
| `duration` | `render_report.duration_seconds` | high |
| `resolution` | `render_report.resolution` | high |
| `codec` | `render_report.codec` | high |
| `audio_lufs` | `render_report.audio_lufs` | high |
| `true_peak_db` | `render_report.true_peak_db` | high |

---

## Forbidden Assumptions

1. ❌ `edit_decisions` has `sections[]` — it has `cuts[]` and `overlays[]`
2. ❌ `render_runtime` can default to HyperFrames — must be user-confirmed
3. ❌ `composition_mode` can be omitted — required, enum: templated\|atelier
4. ❌ `renderer_family` can change at edit stage — locked at proposal
5. ❌ `audio.music` is legacy — prefer `audio.music` object (not top-level `music`)
6. ❌ `silence_cuts` map directly to edit_decisions — they don't; handled by tool
