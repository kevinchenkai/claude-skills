---
name: h3-creative-video
description: Create, rewrite, execute, diagnose, or accept MiniMax-H3 audiovisual videos in T2VA text-only prompt mode and image-conditioned I2VA, FL2VA, or L2VA modes on a remote ComfyUI GPU host. Use when the user supplies a detailed video-generation prompt with no images, asks for prompt-only text-to-video, provides first/last keyframes, needs the official three-field H3 prompt structure, or requests end-to-end generation, paired-seed experiments, silent-black/NaN diagnosis, cut/freeze analysis, filmstrip review, and evidence-backed delivery.
---

# H3 Creative Video

Produce a MiniMax-H3 video from the user's text and optional endpoint images. Route the conditioning
mode before applying any prompt, keyframe, duration, or acceptance rule. Treat empirical findings as
versioned runtime-profile evidence, not universal H3 behavior.

## Route the conditioning mode

| Mode | Anchored input | Prompt opening | Generation contract |
| --- | --- | --- | --- |
| **T2VA** | text only, zero images | start directly with `integrated_multimodal_description:` | omit both `first_frame` and `last_frame` |
| **I2VA** | one first-frame image + text | official first-frame instruction, blank line, three fields | connect only `first_frame` |
| **FL2VA** | first + last frame + text | official two-image alignment, blank line, three fields | connect both image inputs |
| **L2VA** | one last-frame image + text | official last-frame alignment, blank line, three fields | connect only `last_frame` |

When the user supplies a detailed prompt and no image, select **T2VA**. Do not ask for images,
generate keyframes, insert placeholder images, or add a Picture-alignment line. If one image is
provided without saying whether it is first or last, resolve that material ambiguity before running.

Do not confuse conditioning mode with work mode:

| Work mode | Use when | Valid claim |
| --- | --- | --- |
| **Creative production** | choose the best work | candidate preference by a prewritten scorecard; no single-factor causality |
| **Causal experiment** | test one lever | effect only when paired seeds agree and exceed the seed noise floor |

## Assign roles and normalize the request

Record the owners of creative generation, GPU operation, and acceptance. Separate generation from
final acceptance when possible; disclose self-acceptance otherwise.

Capture the original prompt verbatim, conditioning mode, subject, style, setting, duration,
orientation, exact dialogue/lyrics/on-screen text, audio policy, execution intent, delivery gate,
rerun budget, acceptance owner, host, endpoints, and GPU lanes. Preserve the source prompt and its
hash even when rewriting it.

For a detailed T2VA prompt:

1. treat the text as the source brief rather than inventing a replacement concept;
2. preserve hard constraints and every word/punctuation mark of dialogue, lyrics, and visible text;
3. if already in the official structure, validate and use it without creative rewriting unless the
   user asks for optimization;
4. otherwise normalize it into the official three fields and show any material interpretation.

Read `references/t2va_prompt_mode.md` for prompt-only handling.

## Validate a mode-specific runtime profile

The official prompt guide does not define the local graph's inference ceiling. Record mode, host,
checkpoint/revision, graph/runner hash, nodes, launch flags, fps, dimensions, frames, steps, sampler,
scheduler, and GPU binding.

| Mode | Evidence in the recorded project profile | Do not infer |
| --- | --- | --- |
| T2VA | successful 107-frame wiring probe; successful 192- and 243-frame productions at 24fps | no T2VA ceiling has been established |
| I2VA | successful 107-frame wiring probe and 192-frame official reproduction | do not assume FL2VA tail behavior |
| FL2VA | `n % 17 == 5`, `n <= 277`; higher runs produced silent all-black output | do not transfer this ceiling to T2VA |
| L2VA | official prompt structure known; local production profile not calibrated | probe before a full run |

The recorded common profile uses dimensions divisible by 16, area `<= 1032192`, and 24fps. Recheck
after model, graph, or node changes. Probe every untried mode/shape/frame combination at low steps
and verify pixels; a clean decode or `status=success` is insufficient.

For work longer than a validated single generation, choose native single-run audio, segmented
visuals with post-produced continuous audio, intentional silence, or a shorter concept. Never
promise that independently generated audio will join cleanly.

## Core operating rules

1. Validate the prompt for the selected mode with `scripts/h3_prompt_lint.py` before submission.
2. Treat ComfyUI `status=success` as execution state, not media acceptance.
3. Write acceptance criteria before outputs exist; include a requirement matrix for the user's
   detailed T2VA prompt.
4. Apply keyframe findings only to image-conditioned modes. In T2VA, the prompt and seed are the
   visual-conditioning levers.
5. Reuse a known-good config for the same conditioning mode, assert the intended diff, and exercise
   the real CLI/graph path.
6. Pair motion ratios with absolute floors and terminal full-frame duration only when the ending
   activity is a declared requirement. Never relabel a global quiet opening as tail freeze.
7. Continue minimum diagnosis after a delivery-blocking failure; stop delivery, not learning.
8. Record negative results, mode scope, and counterexamples.

## Workflow

### 1. Precheck the exact mode

Validate runtime profile, graph node, optional input wiring, GPU bindings, flags, queues, storage,
and existing jobs without restarting services. For T2VA, prove the graph contains no image loader
feeding `first_frame` or `last_frame`. Track submissions by prompt ID. Read
`references/h3_runbook.md`.

### 2. Validate concept and prompt — user gate when interpretation changes

For an existing detailed prompt, preserve its concept. Reconcile duration, shots, exact speech/text,
sound, and feasibility; ask only when an ambiguity materially changes the output. For a new concept,
write what the viewer sees, feels, and learns, with one primary state transition per shot.

Use the official mode-specific opening and the shared fields in this exact order:

1. `integrated_multimodal_description`
2. `overall_soundscape`
3. `non_diegetic_music`

T2VA has no instruction before field 1. Read `references/prompt_authoring.md` and
`references/official_h3_guide.md`.

### 3. Freeze the work order and evidence manifest

Create `<project>/{assets,orders,docs,outputs}` as needed. Store source and final prompt hashes,
mode, prompt lint result, runtime profile, scorecard, stop conditions, config diff, seeds, prompt
IDs, output hashes, metrics, and review artifacts. T2VA requires no image assets directory content.

### 4. Prepare only the conditioning inputs that exist

- **T2VA:** skip image generation and keyframe acceptance; submit the validated prompt with zero
  image conditions.
- **I2VA/L2VA/FL2VA:** accept supplied or generated endpoint images at full resolution, hash them,
  and connect only the inputs declared by the mode. Read `references/keyframe_imagegen_order.md`.

Run long jobs in `tmux`, stagger lanes when the profile requires it, and vary seeds for samples.

### 5. Gate delivery and continue diagnosis

Check pixels/streams, declared numeric criteria, filmstrip/story, full-resolution frames, prompt
requirement coverage, and human audio review. For T2VA, explicitly review character/object
consistency because no image anchors protect them. A hard failure blocks accepted delivery but must
still produce enough evidence to route the next iteration. Follow
`references/acceptance_criteria.md`.

### 6. Deliver with one status

- **Accepted delivery** — every declared hard gate passed;
- **Creative prototype** — useful for review but one or more technical/semantic gates failed;
- **Invalid output** — corrupt, blank, missing, or unusable.

Deliver the media with prompt, mode, manifest, metrics, filmstrip, full-resolution observations,
audio decision, remaining limitations, and negative findings.

## Route failures by mode

| Problem | T2VA first lever | Image-conditioned first lever |
| --- | --- | --- |
| Subject/object/style absent | concrete prompt facts, timeline placement, then seed | endpoint images if the fact must exist there |
| Identity or appearance drift | simplify prompt, repeat stable visible attributes at shot transitions, compare seeds | endpoint consistency plus video-stage review |
| Ending pose/silhouette | final-shot timeline and candidate selection | last-frame composition |
| Motion path/expression/cut timing | prompt | prompt |
| Mid-shot framing | explicit shot/cut and concrete composition | shot endpoint/cut; FL2VA camera wording alone was weak |
| Tail subject settles while background moves | eye review or calibrated subject ROI | same; whole-frame activity cannot prove subject motion |

The FL2VA tail-freeze experiments in `references/known_findings.md` do not establish how T2VA
responds to the same wording. Do not import their “disproven” status across modes without a T2VA
paired experiment.

## Bundled helpers

Run where required dependencies are available:

| Script | Purpose |
| --- | --- |
| `scripts/h3_prompt_lint.py` | Validate mode-specific opening, field order, shots, timestamps, and dialogue tags |
| `scripts/h3_verify.py` | Gate frames, blankness, dimensions, audio policy, silence, NaN, and A/V duration |
| `scripts/h3_freeze.py` | Gate whole-frame tail activity and terminal freeze; cannot prove subject motion |
| `scripts/h3_cutdetect.py` | Locate isolated hard cuts and compare with expected times; cannot see dissolves |
| `scripts/filmstrip.py` | Build the temporal contact sheet |

Preserve JSON outputs in the evidence manifest.

## References

- `references/t2va_prompt_mode.md` — pure prompt intake, exact template, rewrite and runner contract
- `references/prompt_authoring.md` — shared official prompt rules plus mode-scoped project findings
- `references/official_h3_guide.md` — official base-mode digest and project deviations
- `references/keyframe_imagegen_order.md` — endpoint-image work order for I2VA/L2VA/FL2VA only
- `references/acceptance_criteria.md` — mode-aware gates, diagnostics, comparison, status language
- `references/h3_runbook.md` — mode wiring, runtime precheck, safe submission, monitoring, manifest
- `references/known_findings.md` — evidence tiers with explicit conditioning-mode scope
