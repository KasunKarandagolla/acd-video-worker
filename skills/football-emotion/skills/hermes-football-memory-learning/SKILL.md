---
name: hermes-football-memory-learning
description: Use after a football emotion video project is complete or a major decision has been validated — e.g. "save what we learned from this project", "remember this for next time", "update memory with this project's lessons", "what worked well here that we should reuse". Activates at project completion (after football-retention-quality-control passes) or whenever a specific reusable lesson (a hook pattern, an audio choice, a source type) has proven itself and should persist into Hermes memory for future football-emotion projects.
---

# Hermes Football Memory Learning

Distills a completed project's reusable lessons into a Hermes-memory-appropriate update. Hermes'
`MEMORY.md`/`USER.md` are small, curated files (~2,200 / ~1,375 characters respectively) injected
into every session's system prompt — this skill's entire job is fitting genuinely useful lessons
into that tight budget, not dumping the full project record into memory.

## When to use this

- A project has passed `football-retention-quality-control`
- A specific technique/source/audio choice proved itself mid-project and is worth remembering immediately, without waiting for full project completion

## Required inputs

- The completed (or in-progress) project's key artifacts: `story_plan`, final `qc_report`, notable `clip_candidate` successes/failures, `audio_plan` choices that worked
- Prior Hermes memory content, if readable, to avoid duplicating an existing entry

## Workflow

1. Identify what's genuinely reusable across *future, different* projects — not project-specific trivia. "Silence-before-impact outperformed a sad-piano cue for this heartbreak story" is reusable. "This specific Ronaldo clip was good" is not memory-worthy on its own (it belongs in the project's own on-disk record, not global memory).
2. Write each lesson as a single, short, plain sentence — MEMORY.md-scale, not a paragraph.
3. Check the character budget before writing: MEMORY.md has roughly 2,200 characters total *for everything Hermes remembers*, not just this project's football lessons — this skill must be conservative and prioritize the highest-value 1-3 lessons per project, not try to log everything.
4. If the memory update would exceed budget, don't force it in — instead, write the full record to a project-local file and note only a short pointer/summary line in memory (see `hermes_memory_update.full_project_record_path` in the shared contracts).
5. Before adding a new entry, check for an existing similar entry (if readable) and consolidate/update rather than duplicating — Hermes' own memory system does this via its curator, but this skill should not rely on that and add redundant near-duplicate lines carelessly.
6. Output a `hermes_memory_update` (see `shared/contracts/pipeline-artifacts.md`).

## What belongs in MEMORY.md-scale entries vs. project files

**Memory-worthy (short, cross-project, pattern-level):**
- "For heartbreak stories, holding the silent-face shot 4-5s outperforms a fast cut to the next reaction."
- "Official broadcaster footage of [tournament] has cleaner audio than fan reuploads — prefer it when available."
- "Sad piano felt repetitive when used in 3+ sections of one project — vary music category more."

**Not memory-worthy (belongs in the project's own file, referenced via `full_project_record_path`):**
- Full clip scorecards
- The complete audio asset catalog used
- Full decision logs
- Anything specific to one video that won't generalize

## Decision rules

- Prioritize ruthlessly — 1-3 short lessons per project is normal; do not try to write an exhaustive summary into memory.
- Never write speculative "lessons" that weren't actually confirmed by this project's outcome (e.g., don't claim a technique "worked" if the QC pass actually flagged issues with it).
- Keep audio-specific lessons in the same update rather than treating them as a separate memory-writing pass — this skill covers what a hypothetical separate "audio memory updater" skill would have done, folded in as one section of this skill's output (see architecture decision notes).

## Failure modes to avoid

- Writing memory entries so long they'd blow the MEMORY.md character budget on their own
- Duplicating an existing memory entry instead of updating it
- Treating project-specific trivia as if it were a generalizable lesson
- Claiming a technique "worked" without it having actually been validated by this project's QC outcome

## Handoff

Output: `hermes_memory_update`. This is the last skill in the pipeline for a given project — no
further handoff within this package.

## References

- `shared/contracts/pipeline-artifacts.md` — the `hermes_memory_update` schema
- `analysis/02_repo_analysis.md` — confirmed facts about Hermes' MEMORY.md/USER.md size limits and `session_search` fallback this skill's budget discipline is based on

## v3 Editorial Memory Fields

After each project, remember not only football/story outcomes but also editorial journey lessons: brief clarity, source quantity sufficiency, visual cohesion tier chosen, music-first or cuts-first assembly result, graphics/text decisions, QA failures, and loop-back fixes. Store compact learnings only; keep full details in the project record path.


## V4 Hermes repo bridge memory fields

When the production runs through the confirmed repos, include these fields in the memory update: Hermes commit, OpenMontage commit, selected pipeline, provider menu summary, render runtime, source/license blockers, Backlot gate outcomes, and final artifact paths under `OpenMontage/projects/<project-id>/`.

## V5 patch addendum — memory provenance guard

Before writing to Hermes memory, pass memory entries through `football-fact-provenance-gate` and `tools/memory_claim_lint.py`.

Every memory entry must include:

```yaml
memory_entry:
  lesson: string
  evidence_type: measured_result | editor_observation | user_preference | failed_attempt | hypothesis
  confidence: low | medium | high
  do_not_generalize_beyond: string
  source_project: string
```

Reject exact percentage improvements, exact match facts, legal/license claims, or exact technical values unless they have verified or measured provenance.
