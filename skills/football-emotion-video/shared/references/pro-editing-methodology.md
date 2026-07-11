# Professional Editing Methodology (shared reference)

Used by: football-pro-cutting-pacing, openmontage-edit-planning, football-caption-thumbnail-direction.

Source: consolidated from source pack file `04_pro_editing_methodology_source.md`.

## Editing decision hierarchy (apply in this order for every decision)

1. Emotional purpose
2. Story role
3. Clip clarity
4. Audio priority
5. Pacing
6. Effect/caption treatment

If an effect doesn't improve emotion or clarity, don't use it.

## Cutting techniques

| Technique | Use for | Typical duration | Rule |
|---|---|---|---|
| Fast cuts | buildup montages, skill/energy sequences, comeback acceleration | 0.4–1.2s/shot | Cut on strong beats, not every beat. Never fast-cut crying faces, penalty pauses, trophy emotion, final-walk moments. |
| Hold shots | crying faces, silent pressure, penalty walkup, whistle aftermath, trophy lift, stunned crowd | 2.5–6s+ | Hold longer than instinct on genuine emotion. Keep audio clean. Don't add unneeded zoom/shake. |
| Cut on beat | motivational buildup, action montage, skill-as-proof, crowd celebration | — | Strong beat = cut; music rise = tighter sequence; music drop = decisive reveal. Vary rhythm — don't become mechanical. |
| Cut to reaction | after goal/miss/save/red card/whistle/trophy/commentator shock | reaction within 1–3s | Player reaction first, then crowd/team. For shock moments, reaction may precede replay to build curiosity. |
| Repeat a moment | only for genuinely iconic moments | — | Structure: real-time action → immediate reaction → slow-motion/zoomed detail → aftermath. Repeating ordinary goals is filler. |

## Pacing by section

- **Hook (0:00–0:20):** emotional proof immediately, minimal context, no logo intro, one strong question/promise.
- **Setup (0:20–1:30):** stakes fast, flashbacks only if needed, simple narration, don't overload dates/stats.
- **Pressure (1:30–5:00):** slow down before decisive actions, close-ups + crowd tension, alternate action/reaction, music lower than commentary when commentary matters.
- **Climax (5:00–9:30):** let the decisive moment breathe, silence/commentary can dominate over music, cut to reactions after impact, don't stack multiple effects.
- **Cooldown (last 60–150s):** longer shots, lower music intensity, aftermath/meaning, end on a human image or sentence — not random celebration.

## Transitions

| Transition | Best use | Avoid when |
|---|---|---|
| Hard cut | most action/reaction (default) | — |
| Flash cut | memory fragments, shock, quick pressure | used every few seconds |
| Cross dissolve | flashback, reflection, cooldown | high-energy action |
| Match cut | connecting similar gestures/trophies/faces across eras | forced/unclear match |
| Whip transition | hype/modern montage | serious heartbreak |
| Fade to black | ending, reset, tragedy beat | every section change |
| Silence cut | before impact, after shock | random style decoration (it's an audio decision, not a visual gimmick) |

## Visual effects — assign by scene type, not by taste

```yaml
effect_policy:
  crying_face: minimal_zoom_or_none
  penalty_walkup: no_flashy_effects
  goal_impact: impact_zoom_optional
  flashback: black_white_or_lower_saturation_optional
  trophy_lift: slow_motion_optional
  skill_dribble: speed_ramp_optional
  national_crowd: wide_shot_hold_or_slow_push
```
Every effect used outside this table needs a stated reason tied to emotional purpose — an
unmotivated effect is a QC finding.

## Caption style

- Emotional captions (hooks/turning points/meaning lines): 2–8 words, don't explain the obvious, no unsupported clickbait.
- Commentary captions: only the important words, one emphasis at a time, kept clear of face/ball.
- Quote captions: short, high contrast, no clutter.
- Default to minimal text; heavy captions are for tactical/analytical explanation only, never during raw emotional moments.
- Fonts: clean bold sans-serif, large, high contrast, subtle shadow/stroke. Avoid multiple fonts, neon styles, meme captions in serious scenes, long paragraphs.

## Thumbnail frame logic

Ranked frame types: (1) emotional face + clear context, (2) player vs trophy/scoreboard contrast,
(3) crying player + short text, (4) iconic action frozen at peak, (5) crowd/national emotion.

```yaml
thumbnail_score_10:
  face_emotion: 0-2
  story_clarity: 0-2
  contrast_readability: 0-2
  curiosity: 0-2
  low_clutter: 0-1
  non_misleading: 0-1
```
Text: 2–4 words (`LAST CHANCE`, `HE BROKE`, `ONE KICK`, `IMPOSSIBLE`, `THE BURDEN`, `FINAL TEARS`).
Never let text cover a face; never claim something the footage doesn't support.

## Story-type editing recipes (quick reference)

- **Comeback:** hook with pain → doubt/pressure → increasing pace → first hope → climax with comeback → close with legacy/meaning.
- **Heartbreak:** hook with aftermath/crying/silence → flashback to hope → build final chance → decisive loss/failure → hold aftermath → close respectfully.
- **Legacy:** hook with trophy/final face → flashback to early burden → repeated setbacks → final proof → symbolic legacy close.
- **Underdog:** hook with impossible result/crowd reaction → opponent dominance → underdog suffering/belief → climax upset → collective celebration close.
- **Rivalry/revenge:** hook with conflict → humiliation/doubt → response build → decisive answer → opponent/fan reaction close.

## Pre-finalization quality checklist

- Does the hook show emotion within 5–10 seconds?
- Does every major action have a reaction?
- Are emotional moments allowed to breathe?
- Is music lower than commentary when commentary matters?
- Are effects scene-motivated (per the table above)?
- Are captions short and useful?
- Is the ending meaningful?
- Does the video avoid a reused-content/compilation feel?
