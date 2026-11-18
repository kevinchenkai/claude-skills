---
name: gpu-llm-service-ops
description: >-
  Operate SSH-accessed GPU servers (KSP: train-1, vscode, vla-h200, h100-1..4, ksp-h20-1; hanhai: hanhai-train-1, train-h20) for conda envs and services: vLLM, ComfyUI, ai-toolkit, kohya_ss, LlamaFactory, OneTrainer. Use for shared /nfs/envs, Juscent bin scripts, GPU binding, tmux services, SSH tunnels, model stores and symlinks, custom nodes, task/usage stats, latency and storage benchmarks, KAS multi-node training, KS3 (ks3util) transfers, or speech-to-text (ASR, Whisper) and burned-in subtitle OCR on video or audio files.
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
| KS3 upload/download (cluster ↔ KS3 ↔ Mac), verification | `ks3util` with `-f` | [ks3util.md](references/ks3util.md) |
| ASR (faster-whisper) and burned-in subtitle OCR (RapidOCR); **default host `vscode`** | `scripts/asr_transcribe.py`, `scripts/ocr_burned_subs.py` | [asr_ocr.md](references/asr_ocr.md) |

## When To Use

Any GPU-server-over-SSH job in the routing table above: conda env create/repair, shared `/nfs/envs` recovery, Juscent service lifecycle, ComfyUI custom nodes and model taxonomy, model downloads into shared stores, tmux services, Mac↔GPU tunnels, dual-instance GPU binding, task/usage counts, vLLM TTFT, storage-backend benchmarks, KAS multi-node training, and ASR/OCR on media files.

## Required Inputs

Normalize these before changing anything:

- `GPU_SSH`: full SSH command (see **Server short names** below). Prefer the Mac aliases in **Server short names** below (`ssh train-1` is the default host; it is a KSP pod since 2026-11-17); otherwise use the full command.
- Target service or environment: `vllm`, `comfyui`, `ai-toolkit`, `kohya_ss`, `LlamaFactory`, or `OneTrainer`.
- For ComfyUI node work: plugin repository/name, expected workflow/model, and whether node install, model download, or troubleshooting is requested.
- Whether the user wants execution now or a plan first.
- Model path, served model name, port, and expected tmux session when relevant.
- For usage/task counts: time window, timezone/date boundary, SSH command(s), ai-toolkit path, ComfyUI path, and ComfyUI port if not `8188`.

If the SSH target is missing, ask for it once. If a model directory is ambiguous, inspect candidates and ask or report before launching.

## Default Topology

Use these defaults unless the user gives different paths.

### Server short names

Mac `~/.ssh/config` aliases were reshuffled on 2026-11-13 and 2026-11-17. **Docs, memories and scripts written before 2026-11-17 that say `train-1` or `vscode` mean the hanhai pods**: read them as `hanhai-train-1` / the retired hanhai vscode.

**KSP fleet (current; `User root`, key `~/.ssh/ksp`, port 22):**

| Alias | Hardware · cgroup | Notes |
| --- | --- | --- |
| **`train-1`** | 2×H20 · 16 CPU / 64 GiB | KSP pod since 2026-11-17 (`172.20.249.3`). **Juscent stack not installed** (no `/home/jovyan/code/src`, no conda envs, no services); `/home/share/game/juscent/bin` is visible but untested here. Probe before assuming anything. |
| **`vscode`** (= `ksp-145`, public `vscode-pub`) | 2×H20 · 32 CPU / 128 GiB | Personal dev / jump pod (`172.20.251.145`, EIP `120.92.90.22`). No ComfyUI. Default host for ASR/OCR and the LLM-WIKI. |
| `vla-h200` | 8×H200 | ComfyUI/H3 host for my own distribution (see below). |
| `h100-1` … `h100-4` (`h100-3` = `ksp-h100-3`) | 8×H100 each · 164 CPU / 1600 GiB | Others' jobs may be running (check `nvidia-smi` and cgroup `cpu.stat` first). |
| `ksp-h20-1` | 8×H20 · 190 CPU / 900 GiB | — |

KSP notes:

- All pods mount `/home/share`, `/home/share1` (JuiceFS), the shared `/nfs` (`/nfs/envs/*`) and a persistent `/home/jovyan` (ceph-fuse). Everything else, including `/root` and `/opt`, is reset when the container restarts.
- `huggingface.co` is reachable directly (the hanhai pods needed hf-mirror).
- In-container `free`, `uptime`, `ps` ELAPSED/%CPU are LXCFS-virtualised; trust `/sys/fs/cgroup/{cpu.max,memory.max,cpu.stat}` and `/proc/zoneinfo` instead.
- The pods sit behind Istio: a single `Connection reset` / timeout is often transient, so retry once before calling a host down.
- `vscode` restore after a restart: `bash /home/jovyan/chenkai/vscode-init/restore.sh` (prompt, `ks3util` alias, in-pod KSP ssh config). Its `README.md` has the acceptance checklist; from outside the VPN use `ssh -J vscode-pub <alias>`.
- ComfyUI / H3 on KSP: use my distribution `Juscent/scripts/comfyui-env/README.md` in chenkai_airepo (ports `8290+GPU`, deployed with `deploy.sh`), not the colleague's `juscent/bin/comfyui.sh`.

**hanhai fleet (gateway `hanhai-prod.ai.kingsoft.com:2222`, key `~/.ssh/id_rsa`; users differ per alias):**

| Alias | Status | Full SSH |
| --- | --- | --- |
| `hanhai-train-1` | was alias `train-1` until 2026-11-17; **no GPUs as of 2026-11-17**. Code still under `/home/jovyan/code/src`; all Juscent-stack runbooks below were written for it. | `ssh -p 2222 juscent-train-1-hh-970624@hanhai-prod.ai.kingsoft.com` |
| `train-h20` | storage benchmarking host (`references/storage_io_bench.md`); gateway refused login on 2026-11-17 | `ssh -p 2222 juscent-train-h20-hh-970624@hanhai-prod.ai.kingsoft.com` |
| ~~hanhai vscode~~ (ultra, `vscode-h20-0`) | **offline 2026-11-17**, alias removed. ComfyUI 8189/8190, `/home/jovyan/bin/*-gpu*.sh` wrappers and the ASR/OCR timings came from it. | ~~`vscode-h20-hh-970624@…`~~ |
| ~~`lintrain`~~ | **offline 2026-11-17**, alias removed | — |
| ~~`infer-1`~~ | decommissioned 2026-07-17 (pod still answers, no role) | — |

```bash
ssh train-1 | ssh vscode | ssh vla-h200 | ssh h100-3 | ssh ksp-h20-1   # KSP
ssh -J vscode-pub h100-3                                                # KSP from outside the VPN
ssh hanhai-train-1                                                      # hanhai (no GPU)
```

**Historical hanhai Juscent stack notes (validated 2026-07-16 on hanhai vscode / hanhai-train-1):**

- Env: `/opt/conda/envs/{comfyui,ai-toolkit,onetrain}` → `/nfs/envs/*` (do **not** pip-install into shared NFS envs casually: the volume is shared by every host on both platforms).
- Data (shared):  
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
| ComfyUI | `comfyui` | **`/nfs/envs/comfyui`** (`/opt/conda/envs/comfyui` → symlink) | `/home/jovyan/code/src/ComfyUI` | `comui` | `8188` | **`…/juscent/bin/comfyui.sh`** (hanhai vscode: `~/bin/comfyui-gpu0.sh`) | `/home/share/game/juscent/models` |
| ai-toolkit | `ai-toolkit` | **`/nfs/envs/ai-toolkit`** | `/home/jovyan/code/src/ai-toolkit` | `aitk-ui` | `8675` | **`…/juscent/bin/ai-toolkit.sh`** (hanhai vscode: `~/bin/ai-toolkit-gpu1.sh`) | Juscent models; **output/datasets → share** (see data paths below) |
| kohya_ss | `sdxl` | local or NFS if migrated | `/home/jovyan/code/src/kohya_ss` | `sdxl` | `7860` | (none canonical) | `/home/share/game/juscent/models` |
| LlamaFactory | `lf` / family | often `/nfs/envs/lf-*` | `/home/jovyan/code/src/LlamaFactory` | `lf` | `7861` | (none Juscent bin) | `/home/share/game/seasun/models` |
| OneTrainer | `onetrain` | **`/nfs/envs/onetrain`** | `/home/jovyan/code/src/OneTrainer` | **`onetrain-gui`** | noVNC `6080` / VNC `5901` | **`…/juscent/bin/onetrain.sh`** (hanhai vscode: `~/bin/onetrain-gpu1.sh`) | Seasun models; train outputs under Juscent |

**ai-toolkit shared data (hanhai-train-1 + hanhai vscode, historical):**

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
- Perception/utility models (faster-whisper, RapidOCR, SigLIP2, InsightFace, Qwen3 embedding/reranker, etc.; the movieDB set) live under `/home/share/models/` (root-owned: `sudo mkdir` + `chown jovyan:root`). See `references/asr_ocr.md`.
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
- **KS3 (`ks3util`)**: always `-f` on overwrite (else it prompts `(y or N)` — downloads hang, uploads skip silently); run in a work dir or `--log-path`; long jobs in tmux with `< /dev/null` and an `EXIT=` marker; verify sizes/md5 after transfer. Mac must use the external endpoint, the cluster needs no `sudo`, never print or pass keys, and `rm`/`mv`/`sync --delete` need the data owner's consent. Details: `references/ks3util.md`.
- **ASR / OCR**: default host `ssh vscode` (KSP, no ComfyUI on its GPUs), env `source /nfs/envs/moviedb-env.sh`. For single-speaker talks use ASR + LLM correction and skip OCR. OCR stays on CPU; ASR uses a GPU only when that card's ComfyUI queue is empty and at least 6 GB is free. Exit 0 from Whisper can still be pure hallucination, so honour `ASR_SUSPECT` and spot-check the text. Details: `references/asr_ocr.md`.

## Workflow

1. Establish context.
   - Parse or confirm the SSH command / host role (default `train-1` (KSP), except ASR/OCR which defaults to `vscode`; ComfyUI/H3 on `vla-h200` or a KSP H100 per the comfyui-env README; `hanhai-train-1` only for the old Juscent stack).
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

**Default host:** from 2026-07-17 both ai-toolkit and ComfyUI ran on **hanhai-train-1** (alias `train-1` until 2026-11-17), so one SSH usually covered both. That pod has no GPUs as of 2026-11-17; ask which host to count on. Confirm the window and the localtime day boundary first (`date '+%F %T %Z'`), then compute `--since`.

Fast path — the bundled helper does all of this:

```bash
scripts/gpu_task_counts.sh --since "YYYY-MM-DD HH:MM:SS" --ssh "ssh hanhai-train-1"
# split hosts: --train-ssh / --comfy-ssh ; single stack: --skip-comfy / --skip-train
```

**ai-toolkit — authoritative.** The `Job` table in `aitk_db.db` is persistent (survives restarts). `created_at` is epoch **milliseconds** → `datetime(created_at/1000,'unixepoch','localtime')`. Report total + by-day + by-status (`completed` / `running` / `error` / `stopped`); a `stopped` row at `step=0` is a job created then aborted, not real training.

**ComfyUI — no reliable task count.** `/history` is **in-process and resets on every service restart**, so after any restart in the window it only shows the current session. Verify by dating the earliest surviving prompt (helper prints a WARNING when it is after the window start). The durable proxy is **`output/` files by mtime** — but these are **artifacts, not tasks** (one workflow emits many images), and `output/` resolves to the **shared** `…/comfyui/output`, so files may not all originate from this host. Always state both caveats; never present the artifact count as a task count. For a truer task estimate, group output files by `projects/<name>/` subfolder or filename prefix.
