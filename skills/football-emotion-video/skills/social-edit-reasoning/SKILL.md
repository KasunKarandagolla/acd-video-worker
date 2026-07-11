---
name: social-edit-reasoning
description: >-
  Guides every editorial reasoning decision for reusable emotional sourced-footage videos: football/sports edits, motivational compilations, rejection-to-comeback narratives, documentary montages, and similar theme-driven social videos. Use this at every stage where the agent is deciding what the viewer should feel next, including brief interpretation, sourcing, curation, sequencing, pacing, music/audio, visual cohesion, graphics/text, assembly, QA, loopbacks, and memory. This skill is a router and judgment framework, not a renderer or downloader.
---

# Social Edit Reasoning

This is the editorial judgment router for the whole video journey. It is not a one-time read. Different stages need different reference files, and the agent should load only the relevant reference at the decision point.

## The one rule everything else serves

Every editorial decision — source choice, clip choice, cut point, music swell, silence beat, text card, visual grade, QA fix, or memory lesson — must answer:

> What should the viewer feel right now, and does this choice deepen or interrupt that feeling?

Emotion outranks technique. A clean on-beat cut that kills the emotional moment is wrong. A slightly rough archive shot that carries the story may be correct.

## Adapted priority hierarchy for sourced-footage edits

1. **Emotion** — does the moment make the viewer feel what the story needs now?
2. **Story** — does it advance the arc, or is it just cool footage?
3. **Rhythm** — does it land on the right emotional and musical beat?
4. **Eye-trace / attention flow** — does the viewer know where to look next?
5. **2D visual continuity** — color, quality, aspect ratio, graphics, safe zones.
6. **3D/spatial continuity** — usually least important for sourced football/montage work.

When two considerations conflict, the earlier item wins.

## Stage router

| Stage | Decision being made | Read |
|---|---|---|
| 0. Repo / setup gate | Can this run execute, or only simulate? | `shared/references/repo-bridge/repo-setup-status.md`, `shared/references/repo-bridge/openmontage-schema-lock.md` |
| 0b. Current-event fact lock | Is the match/latest/current claim verified? | `shared/references/current-event-fact-lock.md`, `football-match-identification` |
| 1. Brief Intake | Topic/title -> emotional question, runtime, platform, tone | `shared/references/editorial-journey/brief-interpretation.md` |
| 2. Sourcing Strategy | Search queries, source diversity, recency handling | `shared/references/editorial-journey/sourcing-strategy.md`, `shared/references/live-tournament-sourcing.md` |
| 3. Visual/Source Verification | What is actually visible/audible? | `shared/references/verification-standard.md` |
| 4. Timestamp Extraction | Bounded clips with handles and role labels | `shared/references/editorial-journey/clip-selection.md` |
| 5. Clip Curation | Which candidates earn a place? | `shared/references/editorial-journey/clip-selection.md` |
| 6. Narrative / Sequencing | Arc order, phase coverage, dynamic revision | `shared/references/editorial-journey/narrative-structure.md`, `shared/references/dynamic-arc-revision.md` |
| 7. Pacing / Cuts | Shot duration, rhythm, reaction timing | `shared/references/editorial-journey/pacing-rhythm-cuts.md` |
| 8. Audio / Music / VO | Commentary, crowd, silence, narration, music, SFX | `shared/references/editorial-journey/audio-music.md`, `shared/references/audio-emotion-playbook.md` |
| 9. Visual Cohesion | Archive/stylized/seamless strategy, HDR/SDR, overlays | `shared/references/editorial-journey/visual-cohesion.md` |
| 10. Graphics / Text | Captions, title cards, typography, scoreline templates | `shared/references/editorial-journey/graphics-typography.md` |
| 11. Assembly | Build-to-music timeline, layer order, handles, refinement | `shared/references/editorial-journey/assembly-workflow.md` |
| 12. QA / Export | Editorial, technical, platform, rights, vibe checks | `shared/references/editorial-journey/quality-assurance.md`, `football-platform-export-validator` |
| 13. Memory | Reusable lessons only, provenance guarded | `hermes-football-memory-learning` |

## Critical decision dependencies

Do not skip or reverse stages without a written reason.

```text
Brief intake locks runtime, platform, arc shape, tone
  -> Sourcing locks query space and candidate quantity
  -> Verification locks what is real in the footage
  -> Curation locks clips per arc phase
  -> Sequencing locks rough timeline and emotional order
  -> Music/audio locks precise pacing and dominant sound
  -> Visual/text decisions lock readability and cohesion
  -> Assembly places decisions already made
  -> QA either passes or loops back to the failing stage
```

If feedback arrives after QA suggesting a major change, re-enter at the relevant stage and re-flow forward. Do not patch one isolated stage and pretend the downstream decisions still hold.

## Quick-reference cheat sheet

- Hook immediately; even long-form needs an emotional reason to keep watching.
- One clip, one job. If it adds no new information or intensity, cut it.
- Cut frequency tracks intensity, not a fixed template.
- The fall must be felt, not summarized. Payoff size depends on low-point truth.
- Use a deliberate breath before the peak moment when the footage earns it.
- Duck music under speech by the plan's specified range, then measure after render.
- Avoid three-in-a-row of the same shot type or emotional job.
- Text clarifies, emphasizes, or provides metadata; it must not compensate for weak footage.
- Source diversity and transformation are editorial rules as well as risk controls.

## Reusable skill boundary

Read `shared/references/llm-decision-boundaries.md` before adding new rules to this package.

This skill system should guide the LLM's decisions. It should not hardcode one video's facts, exact scorelines, exact timestamps, exact LUT values, exact clip scores, or exact music keys as reusable guidance.

The LLM is allowed to synthesize a project-specific arc when verified footage demands it, but must record that as an `arc_revision_gate` decision and must not convert it into a reusable rule from one example.

## Expected output

When routing or auditing a project, output and update `editorial_journey_state`:

```yaml
editorial_journey_state:
  current_stage: number
  stage_name: string
  completed_stages: [string]
  blocking_gates: [string]
  planning_mode: executable | simulate_only | hypothesis_only
  locked_decisions:
    runtime: string | null
    platform: string | null
    emotional_question: string | null
    tonal_flavor: string | null
    match_fact_lock_status: string | null
    music_locked: boolean
    openmontage_schema_lock_status: string | null
  missing_prerequisites: [string]
  recommended_next_skill: string
  required_reference: string
  reason: string
```

## Failure modes to avoid

- Starting sourcing before emotional question/runtime/platform/fact lock are handled.
- Jumping from clips directly to OpenMontage without sequencing, music, cohesion, graphics, and QA.
- Treating source titles as visual verification.
- Treating one video's fact pattern as a reusable skill rule.
- Using captions to explain missing footage.
- Claiming technical pass without measured artifacts.
- Continuing after an OpenMontage or Backlot human gate.

## References

- `shared/references/llm-decision-boundaries.md`
- `shared/references/editorial-journey/social-edit-reasoning-router.md`
- `shared/references/editorial-journey/brief-interpretation.md`
- `shared/references/editorial-journey/sourcing-strategy.md`
- `shared/references/editorial-journey/clip-selection.md`
- `shared/references/editorial-journey/narrative-structure.md`
- `shared/references/editorial-journey/pacing-rhythm-cuts.md`
- `shared/references/editorial-journey/audio-music.md`
- `shared/references/editorial-journey/visual-cohesion.md`
- `shared/references/editorial-journey/graphics-typography.md`
- `shared/references/editorial-journey/assembly-workflow.md`
- `shared/references/editorial-journey/quality-assurance.md`
- `shared/references/editorial-journey/genre-playbooks.md`
- `shared/references/current-event-fact-lock.md`
- `shared/references/fact-provenance-standard.md`
- `shared/references/dynamic-arc-revision.md`

## V7 repo-alignment addendum

Before a repo-backed run, invoke `hermes-openmontage-repo-bridge` and require:

1. `repo_setup_status`
2. `openmontage_schema_lock`
3. OpenMontage pipeline manifest inspection
4. tool registry support/provider output
5. render runtime user confirmation when required
6. Backlot checkpoint handling when required

If those are unavailable, continue only in `simulate_only` or `hypothesis_only` mode.
