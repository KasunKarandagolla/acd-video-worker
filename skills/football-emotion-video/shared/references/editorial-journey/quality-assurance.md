# Quality Assurance & Self-Review

Read this in Stage 10, after assembly is complete (Stage 8) and before export/optimization. This stage catches errors and validates that the piece works before leaving the edit suite.

## The QA mindset

QA is not "does this look good?" — that's subjective. QA is "are there any technical or editorial errors that will break the piece on the target platform?"

This is a critical stage because problems caught here are free to fix. Problems found after export are expensive (re-export, re-upload, lost engagement time).

## Before you QA: confirmation checklist

Confirm these are true *before* starting QA:
- [ ] The entire timeline has been watched from start to finish at least once
- [ ] All clips are labeled/identified (you can name what's playing at any timestamp)
- [ ] Audio mixing (speech/music/effects) has been done
- [ ] Text/graphics have been placed (if applicable)
- [ ] Color correction has been done (if applicable)
- [ ] Effects/transitions have been finalized

If any of these are incomplete, finish them first. QA assumes the edit is "done," not "in progress."

## Part 1: Technical QA (watch on phone, with specific goals)

Go through the piece on your target device (the phone/screen where it will actually be watched), playing full-speed, watching for specific technical failures:

### Audio layer checks
**Goal:** No audio glitches, sync issues, or unintelligible moments

- [ ] Listen with headphones or good speakers (phone speaker can hide issues)
- [ ] Speech is always intelligible (not buried under music/SFX)
- [ ] No pops, clicks, or dropout in audio
- [ ] Audio doesn't cut off abruptly at start/end (should fade in/out smoothly)
- [ ] Music volume is consistent (no random loud swells or dips)
- [ ] Sync drifts: does a speaker's mouth move match the audio? (Check at least 2–3 cut points)
- [ ] No echo or reverb artifacts (speech shouldn't sound like it's in a bathroom)

**Common failures:**
- Speech placed with slight delay from its video (the mouth moves before or after the sound)
- Music ducks but never comes back up (stuck low)
- Abrupt silence between clips instead of smooth transition

### Video layer checks
**Goal:** No visual glitches, continuity breaks, or unwatchable clips

- [ ] Every clip plays (no broken/missing media alerts)
- [ ] Resolution acceptable for platform (no severely pixelated/blurry stretches)
- [ ] No obvious jumps or discontinuities in color between shots (yes, subtle differences are OK, but not extreme)
- [ ] Aspect ratio consistent or intentionally varied (if vertical/horizontal mixed, is it obvious or does it seem like a mistake?)
- [ ] Text readable on a phone screen (not too small, not cut off at edges)
- [ ] Aspect ratio matches platform spec (check Stage 11: Platform Optimization if not confirmed yet)

**Common failures:**
- One clip is very blue (cool) and the next is very orange (warm) — looks wrong
- A shot is so pixelated it's unrecognizable (sourced from low-quality YouTube)
- Text card is partially off-screen or centered in a way that gets cut by the UI bezel
- Video plays at wrong speed (accidentally sped up/slowed down during assembly)

### Timing checks
**Goal:** Piece matches intended runtime, cuts are actually on-beat

- [ ] Total runtime matches target (15s / 30s / 60s / 3min+)
- [ ] If a piece should be exactly 30s for platform, is it 29.8–30.2s? (±0.2s is acceptable, anything more is re-export required)
- [ ] Major cuts feel on-beat, not obviously off-beat (watch the first beat-drop, the peak moment, the payoff — do cuts hit these?)
- [ ] No "dead air" (silence or action without music/VO that lasts more than a frame or two, unless intentional per `pacing-rhythm-cuts.md` "breath" rule)

**Common failures:**
- Piece is 31.5s when it needs to be 30s (will be cut off on Reels, get clipped on TikTok)
- A cut happens a half-second after the musical beat, enough to feel noticeably off-time
- There's a 2-second hold on a static shot in the middle of the grind phase with no music/VO (dead air)

## Part 2: Editorial QA (watch a second time, with specific story goals)

Go through the piece *again*, this time focused on whether it works as a story:

### Emotional arc checks
**Goal:** The piece takes the viewer on the intended emotional journey

- [ ] Cold open grabs attention (would you keep watching if you saw this at 0–3 seconds?)
- [ ] Setup establishes stakes (by second 5–8, does the viewer understand what matters?)
- [ ] Fall *feels* like a genuine low point (not rushed, not skimmed)
- [ ] Grind escalates (each clip is slightly more intense/closer/bigger than the last, not flat)
- [ ] Turning point is *visibly* the pivot (music/cuts/visuals all shift at the same moment, not staggered)
- [ ] Triumph lands (is this the biggest/loudest/most impactful moment? Or does something else in the piece feel bigger?)
- [ ] Coda provides release (doesn't end on the peak, but on a held moment after)

**If any of these fail:** Note which phase is weak and consider a re-cut

### Story clarity checks
**Goal:** A first-time viewer understands what's happening without captions

- [ ] By 5 seconds, is it obvious *what* this piece is about (football/motivational/comeback)?
- [ ] By 15 seconds, is it obvious *who* the piece is about (a player, a story, a concept)?
- [ ] At the payoff, is the payoff *visually* clear (not just implied by music or text)?
- [ ] If there's text/VO, is it reinforcing the visuals or competing with them?

**If any fail:** This is usually a curation problem — a stronger clip could clarify, or text placement needs adjustment

### Pacing checks (editorial, not technical)
**Goal:** The piece doesn't feel slow, doesn't feel chaotic

- [ ] Setup and fall have longer holds (breaths), not relentless quick cuts
- [ ] Grind accelerates (cuts get shorter as it progresses) — is this visible?
- [ ] Triumph is the fastest cutting — does it feel more intense than grind?
- [ ] No phase feels dragged out (do you see any clip that makes you think "why is this shot so long?")
- [ ] No phase feels rushed (do you see any part where cuts are so fast you're reading it as chaotic, not exciting?)

**Common failures:**
- The fall holds each shot for 4 seconds, triumph also holds each shot for 4 seconds — feels flat
- The grind has 15 clips cut to 0.5s each for the full phase — feels frantic and hard to follow

### Redundancy checks
**Goal:** No "filler" footage that feels like duplication

- [ ] Are there any back-to-back clips showing the same action from slightly different angles with no narrative purpose? (See `clip-selection.md` for redundancy logic)
- [ ] Are there any "highlight reel" sections where it's just clip, clip, clip with no escalation?

## Part 3: Platform-specific QA (device-dependent, do this if platform is confirmed)

If Stage 11 (Platform Optimization) is already done:

### Mobile vertical (9:16, TikTok/Reels/Shorts)
- [ ] Text readable at small size? (Test: arm's length, phone brightness at 50%)
- [ ] Safe zone respected (important visuals not in the outer 15% of screen edges)
- [ ] No widescreen clips showing so much black pillarbox that they feel unusable?
- [ ] First 1–2 seconds are visually "loud" (bright colors, movement, sharp details)?

### Widescreen horizontal (16:9, YouTube/cinema)
- [ ] Vertical clips don't have excessive pillarbox that makes them look wrong?
- [ ] Titles/graphics positioned so they don't get cut off by OS UI (address bar, notch, etc.)?
- [ ] Subtitle/caption space clear (if captions will be burned in, ensure bottom 15% is visually safe)?

## Part 4: Final checks (spot-check, don't re-watch everything)

- [ ] Export format decided (codec, bitrate, resolution) — see Stage 13 (Export)
- [ ] If multiple aspect ratios exist, have they been tested on each platform they'll be posted to?
- [ ] Do you have a backup of the working timeline file (in case export fails and you need to re-export)?

## The "watch it one more time" rule

After QA passes, watch the piece *one more time* without any specific goal (no checklist, just watching). Does it feel right? If something nags you in that "just watching" pass, go back to QA and hunt for what's wrong.

Professional editors call this the "vibe check." Technical checklists catch mistakes; the vibe check catches things the checklists miss.

## Red flags that require a re-cut, not just a fix

If you find any of these, don't try to band-aid:

- **A clip in the middle of a phase is way weaker than what's around it** (kills the escalation) — swap it for a candidate from curation
- **The fall phase feels rushed** (opposite of the brief's intent) — extend it or add a clip
- **The turning point is unclear** (is this moment supposed to be THE PIVOT or not?) — either make it more obvious or move it
- **The payoff doesn't land** (doesn't feel as big as the buildup promised) — either use a different clip for payoff or rebuild the setup
- **The piece is significantly off-target runtime** (not 29.8–30.2s when it needs to be 30s, for example) — reshuffling won't fix, need to trim/extend phases

These are editorial problems, not QA problems. Go back to Stage 8 (Assembly) or Stage 4 (Sequencing).

## Reasoning checklist for this stage

**Before QA:**
- [ ] Is the timeline considered "done" (assembly, color, effects all complete)?

**Technical QA:**
- [ ] Audio: no glitches, speech intelligible, music consistent, sync correct?
- [ ] Video: no broken clips, resolution acceptable, colors don't jump drastically?
- [ ] Timing: runtime target met, major cuts on-beat?

**Editorial QA:**
- [ ] Emotional arc: cold open → setup → fall → grind → turning point → triumph → coda?
- [ ] Story clarity: does first-time viewer understand what/who in first 15 sec?
- [ ] Pacing: setup/fall slower, grind accelerating, triumph fastest?
- [ ] Redundancy: any filler clips that could be cut?

**Platform QA (if confirmed):**
- [ ] Text readable on device?
- [ ] Safe zones respected?
- [ ] Aspect ratio appropriate for platform?

**Final gate:** Does it pass the vibe check? (Watch once without checklist.)

## V5 addition — scalable runtime tolerance and export gate

For runtime targets, use:

```text
allowed_runtime_drift = max(0.2 seconds, target_runtime_seconds * 0.005)
```

For hard platform limits, the platform limit overrides this editorial tolerance.

Before final delivery, Stage 13 Export is now defined by `shared/references/platform-export-optimization.md` and executed by `football-platform-export-validator`.
