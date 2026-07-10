---
name: football-caption-thumbnail-direction
description: Use when writing captions/text overlays or selecting thumbnail frames and text for a football emotion video — e.g. "write captions for this section", "pick a thumbnail for this video", "what text should go on the thumbnail", "add a quote caption to the hook". Activates once story beats need caption framing/clarity, or once clips are selected and a thumbnail frame/text needs choosing. Covers both captions and thumbnails since they share the same short-text, non-misleading, low-clutter rules.
---

# Football Caption & Thumbnail Direction

Creates minimal, high-impact captions and selects thumbnail frame candidates with short text
options. Captions and thumbnails are combined in one skill because they share the same core rules
(short text, high contrast, non-misleading, don't cover the face) and are usually decided together
once clips are locked.

## When to use this

- Story beats need caption framing or clarity (hooks, turning points, quote moments)
- Clips are selected and a thumbnail candidate/text is needed

## Required inputs

- Script/narration text
- Selected clips with scene roles
- Story theme / title direction

## Workflow — captions

1. Read `shared/references/pro-editing-methodology.md`'s caption-style section.
2. Decide caption type per beat: emotional (hooks/turning points, 2-8 words), commentary (only the important words from real audio), or quote (chapter openings/flashbacks/thesis).
3. Default to minimal text — heavy captions only for tactical/analytical explanation, never during raw emotional moments.
4. Place captions clear of faces and the ball; keep font choice to one clean bold sans-serif per project.
5. Output `caption_plan` entries (see `shared/contracts/pipeline-artifacts.md`).

## Workflow — thumbnails

1. Identify candidate frames from the highest-emotion, clearest clips (ranked: emotional face + context > player vs trophy/scoreboard contrast > crying player + short text > iconic action frozen at peak > crowd/national emotion).
2. Score each candidate on the thumbnail rubric:
```yaml
thumbnail_score_10:
  face_emotion: 0-2
  story_clarity: 0-2
  contrast_readability: 0-2
  curiosity: 0-2
  low_clutter: 0-1
  non_misleading: 0-1
```
3. Propose 2-4 word text options (e.g. `LAST CHANCE`, `HE BROKE`, `ONE KICK`, `IMPOSSIBLE`, `THE BURDEN`, `FINAL TEARS`) that the footage actually supports — never a claim the video doesn't back up.
4. Output `thumbnail_candidate` entries.

## Decision rules

- Text never covers a face.
- Caption/thumbnail text must not explain what's already visually obvious.
- No clickbait the footage doesn't support — this applies equally to captions and thumbnail text.
- Commentary captions emphasize one word/phrase at a time, not full sentences.

## Failure modes to avoid

- Too much text, killing pacing
- Generic quote spam disconnected from the specific story
- Meme-style captions in serious/heartbreak scenes
- A thumbnail that promises an emotion or event the video doesn't actually deliver

## Handoff

Output: `caption_plan` + ranked `thumbnail_candidate` list. Feeds into `openmontage-edit-planning`
(captions placed into the timeline).

## References

- `shared/references/pro-editing-methodology.md` — full caption style and thumbnail scoring rules

## v3 Graphics & Typography Alignment

Read `shared/references/editorial-journey/graphics-typography.md` before planning captions, title cards, quotes, or thumbnail text. Use the minimum effective dose: text must clarify, emphasize, or provide necessary metadata. Check phone readability, safe zones, contrast, duration, and text-to-audio sync before approval.

## V5 patch addendum — penalty scoreline typography

For penalty shootouts, use a two-line score template:

```text
TEAM_A 2–2 TEAM_B
TEAM_A wins 4–3 on penalties
```

Rules: main score large, shootout result smaller, never confuse full-time/extra-time/shootout result, and keep the text safe from the broadcast scorebug. Replace placeholders only after `match_fact_lock.status: verified` and cite the exact source/provenance in the graphics artifact.
