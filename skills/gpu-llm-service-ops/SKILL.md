---
name: gpu-llm-service-ops
description: Operate SSH-accessed GPU servers (train-1, train-h20, vscode/ultra) for conda envs and services: vLLM, ComfyUI, ai-toolkit, kohya_ss, LlamaFactory, OneTrainer. Use for shared /nfs/envs, Juscent bin scripts, GPU binding, tmux services, SSH tunnels, model stores and symlinks, custom nodes, task/usage stats, latency and storage benchmarks, or KAS multi-node training.
---

# GPU LLM Service Ops

## Task Routing

Read **only** the reference for the task at hand; do not load all of `references/` at once.

| Task | Entry point | Read on demand |
|---|---|---|
| Juscent service start/stop/status; reinstall & `/nfs` recovery; dual-instance / GPU binding | `…/juscent/bin/{comfyui,ai-toolkit,onetrain}.sh` | [nfs_envs_and_juscent_bin.md](references/nfs_envs_and_juscent_bin.md) |
| Env install & general repair; model stores & symlinks; SSH tunnels | conda + tmux | [gpu_service_runbook.md](references/gpu_service_runbook.md) |
| ComfyUI custom nodes, model taxonomy, missing-model debugging | — | [comfyui_node_model_ops.md](references/comfyui_node_model_ops.md) |
| ComfyUI install & validation checklist | — | [comfyui_server_runbook.md](references/comfyui_server_runbook.md) |
| OneTrainer install & GUI over noVNC (day-2 via `onetrain.sh`) | — | [onetrainer_runbook.md](references/onetrainer_runbook.md) |
| ai-toolkit / ComfyUI task & usage statistics | `scripts/gpu_task_counts.sh` | **Task Usage / Status** section below |
| vLLM streaming latency benchmark | `scripts/vllm_stream_ttft_client.py` | [gpu_service_runbook.md](references/gpu_service_runbook.md) |
| ComfyUI model link audit | `scripts/audit_model_links.sh` | [comfyui_node_model_ops.md](references/comfyui_node_model_ops.md) |
| Storage I/O benchmarking & placement (JuiceFS / NFS / local) | — | [storage_io_bench.md](references/storage_io_bench.md) |
| Multi-node KAS / VeOmni / NCCL-IB training | — | [kas_multinode_ib.md](references/kas_multinode_ib.md) |

## When To Use

Any GPU-server-over-SSH job in the routing table above: conda env create/repair, shared `/nfs/envs` recovery, Juscent service lifecycle, ComfyUI custom nodes and model taxonomy, model downloads into shared stores, tmux services, Mac↔GPU tunnels, dual-instance GPU binding, task/usage counts, vLLM TTFT, storage-backend benchmarks, and KAS multi-node training.

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
# Prefer Mac ~/.ssh/config aliases (ultra == vscode):
ssh train-1 | ssh train-h20 | ssh vscode | ssh ultra
# Full form if no alias: ssh -p 2222 <user>@hanhai-prod.ai.kingsoft.com
# Users per host are in the table above. infer-1 decommissioned 2026-07-17.
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

3. Execute by branch — pick the entry from the **Task Routing** table above and read only that reference.

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
