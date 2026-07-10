# Social Edit Reasoning Router Reference

This file is the editorial reasoning router integrated into the football-emotion skill system. It should be read when the agent is unsure which editorial stage owns a decision. It is deliberately a router/reference layer, not a renderer and not a competing OpenMontage orchestrator.

---
name: social-edit-reasoning
description: Guides every editorial reasoning decision for long-form emotional storytelling videos made for social media — football/sports edits, motivational compilations, rejection-to-comeback narratives, and similar theme-driven pieces assembled from sourced footage. Use this skill whenever the pipeline is curating clips from raw/sourced footage, structuring the emotional arc, deciding what to cut and where, choosing transitions, syncing cuts to music, mixing audio (voice/music/SFX/ducking), placing text or quotes, or doing any other editorial judgment call — not just at the final assembly step. Consult it at EVERY stage of the pipeline, not once at the start. Not limited to football/motivational content; use for any emotional narrative edit.
---

# Social Edit Reasoning

## What this is

A decision framework for editorial judgment calls, distilled from how working professional editors actually reason (Walter Murch's editing hierarchy, ACE editors interviewed in *Art of the Cut*, and working editors like Vashi Nedomansky) and adapted for compilation-style, sourced-footage social content rather than shot-for-purpose narrative film.

This is not a one-time read. Different stages of the pipeline need different sections below — treat this as a router.

## The one rule everything else serves

**Every editorial decision — clip choice, cut point, music swell, text card — must answer: "what does the viewer feel right now, and does this choice deepen or interrupt that feeling?"**

If a technically "correct" cut (clean match, good resolution, on-beat) doesn't serve the feeling, don't make it. If a technically "wrong" cut (mismatched footage, slightly off-beat) serves the feeling better, make it anyway. Emotion outranks technique. This is the single most consistent thing professional editors say when asked how they actually decide — not "how do I obey the rules" but "what does this do to the audience."

## Adapted priority hierarchy (for sourced-footage compilation edits)

Walter Murch's classic hierarchy, re-ordered for this use case since items 5–6 matter far less when clips come from different sources rather than one shoot:

1. **Emotion** — does the moment make the viewer feel what the story needs them to feel right now
2. **Story** — does it advance the arc, or is it just "cool footage" with nothing to do
3. **Rhythm** — does it land on the right beat, musically and emotionally
4. **Eye-trace** — does the viewer's attention flow naturally from the last frame into this one
5. **2D plane / visual continuity** — do the shots feel like they belong in the same piece (color, quality, aspect ratio)
6. **3D continuity** — physical/spatial matching — barely relevant here, don't over-invest in it

When two considerations conflict, the higher-numbered one loses. A perfect on-beat cut (3) that kills the emotional moment (1) is the wrong cut.

## Pipeline stages → where to look

| Stage | What the LLM is deciding | Read |
|---|---|---|
| **1. Brief Intake** | Title/theme → specific emotional story, runtime, platform, arc shape | `references/brief-interpretation.md` |
| **2. Sourcing Strategy** | Where to search, how many candidates, what to filter at source level | `references/sourcing-strategy.md` |
| **3. Clip Curation** | Which sourced clips earn a place in the edit? | `references/clip-selection.md` |
| **4. Sequencing & Pacing** | What order, how long does each shot hold, where do cuts fall? | `references/pacing-rhythm-cuts.md` |
| **5. Audio/Music/VO** | Track choice, ducking, SFX layering, volume automation, quote/VO placement | `references/audio-music.md` |
| **6. Visual Cohesion** | Color grading, aspect ratio handling, matching sourced footage across sources | `references/visual-cohesion.md` |
| **7. Graphics & Text** | Text placement, typography, hierarchy, safe zones, duration | `references/graphics-typography.md` |
| **8. Assembly Workflow** | Actual timeline construction, music-sync-first methodology, clip placement | `references/assembly-workflow.md` |
| **9. Quality Assurance** | Technical checks, editorial validation, self-review before export | `references/quality-assurance.md` |
| **10. Genre Specifics** | Football, motivational, comeback-arc conventions | `references/genre-playbooks.md` |

Read the relevant reference file *at* that decision point, not all of them up front — they're written to be pulled in independently.

## Quick-reference cheat sheet

Use this for fast decisions; go to the reference files when a call is genuinely hard.

- **Hook immediately.** Even in long-form, the first 3–5 seconds must state or tease the emotional payoff. Don't "build up" to the premise — long-form still competes with a thumb mid-scroll.
- **One clip, one job.** If a candidate clip doesn't add new information or new emotional intensity versus the last one, cut it — don't include it just because it's good footage.
- **Cut frequency should track intensity, not stay constant.** Slower/held shots during setup and low points, faster cuts as tension or energy rises, and a deliberate "breath" (a slightly longer hold, or near-silence) right before the peak moment.
- **Duck music under any speech** (commentary, VO, interview) by roughly 6–12 dB; restore after. Never let music compete with words that matter.
- **Avoid three-in-a-row of the same shot type** (three celebration shots, three reaction shots) without a change of angle, scale, or beat — it reads as padding even if each clip is individually good.
- **The fall must be felt, not summarized.** In comeback/motivational arcs, resist the urge to rush through the low point to get to the payoff — the payoff's size is proportional to how real the low point felt.

## Practical constraint: sourcing footage from YouTube

Since this pipeline sources clips from YouTube rather than original footage, flag this as an operational risk factor, not just a legal footnote: heavy reliance on long unedited lifts from a single broadcast/creator is what triggers Content ID claims and demonetization, regardless of intent. Editorial choices that also happen to reduce this risk: favor short, transformative use of any one source clip, add original value (VO, commentary, structure, music) rather than just resequencing raw footage, and draw from a diversity of sources rather than one channel. This is a business-continuity consideration for the pipeline, worth weighing alongside the emotional/editorial criteria above — not a separate compliance step bolted on afterward.

## Critical decision dependencies (what gates what)

Stages are not independent. Skip early stages and later decisions collapse. Here's what each stage locks in:

```
1. Brief Intake LOCKS IN:
   ├─ Runtime (15s / 30s / 60s / 3min+)
   ├─ Platform (TikTok / YouTube / Instagram)
   ├─ Arc shape (which Murch phases exist)
   └─ Tonal flavor (triumphant / introspective / defiant / etc.)
        ↓ gates ↓
2. Sourcing Strategy LOCKS IN:
   ├─ Search keywords
   ├─ Candidate clip quantity targets
   └─ Source diversity targets
        ↓ gates ↓
3. Clip Curation LOCKS IN:
   └─ Actual clips for each arc phase
        ↓ gates ↓
4. Sequencing LOCKS IN:
   ├─ Rough timeline duration
   └─ Rough pacing per phase
        ↓ gates ↓
5. Music Selection LOCKS IN:
   ├─ Precise pacing (music structure = story pacing)
   └─ Emotional tone (music choice reinforces tone decided in stage 1)
        ↓ gates ↓
6–7. Visual & Graphics LOCKED AFTER music (music decides pacing, pacing decides where text goes)
        ↓ gates ↓
8. Assembly LOCKED AFTER all decisions above (you're just placing what's been decided)
        ↓ gates ↓
9. QA finds gaps or errors → loop back to relevant earlier stage
```

**Key principle:** Don't skip or reverse these stages. If you do assembly before sourcing, you're building blind. If you select music before deciding your runtime, music may not fit. If you don't lock brief intake, everything downstream is guesswork.

**Exception workflow:** If feedback arrives after QA suggesting a major change ("make this more triumphant" or "this is too long"), re-enter at the relevant stage and re-flow forward. Don't try to patch one stage in isolation.

## How to use this file

When a stage of the pipeline needs a judgment call: identify which row in the table above it falls under, read that reference file, apply its heuristics. The files are written to be pulled in independently — you don't need the whole skill in context, just the relevant reference file. If a decision conflicts across files, the later (more specific) file wins.
