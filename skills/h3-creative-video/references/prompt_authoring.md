# Writing H3 Base-Mode Prompts

Select the conditioning mode first, then apply shared audiovisual rules. Never apply an image-mode
instruction or an FL2VA experiment finding to T2VA by default.

## Contents

1. Mode-specific opening
2. Shared fields
3. Shots and camera
4. Dialogue, voiceover, singing, and visible text
5. Style and realism by mode
6. Final-shot design
7. FL2VA-only project findings
8. Audio

## 1. Use the exact opening for the mode

### T2VA — zero images

Start directly with the first core field. There is no image instruction:

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

### I2VA — first frame only

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

### FL2VA — first and last frames

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.

integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

### L2VA — last frame only

```text
How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.

integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

For image modes, `N` is the actual final shot and `S.SS` is the effective duration to two decimal
places. Put the instruction on line 1 and one blank line before the fields. In T2VA, putting an
alignment line on line 1 is an error because no Picture exists.

## 2. Write the three shared fields in order

`integrated_multimodal_description` contains the visible/audible timeline: style, composition,
subjects, environment, actions, shot transitions, speakers, dialogue/singing, camera, and
synchronized diegetic sound.

`overall_soundscape` is one continuous paragraph of 1–4 English sentences for ambience, physical
action sounds, and non-verbal human sounds. Use `N/A` only when the user explicitly requests total
silence.

`non_diegetic_music` is 1–3 English sentences for audience-only score. Specify instrumentation,
tempo, rhythm, and dynamics rather than an abstract emotional purpose. Use `N/A` when no score is
wanted.

Write prose, not a trailing bag of tags. For T2VA source-prompt preservation and acceptance, read
`t2va_prompt_mode.md`.

## 3. Build shots and camera along the timeline

- Write `[Shot 1]` with no timestamp.
- Start later shots with sequential IDs and strictly increasing times:
  `[Shot 2] At 00:03.500, the camera cuts to ...`.
- Keep every cut inside the duration and make it introduce subject, space, state, viewpoint, or
  time. Prefer camera motion when only distance or a slight angle changes.
- Use natural camera-action sentences. Combine motion type with amplitude and speed only when those
  qualifiers are meaningful.

Official camera vocabulary includes Zoom, Push/Pull, Pan, Truck, Tilt, Pedestal, Arc, Tracking,
Static, Shake, POV, and Roll. Example:

```text
The camera pushes in with small amplitude at slow speed toward the folded letter.
```

Recorded cut times have landed on both sides of the written timestamp; treat timestamps as targets
and measure actual cuts.

## 4. Preserve speech, singing, and visible text exactly

Assign stable `(S1)`, `(S2)`, etc. only to characters who speak, sing, or produce an off-screen
human voice. Identify voice and speaker outside the dialogue tag. Put only the exact user text and
language label inside it:

```text
The young woman with a quiet, breathy voice (S1) says: <d>[Chinese] 我在下一站下车。</d>
```

Do not translate or rewrite dialogue/lyrics. For voiceover, use the exact phrase `says in an
off-screen voiceover` and state immediately afterward that the corresponding on-screen character's
lips remain closed.

When a line crosses a cut, use `<scenetrans>` at the connection and explicitly say the audio
continues. Use `<cutoff>` when speech is truncated at the end. Put visible signs, labels, subtitles,
or neon text in English double quotation marks while preserving the original text and punctuation.

## 5. Scope style and realism by conditioning mode

Choose stylized versus lifelike deliberately:

| Goal | Useful direction |
| --- | --- |
| Stylized/genre | name the actual medium or genre: 2D animation, claymation, watercolor, vintage film, cinematic action |
| Lifelike | state observable photographic facts: candid framing, uneven available light, moderate depth, imperfect texture |

Avoid empty quality incantations such as `masterpiece`, `8k`, `hyperrealistic`, `perfect`, or
`stunning` when lifelike believability is the goal.

Mode scope matters:

- **T2VA:** text is the only visual conditioning. Describe stable visible attributes and concrete
  lighting/composition facts in the prompt, then judge the generated result.
- **I2VA/L2VA/FL2VA:** endpoint images set the base identity/form/texture ceiling. Video-stage
  realism wording failed to improve pores/light/depth in paired **FL2VA** experiments, but the
  video stage may still add temporal artifacts.

Do not conclude from FL2VA that realism wording is useless in T2VA.

## 6. Design the final shot without inventing a universal freeze rule

Give each shot one primary state transition; allow secondary hair, fabric, weather, or environment
motion. If a held ending is intended, write and accept it as such. If continued action is required,
avoid an early semantic endpoint and make the ongoing state visible in the timeline.

For FL2VA, also inspect whether the final image composition affords continuation through an exit
direction, unresolved weight transfer, or asymmetric motion. The phrase `still turning` alone did
not guarantee continued subject motion in paired project review.

T2VA has no final image. Its ending lever is the final-shot timeline plus seed/candidate selection.
FL2VA wording failures do not prove that the same T2VA wording is ineffective.

## 7. Keep project findings inside FL2VA scope

The following paired findings came from the recorded FL2VA graph/profile:

| Attempt | Result and scope |
| --- | --- |
| Realism clauses in the video prompt | no improvement to endpoint-derived pores/light/depth |
| Forbid mid-shot pull-back | no seed-consistent effect |
| Swap camera-motion keywords/amplitude adverbs | no seed-consistent effect because endpoint interpolation dominated |
| Reinforce “never stops” / continued-turn wording | did not solve the observed ending behavior |
| Add background motion to solve subject settling | whole-frame movement did not prove subject movement |

Do not ban these controls in T2VA. T2VA has no endpoint images, so prompt camera/style/timeline
language is a primary conditioning path and needs its own paired evidence.

## 8. Direct sound and music, then verify by ear

Keep synchronized dialogue, singing, radio/TV/phone music, footsteps, impacts, and other diegetic
events in the timeline. Summarize ambience and non-verbal sound in `overall_soundscape`. Put only
audience-only score in `non_diegetic_music`.

Project experiments found score instrumentation more directable than ambient sound, but metrics can
only show that audio exists and characterize energy. Listen to verify words, speaker, instrument,
timing, unwanted voice, and musical resolution.

For segmented generations, plan a continuous audio bed or soundtrack in post. Prompt wording
cannot repair a seam between independently generated audio streams.
