# Motion and Cut Diagnostics

Read only when declaring/measuring a motion or cut gate, or diagnosing a suspect result.
Choose the relevant section; defaults are calibrated examples, not universal thresholds.
Routine delivery gates are in [acceptance_criteria.md](acceptance_criteria.md).

## Contents

- Tail activity: ratio, absolute floor, terminal location, subject versus background
- Cuts: isolated spikes, dense-cut filtering, straddled-frame confirmation

## Tail activity only when the brief requires it

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

## Cut detection and its blind spot

A hard cut is an isolated narrow frame-difference spike with quiet neighbors. Counting every frame
above a relative threshold misclassifies sustained motion as many cuts.

```bash
python scripts/h3_cutdetect.py output.mp4 \
  --expected-cut 6.50 --tolerance 0.25 --json
```

Log written versus detected cut time. Do not calibrate a systematic offset until several comparable
samples agree. The detector cannot see dissolves, so zero hard cuts does not prove a single-shot
video. Inspect the filmstrip and the region around every intended cut.

### The quiet-neighbor filter under-reports densely cut work

The "isolated spike with quiet neighbors" rule is calibrated on slow-paced material. **On a densely
cut passage the neighbors are not quiet, so real cuts are filtered out.**

Recorded case: an 8-shot, 12.25s clip reported **5 of 7** cuts and was declared a failed cut gate.
The tool's own JSON showed `"frames_over_threshold": 7` beside a 5-entry `cuts` list — **detection
found all seven; the `quiet_multiplier` filter discarded the two in the fastest passage (1.42s and
2.96s, where cuts were 1.5s apart).** Re-measured, the schedule was **7/7 within 0.14s**. The
output was correct; the criterion was not.

**The bundled detector now admits a spike that towers over its neighbourhood (`--dominance`,
default 8×) even when the neighbours are not quiet**, which fixes both directions of this failure.
Calibrated on known material: it recovers a 53.7× cut whose *incoming* shot ran at 2.8× median
(previously dropped, and previously only recoverable by loosening `--quiet` enough to admit 14 false
positives), recovers the two dense-passage cuts above, and still reports **zero** cuts on a verified
single-shot clip.

Guard against this regardless of tool version:

- Read `frames_over_threshold` alongside the final list. **A filtered count lower than the detected
  count is a signal to inspect, not a result to report.** `cuts_admitted_by_dominance` names the
  cuts that only survived because of the dominance rule.
- When the work order specifies cuts closer together than the detector's quiet window, treat the
  quiet-neighbor rule as **out of calibration** and confirm each expected cut by eye.
- Report "N of M cuts detected" only after checking whether the missing ones were filtered rather
  than absent.
- **Confirm the tool you are running is the one this document describes.** A project copy that has
  drifted from the bundled script may lack `--json`, `frames_over_threshold`, and the dominance
  rule entirely — in which case none of the guidance above is executable.

### Confirming a spike is a real cut — straddle it

To test whether a spike at frame `f` is a genuine scene change, **do not compare `f-1` with `f`**.
The spike means the change lands *on* `f`, so that pair sits inside the transition and can look
almost identical — a recorded review nearly concluded seven real cuts were "not real cuts" this way.

Compare **across** the spike (`f-3` vs `f+2`) and calibrate the magnitude against a **known-real cut
from comparable material**, not against an absolute number. In the recorded case the straddled
differences were 73–99 versus 69–85 for verified cuts — same magnitude, confirming all seven.

> This is the anti-pattern the whole reference warns about, applied to a verification method:
> **the method you use to check a criterion is itself a criterion, and needs its own
> known-good/known-bad calibration.**

