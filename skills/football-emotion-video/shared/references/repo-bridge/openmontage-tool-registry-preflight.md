# OpenMontage Tool Registry Preflight

Run this before any production planning becomes execution.

## Mandatory commands

From `/home/kasun/Music/Director/OpenMontage`:

```bash
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu_summary(), indent=2))"
```

Use this first because it is the human-readable capability rollup.

For deeper inspection:

```bash
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu(), indent=2))"
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.support_envelope(), indent=2))"
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.capability_catalog(), indent=2))"
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_catalog(), indent=2))"
```

## What to extract

Record:

- composition runtimes available: FFmpeg, Remotion, HyperFrames
- analysis tools available: transcription, scene detection, frame sampling, video understanding
- stock/open-footage tools available: Archive.org, Wikimedia, Pexels, Pixabay, Unsplash, etc.
- audio tools available: music generation, user `music_library/`, audio mixing, loudness tools
- video post tools available: trimming, compose, subtitle burn, color grading
- missing provider keys or local installs
- install instructions from registry fields, not from memory

## Do not hardcode tools

OpenMontage declares tool status at runtime. The skill system may know tool families, but the exact configured tools are discovered from the registry.

## Capability status language

Use one of:

- `passed`: all required tools for selected manifest/stage are available
- `degraded`: fallback path exists but changes quality/cost/scope
- `blocked`: no acceptable path exists without setup or user approval

## Football-specific preflight checks

For football emotion videos, explicitly check:

- Can we analyze local/reference video or YouTube/video files?
- Can we ingest real footage legally/user-authorized?
- Can we compose real footage through FFmpeg/Remotion/HyperFrames?
- Can we mix commentary/music/SFX?
- Is `music_library/` present and populated?
- Are subtitle/caption tools available?
- Is Backlot available for review gates?
