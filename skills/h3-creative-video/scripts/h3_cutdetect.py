#!/usr/bin/env python3
"""Hard-cut detection — where did the picture actually cut?

WHY THIS ONLY REPORTS ISOLATED NARROW SPIKES:

  The obvious implementation — "count frames whose diff exceeds 5x the median" —
  is wrong. It once reported 19 cuts for a clip whose "cuts" were a single
  continuous push-in plus a head turn, and nearly caused the wrong seed to be picked.

  A real hard cut is an ISOLATED NARROW SPIKE: 1-2 frames far above median with both
  sides falling quiet. Nineteen CONSECUTIVE over-threshold frames prove the opposite —
  that it is sustained motion, not a cut. Counting alone inverts the conclusion.

KNOWN BLIND SPOT — do not exceed it:

  This CANNOT see dissolves. In near-static clips the model's self-invented
  transitions are gradual, and this reports 0 while a transition plainly exists.

  >>> "0" DOES NOT MEAN "ONE CUT". <<<
  Whether the model added a shot is settled by eye, on a filmstrip. This tool only
  locates hard cuts precisely; it does not replace the human pass.

Relative thresholds are also not comparable between clips with different motion
levels — read the reported median before comparing two clips' spike counts.

usage: h3_cutdetect.py <video.mp4> [...]
"""
import sys

import av
import numpy as np

FPS = 24
SPIKE = 5.0   # spike must exceed median * SPIKE
QUIET = 1.5   # neighbours must fall below median * QUIET
WING = 3      # frames examined on each side


def diffs(path):
    c = av.open(path)
    prev, out = None, []
    for f in c.decode(video=0):
        a = np.asarray(f.to_image().convert("L").resize((92, 164)), dtype=np.float32)
        if prev is not None:
            out.append(float(np.abs(a - prev).mean()))
        prev = a
    c.close()
    return np.array(out)


for p in sys.argv[1:]:
    d = diffs(p)
    if len(d) < 2 * WING + 1:
        print(f"{p}: too short")
        continue
    med = float(np.median(d))
    hi, lo = med * SPIKE, med * QUIET

    cuts = []
    for i in range(WING, len(d) - WING):
        if d[i] < hi:
            continue
        left, right = d[i - WING:i], d[i + 1:i + 1 + WING]
        # allow one adjacent frame to stay high: a cut can straddle 2 frames
        if (left < lo).sum() >= WING - 1 and (right < lo).sum() >= WING - 1:
            cuts.append((i, float(d[i])))

    print(f"{p.split('/')[-1]}")
    print(f"   median={med:.2f}  frames over threshold={int((d > hi).sum())}  "
          f"-> isolated spikes={len(cuts)}")
    for i, v in cuts:
        print(f"      cut @ {i/FPS:.2f}s  magnitude={v:.1f} ({v/med:.0f}x median)")
    if not cuts:
        print("      (no isolated spike; over-threshold frames are sustained motion, not cuts)")
        print("      NOTE: dissolves are invisible here — confirm on a filmstrip.")
