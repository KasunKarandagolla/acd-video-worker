---
name: football-music-library-selector
description: Use when finding candidate music or SFX assets for a football emotion video — e.g. "find music for a heartbreak scene", "what SFX for a goal moment", "suggest tracks for the climax", "build a music library for this project". Activates when football-audio-music-director needs asset recommendations, or when the user directly asks for music/SFX candidates. This skill selects CANDIDATES only — it never marks an asset as cleared for use; that is football-rights-safe-audio-license-checker's job exclusively.
---

# Football Music Library Selector

Selects candidate music/SFX assets from a rights-aware catalog. This skill is the asset selector,
not the editor and not the legal gate — it hands candidates to
`football-rights-safe-audio-license-checker` before anything here can be treated as usable.

## When to use this

- `football-audio-music-director` needs asset recommendations for a section
- The user directly asks for music/SFX suggestions
- Building or refreshing a project's candidate asset shortlist

## Required inputs

- `emotion_type` / music category needed (sad_piano, cinematic_rise, epic_orchestral, dark_ambient, heartbeat_tension, motivational, documentary_piano, crowd_ambience, or an SFX category)
- Approximate duration needed
- Platform (assume `youtube` unless told otherwise)

## Non-negotiable safety rule

**Presence in the catalog is not clearance.** Every candidate this skill returns is a
*ranked possibility*, not an approved asset. Rows in the catalog marked with a search/category
link rather than a direct asset page (`is_exact_asset_page: false`, or marked ⚠️ in the catalog)
are lower-trust by default and must be flagged as needing extra scrutiny when handed to the
license checker.

## Workflow

1. Read `references/music-sfx-catalog.md` for the quick category index. When the user needs real asset options or a broader shortlist, also read `references/full-candidate-music-sfx-catalog.md`.
2. Select: 3 primary candidates, 2 backup alternatives, up to 2 SFX candidates if the section needs them, and 1 silence/crowd-only option — per `shared/references/audio-emotion-playbook.md`, silence or crowd-only audio is frequently the *stronger* choice and should always be offered as an explicit alternative to music, not treated as a fallback of last resort.
3. For each candidate, populate a `music_sfx_candidate` (see `shared/contracts/pipeline-artifacts.md`), including `is_exact_asset_page` and `risk_flag` honestly.
4. Do not rank purely by popularity — suitability for the specific football-emotion use case comes first.
5. Hand the shortlist to `football-rights-safe-audio-license-checker` before any candidate can be used in an `audio_plan`.

## Asset policy

- Prefer royalty-free / free-to-use sources (Pixabay, Mixkit, YouTube Audio Library, Incompetech, Free Music Archive, Freesound, Musopen, FreePD).
- Never recommend copyrighted commercial songs as usable assets — if a commercial track is mentioned at all (e.g. as a style reference the user asked about), label it explicitly as "style reference only, not a usable asset."
- Keep attribution/creator/license notes with every candidate when the license type requires them.
- Do not use music in a misleading way (e.g. implying triumph the story hasn't earned yet).

## Output schema

```yaml
music_library_selection:
  primary_music_candidates: [music_sfx_candidate]
  backup_music_candidates: [music_sfx_candidate]
  sfx_candidates: [music_sfx_candidate]
  silence_or_crowd_only_candidates: [music_sfx_candidate]
  license_verification_required: true
  rejection_notes: [string]
```

## Failure modes to avoid

- Selecting music that would overpower the moment's real emotion (check against `shared/references/audio-emotion-playbook.md`'s hierarchy before finalizing a shortlist)
- Recommending famous copyrighted songs as if they were usable
- Suggesting epic/triumphant music before the story has earned it
- Treating a catalog entry's presence as if it were already legally cleared
- Ignoring the silence/crowd-only option because music feels like the "default" choice

## Handoff

Output: `music_library_selection`. Next skill: `football-rights-safe-audio-license-checker`
(mandatory gate before any candidate reaches `football-audio-music-director`).

## References

- `references/music-sfx-catalog.md` — compact category index and verification framing
- `references/full-candidate-music-sfx-catalog.md` — full ChatGPT + Kimi candidate music/SFX catalog. Candidate reference only; every row still needs final license/page verification before use
- `shared/references/audio-emotion-playbook.md` — when each music type is/isn't appropriate
