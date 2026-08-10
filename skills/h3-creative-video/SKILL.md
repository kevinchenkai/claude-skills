---
name: h3-creative-video
description: Use when creating short creative videos with MiniMax-H3 on a remote GPU box over SSH — designing the concept, writing FL2VA prompts (official three-field format, multi-shot [Shot N] syntax, first/last-frame keyframes), ordering keyframe images from an image generator, running ComfyUI generation, and accepting the result. Covers the six-stage pipeline (environment precheck, creative + technical feasibility, project scaffold and work order, keyframe generation, video generation, acceptance and delivery), the hard model limits (FL2VA frame ceiling, 17k+5 frame grid, area cap, silent NaN), photoreal "de-AI" image specs, and the calibrated acceptance criteria (pixel validity, tail-freeze, cut detection, filmstrip human review). Use for requests like "make a 15-second vertical video of X", "generate a creative video with H3", "the ending freezes", "the face looks AI-generated", or "review this H3 output".
---

# H3 Creative Video

Produce a short creative video with **MiniMax-H3 FL2VA** (first-and-last-frame → video)
on a remote GPU host, from concept to accepted deliverable.

> **This skill encodes what is *hard-won and non-obvious*: model limits, dead ends already
> disproven, and criteria that have been calibrated in both directions.**
> It deliberately does **not** prescribe implementation minutiae — tune those from observed
> output. When this document and a measurement disagree, **measure again, then trust the
> measurement and update this document.**

## When To Use

- "Make a 15-second vertical video of …" / "generate a creative video with H3"
- Writing or reviewing an **FL2VA prompt** (three-field format, `[Shot N]` cuts, keyframe alignment)
- Ordering **first/last keyframes** from an image generator for a video
- Diagnosing H3 output: **ending freezes**, **face looks AI**, **model invented a shot**, **all-black frames**
- Accepting an H3 deliverable, or auditing someone else's acceptance report

## Two Execution Modes

| Mode | Who does what |
| --- | --- |
| **Codex solo** | Codex runs all six stages: precheck → concept → scaffold → **keyframes via its own image generation** → video over SSH → acceptance → delivery. Self-acceptance **must** run the bundled scripts **and** a human-eye pass; `status=success` is not acceptance. |
| **Claude + Codex** | **Codex generates the keyframe images only.** Claude does everything else: concept, work order, video generation, acceptance, delivery. |

> 🔴 **Prefer separating generation from acceptance whenever both agents are available.**
> Real case: the generating agent reported a 0.7–1.0 s freeze as "a low-motion segment
> under 1 second". The numbers were right; the wording understated it. An independent
> reviewer caught it. **Whoever generated it should not sign off on it alone.**

## Required Inputs

Normalize before doing anything:

- **Subject / mood / setting**, and any character reference images
- **Orientation and target duration** — then immediately reconcile against §Hard Limits
- **Realism or stylized** — this is a fork, not a dial (see `references/prompt_authoring.md`)
- **SSH host + ComfyUI ports**, and whether to execute now or plan first

If duration or aspect ratio conflicts with the hard limits, **say so before designing**, not after.

## 🔴 Hard Limits (check these before writing a single line of prompt)

| Limit | Value | Failure mode if violated |
| --- | --- | --- |
| **FL2VA frame ceiling** | **277 frames** | Above it: **silent NaN** — reports `success`, decodes fine, **every pixel 0** |
| **Frame grid** | `n % 17 == 5` | Off-grid counts are rejected or snapped |
| **Area cap** | `width × height ≤ 1032192`, both multiples of 16 | Submission failure |
| **fps** | 24 → `seconds = frames / 24` | Alignment line must match, 2 decimals |

**277 frames = 11.54 s is the longest single FL2VA generation.** Anything longer needs
segment concatenation, and **concatenated audio always breaks at the seam** — prompts
cannot fix that. Say this out loud during concept, not after the user is attached to a number.

> **Any untried resolution or frame count: run a low-step probe first** (a few minutes)
> to prove it doesn't NaN, before spending ~45 min/clip at full settings.

## Operating Rules

1. **Verify pixels, always.** `status=success` ≠ valid frames. Check blank-frame count and NaN.
2. **Criteria fail more often than outputs do.** In this project criteria were wrong 6+ times,
   finished clips 0 times. A FAIL gets re-checked; **so does a PASS**.
3. **Calibrate every new criterion in both directions** — known-good *and* known-bad sample —
   before trusting it. If it can't separate them, delete it; don't tune it until it looks right.
4. **Relative thresholds break when the denominator collapses.** A ÷median criterion can pass a
   nearly-frozen clip because the whole clip is slow. Pair ratios with an absolute floor.
5. **A number crossing a line ≠ the video got better.** The extra motion may come from something
   the model invented. **The human-eye pass is not optional.**
6. **Single variable, two seeds.** No mechanism claims from one seed. If two seeds disagree,
   you have noise, not an effect.
7. **Reuse working config; never hand-copy it.** Assert the diff against the known-good config
   equals exactly the keys you meant to change.
8. **Failure must not look like success.** If a probe, monitor, or self-check would emit the same
   thing when everything is broken, it is not a check.
9. **Judge "is X present" at full resolution.** Thumbnail-scale judgments have been wrong repeatedly.
10. **Record negative results.** Disproven paths are what stop the next project from re-running them.

## Workflow

### Stage 1 — Environment precheck
Confirm the ComfyUI instances are up, **both GPUs launched with identical flags**, and queues are
free. Mixed launch flags mean a different attention kernel — **those outputs are not comparable**,
so an experiment must not straddle them. See `references/h3_runbook.md`.

### Stage 2 — Concept + technical feasibility 🔴 *gate: user confirms*
Produce a short script: what the shot is, what the viewer should feel, and the **one thing each
shot performs**. In the same pass, reconcile against §Hard Limits and these two design rules:

- **One shot performs one action** (~5–6 s). Two actions in one long shot and the model jumps mid-way.
- 🔴 **The final shot's action must have no endpoint.** Walking away / passing by / still turning
  keep going; *arriving, posing, finishing a smile* complete early and the remaining seconds sit still.

**Present the concept *with* its technical consequences and get explicit confirmation.**
If the ask is infeasible as stated (e.g. 15 s in one generation), say so here with the alternative.

### Stage 3 — Project scaffold + work order
Create `<project>/{assets,orders,docs,outputs}`. Write the work order containing the image prompts,
the video prompt, and 🔴 **the acceptance criteria written down before any result exists**.
Templates: `references/keyframe_imagegen_order.md`.

### Stage 4 — Keyframes, then video
**Keyframes first, and they must pass acceptance before any video runs.** Photorealism is decided
here and **cannot be recovered later** — the video stage interpolates between two images; two
smooth AI-looking images cannot produce pores in between. Spec: `references/keyframe_imagegen_order.md`.

Then generate video: long jobs in `tmux`, dual-GPU lanes staggered, **one seed per lane**
(ports are lanes, not variables). See `references/h3_runbook.md`.

### Stage 5 — Acceptance 🔴 *gate*
In order, stopping at the first failure:
1. **Pixels** — frames, blank count, NaN, audio
2. **Criteria** — tail activity (ratio **and** absolute), cut placement, per `references/acceptance_criteria.md`
3. **Human eye** — filmstrip: did it perform the intended thing, or something it invented?
4. **Human ear** — if music was specified, metrics can tell you music exists, not what it is

**If it fails, fix the right layer** — see the routing table below. Re-running the wrong layer is
the most common way to waste a cycle here.

### Stage 6 — Delivery
Copy the finished file to the local machine with its evidence (filmstrip, metrics, criteria results)
and write the conclusion back into the project's findings — **including what failed**.

## 🔴 Which Layer Fixes What

Iterating on the wrong layer is the dominant failure mode. Measured, not guessed:

| Want to change | Only fixable in | Evidence |
| --- | --- | --- |
| Photorealism (pores, uneven light, depth) | **Keyframe images** | Two seeds: adding realism text to the *video* prompt changed nothing |
| Whether a thing exists in frame at all | **Keyframe images** | Prompts cannot add what the frames don't contain |
| The **ending pose** | **Last-frame composition** | Two seeds, same direction |
| Motion path, cut timing, expression arc | **Prompt** | — |
| Mid-shot framing | **Neither** — add an endpoint (i.e. a cut) | Two seeds disproved "don't pull back" wording |
| 🔴 **Tail freeze (~0.7 s)** | **Unsolved** — see `references/known_findings.md` | Wording: no effect. Last-frame composition: seeds disagreed |

**Before changing anything, ask: does the thing I want to change exist in the two keyframes?**
If not, editing the prompt is wasted effort.

## Bundled Helpers

`scripts/` (run where `av`/`numpy` are available — typically the GPU host):

| Script | Answers |
| --- | --- |
| `h3_verify.py` | Frames, blank frames, NaN, audio — **the silent-NaN gate** |
| `h3_freeze.py` | Does the ending keep moving? Ratio **and** absolute floor |
| `h3_cutdetect.py` | Where are the hard cuts? **Cannot see dissolves — "0" ≠ "one cut"** |
| `filmstrip.py` | Contact sheet for the human-eye pass |

## References

| File | Contents |
| --- | --- |
| `references/prompt_authoring.md` | 🔴 **How to write the prompt** — official format, the realism/drama fork, endpoint rule, and a list of things already proven not to work |
| `references/official_h3_guide.md` | Official MiniMax guide digest + **where we deliberately deviate and why** |
| `references/keyframe_imagegen_order.md` | Image work-order template, photoreal spec, banned words |
| `references/acceptance_criteria.md` | Full criteria set + how to calibrate one |
| `references/h3_runbook.md` | Host, ports, tmux, asset placement, config, parameters, two fatal traps |
| `references/known_findings.md` | Proven / disproven / unsolved — **read before proposing an experiment** |
