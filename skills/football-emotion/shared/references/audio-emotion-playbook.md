# Audio & Music Emotion Playbook (shared reference)

Used by: football-audio-music-director, football-commentary-ducking-mixer,
football-audio-quality-control, openmontage-audio-operation-mapper.

Source: consolidated from source pack files `05_audio_music_emotion_playbook_source.md` and
`10_audio_music_selection_and_usage_skill_source.md`. The 255-entry asset catalog lives in
`football-music-library-selector/references/music-sfx-catalog.md`, not here — this file is rules,
not assets.

## Core audio hierarchy (apply in this order unless the story structure says otherwise)

1. **Real commentary** — when the live call already explains why the moment matters
2. **Crowd/stadium audio** — when atmosphere carries national pressure or celebration
3. **Silence / near-silence** — before penalties, after misses, after whistle heartbreak, on crying faces
4. **Narration** — context, transitions, meaning
5. **Music** — emotional glue, buildup, release
6. **SFX** — only to clarify a transition/impact, never to decorate every cut

Music supports emotion. It must never flatten or bury real emotion.

## Music types → when to use, when to drop

| Type | Best for | Start | Drop/remove |
|---|---|---|---|
| Sad piano | heartbreak aftermath, crying player, final walk, lonely defeat | after the decisive loss / during reflective flashback | during raw commentary/crowd/silence beat |
| Cinematic rise | buildup, pre-match pressure, legacy journey | after context is established | at the decisive moment, before commentary dominates |
| Epic orchestral | trophy lift, victory release, national celebration | only once the story has earned triumph | briefly around the peak, then out |
| Dark ambient | pressure, fear of elimination, humiliation buildup | — | when hope or action begins |
| Heartbeat tension | penalty shootouts, final seconds, walkups, VAR waits | — | immediately after impact |
| Motivational buildup | training/preparation, comeback energy | — | avoid generic gym-motivation feel for serious World Cup stories |
| Silence | before penalty, after shocking miss, crying face, whistle devastation, trophy awe | — | 1–5s depending on scene strength; it's an edit decision, not an absence of work |
| Crowd-only | national celebration, stadium pressure, whistle release, anthem | — | keep authentic; never drown it under music |

## Story-stage audio map (8–12 min target)

| Time | Audio goal | Recommended |
|---|---|---|
| 0:00–0:20 | hook emotion | commentary scream, silence, or one sad/epic cue |
| 0:20–1:30 | context clarity | narration + low music |
| 1:30–4:00 | pressure | dark ambient/cinematic rise + crowd/commentary moments |
| 4:00–7:30 | conflict/reversal | music dips, silence cuts, commentary spikes |
| 7:30–10:30 | climax | commentary/crowd/silence dominate; music supports only |
| 10:30–12:00 | meaning | sad piano, soft orchestral, crowd-only, narrator close |

## Commentary / music / silence priority rules

**Commentary must dominate when:** the line is iconic ("Agueroooo!", "They've done it!"), the moment
is decisive (goal/save/whistle), it's a player speech, or the words ARE the story.

**Music must dominate when:** buildup with no specific match audio, montages of multiple moments,
emotional cooldown/legacy sequences, training/behind-the-scenes footage.

**Silence must dominate when:** before decisive moments, after devastating moments, during raw
reactions (crying/shock), when ambient audio alone tells the story.

**Crowd must dominate when:** authentic celebrations, national anthem moments, street celebrations,
any moment where crowd energy IS the emotion.

## Ducking defaults

```yaml
audio_ducking:
  commentary_priority_segment: {music_volume: low, sfx: minimal}
  narrator_segment: {music_volume: low_to_medium, crowd_volume: low_if_distracting}
  silent_emotion_segment: {music_volume: zero_or_very_low, sfx: none}
  celebration_segment: {crowd_volume: high, music_volume: medium_or_rising}
```

## Mixing defaults (targets, not automated — see football-audio-quality-control for the manual checklist)

- Master target: -14 LUFS integrated, -1.0 dBTP true peak, 8–12 LU loudness range (YouTube standard for emotional content)
- Music (primary): -16 LUFS, ducks -6dB on commentary peak
- Music (under commentary): -24 LUFS
- Commentary: -16 LUFS, ducks -12dB when crowd roars
- Crowd: -12 LUFS, no ducking — let it breathe
- SFX: -14 LUFS, ducks -3dB on music peak
- Crossfades: music→music 0.5s equal-power; music→silence 0.3s linear; silence→music 1.0s slow exponential

## SFX placement — sparing, with hard caps

| SFX | Use | Max per video |
|---|---|---|
| Bass hit | decisive goal, scoreboard reveal, shock cut | 3 |
| Whoosh | quick flashback/fast montage transitions | use rarely, never every cut |
| Heartbeat | penalties, final pressure, tunnel-walk tension | keep short — long segments become annoying |
| Crowd roar boost | goal release, whistle, national celebration | boost real crowd audio rather than add fake |
| Camera shutter | legacy/photo-memory, newspaper/social inserts | avoid in serious tragedy unless stylized as media pressure |
| Impact hit | goal/miss/save impact, red card/shock reveal | not every cut |
| Silence cut | sudden emotional stop, missed penalty, whistle heartbreak | one of the most powerful tools — use sparingly |
| Commentator echo | famous short phrase, memory/flashback | not long commentary sections, no fake drama |

## Narrator voiceover rules

Good: explain stakes, connect flashbacks, add meaning after a raw clip, set up why a moment matters.
Bad: explain obvious visuals, speak over emotional commentary, motivational clichés, presenting
unverified facts as true.

## Top audio failure modes (check against these before finalizing any audio plan)

1. Music drowns commentary — can the viewer hear the words? If not, music is too loud.
2. Music doesn't match the emotional beat (sad piano during celebration = dissonance).
3. Overusing one music type (three sad-piano sections in one video feels repetitive).
4. Silence used on a minor moment — kills momentum; reserve for genuinely decisive moments.
5. SFX overuse (bass hit on every goal is annoying — respect the max-per-video caps above).
6. Ignoring bad source audio quality (distorted commentary/clipped crowd can't be fixed in mixing — flag and reject the clip instead).
7. Content-ID risk from unverified "royalty-free" tracks — always route through the license checker.
8. Front-loading all emotional music in the first two minutes, then flat — spread emotional peaks.
9. Abrupt audio cuts at the end — always fade out (minimum 0.5s).
10. Replacing authentic crowd reactions with generic music — crowd audio is more authentic; don't substitute it away.
