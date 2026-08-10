---
name: h3-creative-video
description: Create, revise, diagnose, or accept short creative videos with MiniMax-H3, especially FL2VA first/last-frame generation on a remote ComfyUI GPU host. Use for concept design, official three-field H3 prompts, multi-shot timing, keyframe image orders, SSH execution, silent-black/NaN diagnosis, tail-freeze and cut analysis, filmstrip review, creative-production selection, paired-seed experiments, and end-to-end delivery of roughly 12-second or segmented videos.
---

# H3 Creative Video

Produce a MiniMax-H3 video from concept to an evidence-backed delivery. Treat the empirical rules
in this skill as a **versioned runtime profile**, not universal properties of every H3 deployment.
When measurements disagree with a rule, verify the measurement, record the counterexample, and
update the evidence tier.

## Choose the work mode first

| Mode | Use when | What may change | What may be claimed |
| --- | --- | --- | --- |
| **Creative production** | The goal is the best work | Any user-approved bundle of prompt, keyframes, timing, or audio strategy | Candidate A is preferable by the written scorecard; no single-factor causality |
| **Causal experiment** | The goal is to learn whether one lever works | Exactly one asserted variable, with paired seeds | An effect only if paired seeds agree and exceed the measured seed noise floor |

Do not force a creative redesign into a single-variable experiment. Label the mode in the work
order before generation.

## Assign roles, not model names

Record who owns **creative generation**, **GPU operation**, and **acceptance**. Separate generation
from final acceptance when another reviewer is available. If one agent owns all three, disclose
self-acceptance and require the bundled scripts plus full-resolution eye and ear checks.

## Normalize the request

Capture:

- subject, mood, setting, references, orientation, duration, and realism/stylization target;
- whether the user wants a plan, immediate execution, a causal experiment, or a creative work;
- delivery gate: final-only versus whether a technically failed creative prototype may be shown;
- audio policy: native continuous audio, post-produced audio, silent, or out of scope;
- rerun budget, acceptance owner, SSH host, ComfyUI endpoints, and available GPU lanes.

Resolve duration and architecture before prompt writing.

## Validate a runtime profile

The following values are **validated for the current project graph**, not guaranteed by the
official prompt guide:

| Item | Current profile | Observed failure |
| --- | --- | --- |
| FL2VA frames | `n % 17 == 5`, `n <= 277` | Above the ceiling produced silent all-black output after apparent success |
| Resolution | multiples of 16; area `<= 1032192` | submission failure outside the tested cap |
| fps | 24 | prompt alignment and analysis timing drift if assumed incorrectly |
| Full run | 30 steps, about 45 minutes on the recorded host | environment-dependent |

Before each project, record the host, model/checkpoint revision, workflow or script hash, node
versions, launch flags, fps, dimensions, frame count, steps, sampler, scheduler, and GPU binding.
Probe any untried shape or model revision at low steps before a full run. See
`references/h3_runbook.md`.

One validated FL2VA generation is 277/24 = **11.54 seconds**. For a longer work, choose explicitly:

1. one native generation within the limit;
2. multiple visual generations plus a separately planned continuous audio bed in post;
3. multiple silent segments; or
4. shorten the concept when native uninterrupted audio is mandatory and post is forbidden.

Do not promise that independently generated audio will join cleanly.

## Core operating rules

1. Treat ComfyUI `status=success` as execution state, not media acceptance.
2. Write acceptance criteria before outputs exist and calibrate new metrics on known-good and
   known-bad samples.
3. Pair relative motion ratios with absolute floors and a maximum **terminal full-frame** freeze
   gate. Do not relabel the longest low-motion interval anywhere in the clip as a tail freeze.
4. Continue minimum diagnostic review after a delivery-blocking failure; do not confuse
   “stop delivery” with “stop learning.”
5. Reuse a known-good config, assert the intended diff, and verify it through the real CLI path.
6. Judge existence, identity, hands, and realism at full resolution. Use a filmstrip for timing and
   story, not for tiny structural details.
7. Record negative results and counterexamples. Rewording a disproven clause is not a new test.

## Workflow

### 1. Precheck environment

Validate the runtime profile, exact GPU bindings, launch flags, queues, storage paths, and existing
jobs without restarting services. Ports are lanes, not variables. Track every submission by prompt
ID. Read `references/h3_runbook.md` before remote execution.

### 2. Design concept and feasibility — user gate

Write what the viewer sees, feels, and learns. Give each shot one **primary state transition**;
secondary hair, fabric, weather, and ambient motion may support it.

For the final shot, use both tests:

- **Semantic test:** avoid a task that explicitly completes early, such as arriving or posing.
- **Compositional test:** the last frame must afford continued motion beyond the frame through an
  unresolved direction, asymmetric weight transfer, or an exit vector. The words “still turning”
  alone do not guarantee this.

Explain cuts, duration, audio architecture, and known technical risk, then get confirmation.

### 3. Scaffold and freeze the work order

Create `<project>/{assets,orders,docs,outputs}`. Store the final image prompts, video prompt,
acceptance scorecard, mode, stop conditions, and evidence manifest. The manifest must include input
hashes, prompt hash, config diff, runtime profile, seeds, prompt IDs, output hashes, metrics, and
review artifacts. Use `references/keyframe_imagegen_order.md`.

### 4. Accept keyframes, then generate video

Keyframes set the upper bound for identity, form, lighting, and texture. Video generation can still
introduce morphing, temporal texture, hair, or motion artifacts, so do not treat good keyframes as a
guarantee. Accept the keyframes at full resolution before spending a video run.

Use the official FL2VA alignment line and three named fields. Read
`references/prompt_authoring.md` and `references/official_h3_guide.md`. Run long jobs in `tmux`,
stagger concurrent lanes when the runtime profile requires it, and use different seeds for samples.

### 5. Gate delivery and continue diagnosis

Run in this order:

1. pixels and streams;
2. numeric criteria, including terminal full-frame freeze duration and cut placement;
3. minimum filmstrip review even if step 2 blocks delivery;
4. full-resolution visual review;
5. human ear review according to the declared audio policy.

Follow `references/acceptance_criteria.md`. A hard failure removes delivery eligibility but should
still produce enough evidence to route the next iteration.

### 6. Deliver with an explicit status

Use exactly one status:

- **Accepted delivery** — every declared hard gate passed;
- **Creative prototype** — meaningful for review, but one or more technical gates failed;
- **Invalid output** — corrupt, blank, missing, or not useful for content review.

Deliver the media with its manifest, metrics, filmstrip, full-resolution observations, audio
decision, remaining limitations, and negative findings.

## Route failures to the right layer

| Problem | First lever | Guardrail |
| --- | --- | --- |
| Identity, form, object existence, base realism | keyframes | video prompt is not a proven recovery mechanism |
| Ending pose or silhouette | last-frame composition | inspect the whole pose, not isolated joints |
| Motion path, cut timing, expression trajectory | video prompt | use visible actions, not control-word piles |
| Mid-shot framing | shot endpoint or explicit cut | camera keyword swaps showed no seed-consistent effect |
| Temporal morphing, synthetic hair, motion artifact | candidate/seed, prompt complexity, or architecture | good source frames do not eliminate video-stage artifacts |
| Tail freeze | use the decision tree below | do not spend another round on wording-only reinforcement |

## Tail-freeze decision tree

1. Re-run the terminal full-frame metric with the recorded profile thresholds, then confirm the
   intended subject's tail action by eye. Whole-frame motion cannot prove that the subject moves.
2. If only one paired seed fails, classify the configuration as unstable; do not call it fixed.
3. If both fail and the end composition reads finished, redesign the final frame's spatial exit or
   unresolved weight transfer. This is a composition experiment, not a wording test.
4. If both fail despite an unresolved composition, stop wording-only iteration. Choose one
   user-approved architecture change: shorten the final interpolation window, split the visual
   generation and rebuild audio in post, or accept a labeled creative prototype.
5. Do not claim that “endpoint-free” wording solved freeze until paired seeds pass the freeze gate
   and exceed the seed noise floor.

Read `references/known_findings.md` before proposing any repeat experiment.

## Bundled helpers

Run where PyAV, NumPy, and Pillow are available:

| Script | Purpose |
| --- | --- |
| `scripts/h3_verify.py` | Gate frames, blankness, dimensions, audio policy, silence, NaN, and A/V duration |
| `scripts/h3_freeze.py` | Gate tail ratio, absolute activity, and maximum terminal full-frame freeze; cannot prove subject motion |
| `scripts/h3_cutdetect.py` | Locate isolated hard cuts and optionally compare them with expected times; cannot see dissolves |
| `scripts/filmstrip.py` | Build the contact sheet for story and timing review |

Pass project-calibrated thresholds explicitly and preserve JSON output in the evidence manifest.

## References

- `references/prompt_authoring.md` — prompt decisions, final-frame affordance, shots, camera, audio
- `references/official_h3_guide.md` — official guide digest and project-specific deviations
- `references/keyframe_imagegen_order.md` — keyframe work-order and full-resolution review
- `references/acceptance_criteria.md` — gates, diagnostics, experiment comparison, status language
- `references/h3_runbook.md` — runtime-profile precheck, safe submission, monitoring, manifest
- `references/known_findings.md` — evidence tiers, counterexamples, disproven and open questions
