# Ref2VA Mode

Use for general identity/style/content images, any reference video/audio, or mixed reference roles.
A lone exact first/last image belongs to a base endpoint mode; resolve ambiguous intent before
running. Exact anchors mixed with other references use Ref2VA `keyframe completion`.

For authoring, use the inventory and prompt sections below, plus
[prompt_authoring.md — shared timeline and sound](prompt_authoring.md#shared-timeline-and-sound).
Execution and acceptance sections apply only at those stages. Source revisions and upstream links
are in `official_h3_guide.md`; the node observations here are historical, not live version claims.

## Inventory and stable labels

Published limits at the recorded revision: up to **9 images, 3 videos, 3 audio clips**, at most
**12 files** combined. Each video/audio is **2–15s**; total video duration ≤15s and total audio
reference duration ≤15s. Keep the published production limits even if a node accepts shorter clips.

Freeze an ordered source/connector/label/role manifest before writing. Include hashes,
duration/dimensions/sample rate, enabled video soundtracks, and permissions/consent where relevant.
Labels are independent, 1-based sequences:

- `ref_image_0`, `ref_image_1` → `<Picture 1>`, `<Picture 2>`.
- `ref_video_0`, `ref_video_1` → `<Video 1>`, `<Video 2>`.
- `<Audio N>` counts **enabled video soundtracks in video order first**, then standalone
  `ref_audio_0`, `ref_audio_1`, etc. A video without a connected soundtrack creates no audio label.
- Connect a video's soundtrack only to the same-numbered
  `ref_video_audios.ref_video_audio_N`. The node presents it immediately before its video.

Reordering connectors changes meaning even with identical files and prompt. Hash the final graph.

| Label | Meaning |
| --- | --- |
| `<Subject N>` | Reusable visible content/identity/action abstracted from assets |
| `<Picture N>` | Concrete frame, composition, or storyboard anchor |
| `<Video N>` | Whole-video editing, continuation, camera, cuts, rhythm, or temporal source |
| `<Audio N>` | Copied or referenced signal, including connected video soundtrack |

One subject can combine appearance, motion, and voice from different sources; one asset may define
several subjects. An identity-only image needs no invented standalone picture role. A video's
person/action is a subject; its whole temporal structure is a video role. Keep each meaning stable.

## Six-section prompt

Start physical line 1 with `subject_definitions:`; use this exact order:

```text
subject_definitions:
<Subject 1> is the woman in <Picture 1>, retaining her face and clothing.

summary:
[reference generation] <Subject 1> walks into a new garden.

retention_analysis:
<Subject 1> (appears in [Shot 1]): attribute_transfer - retain face and clothing; replace setting and action.

detailed_description:
The target video uses candid photographic style.
[Shot 1] <Subject 1>, with the referenced face and clothing, walks from screen left into the garden.

overall_soundscape:
Footsteps sound on gravel beneath rustling leaves.

non_diegetic_music:
N/A
```

Define every reusable subject, standalone frame anchor, whole-video role, and audio role.
`summary` is one short paragraph starting with applicable task markers joined by ` + `:

| Marker | Intended relationship |
| --- | --- |
| `keyframe completion` | Concrete first/key/last/edited picture frame |
| `reference generation` | Identity, scene, style, action, camera, or structure guidance |
| `video editing` | Explicitly edit the corresponding `<Video N>` |
| `video continuation` | Continue from the source's end state |
| `audio reuse` | Copy the full or partial original signal |
| `audio reference` | Follow timbre, delivery, beat, content, or texture without signal copying |

Do not infer editing/continuation/reuse just because media exists. In `retention_analysis`, give
one line per semantic reference label, explaining retained/changed/transferred attributes:
visual markers `fully_preserved`, `partially_preserved`, `attribute_transfer`, `weak_reference`;
audio markers `fully_copy`, `partially_copy`, `reference`, `weak_reference`.

In `detailed_description`, place 1–2 style sentences before `[Shot 1]`. At a subject's first clear
appearance, state referenced attributes, frame position, and current action. Cite picture/video/audio
roles where they take effect. Shared shot, timestamp, dialogue and sound rules apply.

`<Subject 2> (S1)` distinguishes a referenced person from the first actual target speaker.
An audio-only lyric cue in copied soundtrack may use `<Audio N>` without inventing a speaker;
a concrete speaker/narrator still needs `(Sx)`. Preserve user dialogue, lyrics, and visible text;
do not import source words when only voice timbre/rhythm/delivery is requested.

State an audio relationship in the audible layer it affects. Do not claim `fully_copy` after trims,
overlay, mixing, replacement, or new dialogue change the signal. Although the recorded node accepts
free-form exact tags without parsing section names, this skill authors the canonical six-section
format for inspectable roles and linting; preserve the source before normalization.

```bash
python scripts/h3_prompt_lint.py prompt.txt --mode ref2va --duration 5.1667 \
  --pictures 2 --videos 1 --audios 2 --json
```

These counts illustrate CLI usage; pass the actual frozen manifest counts for each prompt.
Resolve errors and inspect warnings; lint cannot prove that the graph connects those sources.

## Execution-specific checks

Require `minimax_h3_ref2va_*` transformer, shared H3 text encoder, video/audio VAEs,
`MiniMaxH3ReferenceToVideo`, both decodes and mux. Do not substitute a base `fl2va` transformer.
Reuse only a runner whose real graph supports the exact input types; `h3_runbook.md` records the
Juscent adapter's narrower coverage. Probe the exact reference mix/quantization/shape/length at
low steps and verify pixels/audio before full steps.

Recorded node behavior (recheck after model/node/workflow changes):

- Output snaps upward to `17k+5` at 24 fps; documented trained range approximately 124–362 frames.
  Stock 5s conversion yields 124, not 120 frames. Record requested and effective frames/seconds.
- Reference videos go to Qwen at 2 fps with timestamps, truncate to target frames, then trim down
  to the frame grid. Check that a required late event survives; record effective reference lengths.
- Reference audio is resampled to 32 kHz; video canvases follow the recorded 768-short-edge and
  `768*1344` area policy. Inspect effective dimensions rather than assuming request fidelity.
- `ref_image_size=match` only downsizes to fit output area; `max` only downsizes as needed and allows
  a 2048-pixel short edge. References remain in conditioning throughout sampling, so larger/more/
  longer sources can multiply cost. Start probes with `match`; justify `max` by measured fidelity.
- Recorded workflow uses `res_multistep`, recommending `beta`/`normal` over `simple` for heavy
  references. These are workflow recommendations, not calibrated local defaults.
- Recorded model packages include BF16/pruned BF16, INT8 ConvRot/pruned INT8 ConvRot, and pruned
  FP8-scaled variants; package advice prefers supported INT8 ConvRot, with FP8 fallback. Record the
  exact hash and compatible stack; do not assume quantizations equivalent.

Freeze media metadata, soundtrack mapping, graph hash, tag counts and effective lengths with the
production manifest. Validate decodability and hashes. Do not replace references unless requested.

## Role-specific acceptance and failure routing

Use the common pixel/visual/audio gates, plus one row per declared role:

| Role or failure | Review / first lever |
| --- | --- |
| Subject identity/attributes | Check every named shot and unwanted attribute leakage; verify labels, remove conflicting refs, define concrete attributes, then compare `match`/`max` |
| Picture anchor | Verify the intended concrete frame/composition at the declared point |
| Video edit/continuation/structure | Verify the promised source relationship and retained events; tighten task marker/preservation/timeline, check truncation |
| Audio copy | Listen and compare the declared source region and target trims/mix; support signal retention with waveform/fingerprint evidence |
| Audio reference | Judge declared timbre/style/content; do not require signal identity or import unrequested source speech |
| Wrong voice/audio label | Recount enabled video soundtracks before standalone audio, then verify pairing and exact target words |
| One reference dominates | Narrow roles and remove redundant/contradictory references |
| OOM/slowdown | Profile `match`, fewer/shorter refs or lower source resolution one change at a time |

A familiar face does not pass an edit-source or frame-anchor promise. A new action is not a failure
when only identity was promised. Similar voice is not proof of copied audio, and an audio stream is
not proof of requested words. Scope empirical conclusions to Ref2VA; do not import base-mode ceilings.
