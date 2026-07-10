---
name: football-platform-export-validator
description: >-
  Use after assembly and QA but before final delivery or upload to validate export settings, platform target, aspect ratio, loudness measurement, codec/container, captions, thumbnail requirements, post-render checks, HDR policy, and Content ID or claim-risk scan placeholders for football emotion videos.
---

# Football Platform Export Validator

This skill closes the gap between a good edit plan and a deliverable file. It runs after `football-retention-quality-control` and before final handoff/upload.

## Required inputs

- `openmontage_edit_plan`
- `full_qa_report`
- `audio_loudness_measurement`
- `visual_cohesion_plan`
- `graphics_text_plan`
- target platform(s)
- OpenMontage render runtime confirmed by user/preflight

## Output

```yaml
export_profile:
  platform: youtube_longform | youtube_shorts | tiktok | instagram_reels | other
  aspect_ratio: string
  resolution: string
  codec: string
  container: string
  audio_codec: string
  target_lufs: number
  true_peak: number
  hdr_metadata_policy: preserve | tonemap_to_sdr | strip | unknown
  subtitle_burn_in: true | false
  thumbnail_required: true | false
  runtime_target_seconds: number
  allowed_runtime_drift_seconds: number
  content_id_claim_risk_scan: pending | passed | blocked | not_available
  post_render_checks:
    - audio_loudness_measured
    - video_playback_checked
    - captions_safe_zone_checked
    - thumbnail_exported
    - derivative_exports_created
  pass: true | false
```

## Runtime tolerance formula

```text
allowed_runtime_drift = max(0.2 seconds, target_runtime_seconds * 0.005)
```

If a platform has a hard limit, the hard platform limit overrides the editorial tolerance.

## Blocking failures

- No measured loudness report.
- Export profile target unknown.
- Render runtime not confirmed after OpenMontage preflight.
- Captions or important visuals outside platform safe zones.
- HDR footage exported with unknown policy.
- Any music/SFX asset lacks license approval.
