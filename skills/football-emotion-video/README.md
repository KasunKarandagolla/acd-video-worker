# Football Emotion Skill System — V7 Final Runtime

This is the finalized runtime skill package for football/emotional sourced-footage video planning with Hermes + OpenMontage.

Confirmed target repos:

- Hermes: `NousResearch/Hermes-Agent`
- OpenMontage: `calesthio/OpenMontage`

## What V7 is

V7 keeps the V6 safety/runtime guardrails and folds in the useful essence from the independent Claude skill package:

- stronger `social-edit-reasoning` craft router;
- clearer emotion > story > rhythm > eye-trace hierarchy;
- explicit stage dependency map;
- reusable-skill boundary so the package does not overfit to one video;
- Hermes runtime installation/memory guidance;
- OpenMontage manifest-first and registry-first execution guidance;
- zero-key/free-first OpenMontage capability envelope.

## What V7 is not

It is not a fixed recipe for one Argentina video. It does not hardcode exact opponents, scores, timestamps, LUTs, clip scores, music keys, runtime tricks, or render runtime choices.

The LLM reasoning agent must still make creative decisions from verified footage, user preferences, and the actual OpenMontage provider/schema state.

## Active skills (23)

- `football-audio-music-director`
- `football-audio-quality-control`
- `football-caption-thumbnail-direction`
- `football-clip-scoring`
- `football-commentary-ducking-mixer`
- `football-fact-provenance-gate`
- `football-footage-rights-transformative-risk-assessor`
- `football-match-identification`
- `football-music-library-selector`
- `football-narration-scriptwriting`
- `football-platform-export-validator`
- `football-pro-cutting-pacing`
- `football-retention-quality-control`
- `football-rights-safe-audio-license-checker`
- `football-source-discovery`
- `football-story-strategy`
- `football-timestamp-extraction`
- `football-visual-scene-analysis`
- `hermes-football-memory-learning`
- `hermes-openmontage-repo-bridge`
- `openmontage-audio-operation-mapper`
- `openmontage-edit-planning`
- `social-edit-reasoning`
## Non-bypassable gates

1. `repo_setup_status` before repo-backed execution.
2. `match_fact_lock` before current/latest/2026+ match facts are used.
3. `openmontage_schema_lock` before native OpenMontage artifacts are written.
4. `license_verification_record` before music/SFX are used.
5. `commentary_rights_check` before direct broadcast commentary is used.
6. `footage_rights_risk_record` before third-party match footage is treated as usable.
7. `fact_provenance_report` before exact claims enter final artifacts.
8. `audio_loudness_measurement` before loudness is marked passed.
9. Backlot/human approvals when OpenMontage manifests require them.
10. `football-platform-export-validator` before final delivery.

## Runtime route

```text
hermes-openmontage-repo-bridge
  -> football-match-identification when current/latest match is involved
  -> social-edit-reasoning stage router
  -> story/sourcing/verification/timestamp/curation
  -> dynamic arc revision
  -> sequencing/pacing/audio/license/visual/text
  -> OpenMontage adapter-facing plan
  -> schema-locked native plan only after local repo inspection
  -> QA/export
  -> Hermes memory update
```

## Install stance

Preferred project-local install:

```text
/home/kasun/Music/Director/Hermes-Agent/optional-skills/creative/football-emotion-video/
```

Portable install:

```text
~/.hermes/skills/football-emotion-video/
```

## Validate

```bash
python3 tools/validate_skill_system.py .
python3 tools/validate_packaged_zip.py ../football_emotion_skill_system_v7_final_runtime.zip
```

## Active vs provenance files

This runtime ZIP intentionally excludes old source-pack research dumps, previous changelog stacks, and duplicate validation reports. Those are useful for auditing, but they are not runtime guidance. Keep them outside the active skill package to reduce context drift.
