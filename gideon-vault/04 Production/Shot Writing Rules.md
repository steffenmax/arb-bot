---
type: process
tags: [gideon, locked]
---

# Shot-Writing Rules

For whoever (or whichever agent) writes the Seedance prompts. Enforced by the [[Shot Director]].

- **3–4 camera cuts per 29s video, but one continuous scene.** Same location, same time of day, same lighting. A cut is only a new angle, never a new world.
- **Subtle handheld on every shot.** Use the CAMERA block from [[Prompt Blocks]].
- **Specify exact physical blocking** (where he stands relative to objects). The model put him on the wrong side of the balcony railing when this was vague. See [[Home Location]].
- **NO TEXT block on every shot.** Any spelled-out word or ticker renders as garbage text on screen. Add text in post.
- **Walking + lip-sync is the riskiest combo.** Keep movement minimal while speaking. Let him turn his head, shift weight, look toward the camera. Do not let him walk and talk.
- **One `Lip-sync strictly: "<exact line>"` per shot**, matching the audio segment word for word.
- **Duration = the audio clip's length.** Never round up.
- **Same time of day in every shot:** late-afternoon golden light from the left.

## Shot prompt skeleton

```
[CHARACTER block]
[STYLE block]
[NO TEXT block]
[CAMERA block]
[DIALOGUE block]

Shot N of M. <angle and framing>. <exact blocking relative to railing / doors / quantum computer>. <what his body does — minimal>. Late-afternoon golden light from the left, warm bloom.
Lip-sync strictly: "<exact line from the script>"
```

Use [[Shot Prompt Template]] to generate one.

## Related
[[Production Pipeline]] · [[Prompt Blocks]] · [[Home Location]] · [[Style Lessons]]
