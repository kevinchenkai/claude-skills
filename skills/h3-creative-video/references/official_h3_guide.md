# Official MiniMax-H3 Prompt Guidance

Sources read from the official repositories on 2026-08-11:

- [Video Prompt Writing Guide](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md), Hugging Face `main` at `9ac0dd7aabc2c651fcf0ace4c00b2bffd9c8c8a6`
- [Official H3 skills](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills), GitHub `main` at `fa6891ff7cdaaa03fa4497e89ac64ff169219acf`
- `h3-prompt-writing/references/base-en.txt` for the portable T2VA/I2VA/FL2VA/L2VA format
- `h3-prompt-writing/references/ref-en.txt` for the Ref2VA label and six-section format

Fetch on a networked local machine if the GPU host cannot reach GitHub/Hugging Face.

## Contents

1. Base conditioning modes
2. Exact prompt openings
3. Shared fields
4. Timeline, camera, speech, and text
5. Mode-specific visual path
6. Project deviations and scope
7. Runtime-profile limits
8. Ref2VA separation

## 1. Route one of four base modes

| Mode | Official definition |
| --- | --- |
| **T2VA** | construct the complete audiovisual timeline from text |
| **I2VA** | T2VA body plus a first-frame instruction and forward development |
| **FL2VA** | T2VA body plus first/last instructions and a continuous path between them |
| **L2VA** | T2VA body plus a last-frame instruction and convergence from a plausible earlier state |

The official `h3-prompt-writing` skill also documents Ref2VA separately. This skill's base-mode
workflow must not misclassify general reference media as endpoint images.

## 2. Use the exact mode-specific opening

**T2VA has no image-alignment instruction.** It begins directly with the three fields.

I2VA line 1:

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
```

FL2VA line 1:

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.
```

L2VA line 1:

```text
How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.
```

For image modes, put the instruction first, then one blank line. `N` is the actual final shot and
`S.SS` is effective duration to exactly two decimals.

## 3. Write the shared fields in this order

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

- `integrated_multimodal_description`: visual style, composition, subjects, actions, shots,
  speakers, dialogue/singing, camera, and diegetic sound along the timeline.
- `overall_soundscape`: 1–4 English sentences for ambience, action sounds, and non-verbal human
  sounds; use `N/A` only for explicit complete silence.
- `non_diegetic_music`: 1–3 English sentences for audience-only instrumentation, tempo, rhythm,
  and dynamics; use `N/A` when there is no score.

## 4. Follow official timeline and content notation

- Give `[Shot 1]` no timestamp. Start later sequential shots with strictly increasing times inside
  the duration: `[Shot 2] At 00:03.500, ...`.
- Make a cut introduce subject, space, state, viewpoint, or time. Prefer camera motion for only
  distance or slight-angle changes.
- Write camera type, meaningful amplitude, and meaningful speed as natural actions.
- Use stable `(S1)` IDs only for speaking/singing/off-screen voices.
- Preserve dialogue and lyrics verbatim inside `<d>[Language] ...</d>`; identify voice outside.
- For voiceover, use `says in an off-screen voiceover` and state that visible lips remain closed.
- Use `<scenetrans>` for speech crossing a cut and `<cutoff>` for speech truncated at the end.
- Put visible screen text in English double quotation marks without translating it.

## 5. Write the visual path for the selected mode

| Mode | Recommended shape |
| --- | --- |
| T2VA | style/initial composition → visible and audible timeline → result/reaction |
| I2VA | first-frame anchor → action onset → continuous development → result/reaction |
| FL2VA | first-frame state → intermediate changes → narrowing differences → final-frame state |
| L2VA | plausible earlier state → explicit path → convergence in final shot → last-frame landing |

The official guide generally favors one continuous FL2VA shot and says to use multiple shots only
when explicitly specified. It does not impose that preference on T2VA.

## 6. Keep project deviations mode-scoped

The project uses explicit multi-shot FL2VA when two primary actions or a required framing change
cannot fit a stable continuous interpolation. This is a recorded project deviation, not an official
T2VA restriction.

Paired FL2VA tests found that endpoint composition dominated mid-shot camera keywords and base
realism wording. Those mechanisms depend on supplied endpoint images. Do not transfer them to T2VA,
where the text is the primary visual condition.

The official structure, shot notation, dialogue preservation, sound separation, and T2VA absence of
an alignment instruction are followed directly.

## 7. Separate official prompt rules from runtime limits

The official prompt guide does not state the local frame grid, area cap, or model-specific silent
NaN ceiling. Project evidence currently shows:

| Mode | Recorded evidence |
| --- | --- |
| T2VA | valid 107-, 192-, and 243-frame outputs; ceiling unknown |
| I2VA | valid 107- and 192-frame outputs |
| FL2VA | 277-frame ceiling in one graph/profile; higher runs produced silent all-black output |
| L2VA | prompt format known; local production ceiling uncalibrated |
| Ref2VA | input/prompt/runtime contract known; local production profile uncalibrated |

Record the mode and runtime fingerprint with every limit. Probe untried configurations and verify
pixels rather than treating a successful submission or decode as proof.

## 8. Keep Ref2VA separate from base modes

The official Ref2VA format replaces the base three fields with six sections in order:
`subject_definitions`, `summary`, `retention_analysis`, `detailed_description`,
`overall_soundscape`, and `non_diegetic_music`. It uses stable `<Subject N>`, `<Picture N>`,
`<Video N>`, and `<Audio N>` labels plus explicit task types and preservation relationships.

Ref2VA also uses a distinct transformer and conditioning node. General reference images are not
base-model endpoint images; conversely, exact first/last-frame work should not be moved to Ref2VA
without a reference-generation reason. Read `ref2va_prompt_mode.md` for the complete routing,
inventory, prompt, ComfyUI, and acceptance contract.
