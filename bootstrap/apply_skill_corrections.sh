#!/usr/bin/env bash
# Apply corrections to canonical Football Emotion V7 skills

set -euo pipefail

CANONICAL="/home/kasun/Music/Director/acd-video-worker/skills/football-emotion-video"

log() { echo -e "\033[1;33m→\033[0m $*"; }
ok() { echo -e "\033[0;32m✓\033[0m $*"; }

# 1. football-visual-scene-analysis: Replace frame-extraction-approach.md
log "Correcting frame-extraction-approach.md..."
cat > "$CANONICAL/skills/football-visual-scene-analysis/references/frame-extraction-approach.md" << 'EOF'
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
EOF
ok "frame-extraction-approach.md corrected"

# 2. openmontage-schema-lock.md — Complete field mappings
log "Correcting openmontage-schema-lock.md..."
cat > "$CANONICAL/shared/references/repo-bridge/openmontage-schema-lock.md" << 'EOF'
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
EOF
ok "openmontage-schema-lock.md corrected"

# 3. openmontage-edit-planning/SKILL.md — Remove HyperFrames default, add schema-lock gate
log "Correcting openmontage-edit-planning/SKILL.md..."
cat > "$CANONICAL/skills/openmontage-edit-planning/SKILL.md" << 'EOF'
---
name: openmontage-edit-planning
description: Use when assembling a football emotion story, selected clips, and audio/caption decisions into an executable OpenMontage edit plan — e.g. "build the edit plan for this video", "turn this into an OpenMontage timeline", "assemble the final edit decisions". Activates once selected clips, story plan, and script exist and a concrete, section-by-section OpenMontage-executable timeline is needed. Produces the edit_decisions-shaped artifact OpenMontage consumes; does not itself render video.
---

# OpenMontage Edit Planning

Turns story + selected clips + audio/caption/effect decisions into a concrete, executable edit
plan shaped to match OpenMontage's own `edit_decisions` artifact convention. This skill assembles;
it doesn't invent new creative decisions that other skills own (audio hierarchy comes from
`football-audio-music-director`, cut rhythm from `football-pro-cutting-pacing`, captions from
`football-caption-thumbnail-direction`).

## When to use this

- Selected clips, story plan, and script exist
- An OpenMontage-ready timeline is needed, or an existing plan needs revision

## Required inputs

- `story_plan`
- Scored/selected `clip_candidate` list
- Narration/script text
- Caption plan (if ready — can proceed without and flag as pending)
- Cut/pacing decisions from `football-pro-cutting-pacing` (if ready — can proceed with defaults from `shared/references/pro-editing-methodology.md` otherwise, clearly marked as provisional)
- Audio plan from `football-audio-music-director` (if ready — same provisional-marking rule)

## Workflow

1. For each story-plan section, assign the clips selected for it (`clips: [clip_id]`).
2. Apply cut style per `shared/references/pro-editing-methodology.md`'s decision hierarchy: emotional purpose → story role → clip clarity → audio priority → pacing → effect/caption.
3. Assign transitions using the transition table in that reference — hard cut is the default; anything else needs a reason.
4. Assign effects only per the `effect_policy` table (scene-type-driven, not decorative).
5. Attach caption text if available.
6. Attach audio priority/music action per section from the audio plan (or provisional defaults, clearly marked).
7. **Render runtime**: OpenMontage requires presenting both Remotion and HyperFrames to the user when both are installed and getting explicit confirmation before locking `render_runtime`. This skill states the recommendation but does not silently finalize the choice. See `references/openmontage-handoff-notes.md`.
8. Run the pre-finalization checklist (below) before marking the plan complete.
9. Output `openmontage_edit_plan` (see `shared/contracts/pipeline-artifacts.md`).

## Pre-finalization quality checklist

- Does the hook show emotion within 5-10 seconds?
- Does every major action have a reaction?
- Are emotional moments allowed to breathe (no premature cuts on holds)?
- Is music lower than commentary wherever commentary matters?
- Are effects scene-motivated per the effect policy table?
- Are captions short and useful?
- Is the ending meaningful, not just the last goal?
- Does the plan avoid a reused-content/compilation feel?

This checklist overlaps with `football-retention-quality-control` by design — that skill re-checks the *finished* plan independently; this checklist just prevents obviously broken plans from being handed off in the first place.

## Failure modes to avoid

- Vague edit instructions ("make it emotional") instead of concrete per-scene decisions
- Overusing transitions/effects without a stated reason
- Failing to control audio hierarchy (letting music dominate where commentary should)
- Silently locking a render runtime without the OpenMontage-required user confirmation step

## Handoff

Output: `openmontage_edit_plan`. Next skills: `openmontage-audio-operation-mapper` (audio-specific conversion) and `football-retention-quality-control` (final QC gate before delivery).

## References

- `shared/references/pro-editing-methodology.md` — cutting/pacing/transition/effect/caption rules this skill applies
- `references/openmontage-handoff-notes.md` — what's confirmed vs. assumed about OpenMontage's actual artifact schema and runtime-selection governance
- `shared/references/repo-bridge/openmontage-pipeline-manifest-preflight.md` — manifest-first execution rule
- `shared/references/repo-bridge/openmontage-zero-key-capability-envelope.md` — zero-key/free-first capability guidance

## v3 Timeline Assembly & Visual Cohesion

Before producing final `openmontage_edit_plan`, read:

- `shared/references/editorial-journey/assembly-workflow.md` for build-to-music timeline construction, layer order, handles, and refinement
- `shared/references/editorial-journey/visual-cohesion.md` for archive/stylized/seamless treatment, aspect ratio decisions, color consistency, and mismatch strategy
- `shared/references/editorial-journey/graphics-typography.md` for text placement and safe zones

The edit plan must not be only a sequence of clips. It must include a timeline construction strategy, layer logic, visual cohesion treatment, and places where music-sync matters.

## V4 repo bridge execution rule

Before converting any plan into OpenMontage execution, use `hermes-openmontage-repo-bridge` and read `shared/references/repo-bridge/openmontage-agent-contract.md` plus `shared/references/repo-bridge/openmontage-stage-skill-map.md`.

Do not invent OpenMontage tool calls. Select the pipeline from `pipeline_defs/`, read the stage director skill in `skills/pipelines/`, discover actual tools through `tools.tool_registry`, and only then write `edit_decisions` or auxiliary `projects/<project-id>/football_emotion/` files.

## V5 patch addendum — schema lock and export handoff

Before generating real OpenMontage-native operations, require `openmontage_schema_lock.bridge_status: passed`.

If the schema lock is missing or degraded, output only an `adapter_facing_plan` and list unmapped fields.

After assembly and QC, hand off to `football-platform-export-validator` for export profile and post-render checks.

## V7 addendum — OpenMontage manifest and runtime confirmation

Before converting an adapter-facing plan into native OpenMontage `edit_decisions`, require:

1. Selected pipeline manifest read from `pipeline_defs/`
2. Current stage director skill read from `skills/pipelines/`
3. `tools.tool_registry` provider/support output captured
4. `openmontage_schema_lock.bridge_status: passed`
5. Render runtime user confirmation if more than one runtime is available.

Render-runtime recommendation language must stay conditional:

```yaml
render_runtime_decision:
  recommendation: remotion | hyperframes | ffmpeg_only | user_confirmation_required
  reason: string
  alternatives_presented: [remotion, hyperframes, ffmpeg_only]
  user_confirmed: false
```

Do not silently lock HyperFrames just because prior project notes preferred it. Do not silently lock Remotion just because OpenMontage uses React scenes. The manifest, provider envelope, project style, and user approval govern the final choice.
EOF
ok "openmontage-edit-planning/SKILL.md corrected"

# 4. openmontage-audio-operation-mapper/SKILL.md — Map to edit_decisions.audio
log "Correcting openmontage-audio-operation-mapper/SKILL.md..."
cat > "$CANONICAL/skills/openmontage-audio-operation-mapper/SKILL.md" << 'EOF'
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
EOF
ok "openmontage-audio-operation-mapper/SKILL.md corrected"

# 5. hermes-openmontage-repo-bridge/SKILL.md — Configurable install path
log "Correcting hermes-openmontage-repo-bridge/SKILL.md..."
cat > "$CANONICAL/skills/hermes-openmontage-repo-bridge/SKILL.md" << 'EOF'
---
name: hermes-openmontage-repo-bridge
description: "Use this skill whenever the user wants the football emotion skill system installed, adapted, simulated, or executed inside the confirmed NousResearch/Hermes-Agent plus calesthio/OpenMontage setup. This skill anchors all creative football-video skills to the exact repo layout, OpenMontage pipeline manifests, tool registry, Backlot checkpoints, Hermes skills/memory behavior, and local project paths so the agent does not invent tools, bypass OpenMontage pipelines, or lose the execution contract."
---

# Hermes + OpenMontage Repo Bridge

## Purpose

Bridge the football emotion editorial skill system to the confirmed repos:

- Hermes: `NousResearch/Hermes-Agent`
- OpenMontage: `calesthio/OpenMontage`

This skill does not replace any football creative skill. It tells the agent how to use those skills **inside the actual repo contracts**.

## Use when

Use this before:

- installing the skill system into Hermes
- running a football video project through OpenMontage
- writing OpenMontage edit decisions
- making a local implementation plan
- simulating the full pipeline with exact repo behavior
- debugging why a skill output does not match OpenMontage's expected artifacts

## Required references

Read these in order:

1. `shared/references/repo-bridge/repo-source-lock.md`
2. `shared/references/repo-bridge/hermes-agent-contract.md`
3. `shared/references/repo-bridge/openmontage-agent-contract.md`
4. `shared/references/repo-bridge/openmontage-tool-registry-preflight.md`
5. `shared/references/repo-bridge/openmontage-stage-skill-map.md`
6. `shared/contracts/openmontage-artifact-bridge.md`
7. `shared/references/repo-bridge/hermes-runtime-skill-install.md`
8. `shared/references/repo-bridge/openmontage-pipeline-manifest-preflight.md`
9. `shared/references/repo-bridge/openmontage-zero-key-capability-envelope.md`

## Workflow

### 1. Confirm local repo paths

Expected (configurable via `HERMES_HOME` and `OPENMONTAGE_PROJECTS_DIR`):

```text
$HERMES_HOME/../Hermes-Agent          (or HERMES_AGENT_PATH env)
$OPENMONTAGE_PROJECTS_DIR/../OpenMontage  (or OPENMONTAGE_PATH env)
```

If either path is missing, stop and report the missing clone/setup step.

### 2. Read Hermes/OpenMontage runtime contracts

Before tool calls, read `shared/references/repo-bridge/hermes-runtime-skill-install.md` and `shared/references/repo-bridge/openmontage-pipeline-manifest-preflight.md`. Hermes is the reasoning/memory host; OpenMontage is the pipeline-driven production engine.

### 3. Run OpenMontage capability preflight

From OpenMontage root, run provider/capability discovery through `tools.tool_registry`. Do not assume provider availability from docs.

Minimum command:

```bash
cd $OPENMONTAGE_PROJECTS_DIR/../OpenMontage
source .venv/bin/activate
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu_summary(), indent=2))"
```

### 4. Select OpenMontage pipeline first

For football emotion videos, start by inspecting:

```text
pipeline_defs/documentary-montage.yaml
```

Only choose another pipeline if the manifest/tool situation makes it better.

### 5. Read stage director skill

Before executing a stage, read the pipeline's stage director skill under:

```text
skills/pipelines/<pipeline>/<stage>-director.md
```

Then use the football skill only as domain reasoning support.

### 6. Keep artifacts under project workspace

All project outputs go under:

```text
$OPENMONTAGE_PROJECTS_DIR/<project-id>/
```

Football-specific auxiliary artifacts go under:

```text
$OPENMONTAGE_PROJECTS_DIR/<project-id>/football_emotion/
```

### 7. Respect human gates

If the manifest requires approval, write `awaiting_human`, summarize the artifact, and stop.

### 8. Update Hermes memory after completion

After QA/render, use `hermes-football-memory-learning` to write a memory update about what worked and what failed.

## Failure modes to avoid

- Do not call OpenMontage tools with imagined function names.
- Do not bypass `pipeline_defs/` and stage director skills.
- Do not silently downgrade render runtime.
- Do not invent music/license safety.
- Do not write assets outside `projects/<project-id>/`.
- Do not continue past a human approval gate.
- Do not treat auxiliary football artifacts as canonical OpenMontage schema fields until validated.

## V5 patch addendum — setup and schema locks

At the start of every repo-backed run, create `repo_setup_status` using `shared/references/repo-bridge/repo-setup-status.md`.

If local Hermes/OpenMontage paths are absent, the only allowed actions are `stop` or `simulate_only`; do not claim tool registry preflight passed.

After repo setup passes, create `openmontage_schema_lock` using `shared/references/repo-bridge/openmontage-schema-lock.md`. Do not produce real OpenMontage `edit_decisions`, `asset_manifest`, `scene_plan`, or `render_report` fields until `bridge_status: passed`.

## V7 addendum — manifest-first and zero-key-first

For OpenMontage-backed work, use `shared/references/repo-bridge/openmontage-pipeline-manifest-preflight.md` before choosing any pipeline as final. `documentary-montage` is a strong candidate for real-footage football montage, but it is not a universal default.

Use `shared/references/repo-bridge/openmontage-zero-key-capability-envelope.md` to prefer free/open tools first. Do not assume paid API providers, local GPU video models, or unavailable providers.

If both Remotion and HyperFrames are available, present a short user-confirmation prompt before locking render runtime:

```text
OpenMontage can render this through Remotion or HyperFrames.
- Remotion is better for React/timeline/data/caption-heavy scenes.
- HyperFrames is better for HTML/CSS/GSAP/motion-graphics-heavy scenes.
For this project I recommend: <runtime> because <reason>.
Do you approve this render runtime?
```
EOF
ok "hermes-openmontage-repo-bridge/SKILL.md corrected"

# 6. football-match-identification/SKILL.md — Human verification gate
log "Correcting football-match-identification/SKILL.md..."
cat > "$CANONICAL/skills/football-match-identification/SKILL.md" << 'EOF'
---
name: football-match-identification
description: Use when the user refers to a current, latest, or recent football match without specifying exact details — e.g. "the latest Argentina game", "Ronaldo's last match", "the Champions League final last week". Activates to resolve vague temporal references into exact match identifiers (competition, teams, date, score, key events) before any downstream skill uses those facts. Does not verify live scores via API — produces a `match_fact_lock` artifact for human verification.
---

# Football Match Identification

Resolves vague temporal references ("latest", "recent", "last week") into exact, verifiable match metadata so downstream skills don't hallucinate facts.

## When to use this

- User mentions a current/latest/2024+ match without exact identifier
- Any downstream skill needs `match_fact_lock` before using match facts
- Current-event fact gate (`shared/references/current-event-fact-lock.md`) requires it

## Required inputs

- User's vague reference (e.g., "Messi's last World Cup game")
- Current date (from system/context)

## Workflow

1. Parse the user's reference to extract: player/team, competition hint, temporal hint ("latest", "recent", "2024 final").
2. Search available knowledge (Hermes session history, web search via `browser` tool if available, internal knowledge cutoff) for candidate matches.
3. For each candidate, build a `match_fact_lock` artifact (see `shared/contracts/pipeline-artifacts.md`):
   ```yaml
   match_fact_lock:
     status: verified | ambiguous | not_found | user_confirmation_required
     competition: string
     match: string
     date: string
     teams: [string, string]
     score: string
     key_events: []
     factual_uncertainties: []
     must_not_claim: []
   ```
4. **Critical**: The `status` field MUST be `user_confirmation_required` for any match within the last 30 days or any "latest/recent" claim. There is NO live sports API in Hermes. Do not claim `verified` for current events without explicit user confirmation.
5. If multiple candidates exist (e.g., "Ronaldo last match" — could be club or country), set `status: ambiguous` and list all candidates with distinguishing details.
6. Present the `match_fact_lock` to the user for confirmation before any downstream skill uses the facts.
7. Only after user confirms `status: verified` may downstream skills treat the facts as locked.

## Rejection rules

- Do not use internal knowledge cutoff as "verification" for current events.
- Do not set `status: verified` for any match date > (today - 30 days) without explicit user confirmation.
- Do not invent scores, key events, or player stats.

## Handoff

Output: `match_fact_lock`. Next skill: any skill requiring match facts (they must check `status: verified` before proceeding).

## References

- `shared/references/current-event-fact-lock.md`
- `shared/references/fact-provenance-standard.md`
- `shared/references/live-tournament-sourcing.md`
EOF
ok "football-match-identification/SKILL.md corrected"

# 7. football-source-discovery/SKILL.md — Add explicit handoff to acquisition
log "Correcting football-source-discovery/SKILL.md..."
# Read original and append handoff clarification
ORIGINAL="$CANONICAL/skills/football-source-discovery/SKILL.md"
if grep -q "football-footage-acquisition" "$ORIGINAL"; then
    ok "football-source-discovery already references acquisition skill"
else
    # Append to Handoff section
    sed -i '/^## Handoff$/a\
\
Output: ranked list of `source_video_candidate`. Next skill: `football-footage-acquisition` for\
candidates marked `deep_analysis_candidate: yes` or `maybe` to download and build\
`source_media_review`. Then `football-visual-scene-analysis` for frame/audio review.' "$ORIGINAL"
    ok "football-source-discovery/SKILL.md updated with acquisition handoff"
fi

# 8. Create NEW football-footage-acquisition skill
log "Creating football-footage-acquisition skill..."
mkdir -p "$CANONICAL/skills/football-footage-acquisition"
cat > "$CANONICAL/skills/football-footage-acquisition/SKILL.md" << 'EOF'
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
   cd $OPENMONTAGE_PROJECTS_DIR/../OpenMontage
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
EOF
ok "football-footage-acquisition skill created"

# 9. Update repo-source-lock.md with correct paths
log "Updating repo-source-lock.md..."
cat > "$CANONICAL/shared/references/repo-bridge/repo-source-lock.md" << 'EOF'
# Repo Source Lock — Hermes + OpenMontage

This package is now bridged to these exact upstream repositories:

| Role | Repository | Local path expected | Why it is locked |
|---|---|---|---|
| Reasoning agent, long-term learning, user interaction, skills | `https://github.com/NousResearch/Hermes-Agent` | `$HERMES_HOME/../Hermes-Agent` (or `HERMES_AGENT_PATH`) | Hermes provides CLI/TUI, provider/model switching, tools, gateway, memory/learning loop, skills, and subagent-style work. |
| Video production engine, pipeline manifests, tool registry, Backlot, render/composition | `https://github.com/calesthio/OpenMontage` | `$OPENMONTAGE_PROJECTS_DIR/../OpenMontage` (or `OPENMONTAGE_PATH`) | OpenMontage is pipeline-driven and exposes `pipeline_defs/`, `skills/`, `.agents/skills/`, `tools/`, `schemas/`, `backlot/`, and `remotion-composer/`. |

## Hard boundary

The football emotion skill system is not a replacement for either repo.

- Hermes remains the reasoning/runtime host.
- OpenMontage remains the video production engine.
- This package is the bridge layer: editorial intelligence + football emotion specialization + audio/license safety + artifact handoff rules.

## Pinning commands

```bash
cd $HERMES_HOME/../Hermes-Agent
git rev-parse HEAD > $PROJECT_ROOT/HERMES_AGENT_PINNED_COMMIT.txt

cd $OPENMONTAGE_PROJECTS_DIR/../OpenMontage
git rev-parse HEAD > $PROJECT_ROOT/OPENMONTAGE_PINNED_COMMIT.txt
```

Do not treat docs in this skill package as newer than the local pinned commits. If local repo behavior differs, inspect the local source and update this bridge.
EOF
ok "repo-source-lock.md updated"

echo ""
echo "All skill corrections applied. Run validation:"
echo "  python3 $CANONICAL/tools/validate_skill_system.py $CANONICAL"