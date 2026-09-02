# H3 Prompt Authoring

This is the maintained base-template and shared-notation reference. Ref2VA uses its own six-section
template in [ref2va_prompt_mode.md](ref2va_prompt_mode.md), plus the shared rules below. Official
provenance is in `official_h3_guide.md`; read it only for source audits or convention changes.

## Base openings and fields

T2VA starts on physical line 1 with `integrated_multimodal_description:`. For the other base modes,
use the exact corresponding instruction below, then one blank line before the same three fields.
Substitute the actual final shot for `N` and effective duration to two decimals for `S.SS`.

I2VA:

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
```

FL2VA:

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.
```

L2VA:

```text
How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.
```

Shared base body, in this exact order:

```text
integrated_multimodal_description: [Shot 1] <style, composition, subjects, environment, visible actions, camera, dialogue/singing, synchronized sound, later shots>

overall_soundscape: <ambience, physical sounds, non-verbal human sound>

non_diegetic_music: <audience-only score, or N/A>
```

Develop I2VA forward from the first frame; connect FL2VA's two states through intermediate changes;
lead L2VA from a plausible earlier state into its last-frame landing. Official FL2VA guidance favors
one continuous shot unless multiple shots are explicitly specified. The project's explicit
multi-shot use for competing actions/required reframing is a scoped deviation, not a T2VA rule.

## Shared timeline and sound

- Start `[Shot 1]` without a timestamp. Number later shots sequentially with strictly increasing
  times inside the effective duration: `[Shot 2] At 00:03.500, ...`.
- Give each shot one primary state transition; secondary hair/fabric/weather motion can coexist.
  Cuts should add subject, space, state, viewpoint, or time. Prefer camera movement for a small
  distance/angle change. State camera actions naturally, with speed/amplitude when meaningful.
- Assign stable `(S1)`, `(S2)`, etc. only to speakers, singers, and off-screen voices. Identify the
  voice outside `<d>[Language] exact user text</d>`; preserve dialogue/lyrics and punctuation.
- For voiceover, use `says in an off-screen voiceover` and state immediately that visible lips
  remain closed. Use `<scenetrans>` where speech crosses a cut and explicitly continue the audio;
  use `<cutoff>` for speech truncated by the ending.
- Quote visible signs/captions in English double quotation marks, preserving their original text.
- Put timed speech, singing, radio/TV/phone music, and synchronized sounds in the visual timeline
  (`integrated_multimodal_description` for base modes; `detailed_description` for Ref2VA).
- `overall_soundscape`: one paragraph of 1–4 English sentences for ambience, physical action,
  and non-verbal human sounds. Use `N/A` only for explicitly complete silence.
- `non_diegetic_music`: 1–3 English sentences naming instrumentation, tempo, rhythm, and dynamics;
  `N/A` means no audience-only score. Do not duplicate dialogue or diegetic music here.

## Style, ending, and validation

Honor stylization when requested. For lifelike work, use concrete photographic facts (uneven
available light, moderate depth, imperfect texture, candid framing) instead of quality tags such as
`masterpiece` or `8k`. T2VA relies on prompt/seed for visual conditioning; repeat stable visible
attributes across transitions as needed. Endpoint modes additionally depend on image quality.
FL2VA failures of realism/camera wording do not ban those controls in T2VA.

Accept an intentional hold as a valid ending. For required continued action, avoid an early
semantic endpoint and describe the ongoing state; endpoint composition must also afford it when
a last frame exists. Neither an unfinished verb nor moving background guarantees subject motion.

Validate base prompts before submission:

```bash
python scripts/h3_prompt_lint.py prompt.txt --mode <mode> --duration <effective-seconds> --json
```

Resolve lint errors; inspect warnings. Lint cannot prove user-intent preservation or content
quality. Compare source requirements separately, measure actual cut times when required, and
listen to verify words, speaker, instrument, timing, unwanted voices, and musical resolution.
