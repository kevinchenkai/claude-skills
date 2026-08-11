# H3 Runbook — Remote ComfyUI Generation

Treat host aliases, ports, paths, limits, and timings as a versioned runtime profile. Discover the
actual values and select the conditioning mode before submission.

## Contents

1. Runtime profile
2. Mode wiring
3. Long-run protection
4. Conditional assets
5. Safe runner extension
6. Probes and lanes
7. Prompt-ID monitoring
8. Evidence manifest

## 1. Build a runtime profile

Record:

| Field | Example from the validated profile |
| --- | --- |
| Conditioning mode | `t2va`, `i2va`, `fl2va`, `l2va`, or `ref2va` |
| SSH host | `vscode` |
| ComfyUI lanes | GPU0 → `127.0.0.1:8189`; GPU1 → `127.0.0.1:8190` |
| Code / Python | `/home/jovyan/code/src`; `/nfs/envs/comfyui/bin/python3.11` |
| Model and graph | checkpoint/revision plus workflow or runner SHA |
| Launch profile | full process arguments, attention flags, exact GPU binding |
| Generation profile | dimensions, fps, frames, steps, sampler, scheduler, shift |

Resolve each ComfyUI PID and inspect process arguments plus `/proc/<pid>/environ`, including
`CUDA_VISIBLE_DEVICES`. Only compare lanes whose model, code, nodes, and flags match. Check queues,
but do not treat an empty queue as completion.

## 2. Verify the conditioning wiring

The recorded base graph uses `MiniMaxH3ImageToVideo`; its image inputs are optional:

| Mode | `first_frame` | `last_frame` | Prompt instruction |
| --- | --- | --- | --- |
| T2VA | absent | absent | none; starts with three fields |
| I2VA | connected | absent | official first-frame line |
| FL2VA | connected | connected | official two-picture alignment line |
| L2VA | absent | connected | official last-frame line |

For T2VA, inspect the submitted graph—not just the config name—and prove no `LoadImage` output is
wired to either endpoint input. Never insert a blank/placeholder image to satisfy an FL2VA-only
runner. Select or fix the zero-image graph.

Validate the prompt before a job:

```bash
python scripts/h3_prompt_lint.py <prompt.txt> --mode <mode> --duration <seconds> --json
```

The checkpoint filename may contain `fl2va` even when zero image conditions make the actual request
T2VA. Classify by conditioning inputs and prompt structure, not checkpoint name.

Ref2VA is a separate checkpoint and graph family. Require all of the following:

- a `minimax_h3_ref2va_*` transformer, the shared H3 text encoder, and both H3 VAEs;
- `MiniMaxH3ReferenceToVideo`, not `MiniMaxH3ImageToVideo`;
- a frozen table from every connected `ref_image_N`, `ref_video_N`, `ref_video_audio_N`, and
  `ref_audio_N` to its 1-based `<Picture N>`, `<Video N>`, or `<Audio N>` prompt tag;
- the official six-section prompt beginning with `subject_definitions:`;
- at least one actual reference input; route text-only work to T2VA.

In current ComfyUI, audio ordinals include connected video soundtracks in video order before
standalone audios. Connector reordering is a semantic prompt change even when file hashes and text
are unchanged. Read `ref2va_prompt_mode.md` before building or cloning the graph.

## 3. Protect long runs

Use a uniquely prefixed `tmux` session and log. Inspect existing sessions before starting or
stopping anything and operate only on sessions for the current project.

```bash
ssh <host> 'tmux new-session -d -s <project>-s1 "cd <code-root> && \
  <python> <runner> <tag> http://127.0.0.1:<port> \
  2>&1 | tee /tmp/<project>-s1.log"'
```

Read the log directly; use `tmux capture-pane -S` only as a secondary view. Tmux protects the
process from SSH loss, not from invalid mode routing or monitoring.

## 4. Transfer assets only when the mode has them

T2VA has no endpoint assets; skip image upload and image hashes. For I2VA/L2VA/FL2VA, put real files
under ComfyUI's allowed input root, use relative graph paths, and verify hashes before/after transfer.
For Ref2VA, also validate media counts, per-file and aggregate durations, decodability, dimensions,
sample rate, enabled video soundtrack, connector order, and hashes. Preserve the source file when
extracting a video's audio so provenance remains auditable.

The recorded shared filesystem rejects ownership changes and symlink traversal:

```bash
rsync -rlt --no-perms --no-owner --no-group <asset> <host>:<input-root>/<project>/
```

## 5. Extend a known-good runner for the same mode

Clone a known-good config and assert the intended diff. For T2VA, explicitly remove inherited
image keys as required by the actual runner:

```python
_NEW = dict(**_KNOWN_GOOD)
_NEW.update(prompt=prompt, mode="t2va")
_NEW.pop("start_img", None)
_NEW.pop("end_img", None)

assert _NEW.get("start_img") is None and _NEW.get("end_img") is None
```

If comparing against an FL2VA config, image-key removal and the mode change are intended
architecture differences—not a single-variable causal experiment. Assert the complete expected
diff rather than pretending it is one variable.

Two failures can look successful:

1. a hand-copied config can omit keys while a wrapper still prints `DONE` and exits zero;
2. definitions after `if __name__ == "__main__": main()` appear during import but are unavailable
   when the real CLI enters `main()`.

Keep new definitions numerically above/before the entry point. Exercise real CLI dispatch with a
no-submit validation path when available. Ask of every check: would broken mode wiring produce a
different result?

## 6. Probe mode, shape, and length before full lanes

The recorded graph uses frame counts on `n % 17 == 5`, dimensions divisible by 16, area
`<= 1032192`, and 24fps. Evidence is mode-specific:

- T2VA: 107-frame wiring probe and 192-/243-frame productions succeeded; maximum unknown.
- I2VA: 107-frame probe and 192-frame reproduction succeeded.
- FL2VA: up to 277 succeeded; higher counts produced silent all-black output in this profile.
- L2VA: no local production profile; probe first.
- Ref2VA: official/current-node wiring is documented but no local production profile is calibrated;
  probe the exact asset mix, quantization, `ref_image_size`, shape, and length before full steps.

For current Ref2VA nodes, record requested/effective output frames because lengths snap upward to
`17k+5`. Also record effective reference-video frames: the node truncates clips to the target
length and then trims down to that grid. A nominally present late reference event may therefore
never reach conditioning. Treat the published 2–15-second reference-media specification as the
production contract even if a node revision happens to accept a shorter clip.

Probe any untried mode/shape/frame count at low steps, then run pixel validation. Run different
seeds for independent samples. Stagger lanes only when profiling shows an overlapping memory peak;
the historical ~70 seconds is not universal.

### 6.1 Derive dimensions from the requested aspect ratio — do not eyeball them

🔴 **A non-conforming height is silently rounded down, not rejected.** A recorded run requested
`1344×756` and the encoder delivered **`1344×752`**: `status=success`, valid pixels, valid audio,
and a clip whose aspect ratio silently missed the brief. This is the same failure family as silent
NaN — the run looks successful and the number is simply wrong.

Solve the constraints instead of guessing a height:

```python
# All legal shapes for a target ratio, under the recorded profile.
W_RATIO, H_RATIO = 16, 9          # the brief's requested aspect ratio
AREA_MAX = 1032192                # recorded profile cap
for w in range(512, 1601, 16):
    h = w * H_RATIO // W_RATIO
    if h % 16 == 0 and w * H_RATIO == h * W_RATIO and w * h <= AREA_MAX:
        print(w, h, w * h)
```

For true 16:9 under this profile the complete solution set is **512×288 · 768×432 · 1024×576 ·
1280×720** — `1280×720` is the largest. Note that the frequently used `1344×768` is **1.75:1, not
16:9**; it is a fine landscape shape but it does not satisfy a brief that asks for 16:9.

> 🔴 **Search the whole space, not one height.** In a recorded case the conclusion "true 16:9 is
> unreachable" was drawn after testing only `height = 768`, when `1280×720` satisfied every
> constraint. If a brief names a ratio, enumerate the solutions before declaring it impossible.

**Declare the dimension gate before generating**, and verify the *delivered* stream against it —
never assume the request was honored.

## 7. Monitor by prompt ID

Capture the prompt ID. Monitor success and terminal failure signatures; silence/missing data is
WARN-and-retry, never completion.

Completion needs this chain:

1. `/history/<prompt-id>` reaches terminal success and reports the exact output;
2. the queue no longer contains that prompt ID;
3. the output becomes readable;
4. its hash is fixed and media passes decode/pixel checks.

An empty queue can mean success, failure, cancellation, or no submission. An output path can refer
to stale content. Keep history and final hash.

## 8. Preserve an evidence manifest

Retain:

- conditioning mode, runtime profile, and runner/workflow hash;
- source and final prompt plus hashes and prompt-lint JSON;
- optional endpoint paths/hashes, or an explicit `media: none` for T2VA;
- for Ref2VA: ordered source/connector/label/role table, media metadata, video-soundtrack pairing,
  prompt tag counts, `ref_image_size`, and separate requested/effective target and reference lengths;
- config diff, seed, lane, start time, and prompt ID;
- history state, output path/hash, verify/freeze/cut JSON;
- filmstrip, prompt-requirement matrix, full-resolution observations, audio review, and status.

Copy the deliverable and evidence locally before declaring the remote run complete.
