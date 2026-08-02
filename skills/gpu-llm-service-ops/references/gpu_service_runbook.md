# GPU Service Runbook

This runbook is for operating a user-specified GPU server over SSH. Replace `GPU_SSH` with the full SSH command (or short-name alias) for the target host.

Juscent fleet short names:

```bash
# train-1 — DEFAULT host: ComfyUI + ai-toolkit + OneTrainer
GPU_SSH='ssh -p 2222 juscent-train-1-hh-970624@hanhai-prod.ai.kingsoft.com'
# train-h20 — H20 training / storage I/O benchmarking
GPU_SSH='ssh -p 2222 juscent-train-h20-hh-970624@hanhai-prod.ai.kingsoft.com'
# or: ssh train-1 / ssh train-h20 / ssh vscode when ~/.ssh/config is set
# NOTE: infer-1 was decommissioned 2026-07-17; its ComfyUI role moved to train-1.
```

## Probe

Run this before mutating the remote host:

```bash
$GPU_SSH 'bash -lc "
set -e
hostname
whoami
source /opt/conda/etc/profile.d/conda.sh 2>/dev/null || true
conda info --envs 2>/dev/null || true
nvidia-smi || true
df -h / /home/share /nfs 2>/dev/null || df -h
mount | grep ' on /nfs ' || true
ls -l /opt/conda/envs 2>/dev/null | head -40 || true
ls /nfs/envs 2>/dev/null || true
tmux ls 2>/dev/null || true
ss -ltnp 2>/dev/null | grep -E \":(8000|8188|8675|7860|7861|6080|5901)\" || true
"'
```

For CUDA sanity in an env:

```bash
$GPU_SSH 'bash -lc "
source /opt/conda/etc/profile.d/conda.sh
conda activate vllm
python - <<PY
import sys, torch
print(\"python\", sys.version.split()[0])
print(\"torch\", torch.__version__)
print(\"torch_cuda\", torch.version.cuda)
print(\"cuda_available\", torch.cuda.is_available())
print(\"device_count\", torch.cuda.device_count())
print(\"device0\", torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
PY
"'
```

## Conda Isolation Matrix

Use one conda env per stack:

| Stack | Env | Python baseline | Install path |
| --- | --- | --- | --- |
| vLLM | `vllm` | `3.12` if already working; otherwise follow current vLLM wheel support | `/home/share/game/seasun/vllm` |
| ComfyUI | `comfyui` | `3.11` for custom-node wheel coverage | `/home/jovyan/code/src/ComfyUI` |
| ai-toolkit | `ai-toolkit` | follow upstream, usually `3.11` or `3.12` | `/home/jovyan/code/src/ai-toolkit` |
| kohya_ss | `sdxl` | follow upstream, usually `3.10` or `3.11` | `/home/jovyan/code/src/kohya_ss` |
| LlamaFactory | `lf` | `3.11` is a conservative default | `/home/jovyan/code/src/LlamaFactory` |

Create envs with explicit activation:

```bash
source /opt/conda/etc/profile.d/conda.sh
conda create -y -n <env> python=<version>
conda activate <env>
python -m pip install -U pip wheel setuptools
```

When installing CUDA PyTorch, never accept a CPU fallback silently. After install, run:

```bash
python - <<'PY'
import torch
print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.device_count())
PY
```

## Model Stores

LLM-oriented store:

```text
/home/share/game/seasun/models
```

ComfyUI and image-generation store:

```text
/home/share/game/juscent/models
```

Recommended cache variables for LLM-oriented jobs:

```bash
export HF_HOME=/home/share/game/seasun/models/.hf_cache
export HF_HUB_CACHE=/home/share/game/seasun/models/.hf_cache/hub
export MODELSCOPE_CACHE=/home/share/game/seasun/models/.modelscope
```

Recommended cache variables for ComfyUI or image-generation model work:

```bash
export HF_HOME=/home/share/game/juscent/models/huggingface
export HF_HUB_CACHE=/home/share/game/juscent/models/huggingface/hub
export HF_ASSETS_CACHE=/home/share/game/juscent/models/huggingface/assets
export TRANSFORMERS_CACHE=/home/share/game/juscent/models/huggingface/hub
export MODELSCOPE_CACHE=/home/share/game/juscent/models/.modelscope
```

Some older hosts may already use `/home/share/game/juscent/models/.hf_cache`; verify the cache tree before changing a service. For ai-toolkit, Flux, Qwen-Image, and other ComfyUI-compatible image training should use the Juscent cache, not the Seasun LLM cache.

For ComfyUI, create symlinks from `/home/jovyan/code/src/ComfyUI/models/<type>` to canonical shared directories. Check for broken links:

```bash
find /home/jovyan/code/src/ComfyUI/models -xtype l -print
```

Check for accidental large local model copies:

```bash
find /home/jovyan/code/src/ComfyUI/models -xdev -type f -size +100M -print
```

## Service Lifecycle

### Juscent image stacks (preferred)

On Juscent `train-1` (and `vscode`/`ultra`), use shared control scripts (see `references/nfs_envs_and_juscent_bin.md`):

```bash
# ComfyUI — train-1
$GPU_SSH 'bash /home/share/game/juscent/bin/comfyui.sh status'
$GPU_SSH 'bash /home/share/game/juscent/bin/comfyui.sh restart'

# ai-toolkit / OneTrainer — train-1
$GPU_SSH 'bash /home/share/game/juscent/bin/ai-toolkit.sh status'
$GPU_SSH 'bash /home/share/game/juscent/bin/onetrain.sh status'
$GPU_SSH 'bash /home/share/game/juscent/bin/ai-toolkit.sh restart'
$GPU_SSH 'bash /home/share/game/juscent/bin/onetrain.sh restart'
```

Uniform API: `{start|stop|restart|status}`. Logs: `/tmp/comfyui.log`, `/tmp/aitk-ui.log`, `/tmp/onetrain-gui.log`.  
Do **not** use removed wrappers `start_comfyui_comui.sh`, `start_aitk_ui.sh`, `start_onetrainer_gui.sh`, `stop_onetrainer_gui.sh`.

### Generic tmux (vLLM and stacks without bin scripts)

Inspect:

```bash
$GPU_SSH 'tmux ls 2>/dev/null || true'
$GPU_SSH 'tmux capture-pane -pt vllm -S -160 2>/dev/null | tail -120 || true'
```

Stop a service session:

```bash
$GPU_SSH 'bash -lc "
tmux send-keys -t vllm C-c 2>/dev/null || true
sleep 2
tmux capture-pane -pt vllm -S -80 2>/dev/null | tail -80 || true
tmux kill-session -t vllm 2>/dev/null || true
"'
```

Create or restart a session:

```bash
$GPU_SSH 'bash -lc "
tmux has-session -t vllm 2>/dev/null && tmux kill-session -t vllm || true
tmux new -d -s vllm
tmux send-keys -t vllm \"bash /home/share/game/seasun/vllm/start_vllm.sh 2>&1 | tee /tmp/vllm.log\" C-m
"'
```

Prefer a remote script under `/tmp` for long commands with many quotes or variables, then launch that script from tmux.

## vLLM Launch Template

The canonical launch script is `/home/share/game/seasun/vllm/start_vllm.sh`.
Always use this script — do not inline `vllm serve` arguments directly.

Key fields to update in the script when switching models:
- `model_path` — absolute path under `/home/share/game/seasun/models/`
- `model_name` — the `--served-model-name` alias returned by `/v1/models`

The script auto-detects GPU count (`num_gpus`) and sets `--tensor-parallel-size` accordingly.
To pin to specific GPUs, set `CUDA_VISIBLE_DEVICES` before calling the script, or edit it directly.

Before launch, locate the model directory:

```bash
$GPU_SSH 'ls /home/share/game/seasun/models/ | grep -i <model_keyword>'
```

Verify:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/v1/models | python -m json.tool
```

## ComfyUI Launch Template

**Preferred (Juscent):**

```bash
bash /home/share/game/juscent/bin/comfyui.sh start   # or restart / status / stop
```

Env source of truth: `/nfs/envs/comfyui` (symlink `/opt/conda/envs/comfyui`).  
Session `comui`, port `8188`, log `/tmp/comfyui.log`, code `/home/jovyan/code/src/ComfyUI`.

Manual fallback only when debugging the control script:

```bash
source /opt/conda/etc/profile.d/conda.sh
conda activate /nfs/envs/comfyui   # or: conda activate comfyui
cd /home/jovyan/code/src/ComfyUI
python main.py --listen 0.0.0.0 --port 8188
```

## ComfyUI Custom Nodes And Models

For a new custom node:

1. Clone or update it under `/home/jovyan/code/src/ComfyUI/custom_nodes/<repo>`.
2. Read README, install notes, requirements, and model-loading code.
3. Search for model dependency hints with `rg`: `from_pretrained`, `snapshot_download`, `hf_hub_download`, `modelscope`, `download_models`, `u2net`, `onnx`, `models/`, `checkpoints`, and hard-coded repo IDs.
4. Install only the node's required Python dependencies in the active `comfyui` env.
5. Download large models into `/home/share/game/juscent/models/<type>/...`, preferably in `tmux model`.
6. Link local ComfyUI model paths under `/home/jovyan/code/src/ComfyUI/models/...` to the canonical shared files or directories.
7. Restart via `bash /home/share/game/juscent/bin/comfyui.sh restart` (or manual `tmux comui` fallback), verify `http://127.0.0.1:8188/system_stats`, and scan `/tmp/comfyui.log` / pane for `Traceback`, `Exception`, `ERROR`, `Cannot import`, and auto-download attempts.

Use `references/comfyui_node_model_ops.md` for the detailed taxonomy, ModelScope/Civitai download recipes, and known fixes such as `rembg`, Pixal3D BiRefNet, DINOv3 accessors, and FlashAttention fallbacks. Use `scripts/audit_model_links.sh` after changing local/shared model links.

## ai-toolkit Launch Template

**Preferred (Juscent train-1):**

```bash
bash /home/share/game/juscent/bin/ai-toolkit.sh start   # or restart / status / stop
```

Env: `/nfs/envs/ai-toolkit`. Session `aitk-ui`, port `8675`, log `/tmp/aitk-ui.log`.  
UI workdir: `/home/jovyan/code/src/ai-toolkit/ui` (`npm run start`). Cache vars are set inside the control script (Juscent HF paths; often offline).

Manual fallback for debugging only (must mirror cache env of the bin script):

```bash
cd /home/jovyan/code/src/ai-toolkit/ui
source /opt/conda/etc/profile.d/conda.sh
set +u; conda activate /nfs/envs/ai-toolkit; set -u
export HF_HOME=/home/share/game/juscent/models/huggingface
export HF_HUB_CACHE=/home/share/game/juscent/models/huggingface/hub
export HF_ASSETS_CACHE=/home/share/game/juscent/models/huggingface/assets
export TRANSFORMERS_CACHE=/home/share/game/juscent/models/huggingface/hub
export MODELSCOPE_CACHE=/home/share/game/juscent/models/.modelscope
export PORT=8675
npm run start
```

If upstream changes the UI entrypoint, inspect `/home/jovyan/code/src/ai-toolkit/ui` and update `ai-toolkit.sh` accordingly.

## ai-toolkit Training Outputs

ai-toolkit output is configured per training job, not as a global service setting. In YAML or the UI-generated job config, set the process `training_folder` to a shared path:

```yaml
config:
  process:
    - training_folder: "/home/share/game/juscent/train_outputs/ai-toolkit"
```

Final and intermediate artifacts are saved under:

```text
<training_folder>/<job_name>/
```

Do not point ComfyUI directly at a raw ai-toolkit output root. It contains intermediate checkpoints, optimizer state, logs, samples, and old runs. Publish only selected final artifacts into the ComfyUI taxonomy, preferably through symlinks:

```text
/home/share/game/juscent/models/loras/ai-toolkit/<name>.safetensors
/home/share/game/juscent/models/checkpoints/<name>.safetensors
/home/share/game/juscent/models/diffusion_models/<name>.safetensors
```

## ai-toolkit Dependency And Cache Checks

For ai-toolkit failures during job startup, verify imports and the training entrypoint before changing packages:

```bash
source /opt/conda/etc/profile.d/conda.sh
conda activate ai-toolkit
cd /home/jovyan/code/src/ai-toolkit
python - <<'PY'
import torch, torchvision, torchaudio
import accelerate, transformers, diffusers, peft, bitsandbytes
from toolkit.config_modules import DatasetConfig, preprocess_dataset_raw_config
from jobs import ExtensionJob
print("torch", torch.__version__, "cuda", torch.version.cuda, torch.cuda.is_available())
print("imports ok")
PY
python run.py --help
python -m pip check
```

If `torchaudio` is missing, install the version matching the installed torch and CUDA wheel, and prefer `--no-deps` to avoid replacing torch:

```bash
python -m pip install --no-deps --index-url https://download.pytorch.org/whl/cu128 "torchaudio==<torch_version>+cu128"
```

For Flux2 Klein jobs, `model.name_or_path` controls the transformer/VAE base path, but the text encoder may still be loaded from a separate Hugging Face repo such as `Qwen/Qwen3-8B`. The VAE may also be loaded from `ai-toolkit/flux2_vae`. If logs show Hugging Face download errors, `RuntimeError: Cannot send a request, as the client has been closed`, or similar hub failures, inspect the running worker cache environment and validate local cache hits:

```bash
for pid in $(pgrep -f 'node dist/cron/worker.js|next start --port 8675'); do
  echo "PID $pid"
  tr '\0' '\n' < /proc/$pid/environ | grep -E '^(HF_HOME|HF_HUB_CACHE|HF_ASSETS_CACHE|TRANSFORMERS_CACHE|CONDA_DEFAULT_ENV)=' || true
done

source /opt/conda/etc/profile.d/conda.sh
conda activate ai-toolkit
HF_HOME=/home/share/game/juscent/models/huggingface \
HF_HUB_CACHE=/home/share/game/juscent/models/huggingface/hub \
TRANSFORMERS_CACHE=/home/share/game/juscent/models/huggingface/hub \
python - <<'PY'
from transformers.utils.hub import cached_file
import huggingface_hub
print(cached_file("Qwen/Qwen3-8B", "config.json", local_files_only=True))
print(huggingface_hub.hf_hub_download(repo_id="ai-toolkit/flux2_vae", filename="ae.safetensors", local_files_only=True))
PY
```

## kohya_ss Launch Template

```bash
source /opt/conda/etc/profile.d/conda.sh
conda activate sdxl
cd /home/jovyan/code/src/kohya_ss
./gui.sh --listen 0.0.0.0 --server_port 7860
```

Reuse `/home/share/game/juscent/models` for SDXL/ComfyUI-compatible checkpoints and LoRA files.

## LlamaFactory Launch Template

```bash
source /opt/conda/etc/profile.d/conda.sh
conda activate lf
cd /home/jovyan/code/src/LlamaFactory
llamafactory-cli webui --host 0.0.0.0 --port 7861
```

Use `/home/share/game/seasun/models` for base LLMs and training outputs unless the user gives a task-specific output path.

## Mac-to-GPU SSH Tunnels

Use a local tmux session on the Mac for persistent forwarding:

```bash
tmux new -d -s vllm-forward \
  'ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
   -L 18000:127.0.0.1:8000 \
   -p 2222 user@host'
```

Verify locally:

```bash
curl -fsS http://127.0.0.1:18000/health
curl -fsS http://127.0.0.1:18000/v1/models | python -m json.tool
```

Common local port mapping:

| Service | Remote | Local |
| --- | --- | --- |
| vLLM | `8000` | `18000` |
| ComfyUI | `8188` | `18188` |
| ai-toolkit | `8675` | `18675` |
| kohya_ss | `7860` | `17860` |
| LlamaFactory | `7861` | `17861` |

## vLLM Streaming Benchmark

Use the bundled script after the tunnel is live:

```bash
python /Users/kk/.codex/skills/gpu-llm-service-ops/scripts/vllm_stream_ttft_client.py \
  --base-url http://127.0.0.1:18000/v1 \
  --model Qwen3.5-9B \
  --runs 50 \
  --warmup 5 \
  --max-tokens 32 \
  --output ./vllm_ttft_results.json \
  --csv-output ./vllm_ttft_results.csv
```

Latency split:

```text
ttft_ms = Mac client -> SSH tunnel -> vLLM -> first SSE token -> Mac client
health_rtt_ms = Mac client -> SSH tunnel -> vLLM /health -> Mac client
vllm_est_ms = max(0, ttft_ms - health_rtt_ms)
```

For a stronger split, also run the same client on the GPU host against `http://127.0.0.1:8000/v1` and compare local vs tunnel results.
