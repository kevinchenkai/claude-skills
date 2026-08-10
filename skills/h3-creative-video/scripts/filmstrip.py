#!/usr/bin/env python3
"""Contact sheet — the input for the human-eye pass.

Every numeric criterion measures kinematics. None of them asks whether the shot
performed the thing you wrote. A shot that tilted up to stare at the ceiling once
passed all five numeric checks; the filmstrip is what caught it.

What to look for:
   Orientation — eye-level means eye-level; "from behind" means no face
   Framing     — must match the keyframe, or the model added a cut of its own
   Action      — "keeps walking" must not become "stands still"
   Shot count  — more cuts than designed means the model improvised

usage: filmstrip.py <video.mp4> <out.jpg> [cells=7]
"""
import sys

import av
from PIL import Image

src, out = sys.argv[1], sys.argv[2]
n_cells = int(sys.argv[3]) if len(sys.argv) > 3 else 7

c = av.open(src)
frames = [f.to_image() for f in c.decode(video=0)]
c.close()

n = len(frames)
idx = [int(n * k / (n_cells - 1)) for k in range(n_cells - 1)] + [n - 1]

w, h = 200, 356
strip = Image.new("RGB", (w * len(idx), h))
for i, k in enumerate(idx):
    strip.paste(frames[k].resize((w, h)), (i * w, 0))
strip.save(out, quality=92)

secs = ", ".join(f"{k/24:.1f}s" for k in idx)
print(f"wrote {out}  帧数={n}  采样点: {secs}")
