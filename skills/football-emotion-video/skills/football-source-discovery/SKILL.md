---
name: football-source-discovery
description: Use when finding source videos or footage for a football emotional storytelling video — e.g. "find clips for a Messi World Cup story", "search for Ronaldo heartbreak footage", "find source videos for a comeback story", "discover footage for [player/team/match]". Activates for football/soccer video research, source-video candidate ranking, or when an existing source set for a football-emotion project is too weak or too narrow. Does not analyze actual visual/audio content — hand off to football-visual-scene-analysis for that.
---

# Football Source Discovery

Finds and ranks candidate source videos for a football-emotion story. This skill identifies
candidates only — it does not claim to know what's actually in a video until
`football-visual-scene-analysis` has reviewed it.

## When to use this

- A user requests a football emotional story and no source footage is selected yet
- The existing candidate set is too narrow (single source, single language, only highlight reels)
- A specific story target needs more candidates (e.g. "find more for the pressure section")

## Required inputs

A `user_instruction_profile` (see `shared/contracts/pipeline-artifacts.md`). If the user hasn't
given enough to build one, infer sensible defaults from their phrasing and state the assumption —
don't block on asking unless the topic is genuinely ambiguous (e.g. "Ronaldo" without a match
could mean many different heartbreak or triumph moments; ask which one).

## Workflow

1. Read `shared/references/emotion-pattern-library.md` to know which clip types and story beats this topic needs — this shapes what to search for, not just how to search.
2. Run multiple query styles per topic, not just one phrasing:
   - **Story query** — full narrative framing ("Messi World Cup 2022 full journey")
   - **Moment query** — the decisive scene ("Ronaldo crying tunnel Morocco Portugal 2022")
   - **Editing-style query** — reference for technique ("football cinematic edit emotional")
   - **Official-source query** — prioritize broadcaster/FIFA-style footage for image/audio quality
   - **Non-English query** — football emotion content performs strongly in Spanish, Arabic, Portuguese, French, Hindi, Tamil, etc.; don't restrict to English-only sources
3. For each result, populate a `source_video_candidate` (see contracts file). Do not assume title/description accuracy — mark `metadata_confidence` honestly.
4. Score each candidate with the discovery rubric below and assign `deep_analysis_candidate`.
5. Reject or downgrade per the rejection rules below.
6. Hand off the ranked list to `football-visual-scene-analysis` for anything scored as a deep-analysis candidate.

## Discovery scoring rubric (/10)

```yaml
discovery_score_10:
  emotional_story_potential: 0-2
  visual_scene_potential: 0-2
  audio_commentary_potential: 0-1
  editing_reference_value: 0-1
  audience_signal: 0-1
  source_quality: 0-1
  transformability: 0-1
  verification_confidence: 0-1
```
`8.0–10` deep analysis candidate · `6.0–7.9` inspect manually, may be useful as source footage ·
`4.0–5.9` keep only if topic-specific · `<4.0` reject.

## Rejection rules

Reject or downgrade when a candidate:
- Is a generic highlight compilation with no emotional context
- Relies only on goals, ignoring faces/crowds/commentary/aftermath
- Appears to contain AI-generated fake scenes presented as real footage
- Has heavy watermarks or resolution too low to be usable
- Is shorts-only with no context (may still be usable as a hook *reference*, not a source)
- Makes a current-event claim that cannot be verified this session
- Uses copyrighted music as its main appeal with no reusable editing logic
- Shows emotion with no story context — this produces exploitative output, reject regardless of visual quality

## Verification discipline

Every `source_video_candidate` gets a `verification_status` per
`shared/references/verification-standard.md`. Metadata (title, channel, apparent duration) read
from a search result is not the same as visual/audio review — those fields stay `unverified` until
`football-visual-scene-analysis` actually opens the video.

## Failure modes to avoid

- Returning only highlight compilations because they rank highest by view count
- Recommending current-event/very-recent videos without verifying they exist and are accurate
- Ignoring non-English sources and missing strong emotional material
- Failing to separate "editing-style reference" videos from "actual source footage" candidates — these have different downstream uses and must be labeled via `story_role`

## Handoff

Output: ranked list of `source_video_candidate`. Next skill: `football-footage-acquisition` for
candidates marked `deep_analysis_candidate: yes` or `maybe` to download and build
`source_media_review`. Then `football-visual-scene-analysis` for frame/audio review.

Output: ranked list of `source_video_candidate`. Next skill: `football-visual-scene-analysis` for
every candidate marked `deep_analysis_candidate: yes` or `maybe`.

## References

- `references/priority-story-targets.md` — the ten highest-value story targets to check first (Messi 2022, Argentina-France final, Ronaldo/Morocco, Neymar/Croatia, Germany 7-1 Brazil, Ghana/Uruguay, Baggio 1994, Morocco underdog run, Mbappé heroic failure, Messi-as-proof skill moments) with what to look for in each and why
- `shared/references/emotion-pattern-library.md` — story structures and clip-type priorities
- `shared/references/verification-standard.md` — verification field discipline

## v3 Sourcing Discipline

Read `shared/references/editorial-journey/sourcing-strategy.md` before running queries. Source against the locked brief: runtime determines candidate quantity, tone determines what kind of footage matters, and non-negotiable moments determine specific searches.

For football/sports stories, pull multiple versions of the core moment before selecting one, search for reaction/celebration/context/interview/crowd footage when runtime allows, and flag aspect-ratio, resolution, audio, licensing, and source-diversity risks during sourcing rather than after curation.


## V4 OpenMontage sourcing rule

If this sourcing decision is part of an OpenMontage run, use the selected pipeline's research/assets stage and the registry-discovered source tools. Treat `documentary-montage` as the default candidate pipeline for real-footage football emotion work, but confirm by reading `pipeline_defs/documentary-montage.yaml` locally.

## V5 patch addendum — live tournament sourcing

If the event is live or recent, use `shared/references/live-tournament-sourcing.md`. Record `recency_mode`, `source_availability_status`, and a resourcing schedule.

Do not abandon a fresh theme just because 50 early candidates are mediocre. For fresh events, the correct output may be `rescan_later`.

If the title claims `nobody expected`, gather public expectation evidence from `shared/references/social-sentiment-story-evidence.md` before the story strategy repeats that claim.
