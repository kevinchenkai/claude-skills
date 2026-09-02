---
name: h3-creative-video
description: Write, generate, diagnose, and review MiniMax-H3 audiovisual videos from text, endpoint frames, or image/video/audio references; supports T2VA, I2VA, FL2VA, L2VA, and Ref2VA on remote ComfyUI.
---

# H3 Creative Video

Preserve the user's concept and exact dialogue, lyrics, and visible text. Keep the source prompt;
validate an already canonical prompt without rewriting unless optimization was requested. Respect
the requested stage: advice or prompt editing does not authorize generation.

## Select the conditioning mode

| Actual supplied inputs and roles | Mode | Required graph inputs |
| --- | --- | --- |
| Text, no conditioning media | T2VA | Neither endpoint; no placeholder image or Picture-alignment line |
| Exact first frame | I2VA | `first_frame` only |
| Exact first and last frames | FL2VA | Both endpoints |
| Exact last frame | L2VA | `last_frame` only |
| General identity/style/content image, any reference video/audio, or mixed references | Ref2VA | Dedicated Ref2VA weights/node and inventoried references |

Route by asset role, not checkpoint filename or file count. Resolve an ambiguous image's endpoint
versus reference role before generation; objects mentioned in prose are not attached media.

## Load only the current stage

Paths below are relative to this skill. Read each needed reference once; reuse it in the same
context. Follow links only when their stated condition applies, rather than reading the directory.

| Task/stage | Read |
| --- | --- |
| Write/validate a base prompt | [prompt_authoring.md](references/prompt_authoring.md); for T2VA also [t2va_prompt_mode.md](references/t2va_prompt_mode.md) |
| Plan/write Ref2VA | [ref2va_prompt_mode.md](references/ref2va_prompt_mode.md) plus shared timeline/sound rules in [prompt_authoring.md](references/prompt_authoring.md#shared-timeline-and-sound) |
| Prepare/review actual endpoint images | [keyframe_imagegen_order.md](references/keyframe_imagegen_order.md); apply its style/ending rules only when requested |
| Execute or diagnose infrastructure | [h3_runbook.md](references/h3_runbook.md) and applicable project/host rules; Ref2VA also needs its mode reference |
| Plan production gates or review a result | [acceptance_criteria.md](references/acceptance_criteria.md); Ref2VA also needs its role-specific acceptance section |
| Declare/measure motion or cut gates; investigate suspect metrics | Relevant section of [acceptance_diagnostics.md](references/acceptance_diagnostics.md) |
| Propose experiments or diagnose creative failure | [known_findings.md](references/known_findings.md), limited to the target mode/problem |
| Audit official provenance or update prompt conventions | [official_h3_guide.md](references/official_h3_guide.md) |

## Production contract

1. Before outputs exist, record requirements, duration/aspect ratio, audio policy, scorecard,
   execution intent, rerun budget/stop conditions, and creative/GPU/acceptance owners. Disclose
   material interpretations; resolve consequential ambiguity with the user.
2. Freeze a same-mode config and runtime fingerprint; assert intended changes through the real
   CLI/graph. Probe untried mode/shape/length combinations and verify pixels. Empirical limits
   belong to a specific mode/model/graph/launch profile.
3. Lint the final prompt; freeze real inputs, hashes and label order. Never invent substitute media.
4. Track prompt IDs and positive completion evidence. Execution success is not media validity;
   keep evidence and minimum diagnosis after failure, within the declared budget.
5. Check pixels/streams, requirement coverage, filmstrip, full-resolution frames and audio by ear.
   Metrics cannot establish creative quality or subject motion from background movement. Apply
   tail activity only to a declared moving ending.
6. Deliver media and manifest as **Accepted delivery** (all hard gates pass), **Creative prototype**
   (reviewable, but a gate failed/unverified), or **Invalid output** (unusable). Disclose self-acceptance.

For creative production, choose against the scorecard without claiming single-factor causality.
For causal experiments, follow the paired-seed method in `known_findings.md`. FL2VA findings do not
establish T2VA/Ref2VA behavior. For segmented visuals, plan continuous post-produced audio,
intentional silence, or a shorter concept; independent native audio clips may not join cleanly.

## Reuse the helpers

Use `scripts/h3_prompt_lint.py` before submission (actual frozen media counts for Ref2VA),
`h3_verify.py` for media validity, `h3_freeze.py`/`h3_cutdetect.py` for conditional metrics, and
`filmstrip.py` for temporal review; all live in `scripts/`. Use `--help` and stage examples; retain
JSON results. Read source only to diagnose/adapt behavior, and run where dependencies exist.
