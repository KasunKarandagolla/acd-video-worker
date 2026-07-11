---
name: football-footage-rights-transformative-risk-assessor
description: >-
  Use when assessing reused-content, Content ID, footage-rights, fair-use-style transformation, or FIFA/broadcaster/fan-upload footage risk for football clips. This skill never gives legal approval. It produces a structured risk record and recommends avoid, usable with risk, user must supply rights, or needs legal review before the clip is treated as viable.
---

# Football Footage Rights & Transformative Risk Assessor

This is not a legal approval skill. It creates a clear risk record so the pipeline does not over-block all sports footage, but also does not pretend risky footage is safe.

## When to use

- World Cup / FIFA / UEFA / league broadcast footage
- fan reuploads, social clips, commentary channels
- any clip where `rights_reused_content_risk_1` affects selection
- any project using one source for more than 40% of runtime

## Output

```yaml
footage_rights_risk_record:
  source_type: official | broadcaster | fan_upload | commentary_channel | social_clip | user_supplied
  original_rightsholder_known: true | false | unknown
  clip_duration_seconds: number
  percent_of_final_video: number
  transformation_added:
    - narration
    - analysis
    - structural_reordering
    - captions_context
    - original_audio_music_replacement
    - multi_source_comparison
  market_substitution_risk: low | medium | high | unknown
  attribution_present: true | false
  content_id_risk: low | medium | high | unknown
  recommendation: usable_with_risk | avoid | user_must_supply_rights | needs_legal_review
  wording_allowed: risk_assessed_not_approved
```

## Rules

1. Never output `legal_safe` for third-party match footage.
2. Use `usable_with_risk`, not `approved`.
3. If the clip is long, untransformed, or sourced from a reuploaded highlight compilation, recommend `avoid`.
4. Short excerpts with commentary, structural transformation, captions/context, and source diversity may be `usable_with_risk`, but still require user acceptance.
5. If user supplies licensed footage, record `user_must_supply_rights` until the user confirms the rights basis.

## Handoff

- Feeds `football-clip-scoring` via `rights_reused_content_risk_1`.
- Feeds `football-retention-quality-control` reused-content gate.
- Feeds `football-platform-export-validator` for Content ID / claim-risk scan placeholder.

## V6 patch addendum — user-supplied rights workflow

When the recommendation is `user_must_supply_rights`, immediately invoke `shared/references/user-supplied-footage-rights.md`. Do not treat user intent or possession of a file as rights clearance. Require a `user_supplied_footage_rights` artifact before the footage is treated as usable beyond private/internal testing.

Also use `shared/references/reused-content-thresholds.md` for the shared 25% / 40% / 60% dominant-source thresholds instead of inventing a new threshold.
