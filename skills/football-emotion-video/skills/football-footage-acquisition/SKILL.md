---
name: football-footage-acquisition
description: Use when selected source video candidates need to be downloaded, verified, and prepared for OpenMontage editing — e.g. "acquire the footage for these clips", "download the source videos", "build the source media review". Activates after football-source-discovery and football-clip-scoring have produced a ranked list of clip_candidates with deep_analysis_candidate:yes. Handles sequential download, failure replacement, and source_media_review artifact generation.
---

# Football Footage Acquisition

Downloads, verifies, and manifests local footage files for OpenMontage editing. This skill handles the "careful sequential acquisition" and "replacement of failed candidates" workflow. It does NOT do creative selection — that's done by upstream skills.

## When to use this

- Ranked `clip_candidate[]` list exists from `football-clip-scoring`
- Need local video files and `source_media_review` artifact for OpenMontage `assets` stage

## Required inputs

- Ranked `clip_candidate[]` list (from `football-clip-scoring`)
- `story_plan` (to know how many clips per section)
- Project ID (for output paths)

## Workflow

### 1. Prepare acquisition queue

For each story-plan section requiring clips:
- Take top-ranked `clip_candidate` with `recommended_use` matching that section
- Build acquisition queue: list of `{candidate_id, source_url, section_id, clip_id, attempt=1}`

### 2. Sequential acquisition loop

For each item in queue (max 3 attempts per slot):

```python
# Pseudocode for each acquisition attempt
1. Call OpenMontage video_downloader (yt-dlp) via Hermes terminal tool:
   cd "$OPENMONTAGE_ROOT"
   source .venv/bin/activate
   python -m tools.analysis.video_downloader \
     --url "$SOURCE_URL" \
     --output "$PROJECT_SOURCES_DIR/${CANDIDATE_ID}.mp4"

2. Verify download:
   - audio_probe → duration, codec, sample_rate, channels
   - frame_sampler (4 frames evenly spaced) → visual check
   - transcriber (if audio) → transcript summary

3. On SUCCESS:
   - Build source_media_review entry (see schema below)
   - Mark slot filled
   - Break to next slot

4. On FAILURE (download error, geo-block, age-gate, removed, corrupt):
   - Log failure reason in source_media_review.verification_status: failed
   - Increment attempt
   - If attempt <= 3: try next ranked candidate for same slot
   - If attempt > 3: mark slot as GAP, continue to next slot
```

### 3. Build source_media_review artifact

Output: `source_media_review` (schema in `shared/contracts/pipeline-artifacts.md` / OpenMontage `source_media_review.schema.json`)

```yaml
source_media_review:
  files:
    - path: "projects/<id>/football_emotion/sources/<candidate_id>.mp4"
      media_type: video
      reviewed: true
      technical_probe:
        duration_seconds: float
        width: int
        height: int
        codec: string
        audio_codec: string
        sample_rate: int
        channels: int
      content_summary: string
      transcript_summary: string | null
      representative_frames: [frame_path_1, frame_path_2, ...]
      quality_risks: [string]  # e.g. "low resolution", "mono audio", "watermark visible"
      usable_for: [hero_footage, b_roll, narration_source, ...]
      verification_status: verified | partial | failed
      acquisition_attempt: int
      original_candidate_id: string
      source_url: string
  summary: "Human-readable description of acquired footage"
  planning_implications:
    - "Section X has only 1 verified clip; may need graphics bridge"
    - "All clips 1080p+; no upscaling needed"
```

### 4. Update asset_manifest

Add entries to OpenMontage `asset_manifest` for each acquired file:
```json
{
  "id": "<candidate_id>",
  "type": "video",
  "path": "football_emotion/sources/<candidate_id>.mp4",
  "source_tool": "video_downloader",
  "scene_id": "<section_id>",
  "subtype": "source_footage",
  "license": "unverified",
  "original_url": "<source_url>",
  "generation_summary": "Downloaded from YouTube via yt-dlp; verification_status: verified"
}
```

## Failure modes

- **All candidates exhausted for a slot** → Report GAP in `planning_implications`, continue with other slots
- **video_downloader tool unavailable** → Fallback: direct yt-dlp via terminal (document limitation)
- **No audio track** → Note in `transcript_summary: null`, `quality_risks: ["no_audio"]`
- **Corrupt/incomplete download** → Delete partial file, retry next candidate

## Handoff

Output: `source_media_review` + updated `asset_manifest`. Next: OpenMontage `assets` stage (asset-director) ingests these.
