---
type: agent
tags: [gideon, agent]
role: "Cut audio per shot"
input: "ElevenLabs MP3 of the full take"
output: "Per-shot black-screen 9:16 MP4s (720×1280), each ≤13s, plus a timestamp table"
---

# Audio Splitter

**Input:** ElevenLabs MP3 of the full take
**Output:** Per-shot black-screen 9:16 MP4s (720×1280), each ≤13s, plus a timestamp table

## Brief (paste as system prompt)

Run ffmpeg silencedetect on the take, choose cut points inside pauses so that each segment is ≤13 seconds and contains whole sentences, cut the segments, and render each as a black 720×1280 video carrying that segment's audio. Return a table: shot · start · end · length · exact transcript of the lines inside. Never trim into a word.

## Must read before running
[[Gideon - Character Bible]] · [[Guardrails & Compliance]] · [[Production Pipeline]] · [[Voice Spec]]

## Related
[[Agentic Workflows]]
