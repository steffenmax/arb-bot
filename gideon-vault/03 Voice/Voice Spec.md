---
type: voice
tags: [gideon, locked]
tool: ElevenLabs Voice Design
saved_voice: Gideon
speed: 1.0
stability: 50
similarity: 75
file_tag: sp100_s50_sb75_v4
---

# Voice Specification

> [!important] Never change the saved voice or settings.
> Consistency is the brand.

## Tool and settings

- **Tool:** ElevenLabs Voice Design. Saved voice: **"Gideon"**.
- **Approved settings:** speed 1.0, stability ~50, similarity ~75.
- **File tag:** `sp100_s50_sb75_v4` — keep this in every exported filename so takes are traceable.

## Voice description (used to design the voice)

```
A man in his 40s with a deep, smooth baritone, voiced like an English-dub villain from a 2004 Japanese video game cutscene. Overly dramatic, theatrical, and self-serious, but slightly stiff and unnatural, like a voice actor reading lines in a booth without full context. Slow, deliberate delivery with long, weighty pauses and oddly placed emphasis on certain words. Cold, calm, and mysterious, like a powerful antagonist revealing his master plan. American accent, crisp enunciation, a faint dramatic whisper on key lines. Slightly compressed, early-2000s game audio quality.
```

## Post-processing (optional, for PS2 feel)

- Low-pass ~10–12 kHz
- Subtle bitcrush / 22 kHz resample
- Touch of hall reverb

## Rules

- **Always drive lip-sync from the ElevenLabs file.** Never let the video model voice him.
- **Pronunciation risk:** invented or long words (e.g. "superpositioned") get mispronounced. Test them in ElevenLabs first; if it fails, respell phonetically in the ElevenLabs input only, never in the on-screen script.
- The original ElevenLabs track is laid back over the stitched video in the edit. Generated audio is muted. See [[Production Pipeline]].

## Related
[[Voice Rules (Writing)]] · [[Production Pipeline]] · [[Audio Splitter]]
