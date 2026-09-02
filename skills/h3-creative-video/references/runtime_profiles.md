# Recorded H3 Runtime Profiles

Consult when selecting generation settings, probing, or diagnosing shape/length failures. These
are historical project observations, not a live host inventory or universal model limits. Verify
checkpoint/graph/launch fingerprints against the project's actual manifest before reuse; update
this record only from identifiable evidence. Official source revisions live in `official_h3_guide.md`.

## Base profile and evidence

Recorded common settings: 24 fps, `n % 17 == 5`, width/height divisible by **16**, area at most
**1032192**. Check requested and delivered dimensions/frames: the node can silently alter them.

| Mode | Recorded valid runs | Boundary |
| --- | --- | --- |
| T2VA | 107-frame 1344×768 wiring probe; 192-frame production; 243-frame 1344×768 Space Captain reproduction; 277-frame 1344×768 at 30 steps; 294-frame 1280×720 eight-shot production | Maximum unknown; the 294 case exceeds the FL2VA ceiling |
| I2VA | 107-frame wiring probe; 192-frame official reproduction | Do not infer FL2VA tail behavior |
| FL2VA | Up to 277 frames; higher runs produced silent all-black output | Ceiling belongs to that graph/profile only |
| L2VA | Official prompt format known | Local production profile not calibrated in the inherited evidence |
| Ref2VA | Official/node contract documented at the recorded revisions | No portable creative/ceiling calibration; use current project evidence or probe the exact mix |

The T2VA 294-frame case had seven cuts within 0.14s; the Space Captain cut was within 0.167s.
These observations do not establish a universal timing tolerance. Ref2VA runtime details belong
in `ref2va_prompt_mode.md`, not in the base-mode ceiling table.

## Solve dimensions from the brief

`1344×768` is 1.75:1, not 16:9. A request for `1344×756` produced `1344×752` without error.
Under this area/alignment profile, **1280×720** is the largest exact 16:9 shape; do not test one
height and declare the ratio impossible. Enumerate legal multiples, then declare the dimension
gate before generation and check the delivered stream. Alignment to 32 would reject valid shapes.
The silent round-down is the same failure family as silent NaN: `status=success`, valid pixels and
audio, and a number that is simply wrong. Enumerate the whole space rather than one height:

```python
W_RATIO, H_RATIO = 16, 9          # the brief's requested aspect ratio
AREA_MAX = 1032192                # recorded profile cap
for w in range(512, 1601, 16):
    h = w * H_RATIO // W_RATIO
    if h % 16 == 0 and w * H_RATIO == h * W_RATIO and w * h <= AREA_MAX:
        print(w, h, w * h)
```

Under this profile the complete 16:9 set is **512×288 · 768×432 · 1024×576 · 1280×720**.

## Historical host example

`vscode`: GPU0 → port 8189, GPU1 → 8190; code `/home/jovyan/code/src`, Python
`/nfs/envs/comfyui/bin/python3.11`. These are discovery hints, not values to assume. Resolve each
PID's launch flags and GPU binding before comparing lanes. Attention-kernel differences invalidate
single-factor comparisons even when the ComfyUI version matches.

Probe every untried mode/shape/frame combination at low steps and verify pixels/audio. Revalidate
after model, node, graph, or launch changes. Stagger lanes only when measured memory overlap
requires it; the historical ~70-second offset is not universal.
