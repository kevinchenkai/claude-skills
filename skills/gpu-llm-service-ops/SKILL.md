---
name: gpu-llm-service-ops
description: Use when operating SSH-accessed GPU servers (train-1, train-h20, vscode/ultra) for conda environments and services including vLLM, ComfyUI, ai-toolkit, kohya_ss, LlamaFactory, and OneTrainer; managing shared NFS conda envs under /nfs/envs with /opt/conda/envs symlinks; using Juscent bin control scripts (comfyui.sh, ai-toolkit.sh, onetrain.sh) and GPU-bind or dual-instance wrappers; reinstall recovery (remount NFS + relink + restart); installing OneTrainer GUI via VNC/noVNC; installing ComfyUI custom nodes; downloading or linking models into shared LLM/ComfyUI stores; managing tmux service sessions; creating Mac-to-GPU SSH port forwards; counting ai-toolkit training and ComfyUI inference task usage; running vLLM streaming latency benchmarks; benchmarking or choosing between JuiceFS, NFS, and local storage for checkpoints, envs, and datasets; or multi-node distributed training on the KAS platform with VeOmni, torchrun rendezvous, and NCCL over InfiniBand/RoCE.
---

# GPU LLM Service Ops

## When To Use

Use this skill when the user asks to work on a GPU server over SSH for any of these jobs:

- Create, repair, inspect, or switch isolated conda environments for `vllm`, `comfyui`, `ai-toolkit`, `sdxl`/`kohya_ss`, `lf`/LlamaFactory, or `onetrain`/OneTrainer.
- Operate or recover **shared NFS envs** at `/nfs/envs` and compatibility links under `/opt/conda/envs/*`.
- Start, stop, restart, or status **Juscent image services** via `/home/share/game/juscent/bin/{comfyui,ai-toolkit,onetrain}.sh`.
- Host reinstall recovery: remount `/nfs`, restore JuiceFS paths, recreate env symlinks, restart services.
- Install, update, troubleshoot, or operationalize ComfyUI custom nodes and their Python/model dependencies.
- Download models into shared LLM or ComfyUI stores and create symlinks instead of duplicating large files.
- Diagnose ComfyUI missing-model, auto-download, broken symlink, or shared model taxonomy problems.
- Start, stop, restart, or inspect services in named `tmux` sessions (prefer bin scripts when they exist).
- Link the local Mac to the GPU machine with SSH tunnels and verify service endpoints.
- Count recent ai-toolkit training jobs, ComfyUI prompt executions, and ComfyUI output artifacts on SSH GPU hosts.
- Run OpenAI-compatible vLLM requests, especially streaming TTFT tests.
- Run **dual-instance** ComfyUI or ai-toolkit (one per GPU) for A/B comparison runs, and verify GPU binding.
- Benchmark or choose between **storage backends** (JuiceFS `/home/share1` · `/home/share`, NFS `/nfs`, local overlay) for checkpoints, conda envs, model loading, or datasets.
- Set up or debug **multi-node training on KAS**: `KAS_*` → `torchrun` rendezvous, NCCL over InfiniBand/RoCE, VeOmni/FSDP2 launches.

## Required Inputs

Normalize these before changing anything:

- `GPU_SSH`: full SSH command (see **Server short names** below). Prefer alias `ssh train-1` (default) / `ssh train-h20` / `ssh vscode` when local SSH config is set; otherwise use the full command.
- Target service or environment: `vllm`, `comfyui`, `ai-toolkit`, `kohya_ss`, `LlamaFactory`, or `OneTrainer`.
- For ComfyUI node work: plugin repository/name, expected workflow/model, and whether node install, model download, or troubleshooting is requested.
- Whether the user wants execution now or a plan first.
- Model path, served model name, port, and expected tmux session when relevant.
- For usage/task counts: time window, timezone/date boundary, SSH command(s), ai-toolkit path, ComfyUI path, and ComfyUI port if not `8188`.

If the SSH target is missing, ask for it once. If a model directory is ambiguous, inspect candidates and ask or report before launching.

## Default Topology

Use these defaults unless the user gives different paths.

### Server short names (Juscent fleet)

**`train-1` is the default host for all Juscent work** (training *and* inference) unless the user names another. `infer-1` was decommissioned 2026-07-17 and its ComfyUI role folded into train-1 — do not use it as a default or an example.

| Short name | Role | Full SSH | Primary services |
| --- | --- | --- | --- |
| **`train-1`** | **training + inference (prod, default)** · 2×H20 | `ssh -p 2222 juscent-train-1-hh-970624@hanhai-prod.ai.kingsoft.com` | ComfyUI **GPU0** · ai-toolkit **GPU1** · OneTrainer (`comfyui.sh`, `ai-toolkit.sh`, `onetrain.sh`) |
| **`train-h20`** | H20 training / storage benchmarking | `ssh -p 2222 juscent-train-h20-hh-970624@hanhai-prod.ai.kingsoft.com` | I/O benchmarking across 3 mounts; see `references/storage_io_bench.md` |
| **`vscode`** / **`ultra`** | ultra validation · 2×H20 | `ssh -p 2222 vscode-h20-hh-970624@hanhai-prod.ai.kingsoft.com` | ComfyUI **GPU0** + ai-toolkit **GPU1** (+ optional OneTrainer GPU1) |
| ~~`infer-1`~~ | **decommissioned 2026-07-17** | ~~`juscent-infer-1-hh-970624@…`~~ | merged into `train-1` |

```bash
# Canonical GPU_SSH values
GPU_SSH_TRAIN1='ssh -p 2222 juscent-train-1-hh-970624@hanhai-prod.ai.kingsoft.com'
GPU_SSH_TRAINH20='ssh -p 2222 juscent-train-h20-hh-970624@hanhai-prod.ai.kingsoft.com'
GPU_SSH_VSCODE='ssh -p 2222 vscode-h20-hh-970624@hanhai-prod.ai.kingsoft.com'
# infer-1 decommissioned 2026-07-17 — no canonical value.

# Prefer Mac ~/.ssh/config aliases:
#   ssh train-1 | ssh train-h20 | ssh vscode | ssh ultra
# ultra == vscode (same user/host/port)
```

Gateway: `hanhai-prod.ai.kingsoft.com` · port `2222`. Users differ per short name.

**ultra / vscode notes (validated 2026-07-16):**

- Env: `/opt/conda/envs/{comfyui,ai-toolkit,onetrain}` → `/nfs/envs/*` (do **not** pip-install into shared NFS envs from vscode).
- Data (shared with train-1):  
  `…/ai-toolkit/output` → `/home/share/game/juscent/train_outputs/ai-toolkit`  
  `…/ai-toolkit/datasets` → `/home/share/game/juscent/datasets/ai-toolkit`  
  Concurrent train writes: **one writer per job dir**.
- GPU bind wrappers (local, not share bin):  
  `/home/jovyan/bin/comfyui-gpu0.sh` · `ai-toolkit-gpu1.sh` · `onetrain-gpu1.sh`
- Human handbook: `Work/GPU-Ops/ultra-vscode-ops-handbook-20260716.md`

### Stacks

| Stack | Conda env | Env prefix (source of truth) | Code path | tmux | Port | Control script | Shared models / data |
| --- | --- | --- | --- | --- | --- | --- | --- |
| vLLM | `vllm` / family names | often under `/nfs/envs/*` or local | `/home/share/game/seasun/vllm` | `vllm` | `8000` | `.../seasun/vllm/start_vllm.sh` | `/home/share/game/seasun/models` |
| ComfyUI | `comfyui` | **`/nfs/envs/comfyui`** (`/opt/conda/envs/comfyui` → symlink) | `/home/jovyan/code/src/ComfyUI` | `comui` | `8188` | **`…/juscent/bin/comfyui.sh`** (ultra: `~/bin/comfyui-gpu0.sh`) | `/home/share/game/juscent/models` |
| ai-toolkit | `ai-toolkit` | **`/nfs/envs/ai-toolkit`** | `/home/jovyan/code/src/ai-toolkit` | `aitk-ui` | `8675` | **`…/juscent/bin/ai-toolkit.sh`** (ultra: `~/bin/ai-toolkit-gpu1.sh`) | Juscent models; **output/datasets → share** (see data paths below) |
| kohya_ss | `sdxl` | local or NFS if migrated | `/home/jovyan/code/src/kohya_ss` | `sdxl` | `7860` | (none canonical) | `/home/share/game/juscent/models` |
| LlamaFactory | `lf` / family | often `/nfs/envs/lf-*` | `/home/jovyan/code/src/LlamaFactory` | `lf` | `7861` | (none Juscent bin) | `/home/share/game/seasun/models` |
| OneTrainer | `onetrain` | **`/nfs/envs/onetrain`** | `/home/jovyan/code/src/OneTrainer` | **`onetrain-gui`** | noVNC `6080` / VNC `5901` | **`…/juscent/bin/onetrain.sh`** (ultra: `~/bin/onetrain-gpu1.sh`) | Seasun models; train outputs under Juscent |

**ai-toolkit shared data (train-1 + vscode/ultra):**

| Logical | Entity on share |
| --- | --- |
| `…/ai-toolkit/output` | `/home/share/game/juscent/train_outputs/ai-toolkit` |
| `…/ai-toolkit/datasets` | `/home/share/game/juscent/datasets/ai-toolkit` |

Always activate conda explicitly:

```bash
source /opt/conda/etc/profile.d/conda.sh
# Prefer absolute NFS prefix when present:
conda activate /nfs/envs/<name>
# Name form requires /opt/conda/envs/<name> symlink:
conda activate <name>
```

Do not treat a modified `PATH` as equivalent to conda activation.

## Operating Rules

- Prefer noninteractive SSH commands and `tmux send-keys` / `tmux capture-pane` over manual attach flows.
- **For ComfyUI / ai-toolkit / OneTrainer day-2 ops on Juscent hosts, prefer**  
  `bash /home/share/game/juscent/bin/{comfyui,ai-toolkit,onetrain}.sh {start|stop|restart|status}`  
  over hand-rolled tmux launches. Old wrappers `start_comfyui_comui.sh`, `start_aitk_ui.sh`, `start_onetrainer_gui.sh`, `stop_onetrainer_gui.sh` are **removed** — do not recreate them as the primary path.
- Before changes, run a read-only probe: `hostname`, `whoami`, `conda info --envs`, `nvidia-smi`, `df -h / /home/share /nfs`, `mount | grep /nfs`, `ls -l /opt/conda/envs`, `tmux ls`, and `ss -ltnp` for relevant ports.
- Stop services by control script when available; otherwise tmux session first: `tmux send-keys -t <session> C-c`, inspect, then `tmux kill-session -t <session>` if needed.
- Avoid broad remote `pkill -f` patterns unless the exact process is verified and the user asked to stop it (self-matching guards can kill the control script during deploy).
- Keep large downloads in `tmux model` or another clearly named long-running session.
- For complex `tmux send-keys` commands with variables, quotes, pipes, or redirects, write a short remote script under `/tmp` and send only the script path to tmux.
- For vLLM launches, always use the canonical script `/home/share/game/seasun/vllm/start_vllm.sh` — do not inline `vllm serve` arguments. To switch models, edit `model_path` and `model_name` in that script. Launch via: `tmux send-keys -t vllm "bash /home/share/game/seasun/vllm/start_vllm.sh 2>&1 | tee /tmp/vllm.log" Enter`.
- Put LLM-oriented models under `/home/share/game/seasun/models` and ComfyUI/image-generation models under `/home/share/game/juscent/models`. For ai-toolkit, choose the store by model namespace: Flux/Qwen-Image/ComfyUI-compatible training should use the Juscent store and cache; generic LLM training should use the Seasun store and cache.
- Symlink ComfyUI local model folders to the shared store; avoid copying multi-GB model files into source trees.
- Never `pip install`, untar, or build into `/nfs/envs` casually: NFS writes measured **~145 MB/s vs ~950 MB/s** on both JuiceFS volumes and do not scale with concurrency, and the volume is shared across hosts. Install to local disk and move, or accept a slow serialized write. See `references/storage_io_bench.md`.
- For ComfyUI custom node work, inspect README, requirements, and model-loading code before installing dependencies or downloading models.
- For ComfyUI node runtime import errors, capture the failing stack from `tmux comui` or `/tmp/comfyui.log`, identify the package import path, then install the narrowest missing dependency in the active ComfyUI env. For CUDA extension packages, first record Python, Torch, CUDA runtime, driver, and GPU; prefer a wheel matching the existing Torch ABI and install with `--no-deps` unless deliberately changing Torch.
- When opening Mac-to-GPU tunnels, verify both the remote endpoint and the local forwarded endpoint.
- For statistics requests, keep probes read-only. Distinguish task counts from artifact counts: ai-toolkit has a persistent `Job` table; ComfyUI `/history` is prompt-level but may reset when the service restarts; `output/` file counts are artifact counts and can overcount one task.
- For latency reports, separate network/tunnel baseline from vLLM TTFT using `/health` RTT and streaming first-token timing.
- For OneTrainer, prefer named env `onetrain` at `/nfs/envs/onetrain` rather than OneTrainer's project-local `conda_env`. GUI session name is **`onetrain-gui`** (not `onetrain`).
- For GUI desktop apps such as OneTrainer, bind VNC/noVNC to remote localhost by default and access through an SSH tunnel. Do not expose VNC/noVNC on `0.0.0.0` unless the user explicitly requests it and understands the risk.
- Juscent control scripts use `set -u` and temporarily `set +u` around `conda activate` (conda deactivate hooks can abort on unset `CONDA_BACKUP_*`). Preserve that pattern when editing scripts.
- JuiceFS `bin/` may be root-owned; creating/deleting files often needs `sudo`; editing existing jovyan-owned scripts may not.

## Workflow

1. Establish context.
   - Parse or confirm the SSH command / host role (default `train-1`; else `train-h20` or `vscode`/`ultra`).
   - Identify requested stack, tmux session, port, conda env (prefer `/nfs/envs/<name>`), and model store.
   - If asked to produce a plan, save it as a `.md` and wait for confirmation.

2. Probe the target.
   - Run the read-only commands in one SSH call where practical, **including** `/nfs` mount and env symlinks for Juscent stacks.
   - Capture existing tmux sessions and port owners before stopping or starting services.

3. Execute by branch.
   - **Juscent service lifecycle**: `references/nfs_envs_and_juscent_bin.md` + bin scripts.
   - **Reinstall / NFS recovery**: remount `/nfs` → symlink `/opt/conda/envs/*` → verify code paths → bin `start`/`status` (same reference).
   - Environment installation and general repair: `references/gpu_service_runbook.md`.
   - Model downloads and symlinks: shared-store rules in the runbook.
   - ComfyUI custom nodes, model taxonomy, and missing-model debugging: `references/comfyui_node_model_ops.md` and `references/comfyui_server_runbook.md`.
   - OneTrainer installation and GUI: `references/onetrainer_runbook.md` (day-2 start/stop via `onetrain.sh`).
   - Usage/task statistics: see **Task Usage / Status** section; `scripts/gpu_task_counts.sh` or equivalent read-only SSH commands.
   - SSH tunnel and vLLM benchmark: runbook plus `scripts/vllm_stream_ttft_client.py`.
   - **Dual-instance / GPU binding**: dual wrappers + `/proc/<pid>/environ` verification in `references/nfs_envs_and_juscent_bin.md`.
   - **Storage I/O benchmarking and placement**: `references/storage_io_bench.md`.
   - **Multi-node KAS / VeOmni / NCCL-IB training**: `references/kas_multinode_ib.md`.

4. Verify.
   - Confirm conda env imports and CUDA visibility (`conda activate /nfs/envs/<name>`).
   - Confirm service ports with control-script `status`, `curl`, and logs under `/tmp/*.log`.
   - For ComfyUI, verify `/system_stats`, scan logs for import/download errors, and run `scripts/audit_model_links.sh` when model links changed.
   - For OneTrainer, verify `torch.cuda.is_available()`, key imports, `python scripts/train.py -h`, Tk/customtkinter imports, `pip check`, and the noVNC HTTP endpoint if GUI was installed.
   - For statistics, report the exact window, counts by day/status, and caveats about ComfyUI history retention versus filesystem output artifacts.
   - For benchmarks, save JSON/CSV results and present a concise summary or visualization.
   - For GPU binding, confirm via `/proc/<pid>/environ` — **never** infer binding from `nvidia-smi` memory (an idle service shows ~0 MiB on both cards).
   - For storage benchmarks, always report cold and hot reads in separate columns; never average them.

## Task Usage / Status (查看 ai-toolkit · ComfyUI 执行任务情况)

When the user asks how many / which ai-toolkit training jobs or ComfyUI executions ran (e.g. "统计最近 N 天任务情况"), stay **read-only** and treat the two stacks differently — they have very different data quality.

**Default host:** since 2026-07-17 both ai-toolkit and ComfyUI run on **train-1** (infer-1 decommissioned), so one SSH usually covers both. Confirm the window and the localtime day boundary first (`date '+%F %T %Z'`), then compute `--since`.

Fast path — the bundled helper does all of this:

```bash
scripts/gpu_task_counts.sh --since "YYYY-MM-DD HH:MM:SS" --ssh "ssh train-1"
# split hosts: --train-ssh / --comfy-ssh ; single stack: --skip-comfy / --skip-train
```

**ai-toolkit — authoritative.** The `Job` table in `aitk_db.db` is persistent (survives restarts). `created_at` is epoch **milliseconds** → `datetime(created_at/1000,'unixepoch','localtime')`. Report total + by-day + by-status (`completed` / `running` / `error` / `stopped`); a `stopped` row at `step=0` is a job created then aborted, not real training.

**ComfyUI — no reliable task count.** `/history` is **in-process and resets on every service restart**, so after any restart in the window it only shows the current session. Verify by dating the earliest surviving prompt (helper prints a WARNING when it is after the window start). The durable proxy is **`output/` files by mtime** — but these are **artifacts, not tasks** (one workflow emits many images), and `output/` resolves to the **shared** `…/comfyui/output`, so files may not all originate from this host. Always state both caveats; never present the artifact count as a task count. For a truer task estimate, group output files by `projects/<name>/` subfolder or filename prefix.

## Bundled Helpers

- `scripts/gpu_task_counts.sh`: read-only ai-toolkit `Job` counts + ComfyUI `/history` (with restart detection) and shared `output/` artifact counts over a window. One `--ssh` covers both stacks on train-1.
- `scripts/vllm_stream_ttft_client.py`: local or remote OpenAI-compatible streaming benchmark client. It records `/health` RTT, response header latency, end-to-end TTFT, and estimated vLLM service time.
- `scripts/audit_model_links.sh`: ComfyUI local/shared model link audit helper.
- `references/nfs_envs_and_juscent_bin.md`: **shared `/nfs/envs`, Juscent bin scripts, reinstall recovery, host roles** (2026-07-15+).
- `references/gpu_service_runbook.md`: command templates for setup, tmux services, model stores, SSH tunnels, and validation.
- `references/onetrainer_runbook.md`: OneTrainer named-env install, GitHub/source fallback, CUDA/Tk verification, and GUI over noVNC.
- `references/comfyui_node_model_ops.md`: migrated ComfyUI custom node, model download, symlink, taxonomy, and known gotcha runbook.
- `references/comfyui_server_runbook.md`: concise ComfyUI install and validation command checklist.
- `references/storage_io_bench.md`: JuiceFS/NFS/local mount topology, measured throughput baseline, placement guidance, and the `io_bench_h20.py` harness with its no-`fio`/no-`drop_caches` methodology.
- `references/kas_multinode_ib.md`: KAS multi-node training — `KAS_*` → `torchrun` mapping, NCCL/IB tuning table, and how to verify NCCL is really on IB.
