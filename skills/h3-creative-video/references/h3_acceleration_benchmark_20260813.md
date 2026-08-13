# MiniMax H3 acceleration benchmark and production decision — 2026-08-13

This is a versioned field report, not a universal ranking. It records one H20/ComfyUI runtime
profile, one fixed BM012 image-to-video sample, and the human review decisions made during the
2026-08-08 to 2026-08-13 test campaign. Re-run a small paired control after changing the GPU,
checkpoint, ComfyUI build, attention kernel, LoRA revision, frame count, or sampler graph.

## Final decision

1. **Default for early content iteration: LightX2V MiniMax-H3 Turbo 8-step v1.0 LoRA, run at
   8 NFE with the native video/audio schedules and `MiniMaxH3TurboSampler`.** It is the fastest
   currently usable option in this profile. Its generated audio contains audible noise, so treat
   it as picture-first preview audio, review it by ear, and replace or regenerate audio before
   delivery when sound matters.
2. **Second choice when quality matters more than turnaround: the H3-specific
   `MiniMaxH3MemoryEfficientSageAttentionPatch`, with the normal 30-step Euler/simple graph.**
   It is about 2.08 times slower than the selected LightX2V 8-step setup, but its picture and
   audio are the more dependable review path in the current sample.
3. **Do not use the generic KJ `PathchSageAttentionKJ` Sage2 patch for early iteration.** Its
   completed BM012 P0 run took 54m23s and the final human review judged the result too poor for
   the cost. A planned BM012 P1 rerun was deliberately cancelled; the P0 result already answered
   the production question.
4. **BlockCache is excluded from the current ranking and recommendation.** This report compares
   no-Block paths. Earlier BlockCache and Sage2+BlockCache experiments remain useful historical
   evidence, but they add a second approximation variable and are not the selected workflow.

## Exact no-Block comparison

Common controlled fields for the two strict P1 rows were:

- physical GPU1 on a dual-H20 host;
- `minimax_h3_fl2va_pruned_int8_convrot.safetensors`;
- Qwen3-VL 32B MiniMax-H3 NVFP4/AWQ text encoder;
- BM012 first frame and the same structured P1 prompt;
- seed `2026080516`;
- 1344×768, 24 fps, 226 frames;
- video/audio sigma shifts 12/3;
- no BlockCache and no global ComfyUI Sage launch flag.

| Rank | Path | Prompt | Steps / sampler | Measured time | Relative efficiency | Time versus fastest | Human decision |
| ---: | --- | --- | --- | ---: | ---: | ---: | --- |
| 1 | LightX2V 8-step v1.0 LoRA at 8 NFE, dual-clock | P1 | 8, `MiniMaxH3TurboSampler`, simple | **1029.7 s (17m10s)** | **100%** | **1.00×** | Default early-test path; picture useful, audio noisy |
| 2 | H3-specific Memory-Efficient Sage patch | P1 | 30, Euler, simple | **2143.1 s (35m43s)** | **48.0%** | **2.08×** | Quality-first fallback; slower but more dependable |
| — | Generic KJ Sage2 patch, no Block | P0, not strict P1 | 30, Euler, simple | **3263.1 s (54m23s)** | 31.6% | 3.17× | Rejected: too slow and final picture review was too poor |

The generic Sage2 row is shown as an elimination result, not as a strict P1 ranking row. Do not
claim a P0/P1 causal effect from it. It is still sufficient for the production stop decision:
even its completed P0 run was 1.52 times slower than the H3-specific Sage P1 run and 3.17 times
slower than the selected LightX2V path.

### Selected LightX2V graph

- LoRA: `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors`
- strength: 1.0
- NFE: 8
- sampler: `MiniMaxH3TurboSampler`
- scheduler: simple, denoise 1.0
- dual clock: native ModelSamplingAV video/audio schedules, auto-detected by TurboSampler
- attention: Comfy default, with no extra Sage patch
- shifts: video 12, audio 3

### Selected H3-specific Sage graph

- node: `MiniMaxH3MemoryEfficientSageAttentionPatch`
- observed H20 runtime: `QK_INT8_V_FP8_SM90_ACCUM_FP32`
- steps: 30
- sampler/scheduler: Euler/simple, CFG 1.0
- shifts: video 12, audio 3
- no BlockCache

This H3-specific node is not the generic KJ node named `PathchSageAttentionKJ`, and it does not
load a model file named `sageattn_qk_int8_pv_fp16_cuda`. It patches the H3 model's attention
implementation in the graph and can be enabled per workflow without switching the entire ComfyUI
service launch mode.

## How the human conclusion evolved

The campaign deliberately retained later reviews that overruled earlier impressions.

| Variant | Human review | Status |
| --- | --- | --- |
| Larry 4-step | Complete failure; ordinary and structured prompts did not rescue it | Remove from usable pool |
| Old LightX2V 4-step | Strong dynamic noise and obvious defects; at best a deadline-only content probe | Superseded |
| KIJAI4 | Initially looked best and showed the clearest P0→P1 content change; later BM012 review found dynamic grain, merely passable picture, and **pure-noise audio** | Abandon |
| Tutu 20→8 NFE step100 | More speckle/noise and slightly worse picture; LoRA shape-mismatch warnings appeared on the pruned INT8 base | Abandon; compatibility risk |
| Larry Turbo v4 step600 EMA | Follow-up completed, but did not establish a quality reason to replace the selected paths | Not recommended |
| Native 30-step baseline | Generally ordinary; BM012 content transition showed perspective problems, possibly seed variance | Control only |
| Comfy native `--use-sage-attention` | BM012 P0 was 2141.6 s versus 3263.1 s for generic KJ Sage2, with similar human picture quality | Useful global service option, but requires choosing the launch mode for that ComfyUI instance |
| Generic KJ Sage2 patch only | P0 took 54m23s; final review judged quality too poor for early testing | Reject |
| H3-specific Memory-Efficient Sage only | P1 took 35m43s and retained acceptable picture/audio behavior | Second choice |
| New LightX2V Turbo v1.0 4-step, native 4 NFE | BM012 was 346.6 s; in the first 4-vs-8 sample its picture looked better than the initial native 8-step result | Useful historical speed probe, not final selection |
| New LightX2V Turbo v1.0 8-step, native 8 NFE | Initial BM012 run was 601.7 s | Superseded by the controlled dual-clock rerun |
| New LightX2V 8-step LoRA at 8 NFE, dual-clock | 1029.7 s; final chosen balance of speed and usable picture, with audible noise in generated audio | **Primary recommendation** |

Earlier Sage2+BlockCache results looked better in picture quality than the new LightX2V output and
had acceptable audio in the reviewed samples. They are intentionally not promoted here: they use
two interacting approximation variables, complicate fault attribution, and are far slower than
the selected preview path. If a future investigation reopens caching, test Native → Sage only →
Block only → Sage+Block with the same seed and keep cache-hit logs. Do not merge those timings into
the no-Block table above.

## Creative findings that matter more than another kernel tweak

The acceleration search did not change the strongest production lessons from the earlier paired
FL2VA campaign:

1. **Endpoint material controls form; the video prompt primarily controls motion.** If a required
   effect, silhouette, prop, or composition is absent from the endpoint images, drawing it into the
   endpoint material is usually a stronger lever than adding more prose. In the recorded paired
   test, changing only the endpoint effect form improved the clarity metric by 53% and 44% across
   two seeds and produced the intended full dragon body and claws.
2. **Better endpoint images beat more prompt polishing.** Larger subjects and more face/hand pixels
   removed fast-motion face failures that sampling tweaks did not solve. Spend iteration budget on
   accepted keyframes and multiple seeds before expanding the prompt indefinitely.
3. **Do not pay for 50 steps by default.** A controlled 226-frame run increased from about 36m at
   30 steps to 63.5m at 50 steps (+76% time) for only about +10% on the recorded clarity metric,
   with nearly unchanged composition. The campaign accepted 30 steps as the quality baseline.
4. **Prompt structure still matters.** P1 helped KIJAI4 content responsiveness in the early review,
   but a good prompt cannot repair a fundamentally noisy acceleration path. Preserve the official
   mode-specific structure and evaluate the engine separately.
5. **Seed selection is a production lever.** A single sample can confuse an engine defect with a
   draw defect. Use paired seeds when making causal claims, even though one clearly slow/unusable
   result can justify a pragmatic stop decision.

## Frame and acceptance policy

- Use 226 frames for strict turnaround comparisons in this runtime profile.
- The campaign later reduced exploratory tests to at most 350 frames. Where the active H3 graph
  requires the `17k+5` frame grid, the nearest value not exceeding 350 is 345. This is a local test
  policy, not a universal H3 ceiling.
- Frame ceilings are conditioning-mode and runtime-profile specific. Do not transfer a successful
  Ref2VA or T2VA length to I2VA/FL2VA without a probe.
- A ComfyUI success status is not acceptance. Verify video and audio streams, dimensions, fps,
  frame count, non-black pixels, hashes, and human audio quality. Several rejected accelerators
  produced technically valid MP4 files.
- For the selected LightX2V path, audible generated-audio noise is a known hard caveat. Picture
  approval does not imply audio approval.

## Recommended operating sequence

1. Build and accept the endpoint image(s); put required effect form into the material.
2. Write the official mode-specific prompt, emphasizing motion, state change, continuity, and
   sound intent rather than repeatedly redescribing endpoint form.
3. Run a 226-frame P1 preview with the LightX2V 8-step LoRA at 8 NFE and dual-clock schedules.
4. Review picture and audio separately. Use the preview to correct content and keyframes, not to
   certify final audio.
5. When the picture direction is approved and quality is more important than turnaround, run the
   H3-specific Memory-Efficient Sage 30-step graph with the same seed/prompt/assets for comparison.
6. Keep BlockCache off in the default workflow. Do not use generic Sage2 for early iteration.
7. Preserve workflow JSON, prompt, metadata, ffprobe output, SHA256, and the human decision.

## Evidence identifiers

The measured rows were retained under these campaign directories:

- `11_LIGHTX_DUALCLOCK_8STEP_BM012_P1_20260813`
- `10_H3_MEMEFF_SAGE_BM012_P1_20260813`
- `06_SAGE_NATIVE_VS_KJ_BM012_20260812/KJ_SAGE2`
- `08_LIGHTX2V_TURBO_V1_BM012_P1_20260812`
- `07_NATIVE_SAGE_4CASE_P0P1_20260812`
- `04_FOLLOWUP_NEW_LORAS_20260811`
- `03_E0_NATIVE30`, `03_E1_LARRY4`, `03_E2_LIGHTX2V4`, `03_E3_KIJAI4`

The cancelled pure-Sage2 P1 prompt was `264fc61c-03bb-45e6-8e8c-b35b51890cef`. It was interrupted
only after verifying that it was the sole prompt in the 8188 queue and that the external 8190
queue was empty. It produced no accepted benchmark row.
