# Platform Export Optimization

This stage runs after assembly and QA. It turns a good edit plan into a deliverable file profile.

## Export profile

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
  post_render_checks:
    - audio_loudness_measured
    - video_playback_checked
    - captions_safe_zone_checked
    - thumbnail_exported
    - derivative_exports_created
    - content_id_claim_risk_scan_recorded
```

## Runtime tolerance

```text
allowed_runtime_drift = max(0.2 seconds, target_runtime_seconds * 0.005)
```

Hard platform limits override editorial tolerance.
