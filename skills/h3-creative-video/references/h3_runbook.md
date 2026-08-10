# H3 Runbook — Remote ComfyUI Generation

Host aliases, ports, paths, limits, and timings below are a **runtime profile from one environment**.
Discover and record the actual values before submission; never copy them as universal defaults.

## Contents

1. Runtime profile
2. Long-run protection
3. Asset placement
4. Safe runner extension
5. Lane submission
6. Prompt-ID monitoring
7. Evidence manifest

## 1. Build a runtime profile

Record:

| Field | Example from the validated profile |
| --- | --- |
| SSH host | `vscode` |
| ComfyUI lanes | GPU0 → `127.0.0.1:8189`; GPU1 → `127.0.0.1:8190` |
| Code / Python | `/home/jovyan/code/src`; `/nfs/envs/comfyui/bin/python3.11` |
| Input / output roots | `ComfyUI/input`; `ComfyUI/output` |
| Model and graph | checkpoint/revision plus workflow or runner SHA |
| Launch profile | full process arguments, attention flags, exact GPU binding |
| Generation profile | dimensions, fps, frames, steps, sampler, scheduler, shift |

Do not infer GPU binding from a port name. Resolve each ComfyUI PID and inspect its process
arguments and `/proc/<pid>/environ`, including `CUDA_VISIBLE_DEVICES`. Only compare lanes whose
model, code, nodes, and launch flags match.

Check queue state before submission, but do not treat an empty queue as completion evidence.

## 2. Protect long runs

Use a uniquely prefixed `tmux` session and log file for long jobs. Inspect existing sessions before
starting or stopping anything, and only operate on sessions created for the current project.

```bash
ssh <host> 'tmux new-session -d -s <project>-s1 "cd <code-root> && \
  <python> <runner> <tag> http://127.0.0.1:<port> \
  2>&1 | tee /tmp/<project>-s1.log"'
```

Read the log directly; use `tmux capture-pane -S` only as a secondary view. A detached session
protects the process from SSH loss, but it does not validate the runner or monitor.

## 3. Place and verify assets

Put real files under ComfyUI's allowed input root and use paths relative to that root in the graph.
The validated shared filesystem rejects ownership changes and symlink traversal, so use:

```bash
rsync -rlt --no-perms --no-owner --no-group <asset> <host>:<input-root>/<project>/
```

Hash before and after transfer. An apparently successful upload is not evidence that the intended
version arrived.

## 4. Extend a known-good runner safely

Copy a known-good config in code, change only the intended keys, and assert the diff:

```python
_NEW = dict(**_KNOWN_GOOD)
_NEW.update(end_img="<project>/new-end.png")

_diff = {k for k in set(_NEW) | set(_KNOWN_GOOD) if _NEW.get(k) != _KNOWN_GOOD.get(k)}
assert _diff == {"end_img"}, f"unexpected config diff: {_diff}"
```

Two failure modes can masquerade as success:

1. A hand-copied config can omit keys while the wrapper still prints `DONE` and exits zero.
2. Definitions appended after `if __name__ == "__main__": main()` are read during import but are
   not available when the real CLI enters `main()`.

For the second check, the new definition's line number must be **numerically less than / above** the
entry-point line. More importantly, exercise the real CLI dispatch path with a no-submit validation
mode when the runner offers one. If it does not, add a deterministic argument/config validation path
before relying on an import-only check.

Ask of every check: would completely broken configuration produce a different result?

## 5. Submit lanes as lanes, not variables

For the recorded profile, FL2VA used `n % 17 == 5`, at most 277 frames, 24fps, and 30 steps.
Revalidate these constraints after model, graph, or node changes. Probe every untried shape at low
steps to expose NaN or allocation failure before a full run.

Run different seeds for independent samples. Stagger concurrent starts when profiling shows an
overlapping text-encoder memory peak; the historical value was about 70 seconds, not a universal
constant.

## 6. Monitor by prompt ID

Capture the prompt ID returned by every submission. Monitor both success and terminal failures;
silence or missing data is WARN-and-retry, never completion.

Completion needs this positive chain:

1. `/history/<prompt-id>` reaches a terminal success state and reports the exact expected output;
2. the queue no longer contains that prompt ID;
3. the reported output becomes readable on storage;
4. its hash is fixed and the media passes decode/pixel checks.

An empty queue alone can mean success, failure, cancellation, or a task that was never submitted.
An output path alone can refer to stale content. Keep both history and the final hash.

## 7. Preserve an evidence manifest

For every accepted candidate or useful failure, retain:

- runtime profile and runner/workflow hash;
- first/last-frame paths and hashes;
- exact prompt and prompt hash;
- config diff, seed, lane, start time, and prompt ID;
- history terminal state, output path and hash;
- structured results from verify/freeze/cut tools;
- filmstrip, full-resolution observations, audio review, and delivery status.

Copy the deliverable and evidence locally before declaring the remote run complete.
