# H3 Execution Runbook

Use for execution or infrastructure diagnosis. Prompt-only work does not need this reference.
Read the applicable project/host rules before touching a shared machine. Consult
[runtime_profiles.md](runtime_profiles.md) when selecting/checking settings; it is historical evidence.

## Preflight and actual wiring

Fingerprint mode, host/ports, model/quantization, graph/runner hashes, node version, launch flags,
GPU binding, fps, dimensions, frames, steps, sampler and scheduler. Inspect each PID's arguments
and `CUDA_VISIBLE_DEVICES`. Check jobs, queues, storage and tmux without restarting services.

Base modes use `MiniMaxH3ImageToVideo` and the endpoint wiring selected in SKILL.md. Inspect the
**submitted graph**, not just its config name: T2VA has no endpoint keys or image loader feeding
them, even with a checkpoint named `fl2va`. Never insert a placeholder to satisfy an image-only runner.

Ref2VA requires its dedicated transformer and `MiniMaxH3ReferenceToVideo`. Validate actual media,
connector/label order, and reference counts using [ref2va_prompt_mode.md](ref2va_prompt_mode.md).

Reuse a known-good same-mode config, assert its intended diff, and exercise the real no-submit CLI.
Keep definitions before the entry point. A mode/wiring change is not a single-variable prompt
experiment. Probe untried mode/shape/length; verify pixels/streams even after `DONE` or exit zero.

### Existing Juscent runner boundary

In `chenkai_airepo/Juscent`, use `scripts/h3lib/submit_h3.py` rather than copying a submitter.
Use `--dry-run` for no-submit graph checks. Inspect the installed revision and README/help.

At the revision inspected for this skill, Ref2VA is selected by nonempty `--ref-image`; it accepts
1–9 images and one optional `--ref-video`. It does **not** connect reference audio/video soundtracks
or handle video-only/audio-only Ref2VA. Do not silently drop such inputs or route them through
T2VA. Use a verified compatible runner, or adapt the shared implementation and validate its real
CLI/graph before submission. The skill's general Ref2VA contract is broader than this adapter.

## Shared-host and long-run rules

- Inspect `tmux ls`, `/queue`, and `nvidia-smi` before using a lane. Operate only on your own
  namespaced sessions/jobs/directories; never kill/restart another team's ComfyUI or clear a queue.
- Preserve project output-prefix and cancellation rules. For Juscent, sessions use `ck-`, outputs
  use `chenkai-h3/`, and cancellation targets an ownership-checked exact prompt ID.
- Ask before deleting data. On borrowed `train-1`, follow its extra queue/long-occupancy rules;
  its existing port 8188 belongs to someone else. Confirm execution authorization for any restart.
- Put remote commands lasting more than a few seconds in `tmux`, with a unique session and durable
  log. Read the log directly; `tmux capture-pane -S` is secondary. A restart also needs tmux and
  positive health evidence such as `/system_stats`. Tmux does not turn failed monitoring into success.
- Compare only matching model, graph, node, attention flags, and GPU/runtime profiles. Vary seeds
  for independent samples; stagger lanes only when the measured profile requires it.

For real assets, validate full-resolution endpoints or inventoried references, hash before/after
transfer, and use relative graph paths. Preserve sources when extracting video audio. The recorded
shared storage rejects symlink traversal and ownership changes:

```bash
rsync -rlt --no-perms --no-owner --no-group <asset> <host>:<input-root>/<project>/
```

## Completion and evidence

Capture the prompt ID at submission. Monitor both success and terminal errors; missing/failed
probes mean WARN/retry within the declared timeout, never completion. Completion needs all four:

1. `/history/<prompt-id>` reports terminal success and the exact output;
2. that ID is no longer queued;
3. the file is readable (allow shared-storage delay);
4. its hash is stable and media checks pass.

An empty queue or existing output path may mean failure, cancellation, no submission, or stale data.
Archive the exact history. Avoid repeatedly dumping unchanged queues/full graphs into conversation;
report state changes and errors, retaining full logs as files.

Use `<project>/{assets,orders,docs,outputs}` as needed. Keep one manifest containing:

- source/final prompts and hashes, mode, lint JSON, requirements/scorecard, audio policy, owners,
  budget and stop conditions;
- runtime fingerprint, config diff, seed/lane/start time/prompt ID, history, output path/hash;
- real input hashes or `media: none`; Ref2VA adds its ordered source/connector/label/role inventory,
  soundtrack mapping, metadata, and requested/effective target/reference lengths;
- measurement settings and JSON, filmstrip, full-resolution observations, requirement results,
  audio decision, delivery status, limitations and negative findings.

Copy deliverables and evidence locally before declaring completion. Use
[acceptance_criteria.md](acceptance_criteria.md) for delivery eligibility; infrastructure success alone
never grants acceptance.
