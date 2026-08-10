# H3 Runbook — running generation on the GPU host

> Host aliases, ports and paths below are from one specific environment.
> **Confirm them against the actual machine before relying on them.**

---

## 1. Topology

```bash
ssh vscode            # primary host
```

| Item | Value |
| --- | --- |
| ComfyUI | **GPU0 → `127.0.0.1:8189`**, **GPU1 → `127.0.0.1:8190`** |
| Code | `/home/jovyan/code/src` |
| Python | `/nfs/envs/comfyui/bin/python3.11` (**not** system python) |
| Inputs | `…/ComfyUI/input/<project>/` |
| Outputs | `…/ComfyUI/output/<prefix>/` |

**Before submitting, confirm two things:**

```bash
# ① Both instances launched with identical flags
ssh vscode 'ps -eo cmd | grep [m]ain.py'

# ② Queues are free
ssh vscode 'for p in 8189 8190; do echo -n "$p: "; curl -s "http://127.0.0.1:$p/queue" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(len(d[\"queue_running\"]),len(d[\"queue_pending\"]))"; done'
```

> 🔴 **A run must not straddle differing launch flags.** An attention-kernel flag changes the
> numerics — clips from mismatched instances **are not comparable**, and a disagreement between
> them cannot be attributed.

## 2. tmux for anything long

A full clip takes roughly **45 minutes**. SSH drops; a bare command dies with it.

```bash
ssh vscode 'tmux new-session -d -s ck-run "cd /home/jovyan/code/src && \
  /nfs/envs/comfyui/bin/python3.11 h3_flf_experiment.py <tag> http://127.0.0.1:8189 \
  2>&1 | tee /tmp/ck-run.log"'

ssh vscode 'tail -30 /tmp/ck-run.log'                                  # prefer the log file
ssh vscode 'tmux capture-pane -pt ck-run -S -200 | grep -v "^$" | tail -40'
```

- Prefix your sessions (`ck-`) and **only kill your own**; `tmux ls` before acting.
- 🔴 `capture-pane` **without `-S`** returns blank lines — it captures the visible pane only.
- tmux protects against **interrupted commands**. It does **not** make a monitoring script correct
  (§6).

## 3. Asset placement

Assets must sit in ComfyUI's **`input/`** directory; config paths are **relative to it**.

```bash
rsync -rlt --no-perms --no-owner --no-group <img> vscode:/home/jovyan/code/src/ComfyUI/input/<project>/
```

- **`-rlt --no-perms --no-owner --no-group`, not `-a`** — ownership changes fail on this filesystem.
- 🔴 **Verify md5 after transfer.** "Upload succeeded" ≠ "correct version".
- Symlinks are rejected by ComfyUI's path guard.

## 4. Adding an experiment — two traps that cost real time

**Reuse the known-good config; never retype it.**

```python
_NEW = dict(**_KNOWN_GOOD)
_NEW.update(end_img="<project>/new-end.png")

_diff = {k for k in set(_NEW) | set(_KNOWN_GOOD) if _NEW.get(k) != _KNOWN_GOOD.get(k)}
assert _diff == {"end_img"}, f"unexpected config diff: {_diff}"
```

> 🔴 **Trap 1 — hand-copied config.** Missing keys killed both lanes within 5 seconds, **with
> `rc=0` and a `DONE` line identical to success.** Monitoring looked fine.

> 🔴 **Trap 2 — appended after the entry point.** If the file ends with
> `if __name__ == "__main__": main()`, definitions appended *after* it are never reached by the CLI.
>
> **And importing the module does not catch this** — on import, `__name__` isn't `"__main__"`,
> `main()` never fires, the file is read to the end, and every assertion passes. The real run still
> fails. **Self-check through the real entry point**, e.g. confirm the new definition's line number
> is *below* the `if __name__` line.

**Both traps are the same disease: a failure that looks exactly like success.** Whenever you write
a check, ask — *if this were completely broken, would the output differ?*

## 5. Parameters and lanes

| Item | Value |
| --- | --- |
| Frames | **`n % 17 == 5`**, **≤ 277** for FL2VA |
| Steps | 30 |
| fps | 24 |
| Per clip | ≈ 45 min |

**Probe any untried resolution or frame count first** — a low-step run of the same shape, purely to
prove it doesn't NaN.

Run one lane per GPU, **staggered by ~70 s** so the text-encoder memory peaks don't overlap.

> **Ports are lanes, not variables.** Running the same tag on both cards gives two identical clips.
> Vary the **seed** to get a second sample.

## 6. Monitoring

A monitor that only greps for the success marker stays **silent** through a crash — and silence is
indistinguishable from "still running". **Match terminal failures too** (traceback, error, killed),
and treat "no data" as WARN-and-retry, never as done.

Completion requires **positive evidence**: queue empty **and** the expected outputs present.

## 7. After generation

Verify pixels before discussing content — see `acceptance_criteria.md` §2. Then copy the deliverable
and its evidence back to the local machine.
