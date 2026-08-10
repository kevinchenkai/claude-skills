# T2VA Prompt-Only Mode

Use this reference when the user provides text and no endpoint image. T2VA builds the complete
audiovisual timeline from text; it is not FL2VA with missing assets.

## Contents

1. Routing contract
2. Source-prompt handling
3. Exact official structure
4. Timeline and dialogue rules
5. Runtime wiring
6. Acceptance
7. Project evidence and unknowns

## 1. Routing contract

Select T2VA when there are zero first/last-frame images and the user wants prompt-driven video.
Do not generate images unless the user separately requests a switch to an image-conditioned mode.
Do not add any Picture alignment text.

If the user mentions images only as things that should appear in the scene (for example, “a framed
photo on the wall”), that is still T2VA. Endpoint/reference assets are actual attached or local
conditioning files, not nouns inside the prompt.

## 2. Handle the source prompt without losing intent

Classify the input:

- **Already official:** starts with `integrated_multimodal_description:` and contains the three
  fields in order. Preserve it byte-for-byte after validation unless optimization was requested.
- **Detailed prose:** extract a requirement matrix, then rewrite into the three official fields.
- **Short brief:** expand only enough to create a visible/audible timeline; surface material choices.

Always preserve verbatim:

- dialogue and lyrics, including punctuation and language;
- visible signs, captions, labels, or other on-screen text;
- named people/objects, exclusions, shot count, requested cuts, and duration constraints.

Write rewrite sections in English while retaining dialogue, lyrics, and visible scene text in their
original language. Keep both source and rewritten prompt hashes in the manifest.

## 3. Use the exact official structure

T2VA begins directly with the three fields—no preamble and no blank alignment slot:

```text
integrated_multimodal_description: [Shot 1] <style, initial composition, subject, environment,
visible actions, camera, dialogue/singing, diegetic sound, and later shot transitions>

overall_soundscape: <1–4 English sentences covering ambience, physical sounds, and non-verbal
human sound; use N/A only for explicitly complete silence>

non_diegetic_music: <1–3 English sentences describing instrumentation, tempo, rhythm, and dynamics;
use N/A when there is no audience-only score>
```

Do not insert any of these T2VA-invalid forms:

- `How the reference pictures align ...`
- `For the target video ... <Picture 1> ... fully referenced.`
- `<Picture 1>` / `<Picture 2>` endpoint references.

## 4. Write the audiovisual timeline

- Start `[Shot 1]` without a timestamp; state style and initial composition.
- Number later shots sequentially. Start each with `[Shot N] At 00:MM.SSS,` using strictly
  increasing times inside the requested duration.
- Make every cut introduce new subject, space, state, viewpoint, or time. Prefer camera motion when
  only distance or a slight angle changes.
- Write camera motion as a natural action. Add amplitude/speed only when meaningful.
- Give each speaking/singing voice a stable `(S1)`, `(S2)`, etc.; do not label silent characters.
- Put only the exact line inside `<d>[Language] ...</d>`. Do not translate or improve it.
- For voiceover, use `says in an off-screen voiceover` and state that the visible character's lips
  remain closed.
- Use `<scenetrans>` where a line crosses a cut and state that audio continues. Use `<cutoff>` when
  speech is truncated by the end.
- Put visible text in English double quotation marks while preserving its original characters.
- Keep dialogue/singing/diegetic music in `integrated_multimodal_description`; do not duplicate it
  in `overall_soundscape` or `non_diegetic_music`.

Run:

```bash
python scripts/h3_prompt_lint.py prompt.txt --mode t2va --duration <seconds> --json
```

## 5. Enforce zero-image runtime wiring

In the recorded ComfyUI graph, T2VA uses `MiniMaxH3ImageToVideo` with the `fl2va` checkpoint but
omits both optional image inputs. “fl2va checkpoint” does not mean the prompt is FL2VA.
The official reproducible API request expresses the same contract as `"task": "t2va"` with an
empty `"conditions": []` array.

Require all of the following before submission:

1. config declares T2VA or otherwise selects the zero-image code path;
2. `start_img`/`end_img` or `first_frame`/`last_frame` keys are absent or null as required by the
   actual runner;
3. no `LoadImage` node feeds the conditioning node's endpoint inputs;
4. the prompt contains no image-alignment declaration;
5. the mode/shape/frame combination has a valid probe for the current runtime profile.

Never satisfy a runner that expects an image by inserting a blank or arbitrary placeholder. Fix or
select the T2VA graph instead.

## 6. Accept against the user's prompt

Create a requirement matrix before generation:

| Requirement | Timeline/shot | Evidence method |
| --- | --- | --- |
| subject, environment, object, visible text | specified shot | full-resolution frame(s) |
| action, reaction, camera motion | time range | filmstrip/video review |
| cut/transition | timestamp | cut detector plus eye review |
| dialogue, voiceover, sound, score | time range/full work | human ear; metrics only for presence |
| exclusion | full work | full-resolution and temporal review |

Without endpoint images, inspect identity, wardrobe, object persistence, and spatial continuity at
every shot transition. Tail activity is a hard gate only when the work order declares continued
motion at the end; an intentionally held ending is not automatically a failure.

## 7. Keep project evidence in scope

The recorded project successfully ran:

- a 107-frame, 1344×768 T2VA wiring probe with valid pixels and stereo audio;
- a 243-frame, 1344×768 reproduction of the official Space Captain T2VA case;
- a 192-frame T2VA production in the same inference family.

This proves the zero-image path, not a general maximum duration. The FL2VA 277-frame silent-black
ceiling has not been established for T2VA. Probe new frame counts instead of copying that limit.

FL2VA findings about keyframe realism, last-frame pose, camera interpolation, and ending wording
are not T2VA findings. Re-test them in paired T2VA samples before treating them as proven or
disproven.
