---
name: football-fact-provenance-gate
description: >-
  Use whenever an output contains precise production claims such as exact match facts, scorelines, timestamps, clip scores, LUFS, true peak, BPM, exposure corrections, percentages, color values, retention claims, or memory lessons. This gate labels every precise claim with provenance and rejects unverified precision before artifacts, edit plans, or Hermes memory are finalized.
---

# Football Fact Provenance Gate

This skill prevents fake precision from entering artifacts, OpenMontage plans, or Hermes memory.

## Provenance labels

```yaml
provenance: verified_from_source | measured_by_tool | estimated_by_editor | creative_hypothesis | user_supplied | forbidden_unverified
```

## Required use

Run this gate before finalizing:

- `match_fact_lock`
- `clip_candidate`
- `clip_scorecard`
- `audio_loudness_measurement`
- `openmontage_edit_plan`
- `full_qa_report`
- `hermes_memory_update`

## Decision rules

- Match facts, events, quotes, player participation → `verified_from_source` or `user_supplied` only.
- LUFS, true peak, BPM, exposure, loudness, scene duration, OCR scoreline → `measured_by_tool` only.
- Emotion strength and pacing estimates → `estimated_by_editor` unless measured.
- Story title, tone, suggested hook, mood direction → `creative_hypothesis`.
- Exact percentages or claimed improvements without a measurement → `forbidden_unverified` and must be removed.

## Output

```yaml
fact_provenance_report:
  pass: true | false
  checked_artifacts:
    - artifact: string
      precise_claims_found: integer
      rejected_claims: integer
  findings:
    - claim: string
      provenance: string
      action: keep | downgrade | remove | ask_user | measure
      reason: string
```

## Blocking failures

The gate fails if an artifact contains:

- exact score or exact minute without verified source or user supply,
- measured audio/video values without a measuring tool,
- legal-safe wording for risky footage,
- memory lessons with fake percentages or unmeasured technical constants.

## V6 patch addendum — structural linting

Do not rely only on this skill's prose. For artifact directories, run:

```bash
python3 tools/fact_provenance_lint.py <project_artifacts_dir>
python3 tools/current_event_gate_lint.py <project_artifacts_dir>
```

`fact_provenance_lint.py` is artifact-aware and skips documentation by default. Use `--include-docs` only for noisy package audits. If the lint fails, revise the affected artifact instead of simply appending a late report.
