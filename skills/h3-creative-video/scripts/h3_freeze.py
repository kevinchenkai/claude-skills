#!/usr/bin/env python3
"""Tail-freeze detection — does the ending keep moving, or did it land early?

WHY BOTH A RATIO AND AN ABSOLUTE FLOOR:

  Tail activity = mean frame-diff over the last 2s / median frame-diff of the clip.
  That ratio SELF-NORMALIZES, so a uniformly slow clip passes while visibly frozen.

  Measured:
    known-good  median 2.74   tail abs 2.31   ratio 0.84  -> genuinely moving
    known-bad   median 0.41   tail abs 0.20   ratio 0.50  -> PASSES the 0.40 line, but
                                                             its tail moves 1/11 as much
  The denominator collapsed. Hence: ratio AND absolute, both.

  Freeze onset uses an ABSOLUTE threshold for the same reason — a relative one
  shrinks with the clip and understates a real freeze. Frozen frames sit far below
  normal motion (0.01-0.05 vs a 0.7-2.7 median), so the threshold is not delicate.

CALIBRATE THE FLOORS ON YOUR OWN SAMPLES before trusting them; the defaults come
from one project's known-good/known-bad pair.

usage: h3_freeze.py <video.mp4> [...]
"""
import sys

import av
import numpy as np

FPS = 24
TAIL_SEC = 2.0
RATIO_LINE = 0.40   # relative: tail mean / clip median
ABS_LINE = 1.00     # absolute: tail mean frame-diff
FREEZE_ABS = 0.30   # below this a frame counts as frozen


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
    if len(d) == 0:
        print(f"{p}: no frames")
        continue
    med = float(np.median(d))
    tail = d[-int(TAIL_SEC * FPS):]
    tail_abs = float(tail.mean())
    ratio = tail_abs / med if med > 0 else 0.0

    i = len(d) - 1
    while i >= 0 and d[i] < FREEZE_ABS:
        i -= 1
    frozen = len(d) - (i + 1)

    ok = ratio >= RATIO_LINE and tail_abs >= ABS_LINE
    print(f"{p.split('/')[-1]}")
    print(f"   median={med:.2f}  tail_abs={tail_abs:.2f} (line {ABS_LINE})  "
          f"ratio={ratio:.2f} (line {RATIO_LINE})   {'OK' if ok else 'FAIL'}")
    print(f"   freeze: {frozen/FPS:.2f}s at the end"
          f"{'' if frozen == 0 else f' (from {(i+1)/FPS:.2f}s)'}")
    if ratio >= RATIO_LINE and tail_abs < ABS_LINE:
        print("   ^ ratio passed but absolute failed: the whole clip is slow. Trust the absolute.")
