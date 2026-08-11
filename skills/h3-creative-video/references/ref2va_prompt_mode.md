# Ref2VA Prompt and ComfyUI Mode

Use this reference whenever at least one attached image, video, or audio file supplies identity,
appearance, setting, style, motion, camera, voice, soundtrack, or source-video content rather than
only a base-model first/last endpoint.

Sources inspected on 2026-08-11:

- [MiniMax-H3 repository](https://github.com/MiniMax-AI/MiniMax-H3) at
  `fa6891ff7cdaaa03fa4497e89ac64ff169219acf`, including the official Ref2VA example,
  `skills/h3-prompt-writing/references/ref-en.txt`, and six-section prompt format
- [ComfyUI MiniMax-H3 node](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_minimax_h3.py)
  at `c2bcbecd82ec5ae66594340b395c24ef0217b238`
- [ComfyUI R2V workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_r2v.json)
  at `cca1ea5ea4560108ecc2f44dee951f41ea433062`
- [Comfy-Org MiniMax-H3 ModelScope mirror](https://modelscope.cn/models/Comfy-Org/MiniMax-H3),
  including its model manifest and ComfyUI placement guidance

Treat upstream specifications and current ComfyUI behavior separately. Recheck these sources after
updating the checkpoint, ComfyUI, node, or workflow.

## Contents

1. Route Ref2VA
2. Inventory and label references
3. Write the six-section prompt
4. Wire current ComfyUI
5. Validate duration, shape, and resource cost
6. Preflight and acceptance
7. Failure routing

## 1. Route Ref2VA by asset role

Use Ref2VA when any asset has a general reference role:

- an image supplies identity, wardrobe, object, environment, style, pose, or storyboard guidance;
- a video supplies a subject, action, camera move, edit source, continuation source, pacing, or
  temporal structure;
- audio supplies a waveform to reuse or a voice, music, beat, ambience, or sound texture to follow;
- multiple modalities or reference roles are combined.

Do not route by file count alone:

| User intent | Mode |
| --- | --- |
| no attached media | T2VA |
| one image is explicitly the exact first frame | I2VA |
| one image is explicitly the exact last frame | L2VA |
| two images are explicitly exact first and last frames | FL2VA |
| image is a reusable identity/style/content reference | Ref2VA |
| any reference video or audio is attached | Ref2VA |
| exact frame anchors plus other reference media | Ref2VA with `keyframe completion` in `summary` |

If a single image could mean either an exact endpoint or a reusable reference, resolve that
material ambiguity before generation. Ref2VA and the FL2VA-family base modes use different
transformer weights and conditioning nodes; they are not interchangeable.

## 2. Inventory assets and freeze labels before writing

The published H3 system accepts:

- up to 9 reference images;
- up to 3 reference videos, each 2–15 seconds;
- up to 3 reference audio clips, each 2–15 seconds;
- no more than 12 input files across mixed types;
- no more than 15 seconds total reference-video duration and 15 seconds total reference-audio
  duration.

Create an ordered manifest before prompt authoring. Record source path/URI, hash, duration,
dimensions/sample rate, whether a video's audio is enabled, connector name, assigned label, role,
and rights/consent status when people, voices, brands, or copyrighted material are involved.

ComfyUI labels are 1-based and numbered independently by type:

- `ref_image_0`, `ref_image_1` become `<Picture 1>`, `<Picture 2>`;
- `ref_video_0`, `ref_video_1` become `<Video 1>`, `<Video 2>`;
- audio labels count enabled video soundtracks first in video order, then standalone
  `ref_audio_0`, `ref_audio_1` in their connector order.

For each video, connect its soundtrack only to the same-numbered
`ref_video_audios.ref_video_audio_N`. The node emits that soundtrack's `<Audio N>` immediately
before its `<Video N>` presentation. Reordering connectors after writing the prompt silently
changes label meaning, so hash the final workflow and preserve a label-to-source table.

Use labels according to semantics:

| Label | Use |
| --- | --- |
| `<Subject N>` | reusable visible content abstracted from one or more assets |
| `<Picture N>` | the image file itself when it is a concrete frame/composition/storyboard anchor |
| `<Video N>` | whole-video edit, continuation, camera, cut, rhythm, or temporal source |
| `<Audio N>` | copied or referenced audio signal, including an enabled video soundtrack |

An image used only to define a character belongs inside that subject definition; do not invent a
standalone picture role. A video's person/action is a `<Subject N>`; `<Video N>` identifies the
whole source or structure. An ordinary video does not create `<Audio N>` unless its soundtrack is
actually connected.

## 3. Write the official six-section prompt

Ref2VA does not use the base-mode three-field opening. Begin on physical line 1 with these sections
in this exact order:

```text
subject_definitions:
<Subject 1> is ... in <Picture 1>.

summary:
[reference generation] ...

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - ...

detailed_description:
The target video uses ... style.
[Shot 1] ...

overall_soundscape:
...

non_diegetic_music:
...
```

The stock ComfyUI R2V template demonstrates that the current node can also tokenize a compact
free-form prompt containing exact reference tags; the node itself does not parse the six section
names. For this Skill's authored production work, canonicalize to the official six-section
Context-IR format so asset roles, preservation claims, shot timing, and acceptance remain
machine-lintable. Preserve a compact source prompt verbatim before rewriting it.

### 3.1 Define every reusable unit

Give each subject, standalone frame anchor, whole-video role, and audio role one stable meaning.
One subject may combine appearance from a picture, motion from a video, and voice from an audio
clip. One asset may define several subjects. Never let the same label change meaning between
sections.

### 3.2 Declare task types in `summary`

Start the single short paragraph with one or more applicable fixed task types joined by ` + `:

- `keyframe completion`: a picture is a concrete first/key/last/edited frame;
- `reference generation`: a reference guides identity, scene, style, action, camera, or structure;
- `video editing`: the target directly modifies a source video;
- `video continuation`: the target continues from a source video's end;
- `audio reuse`: the original signal is copied in full or in part;
- `audio reference`: timbre, delivery, music, beat, dialogue content, or texture is followed without
  copying the signal.

Do not infer editing, continuation, or reuse merely because a file is attached. For a direct edit,
state that the target is an edited version of the corresponding `<Video N>`.

### 3.3 Declare preservation in `retention_analysis`

Use one line per semantic reference label. Visual markers are `fully_preserved`,
`partially_preserved`, `attribute_transfer`, or `weak_reference`. Audio markers are `fully_copy`,
`partially_copy`, `reference`, or `weak_reference`. Explain exactly what remains, changes,
transfers, or is only loosely followed. New target actions or backgrounds are not automatically a
fidelity loss.

### 3.4 Write the playback timeline in `detailed_description`

Put one or two style sentences before `[Shot 1]`. Then follow the base shot, timestamp, camera,
speaker, `<d>[Language] ...</d>`, `<scenetrans>`, and `<cutoff>` rules. At a subject's first clear
appearance, state its referenced attributes, frame position, and current action. Cite picture
anchors, video structure, and audio roles exactly where they take effect.

Keep speakers separate from reference sources: `<Subject 2> (S1)` identifies both a referenced
person and the first actual target-video speaker. Reuse the same `(Sx)` at every vocal event. An
audio-only lyric cue inside a directly copied soundtrack can use `<Audio N>` without inventing a
speaker; a concrete person or narrator still needs `(Sx)`.

Preserve user-provided dialogue, lyrics, and visible text exactly. Do not copy words from reference
audio when only its timbre, rhythm, emotion, or delivery is being referenced.

### 3.5 Separate sound layers

Keep timed speech and synchronized sound events in `detailed_description`. Summarize ambience and
physical sounds in `overall_soundscape`; place audience-only score in `non_diegetic_music`. State
an audio copy/reference relationship in whichever audible layer it actually affects. Do not claim
`fully_copy` if new dialogue, mixing, trimming, or replacement changes the signal.

## 4. Wire the current ComfyUI Ref2VA graph

Use the dedicated stack:

- `minimax_h3_ref2va_*.safetensors`, never the `fl2va` transformer;
- shared MiniMax Qwen3-VL text encoder;
- MiniMax H3 video VAE and audio VAE;
- `MiniMaxH3ReferenceToVideo`, not `MiniMaxH3ImageToVideo`;
- `VAEDecode` plus `VAEDecodeAudio`, then mux at 24 fps.

The ModelScope Comfy-Org package currently offers BF16, pruned BF16, INT8 ConvRot, pruned INT8
ConvRot, and pruned FP8-scaled Ref2VA transformers. Its guidance prefers INT8 ConvRot when the
PyTorch/CUDA stack supports it and uses FP8-scaled as a fallback. Record the exact file hash and do
not assume two quantizations are quality- or performance-equivalent.

The official workflow uses `res_multistep`. Its note recommends `beta` or `normal` scheduling over
`simple` for reference-heavy prompts, but this is workflow guidance rather than a calibrated local
finding. Probe the actual host before promoting it to a production default.

## 5. Validate duration, shape, and reference cost

The current node:

- snaps output frames upward to `n % 17 == 5` at 24 fps;
- documents an approximately 124–362-frame trained range;
- presents reference videos to Qwen at 2 fps with timestamps;
- truncates reference video frames to the target frame count, then trims down to the `17k+5` grid;
- resamples reference audio to 32 kHz before encoding;
- caps/rounds video canvases according to its current 768-short-edge, `768*1344`-area policy.

Therefore record requested seconds, requested frames, effective frames, and effective seconds.
Do not assume a nominal 5-second request produces exactly 120 frames: the stock formula yields 124
frames. A reference video longer than the target may be silently truncated by the graph.

For `ref_image_size`:

- `match` only downsizes an image until its pixel area fits the output canvas area;
- `max` only downsizes when needed and permits up to a 2048-pixel short edge.

References remain in the conditioning sequence throughout sampling. `max`, more files, longer
videos, and high-resolution images can multiply token cost and runtime. Start with `match` for a
wiring probe; test `max` only when identity/detail fidelity justifies the measured cost. Never
solve OOM by changing several prompt, asset, and runtime variables at once.

## 6. Preflight and accept by declared role

Before submission:

1. validate file counts, individual and total durations, decodability, and hashes;
2. freeze connector order and render the label manifest;
3. lint the six-section prompt with the actual label counts;
4. assert Ref2VA checkpoint and `MiniMaxH3ReferenceToVideo` wiring;
5. probe the exact reference mix, output shape, length, quantization, and `ref_image_size` at low
   steps; verify pixels and both streams;
6. declare one acceptance row per reference role.

Example lint:

```bash
python scripts/h3_prompt_lint.py prompt.txt --mode ref2va --duration 5.1667 \
  --pictures 2 --videos 1 --audios 2 --json
```

Acceptance must distinguish:

- subject identity/attributes and where they appear;
- concrete picture-frame/composition anchors;
- edit/continuation/structural video relationships;
- full/partial audio copy versus timbre/style/content reference;
- ordinary prompt requirements not tied to a reference.

A perceptually similar voice is not proof of copied audio. An audio stream existing is not proof
of the requested words, speaker, or source relationship. Use listening and, for copy claims,
timeline/waveform or fingerprint evidence appropriate to the intended edit.

## 7. Route common failures

| Failure | First checks and levers |
| --- | --- |
| wrong subject or style attached to a label | compare prompt tags with frozen connector order and hashes |
| identity weak | remove conflicting references, make subject definitions concrete, then compare `match` with `max` |
| one asset overwhelms another | narrow each subject/asset role and reduce redundant or contradictory references |
| source edit drifts | state `video editing`, define `<Video N>` explicitly, and tighten the preservation line |
| continuation restarts instead | state `video continuation` and describe the exact source end state before new action |
| copied audio changes | verify `audio reuse` plus `fully_copy`/`partially_copy`; check soundtrack pairing and trims |
| referenced voice repeats source words | mark `audio reference`, supply exact target dialogue, and say the signal is not copied |
| wrong `<Audio N>` | recount enabled video soundtracks before standalone audios; audio numbering is independent |
| OOM or extreme slowdown | use `match`, fewer/shorter refs, lower-resolution sources, then profile one change at a time |
| reference video role disappears | verify it survived target-length truncation and `17k+5` trimming |

Do not transfer T2VA/FL2VA empirical prompt findings to Ref2VA without paired Ref2VA evidence.
