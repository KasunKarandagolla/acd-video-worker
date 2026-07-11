# OpenMontage Zero-Key Capability Envelope

This reference prevents the football-emotion package from assuming paid APIs are available.

## Zero-key-first stance

The user prefers free/open workflows. Treat paid API providers as optional upgrades, not defaults.

OpenMontage documents a zero-key path built around local/open tools and free/open media sources. The practical football-emotion plan should therefore check the following first:

- FFmpeg for trimming, composition support, audio processing, subtitle burn-in, post-processing, and validation.
- Remotion for React/data-driven visual composition when appropriate.
- HyperFrames for HTML/CSS/GSAP motion-graphics-heavy compositions when available and user-approved.
- Piper TTS for offline narration when narration is needed.
- Archive.org, NASA, Wikimedia Commons, and optional free-key providers such as Pexels, Pixabay, and Unsplash for open/stock footage.
- Built-in subtitle/caption tools when available.
- Backlot for local review and approval gates.

## Football caveat

World Cup and professional match footage is not equivalent to open stock footage. Even when the OpenMontage zero-key documentary path works, FIFA/broadcaster match footage still needs rights/risk handling.

For football projects, zero-key capability can support:

- open archival context clips
- fan atmosphere when user-authorized and risk-assessed
- royalty-free music/SFX after license verification
- narration/caption/graphics/composition
- final render and QA

It does not automatically grant permission to use protected match footage.

## Render runtime confirmation

If both Remotion and HyperFrames are available, present the user with both choices and ask for explicit confirmation before locking `render_runtime`.

Default guidance:

- Remotion: React scene stack, data-driven explainers, subtitles, timeline components, structured visual layouts.
- HyperFrames: HTML/CSS/GSAP, kinetic typography, motion graphics, SVG/character rigs, design-heavy compositions.
- FFmpeg-only: straightforward real-footage trimming, concatenation, audio normalization, subtitle burn, encoding, and lightweight transformations.

This is guidance, not an automatic decision. The local manifest and user approval govern the final choice.
