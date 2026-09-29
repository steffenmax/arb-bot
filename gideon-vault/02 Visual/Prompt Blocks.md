---
type: prompt
tags: [gideon, locked, prompt]
---

# Reusable Prompt Blocks

Paste **all five** into every video prompt, then add the shot description. The [[Shot Director]] agent assembles these; the [[Shot Prompt Template]] has slots for them.

## CHARACTER

```
Gideon, exactly as in @image1. Faceted low-poly silver hair slicked back, darker gray at the temples, with a single thick angular strand falling across his forehead. Smart-glasses headset with a thin silver frame, a matte black module on the right temple, a small camera lens at the front hinge, and a small clear glass prism above his right eye. White earbud in his right ear. Navy quarter-zip pullover zipped halfway over a black turtleneck, silver wristwatch on his left wrist. Neutral, deadpan face, never smiling. Identical in every shot.
```

## STYLE

```
2004 PlayStation 2 pre-rendered cutscene. Faceted low-poly hair and skin, smooth waxy shading, subtle polygon edges on every surface, mild texture blur, limited draw distance. The character and environment share the same rendering style. Nothing photorealistic.
```

## NO TEXT

```
There is no text, lettering, numbers, logos, or symbols anywhere in the video, including on the glasses display, screens, or holograms. The glasses prism only glows with soft, abstract light.
```

> Why: any spelled-out word or ticker gets rendered as garbage text on screen. Add tickers and "not financial advice" in post (CapCut). See [[Shot Writing Rules]].

## CAMERA

```
Subtle handheld camera, like a documentary operator standing a few feet away: slight natural sway, gentle micro-drift, and small breathing movements. Never shaky or chaotic.
```

## DIALOGUE

```
@video1 contains Gideon's complete dialogue audio. The generated audio must match @video1 exactly, and his lip-sync must match the vocal segments in @video1 exactly. His mouth moves only during speech and stays closed and still during pauses. No added words, no music.
```

## Reference slots

| Slot | Contents | Notes |
|---|---|---|
| `@image1` | `gideon_master_sheet.png` | Identity reference, **not** a first frame |
| `@video1` | Black-screen 9:16 MP4 carrying that shot's audio | ≤13s (Seedance 2.0) — see [[Production Pipeline]] |

## Related
[[Visual Spec]] · [[Home Location]] · [[Shot Writing Rules]] · [[Shot Prompt Template]]
