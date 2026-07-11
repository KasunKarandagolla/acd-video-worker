# Frame Extraction Approach — OpenMontage Tool Registry Integration

This skill uses OpenMontage's registered analysis tools via the tool registry.
Do NOT use illustrative ffmpeg commands directly.

## Required Tools (verified via tool registry preflight)

| Tool | Capability | Provider | Purpose |
|------|------------|----------|---------|
| `frame_sampler` | analysis | ffmpeg/local | Sample frames at intervals or scene boundaries |
| `scene_detect` | analysis | ffmpeg/local | Detect scene cuts via PySceneDetect or FFmpeg fallback |
| `transcriber` | analysis | local/whisperx | Transcribe audio if present |
| `video_analyzer` | analysis | multi | Monolithic: download + transcribe + scenes + frames + motion + audio |

## Invocation Pattern (via Hermes `terminal` tool)

```bash
# From OpenMontage repo root with venv activated
cd /path/to/OpenMontage
source .venv/bin/activate

# Frame sampling (scene-guided strategy)
python -m tools.analysis.frame_sampler \
  --input /path/to/video.mp4 \
  --strategy scene_guided \
  --max-frames 20 \
  --output-dir /path/to/frames/

# Scene detection
python -m tools.analysis.scene_detect \
  --input /path/to/video.mp4 \
  --method content \
  --threshold 0.3 \
  --output-json /path/to/scenes.json

# Transcription (if audio present)
python -m tools.analysis.transcriber \
  --input /path/to/video.mp4 \
  --model base \
  --output-json /path/to/transcript.json
```

## Skill Workflow

1. **Preflight**: Run `bridge_preflight.py` → confirm `frame_sampler` and `scene_detect` show `AVAILABLE` in provider menu
2. **Sample frames**: Call `frame_sampler` with `scene_guided` strategy (first frame of each scene + midpoints for scenes >3s)
3. **Detect scenes**: Call `scene_detect` with `content` method (PySceneDetect) or `threshold` fallback
4. **Transcribe**: Call `transcriber` if audio track exists
5. **Analyze**: Review sampled frames + scene list + transcript → produce `video_scene_analysis`

## Verification Requirements

- Every scene in `video_scene_analysis` must have `confidence: high|medium|low|unusable`
- Scenes with `confidence: low` or `manual_review_needed: true` → flag for human review
- Never invent timestamps not present in scene detection output

## Fallback (if tools unavailable)

If `frame_sampler`/`scene_detect` are `UNAVAILABLE`:
- Use `video_analyzer` with `depth: standard` (monolithic but works)
- Document limitation in `verification_status: partial`
