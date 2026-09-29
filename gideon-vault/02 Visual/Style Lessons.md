---
type: visual
tags: [gideon]
---

# Style Lessons (learned the hard way)

Append to this note every time a generation fails in a repeatable way.

| # | Failure | Cause | Fix |
|---|---|---|---|
| 1 | Photoreal drift | Model defaults to realism | Always include "Not photorealistic" and "2004 PlayStation 2 pre-rendered cutscene" |
| 2 | Spiky anime hair, drifted toward a well-known silver-haired game villain | Anime-leaning prompts + silver hair + navy | Avoid spikes; "slicked back", "blocky faceted polygon clumps", finance hair |
| 3 | Real IP bleeding in | Naming existing games/shows/characters | Never name existing IP in prompts (copyright + model pulls in the real design) |
| 4 | Garbage text on screen | Spelled-out words or tickers in the prompt | NO TEXT block always present; add text in post |
| 5 | Gideon outside the railing | Vague blocking | Specify exact physical blocking relative to objects |
| 6 | Lip-sync breaks while walking | Motion + speech | Keep movement minimal while speaking |
| 7 | Mispronounced invented words ("superpositioned") | Video model voicing lines | Never let the video model voice him; drive lip-sync from the ElevenLabs file via black-screen video |
| 8 | Weaker results from still-then-animate | Two-step pipeline | Use one-pass: reference image + audio + full scene prompt (Test A) |

## Related
[[Visual Spec]] · [[Prompt Blocks]] · [[Production Pipeline]]
