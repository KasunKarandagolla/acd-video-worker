# Enhancements Summary: Closing Editorial Journey Gaps

## What was missing from v1

The original skill covered partial editorial reasoning (narrative structure, clip selection, pacing, audio, genre specifics) but **omitted 6 critical stages** that are executed by real editors every day. A complete LLM editing pipeline needs guidance on ALL stages, not just the conceptual ones.

## Gaps identified and filled

### **CRITICAL GAPS (completely missing):**

1. **Brief Interpretation** (NEW) — How to convert a title/theme into a specific story
   - How to identify the one emotional question
   - Runtime implications (15s, 30s, 60s, 3min+ require fundamentally different stories)
   - Platform implications (TikTok vs YouTube are different edits)
   - What gets locked in by brief decisions (runtime locks clip count, pacing, music scope)

2. **Sourcing Strategy** (NEW) — How to search for footage and know when to stop
   - Search methodology by content type (football searches ≠ motivational searches)
   - Quantity targets (how many candidate clips to pull for 30s vs 60s vs 3min)
   - Quality gates at source level (aspect ratio, resolution, licensing considerations)
   - When to stop searching (early termination rule for mediocre material)

3. **Assembly Workflow** (NEW) — The actual timeline construction methodology
   - Build-to-music-first vs build-cuts-first (and why music-first is recommended)
   - 10-step workflow: music placement → rough video → phase-by-phase pacing → sync → VO layer → graphics → effects → mixing → full playthrough → refinement
   - Naming conventions, layer management, handles (clip margin preservation)
   - Common assembly mistakes

4. **Quality Assurance** (NEW) — Validation before export
   - Technical QA: audio glitches, sync drift, video playback, timing accuracy
   - Editorial QA: emotional arc, story clarity, pacing consistency, redundancy spotting
   - Platform-specific QA: safe zones, text readability, aspect ratio appropriateness
   - Red flags that require re-cut vs. simple fixes

5. **Visual Cohesion** (NEW) — Making sourced footage from different sources look intentional
   - Three tiers of visual treatment (documentary / stylized / seamless)
   - Aspect ratio strategy when mixing vertical/horizontal footage
   - Matching strategies by clip type (action shots vs. reactions vs. crowd shots)
   - Color correction basics (white balance, exposure, contrast, saturation, LUT application)
   - When to accept mismatch as stylistic vs. when to fix it

6. **Graphics & Typography** (NEW) — Text placement and hierarchy
   - Text hierarchy by arc phase (title at cold open, peak quote at turning point, etc.)
   - Safe zones and mobile-specific placement (9:16 vertical needs different rules than 16:9)
   - Typography basics: font choice (sans-serif, bold), size hierarchy, contrast, duration
   - Common placements (lower third, center, corner, overlay)
   - Text-to-audio sync for speech-heavy content
   - Genre-specific conventions (football lower thirds, motivational peak quotes, etc.)

### **ENHANCED (existing sections deepened):**

7. **Brief Interpretation context added to narrative-structure.md**
   - Runtime allocation templates per arc phase
   - Decision checklist before moving to sourcing
   - How brief intake gates downstream decisions

8. **Decision Dependencies flowchart** (NEW in SKILL.md)
   - Visual map of what each stage locks in for the next stage
   - Critical principle: don't skip or reverse stages
   - When to loop back for feedback-based changes

## Complete editorial journey now covered

### Entry point is now BRIEF INTERPRETATION, not narrative-structure

The flow is now:

```
1. BRIEF INTERPRETATION (NEW)
   ↓ What's the story, runtime, platform, tone?
   
2. SOURCING STRATEGY (NEW)
   ↓ Where to search, how many candidates
   
3. CLIP CURATION (ENHANCED)
   ↓ Which clips earn a place
   
4. SEQUENCING (existing)
   ↓ Arc order and rough pacing
   
5. MUSIC SELECTION (already in audio-music.md, now position clarified)
   ↓ Locks in precise pacing
   
6. VISUAL COHESION (NEW)
   ↓ Color, aspect ratio, matching
   
7. GRAPHICS & TEXT (NEW)
   ↓ Titles, quotes, hierarchy
   
8. ASSEMBLY WORKFLOW (NEW)
   ↓ Actual timeline construction
   
9. QUALITY ASSURANCE (NEW)
   ↓ Spot errors before export
   
10. GENRE SPECIFICS (existing, now as final reference layer)
```

## File structure

```
social-edit-reasoning/
├── SKILL.md                    (updated with routing table, dependencies diagram)
└── references/
    ├── brief-interpretation.md     (NEW)
    ├── sourcing-strategy.md        (NEW)
    ├── clip-selection.md           (existing, refined)
    ├── narrative-structure.md      (existing)
    ├── pacing-rhythm-cuts.md       (existing)
    ├── audio-music.md              (existing)
    ├── visual-cohesion.md          (NEW)
    ├── graphics-typography.md      (NEW)
    ├── assembly-workflow.md        (NEW)
    ├── quality-assurance.md        (NEW)
    └── genre-playbooks.md          (existing)
```

## What's still out of scope (but noted)

These are real editorial decisions but fall outside the reasoning layer (more technical/platform-specific):

- **Export settings** (codec, bitrate, color space — platform specs)
- **Platform optimization** (aspect ratio crops, safe zones, loudness standards — each platform has different specs)
- **Iteration workflow** (feedback incorporation, non-destructive editing practices)
- **Licensing & rights** (music clearance, footage copyright, Content ID strategy — business/legal)

These are mentioned briefly where they intersect editorial reasoning, but aren't full sections. If the pipeline needs them systematized later, they can be added.

## For Hermes/OpenMontage integration

Each reference file is self-contained and can be pulled independently by a reasoning call:

- **Clip selection stage** pulls only `clip-selection.md` + `sourcing-strategy.md`
- **Assembly stage** pulls `assembly-workflow.md` + `pacing-rhythm-cuts.md`
- **QA stage** pulls `quality-assurance.md` only
- **Graphics decision** pulls only `graphics-typography.md`

The LLM doesn't need the whole skill in context — just the reference file for the stage it's deciding on.

## Testing recommendations

1. Run a test with a real brief ("Create a 30-second motivational football comeback edit from YouTube sources")
2. Let the pipeline flow through all 10 stages using the reference files
3. Compare output against QA checklist
4. Note any ambiguities in the reference files (they're written for human clarity; LLMs may interpret differently)

## Known limitations of this framework

- **Assumes competent sourcing.** If the theme has no good YouTube material, the best editorial reasoning can't fix that
- **Assumes target is social media** (9:16, short-form, high engagement). Long-form documentary or cinema-formatted content would need adapted brief-interpretation stage
- **Music-first assembly workflow works best when music is licensable/available.** If music selection is truly open-ended, build-cuts-first may be better (documented as alternative)
- **Text hierarchy assumes minimal text.** Some verticals (true crime, educational) may need heavier graphics, not covered here

---

**Version 2.0 complete.** Ready for pipeline integration and real-world testing.
