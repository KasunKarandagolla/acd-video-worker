# Session Summary

Run ID: run_20260710_180722
Job: jobs/argentina_hardest_victory.yaml
Title: Argentina's Hardest Victory Nobody Expected
Theme: most recent Argentina World Cup match in 2026
Completed: 2026-07-10T18:07:57.710150+00:00Z

## Stages

### repo_setup_status

- hermes_available: True
- openmontage_available: True

### skill_system_status

- report_exists: True

### llm_api_status

- accessible: True
- api_key_set: True

### hermes_runtime

- success: True
- synthetic: True
- note: Synthetic E2E mode

### match_fact_lock

- status: verified
- match: Synthetic Team A vs Synthetic Team B
- team_a: Team A
- team_b: Team B
- date: 2024-01-01
- schema_valid: True
- path: /kaggle/working/acd-video-worker/state/runs/run_20260710_180722/hermes_artifacts/match_fact_lock.json

### source_discovery

- exit_code: 0
- candidates_count: 1
- synthetic: True

### download_sources

- exit_code: 0
- synthetic: True

### media_analysis

- exit_code: 0
- synthetic: True

### artifact_gate

- exit_code: 0
- gate_passed: True
- blocker: None

### render_attempt

- exit_code: 0

### qa_check

- exit_code: 0
- qa_passed: False
- issues: ['NO AUDIO STREAM FOUND', 'Loudness outside target range (-25 to -10 LUFS)']
- blocker: QA checks failed

### render_output

- render_success: True
- output: /kaggle/working/acd-video-worker/outputs/run_20260710_180722/fallback_render_attempt.mp4
- size_bytes: 44030
- note: Fallback mp4 exists. Not a full OpenMontage render.

## Render Result

Render success: True
Output: /kaggle/working/acd-video-worker/outputs/run_20260710_180722/fallback_render_attempt.mp4
