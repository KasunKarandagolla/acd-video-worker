# Broadcast Overlay and Scorebug Map

Sports footage often contains scorebugs, logos, clocks, lower thirds, and watermarks. These affect crop, captions, and clarity.

## Fields

```yaml
broadcast_overlay_map:
  scorebug_present: true | false
  location: top_left | top_right | bottom_left | bottom_right | unknown
  scoreboard_text: string
  obstructs_action: true | false | unknown
  crop_safe: true | false | unknown
  caption_safe_zones: string
  overlay_conflict_notes: string
```

## Rules

- Do not place captions over score/time overlays.
- Do not crop the decisive moment in a way that removes essential score context.
- Use OCR only as supporting evidence; verify visually when stakes are high.
