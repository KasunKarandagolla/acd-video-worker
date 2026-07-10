# Backlot Checkpoint Governance

Use with OpenMontage when a stage requires human approval.

## Checkpoints

- `research`: match facts, source availability, rights risk.
- `proposal`: story arc, runtime, platform, title direction.
- `assets`: footage and audio license status.
- `edit`: timeline plan, audio plan, captions.
- `compose`: render candidate and QA.

## Awaiting-human state

```yaml
checkpoint_status:
  checkpoint: research | proposal | assets | edit | compose
  state: awaiting_human | approved | rejected | needs_revision
  user_must_approve:
    - string
  artifact_summary: string
  next_allowed_action: stop | revise | proceed
```

## Rule

If a stage is `awaiting_human`, stop. Do not continue in the same run.
