# H3 Acceptance

Read before production to declare gates, and when reviewing a result. Metrics exclude known
failures; they do not prove quality. Calibrate new numeric criteria on known-good and known-bad
material. Prefer independent final review; disclose self-acceptance if it is unavoidable.

## Declare requirements before outputs exist

Record mode, expected frames/dimensions/fps, audio policy (required/optional/forbidden), scorecard,
and every hard requirement. Use `pass`, `fail`, or `not verified`, with timestamp and evidence:

| Requirement | Evidence |
| --- | --- |
| Subject, appearance, environment, objects, exact visible text | Full-resolution frames |
| Actions, expressions, camera, continuity, exclusions | Temporal/video review plus full-resolution frames |
| Requested cuts | Detector plus eye confirmation around each intended cut |
| Exact words/speaker, sound, instrumentation, music | Listening; metrics only establish stream presence/energy |
| Endpoint alignment or Ref2VA relationships | Actual input wiring plus role-specific content review |

T2VA has no endpoint-similarity gate. Check identity, wardrobe, objects, and spatial relationships
across its cuts. Endpoint modes additionally verify that the accepted images reached the right
inputs. For Ref2VA, read its mode reference and retain one acceptance row per declared reference
role; familiar appearance alone cannot establish a promised edit, anchor, or copied-audio relationship.

Tail activity is a gate **only** when continued motion is requested. Before declaring or measuring
motion/cut gates, read the relevant section of [acceptance_diagnostics.md](acceptance_diagnostics.md).
Record tail window, ratio, absolute floor, per-frame freeze threshold and terminal-duration limit;
for cuts record expected times/tolerance. Do not adopt helper defaults as universal truth.

## Pixel and stream gate

Check expected dimensions/frame count/fps, decodable nonempty video, zero blank frames, and no
video NaN. Enforce the declared audio policy; required audio needs samples, no NaN, RMS above the
calibrated silence floor, and A/V duration difference within tolerance.

```bash
python scripts/h3_verify.py output.mp4 \
  --expected-frames 277 --expected-width 736 --expected-height 1312 \
  --audio required --min-audio-rms 0.000001 --max-av-drift 0.25 --json
```

Values are examples from a recorded profile. Verify actual fps from stream metadata as well.
Use the history's exact output path and stable hash. `status=success` and correct frame count can
coexist with all-black output. Invalid pixels/streams block content acceptance; retain the reason.

## Visual and audio review

For every decodable clip, build a filmstrip and inspect failing regions even after a numeric gate
fails. Review the intended state transition, invented shots/objects/actions/expressions, continuity
across cuts, identity during motion, and the actual subject's ending. Background/hair movement
cannot prove the subject is still moving. Then inspect full-resolution faces, hands, proportions,
texture, edges, and small continuity details; thumbnails are insufficient.

Listen according to the declared audio policy:

- Native audio: exact speech/lyrics, speaker, instrumentation, ambience, unwanted voices, artifacts,
  timing and musical resolution.
- Segmented/post-produced audio: each edit's timing, loudness, ambience, phase and musical continuity;
  record source and edit method.
- Ref2VA: validate copy versus reference using its declared source region, trims/mix, and role rules.
- Silence: distinguish intended silence from a failed stream.
- Out of scope/unreviewed: state it; do not mark audio accepted.

RMS/spectral features cannot identify an instrument or prove requested words. If listening or
visual inspection is unavailable, leave the relevant requirements `not verified`.

## Decision and comparison

Stop granting delivery eligibility on a hard failure, but continue enough diagnosis to route the
next iteration within scope/budget. Use exactly one status:

- **Accepted delivery:** every declared hard technical and semantic gate passed.
- **Creative prototype:** reviewable, but a gate failed or remains unverified.
- **Invalid output:** corrupt, blank, missing, or unusable.

For creative production, compare against the prewritten scorecard; paired seeds help when budget
permits, but do not claim a bundled change proves one cause. For causal experiments, read the
paired-seed and noise-floor procedure in [known_findings.md](known_findings.md#causal-comparison).
Store results, measurement settings, review artifacts, limitations and negative findings with the
execution manifest. No score or successful script substitutes for semantic acceptance.
