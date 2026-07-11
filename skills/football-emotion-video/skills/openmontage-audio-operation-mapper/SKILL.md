---
name: openmontage-audio-operation-mapper
description: Use when converting the section-by-section audio_plan into OpenMontage track-shaped operations for the edit_decisions.audio object — e.g. "map audio plan to OpenMontage audio config", "create the audio operations for the edit". Activates after football-audio-music-director and football-commentary-ducking-mixer have produced a complete audio_plan. Outputs the exact structure expected by OpenMontage's edit_decisions.audio schema.
---

# OpenMontage Audio Operation Mapper

Converts the football `audio_plan` (section-by-section) into OpenMontage's `edit_decisions.audio` structure.
This skill does not make creative audio decisions — it only maps.

## When to use this

- Complete `audio_plan` exists (from `football-audio-music-director` + `football-commentary-ducking-mixer`)
- Need `edit_decisions.audio` for OpenMontage `compose` stage

## Required inputs

- `audio_plan` (list of `audio_plan_segment` per `shared/contracts/pipeline-artifacts.md`)

## Mapping Rules (to edit_decisions.audio schema)

### Narration segments
```json
"audio": {
  "narration": {
    "segments": [
      {
        "asset_id": "<music_asset_id_or_narration_asset_id>",
        "start_seconds": <section_start>,
        "end_seconds": <section_end>
      }
    ]
  }
}
```

### Music
```json
"audio": {
  "music": {
    "asset_id": "<music_asset_id>",
    "volume": <0-1>,
    "fade_in_seconds": <float>,
    "fade_out_seconds": <float>,
    "ducking": {
      "enabled": true,
      "threshold_db": -20,
      "reduction_db": 12,
      "attack_ms": 100,
      "release_ms": 300
    }
  }
}
```
- `music_action: start` → set volume, fade_in
- `music_action: rise` → increase volume
- `music_action: duck` → enable ducking with params from audio_plan
- `music_action: drop` → fade_out
- `music_action: remove` → volume 0, fade_out
- `music_action: continue` → no change

### SFX
```json
"audio": {
  "sfx": [
    { "asset_id": "<sfx_asset_id>", "start_seconds": <t>, "volume": <0-1> }
  ]
}
```

### Subtitles
```json
"audio": {
  "subtitles": {
    "enabled": true,
    "style": "sentence",
    "source": "<subtitle_asset_id>",
    "font": "Inter",
    "font_size": 48,
    "color": "#FFFFFF",
    "outline_color": "#000000",
    "background": "#00000088",
    "position": "bottom-center",
    "max_words_per_line": 8
  }
}
```

## Governance fields (copied from proposal/plan)

- `renderer_family` — locked at proposal, carried through
- `render_runtime` — locked at proposal, user-confirmed
- `composition_mode` — locked at proposal

## Failure modes

- Don't invent fields not in `edit_decisions.audio` schema
- Don't assume `silence_cuts` exist in edit_decisions (handled by `silence_cutter` tool pre-compose)
- Every music asset_id MUST have a corresponding `license_verification_record` with `status: approved`

## Handoff

Output: `edit_decisions.audio` fragment (merged into full `edit_decisions` by `openmontage-edit-planning` or directly by pipeline `edit-director`).
