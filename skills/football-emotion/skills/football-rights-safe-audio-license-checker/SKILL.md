---
name: football-rights-safe-audio-license-checker
description: Use before any music or SFX asset is used in a football emotion video edit — e.g. "is this track safe to use", "verify the license for this music", "check copyright risk for this asset", "approve this SFX for the edit". Activates whenever football-music-library-selector produces a candidate, or whenever any music/SFX asset is about to be referenced in an audio_plan or openmontage_edit_plan. This is a mandatory gate — no skill in this package may treat a music/SFX asset as usable without this skill's approval.
---

# Football Rights-Safe Audio License Checker

Verifies the exact license and attribution requirements for a candidate music/SFX asset before it
can be marked usable. This is a production blocker per the source pack's own gap audit — the
system must not automatically use music in a published video without this gate having run.

## When to use this

- Every `music_sfx_candidate` from `football-music-library-selector`, before `football-audio-music-director` builds it into an `audio_plan`
- Any time an asset's license status is uncertain or needs re-checking (e.g. licenses can change — a documented real failure pattern is a creator changing their license between projects)

## Required inputs

- `asset_url` (must be the exact asset page, not a search/category page — see the input note below)
- `asset_name`
- `source_platform`

## The state machine (every asset moves through this, no skipping steps)

```
candidate -> exact_page_found -> license_read -> attribution_generated -> downloaded_cached -> ready_for_openmontage
     |              |                |                    |                   |
   reject         reject           reject               reject              use
```

## Workflow

1. If the candidate's `is_exact_asset_page` is `false` (a search/category link), the first job is finding the actual exact asset page — if it can't be found, the asset is rejected outright, not "approved with a caveat."
2. Read the license text on that exact page.
3. Compare against known-safe license patterns: CC0, CC-BY (with correct attribution), Pixabay Content License, Mixkit Free License. YouTube Audio Library tracks vary per-track — flag as needing an in-app check inside YouTube Studio if that hasn't been done.
4. Generate the required attribution text if the license needs it (see templates in `football-music-library-selector/references/music-sfx-catalog.md`).
5. Assess **Content-ID risk separately from license type** — this is not the same axis. A correctly CC-BY-licensed track can still be Content-ID registered by a distributor and trigger a claim. If there's no way to check this directly, mark `content_id_risk: unknown` rather than assuming low risk from a clean-looking license.
6. Record `checked_date` — a license check is a point-in-time fact, not a permanent one.
7. Output a `license_verification_record` (see `shared/contracts/pipeline-artifacts.md`) with `status: approved | rejected | needs_more_info`.

## Decision rules

- A search/category link is never itself sufficient grounds for approval — the exact page must be found.
- ⚠️-flagged catalog entries (reposts, unofficial channels) require finding the *original* creator/license, not just accepting the repost's claimed license.
- If a track's license cannot be confirmed with reasonable confidence, the default is `rejected` or `needs_more_info` — never `approved` by default.
- Silence and crowd-only audio (already present in the source footage) do not need this gate — they aren't external assets being introduced. Only externally-sourced music/SFX go through this process.
- If a previously-approved asset is reused in a new project, re-check `checked_date` — if it's old, re-verify rather than trusting the prior record indefinitely (creators do change licenses).

## Failure modes to avoid

- Treating catalog presence as clearance (the single most important thing this skill exists to prevent)
- Approving a track because "it's probably fine" without reading the actual license text
- Conflating license type with Content-ID safety — they are different risks
- Skipping re-verification of previously-approved assets on later projects

## Handoff

Output: `license_verification_record` per asset. Only assets with `status: approved` may be
referenced by `football-audio-music-director`'s `audio_plan` output. Rejected/needs-more-info
assets get looped back to `football-music-library-selector` for a replacement candidate.

## References

- `shared/contracts/pipeline-artifacts.md` — the `license_verification_record` schema
- `football-music-library-selector/references/music-sfx-catalog.md` — attribution templates and the ⚠️ flagging convention this skill checks against

## V5 patch addendum — commentary rights check

For direct commentary audio, produce:

```yaml
commentary_rights_check:
  commentary_source: string
  language: string
  broadcaster: string
  match_rightsholder: string
  is_official_clip: true | false | unknown
  is_reupload: true | false | unknown
  transcript_used_only: true | false
  direct_audio_used: true | false
  risk_level: low | medium | high | unknown
  recommendation: use_transcript_only | short_quote_with_risk | user_must_supply_rights | avoid | needs_legal_review
```

If direct audio is too risky, allow paraphrased narration, subtitles over crowd audio, or user-supplied licensed clips.

## V6 patch addendum — commentary gate is parallel to music/SFX gate

Direct broadcast/match commentary cannot be treated as free just because it is already inside the source footage. When an `audio_plan_segment` uses direct commentary audio, require:

```yaml
commentary_rights_check_required: true
commentary_rights_check_id: <id>
```

If `direct_audio_used: true` and no `commentary_rights_check` exists, the audio plan is blocked. If the check returns `use_transcript_only`, the audio director may use paraphrased narration or on-screen text, but not the original commentary audio.

This gate does not decide legal safety. It records risk and allowed workflow language: `use_transcript_only`, `short_quote_with_risk`, `user_must_supply_rights`, `avoid`, or `needs_legal_review`.
