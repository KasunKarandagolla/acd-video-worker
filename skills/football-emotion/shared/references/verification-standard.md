# Verification Standard (shared reference)

Used by: football-source-discovery, football-visual-scene-analysis, football-timestamp-extraction,
football-clip-scoring, football-rights-safe-audio-license-checker, and any skill that outputs a
factual claim about a video, scene, timestamp, or license.

## The rule

A claim is only `verified` when the system has actually reviewed the underlying evidence:

| Claim type | What counts as verification |
|---|---|
| A video exists / is accessible | The agent actually opened/fetched the video page or a search result confirms it, this session |
| A scene/visual detail | Frames were actually extracted (via OpenMontage's frame-sampling tool) and viewed by the agent |
| An audio/commentary detail | Audio was extracted/transcribed and reviewed, or a transcript tool ran on this exact video |
| A timestamp | Both the scene content AND its position in the source video were directly observed |
| A music/SFX asset's license | The exact asset page (not a search/category page) was opened and its license text read this session |
| View counts, durations, upload dates | Read directly from the platform this session, not recalled from training data |

If any of these were not done, the claim must be labeled with one of:

- `unverified` — plausible based on metadata/patterns but not directly reviewed
- `partial` — some elements verified, others not (state which)
- `requires_manual_review` — confidence too low to use without a human checking first

## Required field

Every schema in `shared/contracts/` that carries a factual claim includes a
`verification_status` (or `license_verification_required` / `checked_date`, for license records)
field. Skills must populate it honestly — a skill that omits this field, or defaults it to
`verified` without doing the work above, is producing exactly the "fake timestamp" / "fake
license clearance" failure mode this whole pipeline exists to avoid.

## Why this is load-bearing, not decorative

Downstream skills and OpenMontage itself will treat anything without a verification caveat as
safe to act on. An `unverified` scene claim that flows silently into a final edit plan becomes a
real editing decision made on a guess. An `unverified` license status that flows into a published
video becomes a real copyright/Content-ID risk. This is why every skill in this package references
this file rather than restating verification rules inconsistently in each SKILL.md.

## Confidence labels (for scene/clip work specifically)

- `high` — exact visual/audio reviewed this session
- `medium` — metadata + known context supports the claim, but the exact frame/audio was not reviewed
- `low` — plausible based on common patterns for this kind of footage, not verified
- `unusable` — no reliable access to the source at all

## What NOT to do

- Do not upgrade a claim's confidence because it "seems obviously true" (e.g., assuming a famous
  match's scoreline without checking the specific source video shows it).
- Do not silently drop the verification field to make output look cleaner — an unverified row with
  the label attached is more useful than a confident-looking row that turns out to be wrong.
- Do not treat a search-results snippet as equivalent to opening the actual page.
