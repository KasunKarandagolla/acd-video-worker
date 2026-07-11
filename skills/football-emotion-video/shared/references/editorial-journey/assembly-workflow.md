# Assembly Workflow & Timeline Construction

Read this in Stage 8, when you have sequenced clips (Stage 4) and are about to build the actual timeline. This stage is the physical construction of the edit.

## The assembly question no one asks: what to lock first?

Professional editors face a decision before placing a single clip: do I build to music, or do I build the cuts first?

**Build-to-music workflow** (recommended for this pipeline):
1. Place music first (full track, locked)
2. Place all video clips roughly in timeline, align to music structure
3. Trim clip durations to fit music
4. Micro-sync cuts to beats/moments within music

**This approach because:** Music structure should gate everything (see `audio-music.md` — music structure = story pacing structure). Forcing cuts onto music is faster than force-fitting music to pre-edited cuts.

**Build-cuts-first workflow** (alternative, if music isn't pre-selected):
1. Place all clips in sequence, allow them to run at natural lengths
2. Assemble VO/speech layer (if any) at natural pace
3. *Then* find music that matches the resulting pacing
4. Adjust clip durations to hit music peaks

Only use this if music isn't locked yet (Stage 5 incomplete).

## The actual assembly workflow (build-to-music assumed)

### Step 1: Music placement (10 min)
- Import music to timeline (audio layer)
- Confirm it's the full, uncut track (no pre-fades)
- Mark the critical moments on the music in your NLE (beat markers, waveform notes):
  - Intro ends / build begins
  - Build peaks / drop happens
  - Breakdown starts
  - Final drop or outro
- Measure total music duration and confirm it matches your target runtime from brief intake

### Step 2: Rough video placement (20 min)
- For each arc phase in order (cold open → setup → fall → grind → turning point → triumph → coda), drag the best-candidate clips into the timeline in sequence
- Don't worry about precise trimming yet — just get them in order
- Allow clips to run full-length for now
- Confirm: does the sequence of clips *visually* make narrative sense? If a clip is badly out of place, swap it now.

### Step 3: Phase-by-phase pacing (30–45 min)
This is where the actual rhythm work happens. Go through one arc phase at a time (don't jump around):

For each phase:
- **Confirm runtime:** Add up current clip durations. Does this phase eat up roughly the right % of the total time? (See `brief-interpretation.md` runtime allocation.)
  - If phase is too long: trim longest clips or remove redundant clips
  - If phase is too short: did curation miss a clip for this phase? Add back a candidate
- **Align to music structure:** If this phase is "the fall," map its clips to the music's "build" section (rising tension). Trim clip durations to fit the rise.
- **Check cut frequency:** Using the pacing budget from `clip-selection.md`, are shots held roughly as long as they should be for this phase? (Fall phase should have longer holds than triumph phase.)
- **Mark critical cut points:** For every cut, identify whether it's:
  - On-beat (cut happens exactly on a strong musical moment)
  - Anticipatory (cut slightly before a beat)
  - Intentionally off-beat (in the fall, maybe not every cut is on-beat)

Do this phase-by-phase, don't move to the next phase until this one feels right.

### Step 4: Music-sync micro-timing (30 min)
With pacing roughed in, now zoom in and make sure cut points hit moments in the music:

- **Identify the 3–5 most important cuts** in the entire piece (usually: the turning point, the payoff, a major beat in the grind)
- **Snap each of these to a specific musical moment** (a kick drum hit, a vocal entry, a drop)
- For other cuts: approximate alignment to beat or musical phrasing is enough; don't over-engineer every single cut

**Handling sync problems:** If a clip's natural length doesn't fit the music rhythm:
- Option A: Trim clip to fit music (most common)
- Option B: Speed-ramp the clip (slow it down to extend, speed it up to shorten) — see `pacing-rhythm-cuts.md` for when this works
- Option C: Accept that this clip doesn't sync perfectly and use an L-cut or J-cut to de-emphasize the mismatch (overlap audio/video)

### Step 5: VO/commentary layer (if needed) (15–30 min)

If there's voice-over, speech, or commentary:
- Place speech on its own audio track (separate from music)
- Trim speech to remove breaths, pauses, or dead air (unless the pause is intentional)
- Sync speech to a specific video clip if they're meant to together (e.g., a quote over a specific celebration)
- **Music ducks automatically:** Set up mixing so music is –6dB to –12dB while speech plays (see `audio-music.md` for ducking)

### Step 6: Text/graphics layer (if needed) (15–45 min)
- Place title card at cold open
- Place key quote/peak-line text at the turning point or payoff (see `graphics-typography.md` once it exists)
- Place credits/coda text if applicable
- Confirm text doesn't overlap video action (read `graphics-typography.md` safe zones)

### Step 7: Transitions & effects review (10–20 min)
- Go through the timeline chronologically
- For each cut, confirm it's the intended type:
  - Default hard cut, or
  - J/L-cut (audio lead), or
  - Dissolve (if bridging aspect ratios or time jump), or
  - Speed ramp (if intentional, and only 1–2 max per piece)
- Confirm no over-use of fancy transitions (see `pacing-rhythm-cuts.md` for overuse risk)

### Step 8: Audio-mixing pass (20 min)
- Listen to the full mix with headphones or good speakers
- Check: is speech always audible over music?
- Check: are key sound effects (whistle, impact, goal) hearing clearly?
- Check: does the overall mix feel balanced (no sudden loud jump, no phase where everything is muffled)?
- Check: music volume is consistent throughout (no random swells)
- Note any fixes needed; don't re-mix everything here, just flag

### Step 9: Full playthrough critique (watch once, no notes)
- Play the full timeline on your target device (phone, not just desktop monitor)
- Watch once without stopping
- Does it feel like a story, or a collection of clips?
- Does the emotional arc land (does it make you feel what it was supposed to)?
- Any technical glitches (sync drift, audio pops, visual artifacts)?
- Jot down observations, don't pause to fix yet

### Step 10: Refinement round (30–60 min)
- Go back to timeline with your notes
- Make surgical adjustments:
  - Trim clips that are running long
  - Swap a weak clip if a better candidate exists
  - Move a clip that's out of place
  - Adjust audio levels
  - Fix any sync issues
  - But don't restructure the whole piece — you're refining, not re-cutting

## Practical workflow for Hermes/OpenMontage

- **Naming:** Every clip in the timeline should be named by arc phase (`Cold_Open_1`, `Fall_2`, `Triumph_A`, etc.) so you can quickly identify/swap without scrubbing
- **Layering:** Keep video and audio on separate tracks even if they move together; easier to adjust sync if they're not locked
- **Handles:** Trim clips to your required cut-points, but preserve 2–5 seconds of footage before/after each cut-point (handles) in case you need to micro-adjust without re-importing the source

## Common assembly mistakes to avoid

1. **Placing too many clips at once** — don't dump all 20 clips in the timeline and then figure out timing. Go phase-by-phase.

2. **Finalizing sync before pacing is right** — sync is the last thing to lock, not the first. Rough pacing first, then precise timing.

3. **Ignoring music structure** — if music has a specific build/peak shape, your timeline should *visibly* escalate in sync with it. If they're out of sync, audience feels it.

4. **Letting "cool" footage stay in even though it doesn't serve the story** — good-looking clip that doesn't fit is still a distraction. Cut it.

5. **Over-complicating transitions** — hard cuts are not boring if they're well-timed. Most cuts should be hard cuts.

6. **Not watching on target device** — editing on a big monitor and the piece looks terrible on a phone? That's a common disaster. Watch on phone partway through assembly.

## Reasoning checklist for this stage

- [ ] Have I locked music first or am I building cuts-first because music isn't decided yet?
- [ ] Are clips arranged in correct arc-phase order?
- [ ] Does each arc phase occupy roughly the right % of runtime?
- [ ] Are most shots trimmed to reasonable lengths for their phase (per clip-selection.md budgets)?
- [ ] Are the 3–5 most important cuts aligned to music peaks/beats?
- [ ] Is VO/commentary on its own track separate from music?
- [ ] Have I watched the full timeline on the target device (not just monitor)?
- [ ] Are there any clips in the timeline that don't serve the story (candidates for removal)?
