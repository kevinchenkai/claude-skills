# Acceptance Criteria

Metrics only exclude known failures; they do not prove that a video is good. Calibrate every new
criterion on known-good and known-bad material before turning it into a delivery gate.

## Contents

1. Delivery gating versus diagnosis
2. Mode and measurement profile
3. Pixel and stream validity
4. Tail activity and terminal full-frame freeze
5. Cut detection
6. Prompt-requirement coverage
7. Human-eye pass
8. Human-ear pass
9. Version comparison modes
10. Delivery status and evidence

## 1. Separate delivery gating from diagnosis

| Layer | Delivery consequence | Diagnostic consequence |
| --- | --- | --- |
| Pixels/streams fail | classify as **Invalid output** and stop content acceptance | record the exact invalid condition; do not infer creative quality |
| Numeric gate fails | block **Accepted delivery** | still build a minimum filmstrip and inspect the failing region |
| Eye or ear gate fails | block **Accepted delivery** | describe what actually happened and route the correct layer |

“Stop at the first failure” means stop granting delivery eligibility. It does **not** mean discard
the evidence needed to understand the failure. Never skip the minimum human-eye review for a
decodable clip.

## 2. Declare conditioning mode and profile before measuring

Write the conditioning mode, expected frame count, dimensions, fps, audio policy, tail window,
tail ratio line, absolute activity floor, per-frame freeze threshold, maximum terminal
**full-frame** freeze duration, expected cut times, and cut tolerance. Store these values with the
measurement output.

The helper defaults come from one project and are examples, not portable truth.

For T2VA, also record `endpoint images: none` and validate that the graph omitted both image
conditions. Do not require keyframe similarity or alignment checks. For I2VA/L2VA/FL2VA, verify the
declared endpoint images actually reached the corresponding graph inputs.

## 3. Pixel and stream validity

Require according to the declared profile:

- expected frame count and dimensions;
- zero blank frames, no video NaN, and a decodable non-empty video stream;
- audio required, optional, or forbidden as specified before generation;
- when audio is required: non-empty samples, no NaN, RMS above the calibrated silence floor, and
  A/V duration difference within tolerance.

Example:

```bash
python scripts/h3_verify.py output.mp4 \
  --expected-frames 277 --expected-width 736 --expected-height 1312 \
  --audio required --min-audio-rms 0.000001 --max-av-drift 0.25 --json
```

ComfyUI `status=success` is not media validity. Silent all-black runs have reported success and
decoded to the expected frame count. Files may also appear late on shared storage: use the task
history's exact output path, wait until it is readable, then hash and decode it.

## 4. Apply tail activity only when the brief requires it

Tail activity is not a universal quality gate. An intentionally held or resolved T2VA ending may
be correct. Declare this gate before generation only when the prompt requires continued whole-frame
or subject motion through the end.

Measure three distinct properties:

1. tail activity ratio = mean frame difference over the tail window / clip median;
2. absolute tail activity = mean frame difference over the tail window;
3. terminal full-frame freeze duration = consecutive time at the exact end below the absolute
   per-frame threshold.

All declared gates must pass. A ratio alone can pass a uniformly slow clip because its denominator
collapses. Conversely, high absolute activity can come from hair, fabric, camera noise, or invented
content while the subject has already settled. The freeze-duration gate only detects whole-frame
stillness. The eye check—or a separately calibrated subject ROI metric—answers whether the intended
subject and action continued.

Do **not** take the longest low-motion run across the whole clip and call it tail freeze. In the V3
counterexample, reported 2.12s/1.04s “freeze” intervals were actually the intentionally quiet
opening at 0–2.12s/0–1.04s. Restrict a plateau analysis to a predeclared final-shot/subject region,
or leave that claim to human review until a valid ROI metric exists.

Example using the current project's calibrated defaults:

```bash
python scripts/h3_freeze.py output.mp4 \
  --tail-sec 2 --ratio-line 0.40 --abs-line 1.0 \
  --freeze-abs 0.30 --max-freeze-sec 1.0 --json
```

Report failed endings plainly as `terminal full-frame freeze: 0.67s`; do not soften them into “a
low-motion segment under/around one second.” Confirm by eye whether the measured movement belongs
to the intended subject and action.

## 5. Cut detection and its blind spot

A hard cut is an isolated narrow frame-difference spike with quiet neighbors. Counting every frame
above a relative threshold misclassifies sustained motion as many cuts.

```bash
python scripts/h3_cutdetect.py output.mp4 \
  --expected-cut 6.50 --tolerance 0.25 --json
```

Log written versus detected cut time. Do not calibrate a systematic offset until several comparable
samples agree. The detector cannot see dissolves, so zero hard cuts does not prove a single-shot
video. Inspect the filmstrip and the region around every intended cut.

## 6. Check prompt-requirement coverage

For T2VA, turn the user's detailed source prompt into a pre-generation matrix of independently
reviewable requirements: subject/environment, appearance, objects, actions, shot/camera changes,
visible text, dialogue/voiceover, sound/music, and exclusions. Record each as pass, fail, or not
verified with a timestamp and evidence method.

Do not mark a requirement green merely because related content appears. For example, “audio stream
exists” does not verify the requested words, speaker, or instrument. In image-conditioned modes,
apply the same matrix in addition to endpoint alignment.

## 7. Human-eye pass

Use a filmstrip to ask:

1. Can a reviewer retell the intended state transition?
2. Did the model invent a close-up, shot, expression, object, or action?
3. Does the intended subject continue through the ending, or do only background details move?
4. Does anything pop at a cut: identity, proportion, wardrobe, framing, or background?
5. Is identity stable during large motion?
6. For T2VA, do appearance, wardrobe, objects, and spatial relationships persist across every cut?

Then inspect full-resolution frames for face, hands, texture, edge artifacts, and small continuity
details. The filmstrip is a temporal summary, not a substitute for full-resolution inspection.

## 8. Human-ear pass

Apply the declared audio policy:

- **Native audio:** listen for requested instrumentation, ambience, dialogue, unwanted speech,
  artifacts, and whether the score resolves against the intended ending.
- **Post-produced continuous audio:** listen across every edit for timing, loudness, ambience, phase,
  and musical discontinuity; document the source and edit method.
- **Silent:** verify that silence is intentional rather than a failed stream.
- **Out of scope:** state that audio was not accepted; do not mark it green.

Spectral features and RMS can establish that audio exists. They cannot identify an instrument or
judge whether the sound suits the work.

## 9. Compare versions according to work mode

### Causal experiment

- Assert one config difference and keep prompts byte-identical except for the declared variable.
- Keep conditioning mode and endpoint wiring identical unless mode itself is the declared variable.
- Use paired seeds: the same seeds on control and treatment.
- Establish the same-prompt seed noise floor before attributing an effect.
- Require both paired seeds to agree in direction and exceed that noise floor.

If the seeds disagree, report instability/noise—not a win.

### Creative production

Allow a user-approved bundle of changes. Compare candidates against the prewritten scorecard,
show paired seeds when budget permits, and choose a work. Do not attribute the result to a single
prompt phrase, keyframe detail, or parameter.

## 10. Delivery status and evidence

Use one status:

- **Accepted delivery:** all declared hard gates pass.
- **Creative prototype:** useful for creative review but one or more technical gates fail.
- **Invalid output:** corrupt, blank, missing, or unusable.

Record what passed, failed, could not be verified, and remains known-risk. Preserve runtime profile,
conditioning mode, source/final prompt hashes, optional input hashes, config diff, seeds, prompt
IDs, output hashes, JSON measurements, filmstrips, full-resolution observations, and audio decision.
