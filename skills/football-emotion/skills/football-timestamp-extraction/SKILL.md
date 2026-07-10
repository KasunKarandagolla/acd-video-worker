---
name: football-timestamp-extraction
description: Use when converting scene analysis into a timestamped table of clip candidates for a football emotion video — e.g. "extract timestamps for the penalty sequence", "give me clip timestamps from this analysis", "build the clip candidate list". Activates after football-visual-scene-analysis has produced scene-level output and a timestamped, editor-ready table is needed. This is a scene-intelligence task, not a transcript task — do not run this on title/metadata alone.
---

# Football Timestamp Extraction

Converts reviewed scene/audio understanding into a timestamped table of clip candidates that
`football-clip-scoring` can rank. This is not transcription — it combines frame understanding,
audio cues, emotional story role, and editability into one row per candidate clip.

## When to use this

- A `video_scene_analysis` exists from `football-visual-scene-analysis`
- Source video duration/timestamps are known (i.e., scenes were tied to actual positions in the file)

## Required inputs

- `video_scene_analysis` for the source video
- Audio cues / transcript if available
- The target story structure (from `story_plan` or `user_instruction_profile`), to know which
  editor timeline role each candidate should be evaluated against

## Workflow

1. For each scene in the `video_scene_analysis`, decide whether it's a standalone clip candidate or needs merging with adjacent scenes (e.g., "walkup" + "the kick" + "immediate reaction" often belong together as one clip spanning several scene rows).
2. Include the moment **before, during, and after** the decisive action — a clip cut too tight loses the reaction that makes it emotionally legible.
3. Label each candidate by `editor_timeline_role` per the timeline model in `football-visual-scene-analysis`.
4. Only claim an exact timestamp when the row is `confidence: high` or `medium` in the source scene analysis — otherwise mark the row `UNVERIFIED — requires manual review` rather than inventing a plausible-looking range.
5. Output `clip_candidate` rows (see `shared/contracts/pipeline-artifacts.md`) — scoring itself belongs to `football-clip-scoring`, not this skill; this skill's job is producing well-formed candidates, not ranking them.

## What makes a timestamp row good vs. bad

**Bad row (reject this pattern):**
```
| 2:00-2:30 | Goal | Messi scores | music | good edit | emotional | use goals |
```
Too generic — no visual specificity, no audio specificity, no edit instruction, no emotional purpose.

**Good row:**
```
| 6:42-7:05 | Pressure climax | Player walks toward penalty spot; camera alternates between
face, goalkeeper, crowd, teammates | Crowd noise rises; music should be removed/reduced | Hold
pre-kick pause, cut to reaction immediately after outcome | Builds unbearable waiting before
release or heartbreak | Penalty emotion comes from the wait before the kick — don't overcut |
```

## Universal timestamp targets (check for these regardless of specific topic)

1. Before the decisive event
2. The decisive event itself
3. Immediate player reaction
4. Crowd/fan reaction
5. Commentator line
6. Scoreboard/final result
7. Aftermath/tunnel/celebration
8. Symbolic object: trophy, shirt, flag, medal, boots, empty stadium

## Failure modes to avoid

- Fabricating precise timestamps that weren't actually confirmed in the scene analysis
- Clipping only the action and missing the reaction that gives it emotional weight
- Ignoring audio peaks or silence opportunities when defining clip boundaries
- Treating this as a transcription pass rather than a scene-intelligence pass

## Handoff

Output: table of `clip_candidate` rows. Next skill: `football-clip-scoring` to rank and select.

## References

- `shared/references/verification-standard.md` — confidence labels and when a timestamp can be treated as trustworthy
- `shared/references/emotion-pattern-library.md` — clip-type priorities that inform which candidates are worth extracting at all

## V5 patch addendum — penalty sub-arc and match-clock normalization

For penalties or shootouts, use `shared/references/penalty-shootout-subarc.md`. Extract walk-up, face close-up, goalkeeper read, crowd silence, kick, result, immediate reaction, and secondary reaction as separate candidates when footage allows.

Normalize stoppage-time notation where possible: keep both the match-clock form (`90+2'`) and the broadcast-timeline form (`92:15`) with provenance. Do not invent either value.
