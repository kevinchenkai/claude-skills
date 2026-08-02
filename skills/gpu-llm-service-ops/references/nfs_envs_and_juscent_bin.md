# Shared NFS Envs + Juscent bin Control Scripts

Canonical ops for Juscent image stacks after the 2026-07-15 migration.
Human handbook (local): `Work/GPU-Ops/juscent-nfs-envs-ops-handbook-20260715.html`.

## Server short names / Host roles

| Short name | Role | Full SSH | Services |
| --- | --- | --- | --- |
| **`train-1`** | **training + inference (prod, default)** · 2×H20 | `ssh -p 2222 juscent-train-1-hh-970624@hanhai-prod.ai.kingsoft.com` | ComfyUI (GPU0), ai-toolkit UI (GPU1), OneTrainer GUI |
| **`train-h20`** | H20 training / storage benchmarking | `ssh -p 2222 juscent-train-h20-hh-970624@hanhai-prod.ai.kingsoft.com` | I/O benchmarks across 3 mounts |
| **`vscode`** / **`ultra`** | ultra validation · **2×H20** | `ssh -p 2222 vscode-h20-hh-970624@hanhai-prod.ai.kingsoft.com` | ComfyUI + ai-toolkit (+ optional OneTrainer); GPU-bound wrappers |
| ~~`infer-1`~~ | **decommissioned 2026-07-17** | ~~`juscent-infer-1-hh-970624@…`~~ | merged into `train-1` |

```bash
GPU_SSH_TRAIN1='ssh -p 2222 juscent-train-1-hh-970624@hanhai-prod.ai.kingsoft.com'
GPU_SSH_TRAINH20='ssh -p 2222 juscent-train-h20-hh-970624@hanhai-prod.ai.kingsoft.com'
GPU_SSH_VSCODE='ssh -p 2222 vscode-h20-hh-970624@hanhai-prod.ai.kingsoft.com'
# Mac SSH config aliases: Host train-1 / Host train-h20 / Host vscode / Host ultra
# ultra == vscode ; infer-1 decommissioned 2026-07-17
```

Shared gateway: `hanhai-prod.ai.kingsoft.com` · `-p 2222`. Users differ per short name.

Human handbooks (local):  
`Work/GPU-Ops/juscent-nfs-envs-ops-handbook-20260715.html` ·  
`Work/GPU-Ops/ultra-vscode-ops-handbook-20260716.md`

## Shared Conda Envs on NFS

### Mount

```text
nfs.inner.ai.kingsoft.com:.../shared-conda-env-nfs  on  /nfs  (nfs4)
```

Probe:

```bash
mount | grep ' on /nfs '
df -h /nfs
ls -la /nfs/envs
```

### Layout

| Path | Meaning |
| --- | --- |
| `/nfs/envs/<name>` | Real conda env prefix (shared across hosts) |
| `/opt/conda/envs/<name>` | Compatibility symlink → `/nfs/envs/<name>` |
| Shebangs in env bins | Rewritten to `#!/nfs/envs/<name>/bin/python` (etc.) |

Primary Juscent envs:

| Env | Used on | Notes |
| --- | --- | --- |
| `comfyui` | **train-1** · vscode/ultra | torch ~2.10+cu129 in current fleet |
| `ai-toolkit` | train-1 · **vscode/ultra** | Next.js UI + training workers |
| `onetrain` | train-1 · **vscode/ultra** | OneTrainer + Tk GUI |

Do **not** dual-write / ad-hoc `pip install` into `/nfs/envs/*` from ultra — changes affect all hosts.

Also present under `/nfs/envs` (not covered by Juscent bin scripts): `vllm-qwen3-family`, `lf-qwen3-family`, `veomni-qwen3-family`, helpers like `activate.sh`, `healthcheck.sh`.

### Activate

```bash
source /opt/conda/etc/profile.d/conda.sh
# Prefer absolute NFS path (works even if /opt symlink missing):
conda activate /nfs/envs/comfyui
# Or name form (requires symlink):
conda activate comfyui
```

Do **not** treat a hand-edited `PATH` as activation.

### Migrate a local env onto NFS (pattern)

Use only when deliberately relocating; production fleets should already be on NFS.

1. Stop services that use the env.
2. `rsync -aH --info=progress2 --no-group /opt/conda/envs/<name>/ /nfs/envs/<name>/`
   - JuiceFS/NFS often yields rsync exit `23` on chgrp; data may still be fine — verify sizes.
3. Rewrite shebangs under `/nfs/envs/<name>/bin` from old prefix to `/nfs/envs/<name>`.
4. Replace local prefix: `mv /opt/conda/envs/<name> /opt/conda/envs/<name>.bak.<date>` then  
   `ln -sfn /nfs/envs/<name> /opt/conda/envs/<name>`.
5. Smoke-test: `conda activate /nfs/envs/<name>` + key imports + CUDA.
6. Start service via bin script (below).

## Juscent Control Scripts

Directory (JuiceFS share):

```text
/home/share/game/juscent/bin/
  comfyui.sh
  ai-toolkit.sh
  onetrain.sh
```

**Removed** (do not recreate or document as primary):  
`start_comfyui_comui.sh`, `start_aitk_ui.sh`, `start_onetrainer_gui.sh`, `stop_onetrainer_gui.sh`.

### Uniform API

```bash
bash /home/share/game/juscent/bin/<script>.sh {start|stop|restart|status}
```

| Script | Host | tmux session | Port(s) | Workdir | Log | `CONDA_ENV` |
| --- | --- | --- | --- | --- | --- | --- |
| `comfyui.sh` | train-1 · vscode | `comui` | `8188` | `/home/jovyan/code/src/ComfyUI` | `/tmp/comfyui.log` | `/nfs/envs/comfyui` |
| `ai-toolkit.sh` | train-1 · vscode | `aitk-ui` | `8675` | `.../ai-toolkit/ui` (`npm run start`) | `/tmp/aitk-ui.log` | `/nfs/envs/ai-toolkit` |
| `onetrain.sh` | train-1 · vscode | `onetrain-gui` | noVNC `6080`, VNC `5901` | `.../OneTrainer` (`train_ui.py`) | `/tmp/onetrain-gui.log` | `/nfs/envs/onetrain` |

### ai-toolkit shared data paths (train-1 + vscode)

| Code-side path | Share entity |
| --- | --- |
| `/home/jovyan/code/src/ai-toolkit/output` | `/home/share/game/juscent/train_outputs/ai-toolkit` |
| `/home/jovyan/code/src/ai-toolkit/datasets` | `/home/share/game/juscent/datasets/ai-toolkit` |

Both hosts use **symlinks** to the same entities. Only one machine should write the same job output dir at a time.

### ultra / vscode GPU bind wrappers

Share bin scripts do **not** hardcode `CUDA_VISIBLE_DEVICES`. On vscode, prefer local wrappers:

```bash
# /home/jovyan/bin/comfyui-gpu0.sh · ai-toolkit-gpu1.sh · onetrain-gpu1.sh
bash /home/jovyan/bin/comfyui-gpu0.sh start      # GPU0 → :8188
bash /home/jovyan/bin/ai-toolkit-gpu1.sh start   # GPU1 → :8675
# Optional OneTrainer (same GPU1; stagger with heavy aitk jobs)
bash /home/jovyan/bin/onetrain-gpu1.sh start
```

```bash
# Preferred lifecycle
ssh vscode 'bash /home/jovyan/bin/comfyui-gpu0.sh status'
ssh vscode 'bash /home/jovyan/bin/ai-toolkit-gpu1.sh status'
ssh ultra  'bash /home/jovyan/bin/comfyui-gpu0.sh restart'   # ultra == vscode
```

`train-1` carries the same single-GPU wrappers at `/home/jovyan/bin/{comfyui-gpu0,ai-toolkit-gpu1,onetrain-gpu1}.sh` (verified 2026-07-24).

### Dual-instance wrappers on train-1 (2×H20)

Verified 2026-07-24. These run **two isolated instances of one stack**, one per GPU — used for A/B comparison runs. They are local (`/home/jovyan/bin`), not share bin, and both take `{start|stop|restart|status}`.

| Wrapper | Instances | tmux | Ports | Isolation |
| --- | --- | --- | --- | --- |
| `comfy-dual-infer.sh` | `gpu0-baseline`, `gpu1-ema-dropout` | `comfy-gpu0-baseline`, `comfy-gpu1-ema-dropout` | `8188`, `8189` | separate `--output/--temp/--user` under `…/juscent/comfyui/ema-comparison-20260717`; **`--database-url sqlite:///:memory:`** |
| `aitk-dual-ui.sh` | GPU1 (original), GPU0 (hard-link clone) | `aitk-gpu1`, `aitk-gpu0` | `8675`, `8676` | GPU0 uses a separate code tree `…/src/ai-toolkit-gpu0` with its own database |

```bash
ssh train-1 'bash /home/jovyan/bin/comfy-dual-infer.sh status'
ssh train-1 'bash /home/jovyan/bin/aitk-dual-ui.sh status'
```

Notes that matter when editing or debugging these:

- Both export offline HF caching: `HF_HOME`/`HF_HUB_CACHE` under `/home/share/game/juscent/models/huggingface` plus `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. A "model not found" failure here is usually the offline flag, not a missing file.
- `aitk-dual-ui.sh` sets `AITK_FORCE_GPU_IDS` **in addition to** `CUDA_VISIBLE_DEVICES`, and `CUDA_DEVICE_ORDER=PCI_BUS_ID`. The ai-toolkit UI needs the former to bind correctly.
- The dual wrappers refuse to start if the port is already occupied — stop the single-instance service first; `comfyui.sh` and `comfy-dual-infer.sh` both want `:8188`.
- Related post-processing helpers on train-1: `/home/jovyan/bin/post-train-ema-pipeline.sh` and `run-ema-comparison.py`.

### Verifying GPU binding

`nvidia-smi` memory is **not** evidence of binding — an idle service shows ~0 MiB. Check the process environment instead:

```bash
ssh train-1 'p=$(tmux list-panes -t comui -F "#{pane_pid}" | head -1); \
  cp=$(pgrep -P $p -f python | head -1); cp=${cp:-$p}; \
  tr "\0" "\n" < /proc/$cp/environ | grep -E "^CUDA_VISIBLE_DEVICES|^AITK_FORCE_GPU"'
```

If a service was started **without** a wrapper, `CUDA_VISIBLE_DEVICES` will be absent — meaning it can see **both** GPUs, not GPU0.

**`status` output is not proof of binding.** `comfy-dual-infer.sh status` prints `physical_gpu=0` from its own configuration table regardless of how the listening process was actually started; `tmux=down http=up` means something else owns the port. Observed on train-1 2026-07-24: status reported `physical_gpu=0` while the process holding `:8188` (tmux `comui`, started via the plain `comfyui.sh` path) had no `CUDA_VISIBLE_DEVICES` at all. Only `/proc/<pid>/environ` settles it. By contrast `aitk-dual-ui.sh status` does read live per-PID env and is trustworthy.

### Preferred lifecycle commands

```bash
# ComfyUI
ssh train-1 'bash /home/share/game/juscent/bin/comfyui.sh status'
ssh train-1 'bash /home/share/game/juscent/bin/comfyui.sh restart'

# Training UIs
ssh train-1 'bash /home/share/game/juscent/bin/ai-toolkit.sh status'
ssh train-1 'bash /home/share/game/juscent/bin/onetrain.sh status'
ssh train-1 'bash /home/share/game/juscent/bin/ai-toolkit.sh restart'
ssh train-1 'bash /home/share/game/juscent/bin/onetrain.sh restart'
```

Prefer these over raw `tmux send-keys` for day-2 ops. Use manual tmux only when debugging a broken script or installing new stacks.

### Behavior notes

- `start`: if port already listening, no-op success; else `tmux new -d` running `bash <self> _run`, wait up to ~80s for HTTP readiness.
- `stop`: Ctrl-C in tmux → kill session → `fuser -k PORT/tcp` if needed; onetrain also kills Xvfb/x11vnc/websockify/fluxbox via pid files under `/tmp/onetrainer-gui`.
- `status`: session up/down + port + lightweight HTTP probe (ComfyUI uses `/system_stats`).
- Scripts use `set -u`. Around `conda activate`, they temporarily `set +u` because conda deactivate hooks (e.g. binutils) reference unset `CONDA_BACKUP_*` variables and would abort the start pane. **Keep that protection** when editing scripts.
- Share `bin/` directory is often root-owned; creating/deleting files may need `sudo`. Editing existing jovyan-owned scripts may work without sudo.
- Avoid broad `pkill -f` patterns that can match the control script itself when editing/deploying.

### Mac tunnels

```bash
# Production
ssh -N -L 8188:127.0.0.1:8188 train-1
ssh -N -L 8675:127.0.0.1:8675 train-1
ssh -N -L 6080:127.0.0.1:6080 train-1   # open http://127.0.0.1:6080/vnc.html

# ultra / vscode (2×H20 dual-stack)
ssh -N -L 8188:127.0.0.1:8188 vscode
ssh -N -L 8675:127.0.0.1:8675 vscode
ssh -N -L 6080:127.0.0.1:6080 vscode
```

## Reinstall Recovery (shortest path)

After a GPU pod/host reinstall:

1. **Mount NFS** to `/nfs` (shared-conda-env-nfs). Confirm `ls /nfs/envs`.
2. **Restore JuiceFS** mounts if used (`/home/share`, `/home/jovyan` as applicable) so code + models exist.
3. **Symlinks**:
   ```bash
   # train-1
   ln -sfn /nfs/envs/comfyui /opt/conda/envs/comfyui
   # train-1
   ln -sfn /nfs/envs/ai-toolkit /opt/conda/envs/ai-toolkit
   ln -sfn /nfs/envs/onetrain   /opt/conda/envs/onetrain
   ```
4. **Code paths present**:
   - train-1: `/home/jovyan/code/src/ComfyUI`
   - train-1: `/home/jovyan/code/src/ai-toolkit`, `/home/jovyan/code/src/OneTrainer`
5. **OneTrainer GUI apt deps** if missing: `Xvfb`, `x11vnc`, `websockify`, `fluxbox`, and common OpenGL libs (`libGL`, etc.).
6. **Start** with bin scripts; `status` until ready.
7. Optional: restore any host-local caches not on share (rare).

Do not reinstall whole conda envs from scratch if `/nfs/envs` is healthy.

## Model / Cache Defaults (scripts)

| Stack | Primary models | Cache env in control script |
| --- | --- | --- |
| ComfyUI | `/home/share/game/juscent/models` | `MODELSCOPE_CACHE`, `HF_ENDPOINT`, etc. |
| ai-toolkit | Juscent store for image training | `HF_*` under juscent/models/huggingface, often offline |
| OneTrainer | seasun models + juscent train outputs | `HF_*` under seasun/models/.hf_cache |

## Quick Health

```bash
ssh train-1 'bash /home/share/game/juscent/bin/comfyui.sh status; ls -l /opt/conda/envs/comfyui; mount | grep " on /nfs "'
ssh train-1 'bash /home/share/game/juscent/bin/ai-toolkit.sh status; bash /home/share/game/juscent/bin/onetrain.sh status; ls -l /opt/conda/envs/{ai-toolkit,onetrain}'
```

### Common failures

| Symptom | Check | Fix |
| --- | --- | --- |
| Session dies immediately | `/tmp/<service>.log` | NFS mount, env path, `set +u` around activate |
| Port never ready | log + `tmux capture-pane` | missing code dir, npm deps, GUI packages |
| `/nfs/envs` missing | `mount`, `df -h /nfs` | remount PVC/NFS |
| Broken `/opt/conda/envs/X` | `ls -l` | recreate `ln -sfn` |
| OneTrainer blank GUI | Xvfb/libGL | apt install GUI stack, restart |

## Verified Snapshot (2026-07-15)

- infer-1: `comfyui.sh restart` → :8188 ready, ComfyUI 0.26.2, torch 2.10.0+cu129
- train-1: `ai-toolkit.sh restart` → :8675 HTTP 200
- train-1: `onetrain.sh restart` → :6080 noVNC, :5901 VNC, `CONDA_PREFIX=/nfs/envs/onetrain`
