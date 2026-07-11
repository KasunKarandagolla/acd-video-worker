# Clip Selection & Curation

Read this in Stage 3, after sourcing has produced candidate footage and before sequencing begins. This stage decides which candidate clips earn a place in the edit.

## Core principle

A clip is not selected because it is cool. It is selected because it performs a job in the emotional journey: clarify stakes, deepen the fall, show pressure, create a turning point, land the payoff, or release the audience after the peak.

## Required inputs

- `brief_interpretation` with emotional question, runtime, platform, tonal flavor, and non-negotiable moments.
- `source_video_candidate` list from sourcing.
- Verified or partially verified `scene_candidate` / `clip_candidate` rows where possible.
- Any source-level risk flags: aspect ratio, resolution, audio quality, licensing/reused-content risk.

## Five-axis curation check before scoring

For every candidate, answer:

1. **Emotion:** What does this make the viewer feel right now?
2. **Story:** Which arc phase does it serve?
3. **Rhythm:** Does its natural duration fit the pacing needed by that phase?
4. **Visual clarity:** Can a first-time viewer understand the moment quickly?
5. **Transformability/risk:** Can it be used briefly and originally without becoming a lazy lift from one source?

## Clip Score /10

Use the canonical scorecard in `shared/contracts/pipeline-artifacts.md`:

```yaml
emotional_strength_2: 0-2
visual_clarity_2: 0-2
story_relevance_2: 0-2
audio_commentary_value_1: 0-1
uniqueness_1: 0-1
editability_1: 0-1
rights_reused_content_risk_1: 0-1
total_10: 0-10
```

Thresholds:

- `8.0-10`: core story clip, strong candidate for hook/turning point/climax.
- `6.0-7.9`: useful support clip.
- `4.0-5.9`: context-only or replace if better footage exists.
- `<4.0`: reject.

## Redundancy rule

Avoid selecting three clips in a row with the same emotional job or same visual type. Three celebration shots, three crowd shots, or three dribble clips back-to-back usually read as padding unless each escalates in scale, emotion, or meaning.

## Phase coverage gate

Before sequencing, confirm every required arc phase has at least one credible clip. Do not hide missing fall/grind/context footage with captions. If the visual evidence is missing, either return to sourcing or change the story scope.

## Rejection rules

Reject or downgrade clips that:

- are visually unclear at target platform size;
- duplicate another stronger clip without adding new emotion or information;
- rely on copyrighted music/editing from another creator rather than raw useful footage;
- are too long and cannot be transformed safely;
- have aspect ratio/resolution problems that would dominate the edit;
- show emotion without context in a way that feels exploitative.

## Output

Produce selected `clip_candidate` rows with scorecards, recommended use, openmontage notes, and any source risk flags. Hand off to Stage 4 sequencing/pacing.

## Reasoning checklist

- [ ] Does every selected clip answer the emotional question?
- [ ] Does every arc phase have at least one real visual candidate?
- [ ] Are low-point/fall clips strong enough for the payoff to matter?
- [ ] Are there redundant clips that only exist because they look good?
- [ ] Have source concentration and reused-content risk been flagged?
