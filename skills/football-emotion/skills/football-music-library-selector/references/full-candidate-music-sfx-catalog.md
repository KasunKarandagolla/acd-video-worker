# Full Candidate Music/SFX Catalog — Verification Required

This file imports the full ChatGPT + Kimi integrated music/SFX catalog into Claude's cleaner skill architecture.

**Status:** candidate reference library only. Nothing in this file is automatically cleared for use.

Runtime rule:

```text
Candidate asset -> exact source page -> strict license verification -> attribution text -> local cache -> OpenMontage use
```

Every selected row must pass `football-rights-safe-audio-license-checker` before it can appear in an `audio_plan` or OpenMontage operation. Rows that are search/category links, generic YouTube Audio Library links, Freesound pages, or ⚠️ BreakingCopyright-style/reupload references require extra scrutiny and must not be treated as verified.

---

# 11 — Music Library Selector Skill Source

## Integration status
This is the final integrated source for the future `football-music-library-selector` skill. It uses Kimi's larger catalog because it has named tracks/categories and 255 numbered candidates. It also applies our stricter verification policy.

## Non-negotiable safety correction
Do **not** treat this library as automatically cleared music. Treat it as a ranked candidate catalog. The skill may suggest assets, but only `rights-safe-audio-license-checker` may approve them for use.

There are 15 higher-risk ⚠️ entries in Kimi's version. Those are kept for research value but must not be used until the exact original source and license are verified.


# Verification-first policy added after Kimi integration

Kimi's pack is useful because it adds named tracks, categories, source links, and 255 candidate entries. However, the final skill must treat this as a **candidate catalog**, not a legal whitelist. Reasons:

- Many entries link to source search/category pages, not exact downloadable asset pages.
- YouTube Audio Library links are usually generic and require checking the track inside YouTube Studio.
- Freesound licenses vary per upload.
- BreakingCopyright-style YouTube repost links must be treated as **caution** until the original creator/source license is found.
- Final output must store `checked_date`, `exact_asset_url`, `license_type`, `creator`, and `attribution_text` before OpenMontage uses the asset.

The safe runtime rule is:

```text
Candidate asset -> exact source page -> license verification -> attribution text -> local cache -> OpenMontage use
```



---

# 11_music_library_skill_source.md

# Skill Source: Music Library Selector (`music_library_selector`)

## Purpose
Provide a curated, rights-safe music and SFX library for football emotional storytelling videos. Provide a curated candidate library from rights-safe source families for football emotional storytelling videos. Entries are NOT final legal approvals. Every chosen asset must be verified on its exact source page before use, especially if the row is a search/category link rather than a direct asset page.

## Activation Triggers
- When `audio_music_director` needs asset recommendations
- When user says: "find music for heartbreak," "what SFX for goals," "music library for football videos"
- When building a local music library for OpenMontage pipeline
- When verifying license status of any audio asset

## Inputs
- `emotion_type`: Target emotion (sad_piano, epic_orchestral, etc.)
- `duration_needed`: Approximate duration needed in seconds
- `attribution_preference`: "none", "minimal", "acceptable"
- `platform`: "youtube", "multi_platform", "commercial"

## Outputs
- `asset_recommendations.json`: Ranked list of matching assets
- `license_verification_checklist.md`: Per-asset license status
- `attribution_text.txt`: Ready-to-paste attribution strings

---

## License Legend

| Code | Meaning | Attribution Required | Commercial Use | YouTube Safe |
|---|---|---|---|---|
| **PD** | Public Domain | No | Yes | Yes |
| **CC0** | Creative Commons Zero | No | Yes | Yes |
| **CC-BY** | Attribution Required | Yes | Usually yes | Only if attribution is correct and source is exact |
| **Pixabay** | Pixabay Content License | Usually no | Usually yes | Likely, after exact asset verification |
| **Mixkit** | Mixkit Free License | Usually no | Usually yes | Likely, after exact asset verification |
| **YAL** | YouTube Audio Library | Varies per track | Usually yes for YouTube | Verify inside YouTube Studio |
| **FMA** | Free Music Archive (varies) | Varies per track | Varies | Check per track |
| **FS-CC** | Freesound Creative Commons | Varies per upload | Varies | Must check exact sound page |
| **⚠️** | Requires final verification | — | — | Must verify before use |

**CRITICAL RULE:** Every asset must be individually verified before use. Rows marked ⚠️ are higher-risk candidates and must not be used until the exact original source/license is found. Search/category links are discovery targets, not license proof.

---

## SAD PIANO (25 entries)

| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 1 | "Growing Up" | Scott Buckley | YouTube Audio Library | 3:42 | YAL | https://www.youtube.com/audiolibrary/music | Heartbreak, career ending |
| 2 | "Undertow" | Scott Buckley | YouTube Audio Library | 4:15 | YAL | https://www.youtube.com/audiolibrary/music | Deep sadness, reflection |
| 3 | "A Kind of Hope" | Scott Buckley | YouTube Audio Library | 3:28 | YAL | https://www.youtube.com/audiolibrary/music | Melancholic hope, bittersweet |
| 4 | "Touch" | Mattia Cupelli | FreePD / Gumroad | 3:22 | ⚠️ CC-BY (verify current) | https://mattiacupelli.bandcamp.com/ | Player crying, devastation |
| 5 | "Heartbreaking" | Kevin MacLeod | Incompetech | 2:30 | CC-BY | https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100208 | Disappointment, loss |
| 6 | "Cryptic Sorrow" | Kevin MacLeod | Incompetech | 2:45 | CC-BY | https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100276 | Sad solo piano, reality feel |
| 7 | "Disquiet" | Kevin MacLeod | Incompetech | 3:10 | CC-BY | https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1500036 | Unease, tension |
| 8 | "Memories" | NickOST | Pixabay Music | 2:50 | Pixabay | https://pixabay.com/music/search/memories/ | Nostalgia, retirement |
| 9 | "Stillstand" | Myuu | YouTube (BreakingCopyright) | 3:00 | ⚠️ CC-BY (verify) | https://www.youtube.com/watch?v= (search "Myuu Stillstand") | Sad piano, isolation |
| 10 | "DISINTEGRATING" | Myuu | YouTube (BreakingCopyright) | 2:40 | ⚠️ CC-BY (verify) | https://www.youtube.com/watch?v= (search "Myuu DISINTEGRATING") | Somber, collapse |
| 11 | "BITTERSWEET" | PunchDeck | YouTube (BreakingCopyright) | 3:15 | ⚠️ CC-BY (verify) | https://www.youtube.com/watch?v= (search "PunchDeck BITTERSWEET") | Mixed emotions |
| 12 | "LIGHTS" | Alex Productions | YouTube (BreakingCopyright) | 3:30 | ⚠️ CC-BY (verify) | https://www.youtube.com/watch?v= (search "Alex Productions LIGHTS") | Emotional background |
| 13 | "FOR THE KING" | SolasComposer | YouTube (BreakingCopyright) | 2:55 | ⚠️ CC-BY (verify) | https://www.youtube.com/watch?v= (search "SolasComposer FOR THE KING") | Sad orchestral |
| 14 | "WHAT HAPPENS WHEN WE DIE" | Savfk Music | YouTube (BreakingCopyright) | 4:00 | ⚠️ CC-BY (verify) | https://www.youtube.com/watch?v= (search "Savfk WHAT HAPPENS") | Soundtrack sadness |
| 15 | "GATEKEEPER" | The Piano Says | YouTube (BreakingCopyright) | 3:10 | ⚠️ CC-BY (verify) | https://www.youtube.com/watch?v= (search "The Piano Says GATEKEEPER") | Piano solo |
| 16 | "COZY PLACE" | Keys Of Moon | YouTube (BreakingCopyright) | 2:45 | ⚠️ CC-BY (verify) | https://www.youtube.com/watch?v= (search "Keys Of Moon COZY PLACE") | Easy listening sadness |
| 17 | "UNCERTAINTY" | Arthur Vyncke | YouTube (BreakingCopyright) | 3:20 | ⚠️ CC-BY (verify) | https://www.youtube.com/watch?v= (search "Arthur Vyncke UNCERTAINTY") | Sad piano, doubt |
| 18 | "GENTLE AND SOFT" | Alex Productions | YouTube (BreakingCopyright) | 2:30 | ⚠️ CC-BY (verify) | https://www.youtube.com/watch?v= (search "Alex Productions GENTLE") | Soft piano |
| 19 | "ICICLES" | The Piano Says | YouTube (BreakingCopyright) | 3:00 | ⚠️ CC-BY (verify) | https://www.youtube.com/watch?v= (search "The Piano Says ICICLES") | Nostalgic piano |
| 20 | "YULETIDE" | The Piano Says | YouTube (BreakingCopyright) | 2:50 | ⚠️ CC-BY (verify) | https://www.youtube.com/watch?v= (search "The Piano Says YULETIDE") | Sentimental piano |
| 21 | "IN MEMORIAM" | Onycs | Pixabay Music | 3:15 | Pixabay | https://pixabay.com/music/search/in%20memoriam/ | Memorial, tribute |
| 22 | "MEMORIAL DAY" | Alex Productions | Pixabay Music | 2:40 | Pixabay | https://pixabay.com/music/search/memorial/ | Funeral, tribute |
| 23 | "ECHOES OF HOME" | Scott Buckley | YouTube Audio Library | 3:45 | YAL | https://www.youtube.com/audiolibrary/music | Nostalgia, homecoming |
| 24 | "THE CHIMES" | Ross Bugden | YouTube (BreakingCopyright) | 3:30 | ⚠️ CC-BY (verify) | https://www.youtube.com/watch?v= (search "Ross Bugden THE CHIMES") | Ambient soft piano |
| 25 | "SOURCE D'AMOUR" | Amarià | YouTube (BreakingCopyright) | 2:55 | ⚠️ CC-BY (verify) | https://www.youtube.com/watch?v= (search "Amarià SOURCE D'AMOUR") | Nostalgic love |

---

## EMOTIONAL CINEMATIC / DOCUMENTARY PIANO (20 entries)

| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 26 | "Awaken" | Alex-Productions | YouTube Audio Library | 3:00 | YAL | https://www.youtube.com/audiolibrary/music | Inspiring cinematic |
| 27 | "A Better Future" | Miguel Johnson | YouTube Audio Library | 3:20 | YAL | https://www.youtube.com/audiolibrary/music | Hopeful documentary |
| 28 | "Illusions" | Keys Of Moon | YouTube Audio Library | 2:50 | YAL | https://www.youtube.com/audiolibrary/music | Emotional calm piano |
| 29 | "Warm Memories" | Keys Of Moon | YouTube Audio Library | 3:10 | YAL | https://www.youtube.com/audiolibrary/music | Emotional inspiring |
| 30 | "Yearning" | Shane Ivers | YouTube Audio Library | 3:00 | YAL | https://www.youtube.com/audiolibrary/music | Sober sad |
| 31 | "fault" | rexlambo | YouTube Audio Library | 2:40 | YAL | https://www.youtube.com/audiolibrary/music | Emotional free |
| 32 | "Instructions For Living A Life" | Savfk Music | YouTube Audio Library | 4:00 | YAL | https://www.youtube.com/audiolibrary/music | Piano instrumental |
| 33 | "BLOOM" | Onycs | Pixabay Music | 3:00 | Pixabay | https://pixabay.com/music/search/bloom/ | Instrumental ambient |
| 34 | "BIEN-AIMÉE" | Arthur-Marie Brillouin | Pixabay Music | 2:45 | Pixabay | https://pixabay.com/music/search/bien-aimee/ | Ambient piano |
| 35 | "WALKING HOME" | Alex Productions | Pixabay Music | 3:10 | Pixabay | https://pixabay.com/music/search/walking%20home/ | Piano reflective |
| 36 | "THE FISHER KING" | Justin Allan Arnold | Pixabay Music | 3:30 | Pixabay | https://pixabay.com/music/search/fisher%20king/ | Melancholic classical |
| 37 | "DEEP DIVE" | The Piano Says | Pixabay Music | 2:50 | Pixabay | https://pixabay.com/music/search/deep%20dive/ | Calm chill |
| 38 | "INCREDULITY" | Scott Buckley | YouTube Audio Library | 3:15 | YAL | https://www.youtube.com/audiolibrary/music | Classical doubt |
| 39 | "LOST" | Johny Grimes | YouTube Audio Library | 2:30 | YAL | https://www.youtube.com/audiolibrary/music | Electronic future garage |
| 40 | "MAGIC VALENTINE'S" | Alex Productions | Pixabay Music | 2:40 | Pixabay | https://pixabay.com/music/search/magic%20valentine/ | Love emotional |
| 41 | "MIDVINTER" | Scott Buckley | YouTube Audio Library | 3:00 | YAL | https://www.youtube.com/audiolibrary/music | Piano Christmas |
| 42 | "MEADOW WALTZ" | Keys Of Moon | Pixabay Music | 2:50 | Pixabay | https://pixabay.com/music/search/meadow%20waltz/ | Waltz classical |
| 43 | "Home" | Neutrin05 | YouTube Audio Library | 3:20 | YAL | https://www.youtube.com/audiolibrary/music | Chill piano electronic |
| 44 | "Emotional Piano Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/emotional%20piano/ | Browse for matches |
| 45 | "Sad Piano Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/sad%20piano/ | Browse for matches |

---

## CINEMATIC RISE / BUILDUP (20 entries)

| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 46 | "Dramatic Glory Full Length" | Sonican | Pixabay Music | 2:30 | Pixabay | https://pixabay.com/music/dramatic-classical-epic-orchestral-dramatic-glory-full-length-377702/ | Epic orchestral dramatic |
| 47 | "Epic Mystery of Tension" | Sonican | Pixabay Music | 2:16 | Pixabay | https://pixabay.com/music/search/epic%20mystery%20of%20tension/ | Orchestral tension |
| 48 | "Epic Drama Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/epic%20drama/ | Browse dramatic builds |
| 49 | "Dramatic Orchestral Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/dramatic%20orchestral/ | Browse orchestral builds |
| 50 | "Epic Orchestral Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/epic%20orchestral/ | Browse epic builds |
| 51 | "Dramatic Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/dramatic/ | Browse dramatic |
| 52 | "Epic Orchestra Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/epic%20orchestra/ | Browse epic orchestra |
| 53 | "Orchestral Tension Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/orchestral%20tension/ | Browse tension |
| 54 | "Cinematic Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/cinematic/ | Browse cinematic |
| 55 | "Dramatic Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/mood/dramatic/ | Browse dramatic |
| 56 | "Exciting Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/mood/exciting/ | Browse exciting |
| 57 | "Film Score Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/film-score/ | Browse film score |
| 58 | "Orchestral Hybrid Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/orchestral-hybrid/ | Browse hybrid orchestral |
| 59 | "Epic Drama Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/epic-drama/ | Browse epic drama |
| 60 | "Drama Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/drama/ | Browse drama |
| 61 | "Carpe Diem" | Kevin MacLeod | Incompetech | 3:00 | CC-BY | https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100306 | Contemporary rise |
| 62 | "Angel Share" | Kevin MacLeod | Incompetech | 2:45 | CC-BY | https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100274 | Dreamy build |
| 63 | "Dreamer" | Kevin MacLeod | Incompetech | 3:10 | CC-BY | https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100290 | Soaring build |
| 64 | "Soaring" | Kevin MacLeod | Incompetech | 2:50 | CC-BY | https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100302 | Ascending build |
| 65 | "Super Power Cool Dude" | Kevin MacLeod | Incompetech | 2:30 | CC-BY | https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100304 | Energetic build |

---

## EPIC ORCHESTRAL / TRIUMPH (20 entries)

| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 66 | "Dramatic Glory Full Length" | Sonican | Pixabay Music | 2:30 | Pixabay | https://pixabay.com/music/dramatic-classical-epic-orchestral-dramatic-glory-full-length-377702/ | Trophy lift, triumph |
| 67 | "Epic Orchestral Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/epic%20orchestral/ | Browse epic triumph |
| 68 | "Epic Drama Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/epic%20drama/ | Browse epic drama |
| 69 | "Epic Powerful Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/epic%20powerful/ | Browse powerful epic |
| 70 | "Epic Trailer Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/epic%20trailer/ | Browse trailer epic |
| 71 | "Epic Battle Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/epic%20battle/ | Browse battle epic |
| 72 | "Dramatic Cinematic Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/dramatic%20cinematic/ | Browse cinematic epic |
| 73 | "Film Score Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/film-score/ | Browse film score triumph |
| 74 | "Exciting Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/mood/exciting/ | Browse exciting triumph |
| 75 | "Cinematic Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/cinematic/ | Browse cinematic |
| 76 | "Orchestral Hybrid Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/orchestral-hybrid/ | Browse hybrid triumph |
| 77 | "Epic Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/epic/ | Browse epic |
| 78 | "Heroic Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/heroic/ | Browse heroic |
| 79 | "Inspiring Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/inspiring/ | Browse inspiring |
| 80 | "Triumphant Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/triumphant/ | Browse triumphant |
| 81 | "Victory Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/victory/ | Browse victory |
| 82 | "Glory Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/glory/ | Browse glory |
| 83 | "Champion Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/champion/ | Browse champion |
| 84 | "Win Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/win/ | Browse win |
| 85 | "Success Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/success/ | Browse success |

---

## DARK AMBIENT / TENSION (15 entries)

| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 86 | "Dark Ambient Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/dark%20ambient/ | Browse dark tension |
| 87 | "Tension Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/tension/ | Browse tension |
| 88 | "Suspense Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/suspense/ | Browse suspense |
| 89 | "Horror Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/horror/ | Browse horror tension |
| 90 | "Dark Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/dark/ | Browse dark |
| 91 | "Tension Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/tension/ | Browse tension |
| 92 | "Ominous Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/ominous/ | Browse ominous |
| 93 | "Thriller Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/thriller/ | Browse thriller |
| 94 | "Suspense Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/suspense/ | Browse suspense |
| 95 | "Eerie Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/eerie/ | Browse eerie |
| 96 | "Creepy Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/creepy/ | Browse creepy |
| 97 | "Dread Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/dread/ | Browse dread |
| 98 | "Foreboding Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/foreboding/ | Browse foreboding |
| 99 | "Menacing Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/menacing/ | Browse menacing |
| 100 | "Unnerving Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/unnerving/ | Browse unnerving |

---

## HEARTBEAT TENSION / PRESSURE (10 entries)

| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 101 | "Heartbeat Sound Effect" | Various | Pixabay SFX | 0:30 | Pixabay | https://pixabay.com/sound-effects/search/heartbeat/ | Penalty tension |
| 102 | "Heartbeat Sound Effect" | Various | Freesound | 0:20 | FS-CC | https://freesound.org/search/?q=heartbeat | Penalty tension |
| 103 | "Heartbeat Sound Effect" | Various | Mixkit SFX | 0:25 | Mixkit | https://mixkit.co/free-sound-effects/heartbeat/ | Penalty tension |
| 104 | "Tension Drone" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/tension%20drone/ | Pressure buildup |
| 105 | "Pressure Music" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/pressure/ | Pressure moments |
| 106 | "Tension Rise" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/tension/ | Tension buildup |
| 107 | "Pressure Build" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/pressure/ | Pressure music |
| 108 | "Nervous Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/nervous/ | Nervous tension |
| 109 | "Anxious Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/anxious/ | Anxious tension |
| 110 | "Stressed Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/stressed/ | Stressed tension |

---

## MOTIVATIONAL BUILD-UP (15 entries)

| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 111 | "Motivational Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/motivational/ | Browse motivational |
| 112 | "Inspiring Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/inspiring/ | Browse inspiring |
| 113 | "Uplifting Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/uplifting/ | Browse uplifting |
| 114 | "Energetic Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/energetic/ | Browse energetic |
| 115 | "Powerful Collection" | Various | Pixabay Music | Various | Pixabay | https://pixabay.com/music/search/powerful/ | Browse powerful |
| 116 | "Action Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/action/ | Browse action |
| 117 | "Chasing Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/chasing/ | Browse chasing |
| 118 | "Driving Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/driving/ | Browse driving |
| 119 | "Energetic Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/energetic/ | Browse energetic |
| 120 | "Gym Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/gym/ | Browse gym/training |
| 121 | "Workout Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/workout/ | Browse workout |
| 122 | "Sports Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/sports/ | Browse sports |
| 123 | "Training Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/training/ | Browse training |
| 124 | "Competition Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/competition/ | Browse competition |
| 125 | "Race Collection" | Various | Mixkit | Various | Mixkit | https://mixkit.co/free-stock-music/tag/race/ | Browse race |

---

## CROWD AMBIENCE / STADIUM SOUNDS (15 entries)

| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 126 | "Crowd Cheering in Stadium" | vishiv | Pixabay SFX | 0:30 | Pixabay | https://pixabay.com/sound-effects/search/stadium/ | Stadium cheer |
| 127 | "Stadium Roar (concert)" | MrMark81 | Pixabay SFX | 0:26 | Pixabay | https://pixabay.com/sound-effects/search/stadium/ | Stadium roar |
| 128 | "Football Crowd Collection" | Various | Pixabay SFX | Various | Pixabay | https://pixabay.com/sound-effects/search/football-crowd/ | Browse football crowds |
| 129 | "Stadium Crowd Collection" | Various | Pixabay SFX | Various | Pixabay | https://pixabay.com/sound-effects/search/stadium/ | Browse stadium |
| 130 | "Crowd Booing" | Various | Pixabay SFX | 0:15 | Pixabay | https://pixabay.com/sound-effects/search/crowd%20boo/ | Crowd disapproval |
| 131 | "Crowd Gasps" | Various | Pixabay SFX | 0:10 | Pixabay | https://pixabay.com/sound-effects/search/crowd%20gasp/ | Shock reactions |
| 132 | "Crowd Applause" | Various | Pixabay SFX | 0:20 | Pixabay | https://pixabay.com/sound-effects/search/crowd%20applause/ | Applause |
| 133 | "Crowd Chanting" | Various | Pixabay SFX | 0:30 | Pixabay | https://pixabay.com/sound-effects/search/crowd%20chant/ | Fan chants |
| 134 | "Stadium Atmosphere" | Various | Pixabay SFX | 1:00 | Pixabay | https://pixabay.com/sound-effects/search/stadium%20atmosphere/ | Pre-match buzz |
| 135 | "Football Whistle" | Various | Pixabay SFX | 0:05 | Pixabay | https://pixabay.com/sound-effects/search/football%20whistle/ | Referee whistle |
| 136 | "Goal Cheer" | Various | Pixabay SFX | 0:15 | Pixabay | https://pixabay.com/sound-effects/search/goal%20cheer/ | Goal celebration |
| 137 | "Crowd Roar" | Various | Freesound | 0:20 | FS-CC | https://freesound.org/search/?q=crowd+roar | Crowd roar |
| 138 | "Stadium Ambience" | Various | Freesound | 1:00 | FS-CC | https://freesound.org/search/?q=stadium+ambience | Stadium ambience |
| 139 | "Football Match Atmosphere" | Various | Freesound | 2:00 | FS-CC | https://freesound.org/search/?q=football+match | Match atmosphere |
| 140 | "Crowd Reaction Collection" | Various | Mixkit SFX | Various | Mixkit | https://mixkit.co/free-sound-effects/crowd/ | Browse crowd reactions |

---

## WHOOSHES / TRANSITIONS (10 entries)

| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 141 | "Whoosh Sound Effect" | Various | Pixabay SFX | 0:20 | Pixabay | https://pixabay.com/sound-effects/search/whoosh/ | Transitions |
| 142 | "Whoosh Sound Effect" | Various | Mixkit SFX | 0:15 | Mixkit | https://mixkit.co/free-sound-effects/whoosh/ | Transitions |
| 143 | "Whoosh Sound Effect" | Various | Freesound | 0:10 | FS-CC | https://freesound.org/search/?q=whoosh | Transitions |
| 144 | "Swoosh Sound Effect" | Various | Pixabay SFX | 0:15 | Pixabay | https://pixabay.com/sound-effects/search/swoosh/ | Fast transitions |
| 145 | "Swipe Sound Effect" | Various | Pixabay SFX | 0:10 | Pixabay | https://pixabay.com/sound-effects/search/swipe/ | Quick cuts |
| 146 | "Transition Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/transition/ | General transitions |
| 147 | "Cinematic Whoosh" | Various | Mixkit SFX | 0:25 | Mixkit | https://mixkit.co/free-sound-effects/cinematic/ | Cinematic transitions |
| 148 | "Fast Whoosh" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/fast/ | Fast cuts |
| 149 | "Air Whoosh" | Various | Mixkit SFX | 0:15 | Mixkit | https://mixkit.co/free-sound-effects/air/ | Air transitions |
| 150 | "Wind Whoosh" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/wind/ | Wind transitions |

---

## IMPACT HITS / BASS HITS (10 entries)

| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 151 | "Bass Hit Sound Effect" | Various | Pixabay SFX | 0:10 | Pixabay | https://pixabay.com/sound-effects/search/bass%20hit/ | Impact moments |
| 152 | "Impact Sound Effect" | Various | Pixabay SFX | 0:10 | Pixabay | https://pixabay.com/sound-effects/search/impact/ | General impacts |
| 153 | "Thud Sound Effect" | Various | Pixabay SFX | 0:10 | Pixabay | https://pixabay.com/sound-effects/search/thud/ | Low impacts |
| 154 | "Bass Hit Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/bass/ | Bass impacts |
| 155 | "Impact Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/impact/ | General impacts |
| 156 | "Thud Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/thud/ | Thud impacts |
| 157 | "Sub Bass Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/sub-bass/ | Sub-bass impacts |
| 158 | "Punch Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/punch/ | Punch impacts |
| 159 | "Kick Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/kick/ | Kick impacts |
| 160 | "Slam Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/slam/ | Slam impacts |

---

## RISERS / BUILD-UPS (10 entries)

| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 161 | "Riser Sound Effect" | Various | Pixabay SFX | 0:20 | Pixabay | https://pixabay.com/sound-effects/search/riser/ | Pre-climax build |
| 162 | "Riser Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/riser/ | Pre-climax build |
| 163 | "Riser Sound Effect" | Various | Freesound | 0:15 | FS-CC | https://freesound.org/search/?q=riser | Pre-climax build |
| 164 | "Build Up Sound Effect" | Various | Pixabay SFX | 0:25 | Pixabay | https://pixabay.com/sound-effects/search/build%20up/ | Build-up |
| 165 | "Crescendo Sound Effect" | Various | Pixabay SFX | 0:20 | Pixabay | https://pixabay.com/sound-effects/search/crescendo/ | Crescendo |
| 166 | "Sweep Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/sweep/ | Sweep build |
| 167 | "Swelling Sound Effect" | Various | Mixkit SFX | 0:25 | Mixkit | https://mixkit.co/free-sound-effects/swelling/ | Swelling build |
| 168 | "Rising Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/rising/ | Rising tension |
| 169 | "Uplifting Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/uplifting/ | Uplifting build |
| 170 | "Intensifying Sound Effect" | Various | Mixkit SFX | 0:25 | Mixkit | https://mixkit.co/free-sound-effects/intensifying/ | Intensifying build |

---

## CAMERA SHUTTER / FREEZE FRAME (5 entries)

| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 171 | "Camera Shutter Sound Effect" | Various | Pixabay SFX | 0:10 | Pixabay | https://pixabay.com/sound-effects/search/camera%20shutter/ | Freeze frames |
| 172 | "Camera Shutter Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/camera/ | Freeze frames |
| 173 | "Camera Shutter Sound Effect" | Various | Freesound | 0:10 | FS-CC | https://freesound.org/search/?q=camera+shutter | Freeze frames |
| 174 | "Shutter Sound Effect" | Various | Pixabay SFX | 0:10 | Pixabay | https://pixabay.com/sound-effects/search/shutter/ | Freeze frames |
| 175 | "Click Sound Effect" | Various | Mixkit SFX | 0:05 | Mixkit | https://mixkit.co/free-sound-effects/click/ | Quick freeze |

---

## SILENCE STRATEGY (5 entries)

| # | Strategy | Description | Football Use | Technical Note |
|---|---|---|---|---|
| 176 | "Pre-penalty silence" | Complete audio cut 2-3s before penalty kick | Penalty shootouts | Must be preceded by audio for contrast |
| 177 | "Post-goal silence" | 1-2s silence after goal before celebration | Goal moments | Lets the moment breathe |
| 178 | "Pre-whistle silence" | 2-3s silence before final whistle | Match endings | Maximum tension |
| 179 | "Post-elimination silence" | 3-5s silence after elimination whistle | Heartbreak moments | Let devastation sink in |
| 180 | "Transition silence" | 0.5-1s silence between major story beats | Story transitions | Clean break between acts |

---

## COMMENTATOR ECHO STYLE (5 entries)

| # | Technique | Description | Football Use | Technical Spec |
|---|---|---|---|---|
| 181 | "Single word echo" | Echo on one iconic word ("GOAL!", "NO!") | Maximum impact moments | 0.5s decay, -16 LUFS |
| 182 | "Phrase echo" | Echo on short phrase ("He's done it!", "Unbelievable!") | Climax commentary | 0.8s decay, -18 LUFS |
| 183 | "Name echo" | Echo on player name ("Messi! Messi! Messi!") | Player-focused moments | 1.0s decay, -20 LUFS |
| 184 | "Reverb tail extension" | Extend natural reverb of commentary | Stadium atmosphere | 2-3s tail, -24 LUFS |
| 185 | "Stutter echo" | Rapid repeat of first syllable ("Ag-Ag-Aguero!") | Maximum excitement | 0.1s intervals, -14 LUFS |

---

## ADDITIONAL SFX CATEGORIES (65 entries)

### Applause & Cheers (10 entries)
| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 186 | "Applause Sound Effect" | Various | Pixabay SFX | 0:20 | Pixabay | https://pixabay.com/sound-effects/search/applause/ | General applause |
| 187 | "Cheering Sound Effect" | Various | Pixabay SFX | 0:20 | Pixabay | https://pixabay.com/sound-effects/search/cheering/ | General cheering |
| 188 | "Clapping Sound Effect" | Various | Pixabay SFX | 0:15 | Pixabay | https://pixabay.com/sound-effects/search/clapping/ | Clapping |
| 189 | "Cheer Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/cheer/ | Cheer |
| 190 | "Applause Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/applause/ | Applause |
| 191 | "Clapping Sound Effect" | Various | Mixkit SFX | 0:15 | Mixkit | https://mixkit.co/free-sound-effects/clapping/ | Clapping |
| 192 | "Crowd Cheer Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/crowd-cheer/ | Crowd cheer |
| 193 | "Stadium Cheer Sound Effect" | Various | Mixkit SFX | 0:25 | Mixkit | https://mixkit.co/free-sound-effects/stadium-cheer/ | Stadium cheer |
| 194 | "Goal Celebration Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/goal-celebration/ | Goal celebration |
| 195 | "Victory Cheer Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/victory-cheer/ | Victory cheer |

### Whistles & Referee (5 entries)
| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 196 | "Whistle Sound Effect" | Various | Pixabay SFX | 0:05 | Pixabay | https://pixabay.com/sound-effects/search/whistle/ | Referee whistle |
| 197 | "Whistle Sound Effect" | Various | Mixkit SFX | 0:05 | Mixkit | https://mixkit.co/free-sound-effects/whistle/ | Referee whistle |
| 198 | "Referee Whistle Sound Effect" | Various | Pixabay SFX | 0:05 | Pixabay | https://pixabay.com/sound-effects/search/referee%20whistle/ | Referee whistle |
| 199 | "Blow Whistle Sound Effect" | Various | Mixkit SFX | 0:05 | Mixkit | https://mixkit.co/free-sound-effects/blow-whistle/ | Blow whistle |
| 200 | "Sports Whistle Sound Effect" | Various | Mixkit SFX | 0:05 | Mixkit | https://mixkit.co/free-sound-effects/sports-whistle/ | Sports whistle |

### Ball Sounds (5 entries)
| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 201 | "Ball Kick Sound Effect" | Various | Pixabay SFX | 0:10 | Pixabay | https://pixabay.com/sound-effects/search/ball%20kick/ | Ball kick |
| 202 | "Ball Bounce Sound Effect" | Various | Pixabay SFX | 0:10 | Pixabay | https://pixabay.com/sound-effects/search/ball%20bounce/ | Ball bounce |
| 203 | "Soccer Ball Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/soccer-ball/ | Soccer ball |
| 204 | "Football Kick Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/football-kick/ | Football kick |
| 205 | "Ball Hit Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/ball-hit/ | Ball hit |

### Cinematic SFX (10 entries)
| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 206 | "Cinematic Sound Effect" | Various | Pixabay SFX | 0:20 | Pixabay | https://pixabay.com/sound-effects/search/cinematic/ | Cinematic moments |
| 207 | "Cinematic Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/cinematic/ | Cinematic moments |
| 208 | "Epic Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/epic/ | Epic moments |
| 209 | "Dramatic Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/dramatic/ | Dramatic moments |
| 210 | "Trailer Sound Effect" | Various | Mixkit SFX | 0:25 | Mixkit | https://mixkit.co/free-sound-effects/trailer/ | Trailer moments |
| 211 | "Blockbuster Sound Effect" | Various | Mixkit SFX | 0:25 | Mixkit | https://mixkit.co/free-sound-effects/blockbuster/ | Blockbuster moments |
| 212 | "Movie Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/movie/ | Movie moments |
| 213 | "Film Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/film/ | Film moments |
| 214 | "Hollywood Sound Effect" | Various | Mixkit SFX | 0:25 | Mixkit | https://mixkit.co/free-sound-effects/hollywood/ | Hollywood moments |
| 215 | "Atmospheric Sound Effect" | Various | Mixkit SFX | 0:30 | Mixkit | https://mixkit.co/free-sound-effects/atmospheric/ | Atmospheric moments |

### Emotional SFX (10 entries)
| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 216 | "Emotional Sound Effect" | Various | Pixabay SFX | 0:20 | Pixabay | https://pixabay.com/sound-effects/search/emotional/ | Emotional moments |
| 217 | "Sad Sound Effect" | Various | Pixabay SFX | 0:20 | Pixabay | https://pixabay.com/sound-effects/search/sad/ | Sad moments |
| 218 | "Emotional Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/emotional/ | Emotional moments |
| 219 | "Sad Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/sad/ | Sad moments |
| 220 | "Melancholy Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/melancholy/ | Melancholy moments |
| 221 | "Somber Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/somber/ | Somber moments |
| 222 | "Heartbreaking Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/heartbreaking/ | Heartbreaking moments |
| 223 | "Tearful Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/tearful/ | Tearful moments |
| 224 | "Sorrow Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/sorrow/ | Sorrow moments |
| 225 | "Grief Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/grief/ | Grief moments |

### Victory SFX (10 entries)
| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 226 | "Victory Sound Effect" | Various | Pixabay SFX | 0:20 | Pixabay | https://pixabay.com/sound-effects/search/victory/ | Victory moments |
| 227 | "Triumph Sound Effect" | Various | Pixabay SFX | 0:20 | Pixabay | https://pixabay.com/sound-effects/search/triumph/ | Triumph moments |
| 228 | "Victory Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/victory/ | Victory moments |
| 229 | "Triumph Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/triumph/ | Triumph moments |
| 230 | "Success Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/success/ | Success moments |
| 231 | "Win Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/win/ | Win moments |
| 232 | "Champion Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/champion/ | Champion moments |
| 233 | "Glory Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/glory/ | Glory moments |
| 234 | "Celebration Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/celebration/ | Celebration moments |
| 235 | "Fanfare Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/fanfare/ | Fanfare moments |

### Tension SFX (10 entries)
| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 236 | "Tension Sound Effect" | Various | Pixabay SFX | 0:20 | Pixabay | https://pixabay.com/sound-effects/search/tension/ | Tension moments |
| 237 | "Suspense Sound Effect" | Various | Pixabay SFX | 0:20 | Pixabay | https://pixabay.com/sound-effects/search/suspense/ | Suspense moments |
| 238 | "Tension Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/tension/ | Tension moments |
| 239 | "Suspense Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/suspense/ | Suspense moments |
| 240 | "Dramatic Tension Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/dramatic-tension/ | Dramatic tension |
| 241 | "Nervous Tension Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/nervous-tension/ | Nervous tension |
| 242 | "Intense Tension Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/intense-tension/ | Intense tension |
| 243 | "Pressure Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/pressure/ | Pressure moments |
| 244 | "Stress Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/stress/ | Stress moments |
| 245 | "Anxiety Sound Effect" | Various | Mixkit SFX | 0:20 | Mixkit | https://mixkit.co/free-sound-effects/anxiety/ | Anxiety moments |

### Misc SFX (10 entries)
| # | Track/Collection Name | Artist | Source | Duration | License | Source/Search Link | Football Use |
|---|---|---|---|---|---|---|---|
| 246 | "Boo Sound Effect" | Various | Pixabay SFX | 0:10 | Pixabay | https://pixabay.com/sound-effects/search/boo/ | Crowd disapproval |
| 247 | "Gasp Sound Effect" | Various | Pixabay SFX | 0:10 | Pixabay | https://pixabay.com/sound-effects/search/gasp/ | Shock gasp |
| 248 | "Sigh Sound Effect" | Various | Pixabay SFX | 0:10 | Pixabay | https://pixabay.com/sound-effects/search/sigh/ | Disappointment sigh |
| 249 | "Cry Sound Effect" | Various | Pixabay SFX | 0:10 | Pixabay | https://pixabay.com/sound-effects/search/cry/ | Crying |
| 250 | "Sob Sound Effect" | Various | Pixabay SFX | 0:10 | Pixabay | https://pixabay.com/sound-effects/search/sob/ | Sobbing |
| 251 | "Breath Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/breath/ | Deep breath |
| 252 | "Sigh Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/sigh/ | Sigh |
| 253 | "Gasp Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/gasp/ | Gasp |
| 254 | "Exhale Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/exhale/ | Exhale |
| 255 | "Inhale Sound Effect" | Various | Mixkit SFX | 0:10 | Mixkit | https://mixkit.co/free-sound-effects/inhale/ | Inhale |

---

## Attribution Templates

### CC-BY Attribution (Incompetech, BreakingCopyright tracks)
```
Music: [Track Name] by [Artist]
License: Creative Commons Attribution 3.0 Unported (CC BY 3.0)
Source: [Link to source]
```

### Pixabay Attribution (optional but appreciated)
```
Music/SFX from Pixabay
[Track Name] by [Artist]
https://pixabay.com/
```

### Mixkit Attribution (optional but appreciated)
```
Music/SFX from Mixkit
[Track Name]
https://mixkit.co/
```

### YouTube Audio Library Attribution (varies per track)
```
Music from YouTube Audio Library
[Track Name] by [Artist]
License: [As specified in Audio Library]
```

### Freesound Attribution (varies per upload)
```
Sound effect from Freesound
[Sound Name] by [Uploader]
License: [CC type as specified on upload page]
https://freesound.org/
```

---

## Final License Verification Checklist

Before using ANY asset, verify:

- [ ] **Source page is accessible** — Link works, page loads
- [ ] **License is clearly stated** — No ambiguity about usage rights
- [ ] **Commercial use is permitted** — YouTube monetization is commercial use
- [ ] **Attribution requirements are understood** — Know exactly what to put in description
- [ ] **No "sampling" or "remix" restrictions** — Some CC licenses restrict derivative works
- [ ] **No platform restrictions** — Some licenses ban TV/radio (not relevant for YouTube)
- [ ] **Uploader is the rights holder** — Freesound especially: verify uploader created the sound
- [ ] **No recent license changes** — Check upload date; licenses can change
- [ ] **Downloaded file matches source** — Verify file integrity after download
- [ ] **Attribution is placed in video description** — Before publishing

**⚠️ CRITICAL:** If any checkbox cannot be verified, DO NOT USE the asset. Find an alternative with an exact asset page, clear license, and saved attribution metadata.

---

## Quick Reference: Where to Use Each Asset Type

| Asset Type | Football Moment | Emotion | Story Stage |
|---|---|---|---|
| Sad Piano | Player crying, elimination | Heartbreak, devastation | Climax, cooldown |
| Emotional Cinematic | Trophy lift, legacy moment | Triumph, pride | Climax |
| Cinematic Rise | Pre-match, comeback beginning | Anticipation, hope | Buildup |
| Epic Orchestral | Championship, national triumph | Elation, catharsis | Climax |
| Dark Ambient | Pressure, burden | Unease, dread | Buildup |
| Heartbeat Tension | Penalties, final minutes | Anxiety, tension | Climax |
| Motivational Build-Up | Training, comeback sequence | Determination, energy | Buildup |
| Documentary Piano | Flashback, reflection | Nostalgia, meaning | Cooldown |
| Crowd Ambience | Celebrations, anthems | Authenticity, scale | Any |
| Whooshes | Transitions, fast cuts | Energy, movement | Any |
| Impact Hits | Goals, tackles | Impact, power | Climax |
| Bass Hits | Major moments | Emphasis | Climax |
| Risers | Pre-climaxes | Building tension | Buildup |
| Camera Shutter | Freeze frames | Memory, iconic | Any |
| Silence | Before decisive moments | Maximum tension | Climax |
| Commentator Echo | Iconic lines | Amplification | Climax |

---

# Required selector output schema

```yaml
music_library_selection:
  request_id: string
  story_type: string
  section_id: string
  emotional_role: hook | context | pressure | action | climax | aftermath | legacy | outro
  recommended_assets:
    - rank: int
      asset_name: string
      creator: string
      source_platform: string
      source_or_search_link: string
      exact_asset_url_required: true
      expected_license_type: string
      attribution_likely_required: bool | unknown
      football_use_case: string
      suitability_score: 1-10
      risk_tier: low | medium | high | unknown
      verification_status: candidate_only | verified | rejected
  fallback_assets: []
  crowd_or_silence_option:
    use_instead_of_music: bool
    reason: string
  required_next_skill: rights-safe-audio-license-checker
```

# Rejection rules

Reject any asset if:

- exact source page cannot be found;
- license text is unclear;
- commercial/YouTube use is not allowed;
- attribution cannot be generated;
- source appears to be a reupload of someone else's copyrighted track;
- Content ID or claim risk is unknown for a high-stakes first upload;
- it emotionally overpowers real commentary/crowd/silence.
