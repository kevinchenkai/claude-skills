# ComfyUI Node And Model Ops

Use this reference inside `gpu-llm-service-ops` for ComfyUI custom node installation, dependency analysis, model downloads, model symlink repair, taxonomy normalization, and model-missing or auto-download debugging.

## Default Context

Use this server and paths unless the user gives a different target:

```bash
ssh train-1   # ssh -p 2222 juscent-train-1-hh-970624@hanhai-prod.ai.kingsoft.com
COMFY=/home/jovyan/code/src/ComfyUI
COMFY_ENV=comfyui
LEGACY_VENV=/home/jovyan/code/venvs/comfyui
LOCAL_MODELS=/home/jovyan/code/src/ComfyUI/models
SHARE_MODELS=/home/share/game/juscent/models
LOG_DIR=/home/share/game/juscent/model_logs
```

Activate the environment before Python or pip work. Prefer conda when the target was built with the multi-env layout:

```bash
source /opt/conda/etc/profile.d/conda.sh
conda activate comfyui
```

On older reference servers that still use a venv:

```bash
source /home/jovyan/code/venvs/comfyui/bin/activate
```

## Operating Rules

- If the user asks for a plan or says not to execute yet, produce a plan and wait for confirmation.
- Prefer noninteractive SSH commands and `tmux send-keys` / `tmux capture-pane` over manual attach flows.
- Put long downloads and background model operations in `tmux model`.
- Keep `tmux comui` for the ComfyUI server process and immediate log inspection.
- For complex `tmux send-keys` commands that use shell variables, quotes, or pipes, write a short script under `/tmp` on the remote host and send only the script path to tmux. This avoids nested local/remote/tmux quoting that can expand variables like `$TARGET` or `$LOG` too early.
- Never leave ComfyUI stopped after a successful install or migration unless the user asked for that.
- Put reports and inventories under `/home/share/game/juscent/model_logs/`.
- Do not keep compatibility symlinks at `/home/share/game/juscent/models` root unless the user explicitly asks. Local ComfyUI symlinks are OK and should point directly to canonical typed shared paths.

## Workflow

1. Inspect the node/plugin.
   - Clone or update under `/home/jovyan/code/src/ComfyUI/custom_nodes/<repo>`.
   - Read `README`, `requirements`, install notes, and model-loading code.
   - Search for dependency hints with `rg`: `from_pretrained`, `snapshot_download`, `hf_hub_download`, `modelscope`, `download_models`, `u2net`, `onnx`, `models/`, `checkpoints`, and hard-coded repo IDs.

2. Install Python dependencies.
   - Use the active ComfyUI environment.
   - Install only the plugin requirements and any explicit missing packages.
   - Restart ComfyUI after dependency changes.

3. Download models.
   - Prefer ModelScope sources for large model repos when available.
   - Download into the canonical shared taxonomy under `/home/share/game/juscent/models`.
   - If the user explicitly asks for a repository copy with original structure, download to the requested shared directory and do not normalize, move, or link files unless separately requested.
   - Use `tmux model` for slow downloads.
   - Verify files exist and are nonzero before creating local symlinks.

4. Link models into ComfyUI.
   - Link only from `/home/jovyan/code/src/ComfyUI/models/...` to canonical shared paths.
   - Do not point local links at shared-root aliases.
   - If a package uses its own cache directory, link that cache to the canonical shared file too. Example: `rembg` expects `/home/jovyan/.u2net/u2net.onnx`.

5. Validate.
   - Check local broken symlinks with `find "$LOCAL_MODELS" -xtype l`.
   - Check no large real model files remain locally: `find "$LOCAL_MODELS" -xdev -type f ! -xtype l -size +100M`.
   - Check shared-root compatibility symlinks are absent unless intentionally requested.
   - For reports that sum large files, use Python integer arithmetic instead of shell `awk` sums, which may overflow on multi-GB inventories in some remote environments.
   - Start or restart ComfyUI, verify `0.0.0.0:8188`, and scan tmux logs for `Traceback`, `Exception`, `ERROR`, `Cannot import`, and auto-download attempts.

## Runtime Import Error Repair

Use this flow when a node imports successfully at ComfyUI startup but fails during prompt execution, especially with `ModuleNotFoundError` inside a model loader:

1. Capture the full runtime stack from `tmux comui` and identify the deepest missing import, the node type, and the local file path:

```bash
tmux capture-pane -pt comui -S -500 | grep -i -C 8 'ModuleNotFoundError\|No module named\|<node-or-package-name>'
```

2. Inspect the implicated node and model code before installing:

```bash
cd /home/jovyan/code/src/ComfyUI
rg -n 'import <package>|from <package>|<package>' custom_nodes models
```

3. Record the runtime ABI before installing CUDA extension packages:

```bash
source /opt/conda/etc/profile.d/conda.sh
conda activate comfyui
python - <<'PY'
import sys, torch
print("python", sys.version)
print("torch", torch.__version__)
print("torch_cuda", torch.version.cuda)
print("cuda_available", torch.cuda.is_available())
print("gpu", torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
PY
nvidia-smi --query-gpu=driver_version,name --format=csv,noheader
```

4. Prefer a prebuilt wheel that matches the existing Python, Torch, and CUDA ABI. Use `--no-deps` for narrowly repairing a missing extension so `pip` does not replace the working Torch stack:

```bash
python -m pip install --no-deps /path/to/package_matching_current_torch.whl
```

5. If remote GitHub/PyPI downloads are slow or unstable, download the wheel locally, verify SHA256, upload to a shared wheel cache, then install from that local path:

```bash
mkdir -p /home/share/game/juscent/wheels/<package>
sha256sum /home/share/game/juscent/wheels/<package>/<wheel>.whl
python -m pip install --no-deps /home/share/game/juscent/wheels/<package>/<wheel>.whl
```

Do not trust apparent file size while a downloader sidecar such as `.aria2` exists; `aria2c` can preallocate the final file.

6. Verify both the package and the original failing model import before restarting ComfyUI:

```bash
python - <<'PY'
import torch
print("torch", torch.__version__, "cuda", torch.version.cuda, torch.cuda.is_available())
import <package>
print("<package>", getattr(<package>, "__version__", "unknown"))
PY
```

7. Restart `tmux comui`, verify `/system_stats`, and scan logs:

```bash
tmux send-keys -t comui C-c
sleep 5
tmux kill-session -t comui 2>/dev/null || true
bash /home/share/game/juscent/bin/comfyui.sh restart
# fallback only: tmux new -d -s comui ... manual launch
sleep 15
curl -fsS http://127.0.0.1:8188/system_stats | head -c 600
tmux capture-pane -pt comui -S -400 | grep -Ei 'Traceback|ModuleNotFoundError|No module named|ERROR|Cannot import'
```

## tmux Split

Use `comui` for the service:

```bash
tmux has-session -t comui 2>/dev/null || tmux new -d -s comui
tmux send-keys -t comui C-c
tmux send-keys -t comui 'cd ~/code/src/ComfyUI' C-m
tmux send-keys -t comui 'source /opt/conda/etc/profile.d/conda.sh && conda activate comfyui' C-m
tmux send-keys -t comui 'python main.py --listen 0.0.0.0 --port 8188' C-m
```

If the target is the older venv-based reference server, replace the activation line with:

```bash
tmux send-keys -t comui 'source /home/jovyan/code/venvs/comfyui/bin/activate' C-m
```

Use `model` for downloads and long-running setup:

```bash
tmux has-session -t model 2>/dev/null || tmux new -d -s model
tmux send-keys -t model 'cd /home/share/game/juscent/models' C-m
```

Inspect instead of attaching when possible:

```bash
tmux capture-pane -pt comui -S -160 | tail -120
tmux capture-pane -pt model -S -160 | tail -120
```

For long commands with variables, generate a remote script first:

```bash
cat > /tmp/model_download.sh <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
TARGET=/home/share/game/juscent/models/example-model
LOG=/home/share/game/juscent/model_logs/example_download_$(date +%Y%m%d_%H%M%S).log
mkdir -p /home/share/game/juscent/model_logs "$TARGET"
{
  echo "start $(date)"
  # download command here
  echo "done $(date)"
} 2>&1 | tee -a "$LOG"
SCRIPT
chmod +x /tmp/model_download.sh
tmux send-keys -t model '/tmp/model_download.sh' C-m
```

## Download Recipes

### ModelScope

Use full repository download when the user asks to preserve the upstream directory structure:

```bash
/opt/conda/bin/modelscope download \
  --model owner/repo \
  --local_dir /home/share/game/juscent/models/repo-name
```

Use a repository-relative path for single-file downloads. If a card says a file belongs in `ComfyUI/models/diffusion_models` but the actual repo stores it under `split_files/diffusion_models/...`, pass the real repo path to ModelScope:

```bash
/opt/conda/bin/modelscope download \
  --model owner/repo \
  split_files/diffusion_models/model.safetensors \
  --local_dir /home/share/game/juscent/models/diffusion_models
```

If `modelscope download` fails with `NotExistError: The file path ... not exist`, inspect the model card/API or try the `split_files/...` path. ModelScope may leave `._____temp` while downloads are active; after success it should be empty or removable.

### Civitai / Civitai.red

For Civitai model versions, first inspect metadata through the version API:

```bash
curl -L -A 'Mozilla/5.0' \
  'https://civitai.red/api/v1/model-versions/<version_id>'
```

The metadata usually includes `files[].name`, `files[].sizeKB`, `files[].downloadUrl`, `files[].metadata`, and `files[].hashes.SHA256`. Download through the version download endpoint with `aria2c` in `tmux model`:

```bash
aria2c \
  --continue=true \
  --max-connection-per-server=8 \
  --split=8 \
  --min-split-size=64M \
  --auto-file-renaming=false \
  --allow-overwrite=true \
  --summary-interval=10 \
  --user-agent='Mozilla/5.0' \
  --dir=/home/share/game/juscent/models/model-name \
  --out=model-file.safetensors \
  'https://civitai.red/api/download/models/<version_id>'
```

Do not trust the apparent `.safetensors` size while `.aria2` exists; `aria2c` preallocates the final file. Treat completion as valid only after the `.aria2` sidecar disappears and SHA256 matches the API metadata:

```bash
sha256sum /home/share/game/juscent/models/model-name/model-file.safetensors
```

A `HEAD -L` request to the final signed R2 URL may return `403 Forbidden` even when a normal `GET` download works. Prefer the API metadata plus `aria2c`/`curl GET` before deciding that login is required.

## Model Taxonomy

Use these canonical shared directories:

```text
/home/share/game/juscent/models/3d
/home/share/game/juscent/models/BiRefNet
/home/share/game/juscent/models/DINOv3
/home/share/game/juscent/models/LLM
/home/share/game/juscent/models/MoGe
/home/share/game/juscent/models/checkpoints
/home/share/game/juscent/models/clip
/home/share/game/juscent/models/diffusion_models
/home/share/game/juscent/models/loras
/home/share/game/juscent/models/rembg
/home/share/game/juscent/models/text_encoders
/home/share/game/juscent/models/vae
/home/share/game/juscent/models/video
```

Keep non-model software out of `models`:

```text
/home/share/game/juscent/wheels
/home/share/game/juscent/bin
```

## Known Gotchas

- `rembg` `ReadTimeout` to GitHub usually means `/home/jovyan/.u2net/u2net.onnx` is missing or points to an old alias. Fix it to:

```bash
ln -sfn /home/share/game/juscent/models/rembg/rembg-u2net/u2net.onnx /home/jovyan/.u2net/u2net.onnx
```

- Pixal3D `BiRefNet` with `transformers 5.4.0` can fail with `Tensor.item() cannot be called on meta tensors`. Patch the local RMBG remote-code file under `/home/share/game/juscent/models/BiRefNet/RMBG-2.0/birefnet.py` and the matching Hugging Face dynamic module cache so `torch.linspace(...)` calls include `device="cpu"`, and add `all_tied_weights_keys = {}` to the `BiRefNet` class.
- Pixal3D `RunningHubPixal3DModelLoader` can fail during NAF loading with `ModuleNotFoundError: No module named 'natten'`. Inspect the stack for `/home/jovyan/code/src/ComfyUI/models/NAF/src/layers/attentions.py`; it may first try old `natten.functional` APIs and then fall back to `from natten import na2d`. Install a NATTEN wheel that matches the active ComfyUI Torch ABI as closely as possible, with `--no-deps` to avoid replacing Torch. Example from a working H20 ComfyUI env: Python 3.11, `torch 2.10.0+cu129`, CUDA 12.9 used `natten-0.21.6+torch2100cu128-cp311-cp311-linux_x86_64.whl`; verify `natten.HAS_LIBNATTEN is True`, `from natten import na2d`, and the NAF attention import before restarting `tmux comui`.
- Pixal3D DINOv3 feature extraction can fail with `'DINOv3ViTModel' object has no attribute 'layer'` on newer `transformers`. The model is reusable; patch Pixal3D accessors to use `model.layer` when present, otherwise `model.model.layer`. Relevant files include `pixal3d/trainers/flow_matching/mixins/image_conditioned_proj.py`, `pixal3d/trainers/flow_matching/mixins/image_conditioned.py`, and `pixal3d/modules/image_feature_extractor.py`.
- Pixal3D dense attention can fail with `TypeError: 'NoneType' object is not callable` at `flash_attn.flash_attn_func(...)` when the workflow selects `flash_attn` but the environment lacks callable FlashAttention bindings. Patch `pixal3d/modules/attention/full_attn.py` to fall back to PyTorch `torch.nn.functional.scaled_dot_product_attention` for dense attention, or tell the user to select `sdpa` in the loader node.
- Pixal3D sparse attention can fail with `module 'flash_attn' has no attribute 'flash_attn_varlen_qkvpacked_func'` when sparse attention is configured for FlashAttention but varlen FlashAttention bindings are unavailable. Patch `pixal3d/modules/sparse/attention/full_attn.py` with a per-batch `VarLenTensor` fallback using PyTorch `scaled_dot_product_attention`.
- If a ComfyUI node auto-downloads from GitHub or Hugging Face during prompt execution, stop and identify the missing local file. Download it through `tmux model`, place it under the taxonomy, and link it where that library expects it.
- When reorganizing shared models, never delete real model files until a copy has been verified. Across filesystems, copy to a temporary path, verify size, then replace local copies with symlinks.

## Helper Script

Use `scripts/audit_model_links.sh` to summarize local model links, broken links, large local files, and shared-root symlink aliases:

```bash
bash /Users/kk/.codex/skills/gpu-llm-service-ops/scripts/audit_model_links.sh \
  /home/jovyan/code/src/ComfyUI/models \
  /home/share/game/juscent/models
```
