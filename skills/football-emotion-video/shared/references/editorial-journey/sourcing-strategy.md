# Sourcing Strategy & Search

Read this in Stage 2, after brief intake (Stage 1) is complete. This stage converts a story hypothesis into candidate footage via search.

## Pre-search: what you should know before typing a query

From the brief intake (Stage 1), you should have locked in:
- Runtime target (which gates how many clips you need)
- Tonal flavor (which gates what kind of footage to look for)
- Non-negotiable moments (which gate specific searches)

If you don't have these, stop and re-read `brief-interpretation.md`. Sourcing without a brief is wasteful.

## Search strategy by content type

### Football / sports edits

**Must-have searches (non-negotiable):**
- `[Player Name] goal/score/win [Year/Season]` — the moment itself
- `[Player Name] celebration/reaction` — immediate aftermath
- `[Player Name] [context of comeback]` — e.g., "injury return" or "demotion recovery"
- `[Competition] final moment [relevant year]` — for context/stakes

**Context searches (depth, only if runtime allows):**
- `[Player Name] interview [relevant year]` — VO/commentary potential
- `[Team/League] crowd reaction` — intercut material
- `[Player Name] training/preparation` — grind phase footage

**Sourcing discipline:**
- Pull 3–5 versions of the core moment (different angles/broadcasts if available) before deciding on the "canonical" one
- For each non-negotiable moment, pull 5–8 candidate clips, then rank by the 5-axis scoring rubric in `clip-selection.md`
- Stop searching for a specific beat once you have 2–3 strong options; more is redundancy unless runtime demands it

### Motivational / speech edits

**Must-have searches:**
- `[Speaker Name] [Topic/Quote] speech/motivation` — the actual speech
- `[Speaker Name] [Topic]` — b-roll of the person/context
- If the speaker is a public figure: `[Speaker Name] [moment being discussed]` — real footage of the thing being talked about

**Context searches:**
- `[Speaker Name] interview/background` — who is this person, why should we care
- `[Topic] real-world examples` — b-roll showing what the speech is about (poverty, struggle, achievement, etc.)

**Sourcing discipline:**
- Pull the full speech first (don't optimize for short clips yet), listen/watch it fully to identify the peak line
- Search for b-roll that matches *specific phrases* in the speech, not generic "motivation" footage
- Avoid stock footage that doesn't connect to the actual words (this reads as insincere)

### Comeback / rejection-to-triumph edits

**Must-have searches:**
- `[Subject] [Low point]` — the fall (injury, demotion, failure, public criticism, etc.)
- `[Subject] comeback/return` — the triumph
- `[Subject] [specific moment of proving doubters wrong]` — the turning point

**Context searches:**
- `[Subject] interview/reaction [relevant date]` — VO/commentary
- `[Subject] training/preparation` — grind phase
- `[Doubters/Critics] reaction to return` — crowd/media response to the comeback

**Sourcing discipline:**
- The fall phase needs *real* visual documentation, not narrated implication — if you can't find clips of the actual fall, you'll need heavier VO/text to establish it
- Seek contrast pairs (same location/pose, different time) for match-cut potential (see `pacing-rhythm-cuts.md`)

## Quantity guidance (how many candidates to evaluate)

This depends on runtime. Use this as a starting target:

| Runtime | Expected clip count in final edit | Candidate clips to pull per beat | Total candidates to pull |
|---|---|---|---|
| 15 sec | 3–5 | 8–10 per clip (!) | 25–50 |
| 30 sec | 8–12 | 5–8 per beat | 40–80 |
| 60 sec | 15–25 | 3–5 per beat | 45–100 |
| 3 min+ | 30+ | 2–3 per beat | 60–90 |

These seem high, but sourcing is a filtering operation — you're generating surplus to have optionality. Professional editors often source 3–5x the eventual clip count.

**Early termination rule:** If you've pulled 50+ candidate clips and they're all mediocre (no standout moments), consider that the theme may not have enough good sourced footage and flag it before moving to curation. Better to know now than to build an edit from weak material.

## Quality gates (what to filter out *during* sourcing)

Before curating (Stage 3), filter at source level:

- **Aspect ratio mismatch too extreme?** Widescreen broadcast + vertical TikTok footage can work if intentional, but don't pull candidates from incompatible aspect ratios unless you're ready to crop/pan aggressively. Flag these separately.
- **Resolution too low for target platform?** 480p footage upscaled to 1080p will show compression artifacts. Lower bar for archival/iconic moments; higher bar for generic b-roll.
- **Audio quality unusable?** If it's a speech edit, the audio is non-negotiable. If it's background b-roll, audio can be replaced. Know which kind you're pulling.
- **Licensing risk?** Archived footage from official leagues (NFL, Premier League, etc.) has clearer licensing than random fan footage. Don't source from channels/content that are themselves copyright-risky (re-uploads without attribution).

## The open-loop risk: when to stop sourcing

It's possible to search forever. Set a stopping point:

- Once you have 2–3 strong candidates for each non-negotiable moment AND
- Once you've filled each arc phase with at least one candidate clip AND
- Once you've generated the quantity target for your runtime (from table above)

**Then move to Stage 3 (Curation).** You can always go back to sourcing if curation reveals a gap (e.g., "I have 3 strong payoff shots but no good grind footage"), but do that as exception, not norm.

## Practical sourcing constraints (Hermes/OpenMontage specific)

- YouTube search caps at typically 50–100 results per query, with most useful results in the first 20
- Repeat searches with different keywords when you hit a wall (e.g., `[Player] goal` vs. `[Player] scores` vs. `[Player] [Match] highlights`)
- Archive.org and other tape libraries have different indexing — consider multiple sources if sourcing a historical moment
- Be explicit about source diversity: "3 clips from official league, 2 from broadcaster, 2 from fan uploads" is healthier than "7 from one channel"

## Reasoning checklist for this stage

- [ ] Do I have the brief intake complete (runtime, tone, non-negotiable moments)?
- [ ] Have I pulled 3–5 versions of core moments before settling on one?
- [ ] Am I at or above the quantity target for my runtime?
- [ ] Do I have at least one candidate for each arc phase?
- [ ] Have I sourced from multiple channels (not over-relying on one)?
- [ ] Have I flagged aspect ratio / resolution / licensing risks?
- [ ] Have I quality-filtered at source (removed obviously unusable footage)?

## V5 addition — live events

For live/recent tournament events, use `shared/references/live-tournament-sourcing.md`. Do not apply the archive-era stopping rule too early. Use rescan states when official footage is not yet available.
