# Visual Cohesion & Matching Sourced Footage

Read this in Stage 6, after sequencing (Stage 4) is locked. This stage handles the fact that sourced footage comes from different cameras, broadcasters, and eras and needs to feel intentional rather than mismatched.

## The visual cohesion problem

Sourced footage from YouTube/archives is inherently mismatched:
- Different broadcasters (ESPN vs. stadium feed vs. raw phone video)
- Different eras (archived 2015 footage vs. recent 2024 broadcast)
- Different color grades (warm, cool, flat, contrasty)
- Different aspect ratios (16:9, 9:16, 4:3)
- Different resolutions (4K → 480p all mixed)

Your job is not to make everything look identical (impossible and would be boring). Your job is to make the *choices* intentional so mismatches read as stylistic decisions, not mistakes.

## Three tiers of visual treatment (choose one per piece)

### Tier 1: Documentary / Archive aesthetic
**Intent:** Mismatch is *part* of the story — footage is valued for authenticity, not polish

**When to use:** Historical comeback stories, "written off by everyone" narratives where the raggedness of archived footage underscores the authenticity

**Approach:**
- Lean into color/quality differences as time markers (old footage is cooler/grainier, recent footage is warmer/sharper)
- Don't color-correct across timeline, let eras look different
- Mismatched aspect ratios become chapter breaks (vertical phones → horizontal broadcast → close-up cutaway)
- Use B&W or desaturated sections of low-quality footage to stylize rather than hide

**Risks:** Can read as amateurish if not intentional; requires confident editing to pull off

### Tier 2: Stylized / Color-coded unity
**Intent:** Each arc phase has a consistent color grade that ties it together, even if individual clips come from different sources

**When to use:** Most social content — you want polish without looking generic

**Approach:**
- Pick a LUT (look-up table) or grade for each arc phase (cool/desaturated for the fall, warm/saturated for triumph)
- Apply uniformly to all clips in that phase, regardless of source
- Aspect ratio mismatches are hidden via centering/cropping or treated as intentional chapter breaks (transition via freeze frame or text card when switching aspect ratio)
- Speed ramps or dissolves can bridge clips when quality jump is too jarring

**Risks:** Can look over-processed if the grade is too strong

### Tier 3: Transparent / Seamless unity
**Intent:** Footage looks like it all came from one shoot, or at least one aesthetic

**When to use:** Rarely achievable with sourced footage, but possible when sourcing from a single broadcaster or archive (e.g., all clips from the same match)

**Approach:**
- Aggressive color correction to match skin tones and whites across all clips
- Consistent exposure (brightness, contrast)
- Match motion blur / frame rate where possible (24p vs 60p footage noticeable on cuts; slow-motion can hide this)
- Cut on action to hide resolution/quality jumps (see `pacing-rhythm-cuts.md`)
- Avoid aspect ratio mismatch entirely if possible

**Risks:** Time-intensive; rarely possible with truly diverse sourcing

## Aspect ratio decisions

Aspect ratio choices gate platform optimization (Stage 11) but *should* be decided here based on sourced material:

**If sourced footage is mixed aspect ratios:**

Option A: Crop everything to a single format (e.g., center-crop all widescreen to 9:16 for TikTok)
- Fastest, but loses information
- Use if you have surplus wide shots

Option B: Embrace the mismatch intentionally
- Vertical phone footage in the fall (intimacy), widescreen broadcast in triumph (scale)
- Requires text cards or graphics to bridge aspect-ratio cuts (visual chapter break)
- More intentional, less "mistake-like"

Option C: Pillarbox or letterbox mismatched footage
- Visible bars (black letterbox on vertical, pillarbox on horizontal)
- Acceptable for archival/documentary tier
- Rarely used in polished social content

**Recommendation:** Plan aspect ratio in Stage 1 (brief intake) and source accordingly. Decide here if the actual sourced footage forces a compromise.

## Matching strategies by clip type

### Matching action shots (goal, moment, climax)
- **Priority:** Cut on action hides mismatches (motion blur conceals resolution jump)
- **Matching goal:** Skin tone consistency (faces are the first thing the eye corrects for)
- **Acceptable mismatch:** Resolution (as long as not extreme), slight exposure difference
- **Unacceptable mismatch:** Aspect ratio (if the goal is the peak moment, don't crop it away)

### Matching reaction shots (faces, crowd, celebration)
- **Priority:** Skin tone match is critical (close-ups of faces are unforgiving)
- **Matching goal:** Consistent exposure (brightness), white balance (warmth)
- **Acceptable mismatch:** Slight framerate difference, some compression artifacts
- **Unacceptable mismatch:** One shot is very blown-out (overexposed) and the next is dark — correction is obvious and jarring

### Matching crowd / wide shots
- **Priority:** Aspect ratio (crowd shots are wide and aspect-ratio mismatch is very visible here)
- **Matching goal:** Color temp (overall warmth/coolness)
- **Acceptable mismatch:** Resolution, some quality jump
- **Unacceptable mismatch:** Drastic color shift (one shot is very cool, next is very warm)

### Matching VO/speech over b-roll
- **Priority:** Audio is locked, visuals serve it; aspect ratio and color matching are secondary
- **Acceptable mismatch:** Almost anything, since audio attention pulls focus
- **Strategy:** This is where "Tier 2 — color-coded phases" works best (VO is same audio layer, but color/grade changes with emotion)

## Practical grading approach (non-technical shorthand)

Most editors don't need to be colorists. If you're not doing professional color correction:

1. **White balance:** Are the whites in the shot neutral, or do they look yellow/blue/orange? Correcting white balance first is half the battle. Most NLE (editing software) has a "white balance" eyedropper.

2. **Exposure:** Is this shot brighter or darker than the one before? A 10–15% exposure adjustment often feels natural; bigger jumps are noticeable.

3. **Contrast:** Is this shot flat (low contrast, dull) or punchy (high contrast, vivid)? Flat clips can be selectively boosted.

4. **Saturation:** Is one shot's colors much more vibrant than another? Selective desaturation of overly vibrant shots can help unity.

5. **LUT/grade:** If multiple shots are from vastly different sources (e.g., 2010 archive vs 2024 broadcast), applying a single LUT/filter over all of them can unify even if it's not a perfect match to either source.

**Rule of thumb:** If you can identify what's *different* about a shot's look, you can make a small adjustment that will feel more intentional.

## When to accept (or lean into) mismatch

Not every mismatch needs fixing. Accept it if:

- **It serves the story:** Old footage in the fall, modern footage in triumph. Mismatch is *time*.
- **It's subtle:** A small white balance difference that the eye doesn't catch consciously.
- **The cut on action hides it:** Motion blur during the cut conceals the jump.
- **It's at a chapter break:** A text card or graphics transition gives permission for a visual reset.

Don't try to fix every tiny thing — that's how edits look over-processed and fake.

## Practical constraint: archive footage

Archive footage (pre-2000s) is often heavily compressed, grainy, or color-shifted by storage/transfer. For these:

- Embrace the graininess (don't try to denoise, it'll look processed)
- Desaturate slightly to make color shift less obvious
- Use speed ramps or slow-motion to make the graininess feel intentional ("vintage" look)
- Treat as Tier 1 (documentary aesthetic)

## Reasoning checklist for this stage

- [ ] Have I chosen a visual cohesion tier (archive/stylized/seamless)?
- [ ] Have I decided on target aspect ratio(s)?
- [ ] For action shots, am I cutting on action to hide resolution jumps?
- [ ] For reaction/close-up shots, have I white-balanced for skin tone consistency?
- [ ] For wide/crowd shots, is color temperature consistent?
- [ ] Have I identified any mismatches that actively harm the piece (vs. those that just exist)?
- [ ] Are my corrections intentional, not just "trying to fix everything"?

## V5 addition — HDR and broadcast overlay checks

Before applying creative LUTs, check `video_color_metadata` from `shared/references/hdr-sdr-handling.md`.

Before placing text or cropping, check `broadcast_overlay_map` from `shared/references/broadcast-overlay-map.md`.
