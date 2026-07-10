# HDR / HLG / SDR Handling

Modern sports broadcasts may use HDR/HLG. Ordinary LUTs can break footage if HDR status is unknown.

## Required fields

```yaml
video_color_metadata:
  hdr_detected: true | false | unknown
  transfer_function: sdr | hlg | pq | unknown
  tone_map_required: true | false | unknown
  tone_map_method: string
  post_tonemap_review_required: true | false
```

## Rule

Do not apply a creative LUT before checking HDR/SDR status. If HDR/SDR is mixed, tone-map or normalize first, then apply the visual cohesion treatment.
