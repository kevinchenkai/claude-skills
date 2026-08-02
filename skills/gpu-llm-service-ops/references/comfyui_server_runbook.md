# ComfyUI Server Runbook

## Standard Install Flow

Use this flow for a new custom node:

1. SSH to the server.
2. Stop or leave ComfyUI running depending on the change:
   - For dependency installs and Python package changes, stop and restart.
   - For pure model downloads and symlink fixes, ComfyUI can often stay running.
3. Clone or update the node repository under `custom_nodes`.
4. Activate the ComfyUI environment. Prefer `source /opt/conda/etc/profile.d/conda.sh && conda activate comfyui` on conda-isolated servers; use `/home/jovyan/code/venvs/comfyui` only on older venv-based reference servers.
5. Install `requirements.txt`.
6. Analyze model-loading code and README.
7. Download models into `/home/share/game/juscent/models/<type>/...`.
8. Link expected ComfyUI paths under `/home/jovyan/code/src/ComfyUI/models/...`.
9. Restart via `bash /home/share/game/juscent/bin/comfyui.sh restart` (session `comui`; env `/nfs/envs/comfyui`).
10. Verify port `8188`, `/system_stats`, and tmux logs.

## ModelScope Download Patterns

Prefer the ModelScope CLI if available:

```bash
modelscope download --model owner/model-name --local_dir /home/share/game/juscent/models/<type>/<model-name>
```

If the CLI is missing but the Python package is installed:

```bash
python - <<'PY'
from modelscope import snapshot_download
snapshot_download(
    "owner/model-name",
    local_dir="/home/share/game/juscent/models/<type>/<model-name>",
)
PY
```

If neither exists, install or use the plugin's documented downloader inside the ComfyUI venv, then move or link the result into the canonical shared location.

## Verification Commands

```bash
LOCAL=/home/jovyan/code/src/ComfyUI/models
SHARE=/home/share/game/juscent/models

find "$LOCAL" -xtype l -print
find "$LOCAL" -xdev -type f ! -xtype l -size +100M -printf '%s %p\n' | sort -nr | head
find "$SHARE" -maxdepth 1 -type l -printf '%p -> %l\n' | sort
find "$SHARE" -xtype l -print

ps -eo pid,ppid,stat,etime,cmd | grep -E 'python .*main.py.*--port 8188' | grep -v grep
ss -ltnp 2>/dev/null | grep :8188
curl -fsS http://127.0.0.1:8188/system_stats | head -c 300
tmux capture-pane -pt comui -S -200 | grep -Ei 'Traceback|Exception|ERROR|Cannot import|download'
```

## Existing Canonical Examples

```text
3d/Pixal3D
3d/NAF
3d/TRELLIS-image-large
3d/TRELLIS.2-4B
BiRefNet/RMBG-2.0
DINOv3/dinov3-vitl16-pretrain-lvd1689m
MoGe/moge-2-vitl
rembg/rembg-u2net/u2net.onnx
video/SEEDVR2/seedvr2-model
video/SEEDVR2/SeedVR2_comfyUI
```
