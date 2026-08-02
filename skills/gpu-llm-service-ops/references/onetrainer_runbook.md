# OneTrainer Runbook

Use this when installing `Nerogar/OneTrainer` on a GPU host, especially when the user asks for an independent `onetrain` conda env.

**Day-2 ops (Juscent train-1, preferred):** env lives at `/nfs/envs/onetrain`; control script is:

```bash
bash /home/share/game/juscent/bin/onetrain.sh {start|stop|restart|status}
```

tmux session: **`onetrain-gui`** (not `onetrain`). Ports: noVNC `6080`, VNC `5901`. Log: `/tmp/onetrain-gui.log`.  
Details: `references/nfs_envs_and_juscent_bin.md`.

## Research Notes

- Upstream repo: `https://github.com/Nerogar/OneTrainer`.
- Current upstream launch scripts use Python `>=3.10,<3.14` and default to Python `3.13`.
- `install.sh` creates a project-local conda env named `conda_env` when conda is available. For shared GPU hosts, avoid that unless the user asks for upstream defaults; install requirements directly into named env `onetrain`.
- CUDA requirements currently include PyTorch `cu128`, `onnxruntime-gpu`, `nvidia-nccl-cu12`, and `bitsandbytes`.
- OneTrainer GUI is a Tk/customtkinter desktop app (`scripts/train_ui.py`), not a web service. Remote GUI needs X11 forwarding, VNC/noVNC, xpra, or similar.

## Probe and Optional vLLM Shutdown

Before changing anything, run the standard read-only probe plus GUI checks:

```bash
hostname
whoami
source /opt/conda/etc/profile.d/conda.sh && conda info --envs
nvidia-smi
df -h / /home/share
tmux ls 2>/dev/null || true
ss -ltnp | grep -E ':(8000|5901|6080|7860|7861|8188|8675)' || true
echo "DISPLAY=${DISPLAY:-}"
which Xvfb x11vnc websockify fluxbox xpra vncserver 2>/dev/null || true
```

If the user asks to stop vLLM first, identify the exact tmux session and port owner, then stop via tmux:

```bash
tmux capture-pane -t vllm -p -S -60 || true
tmux send-keys -t vllm C-c
sleep 8
ss -ltnp | grep ':8000' || true
nvidia-smi
tmux ls 2>/dev/null || true
```

Only use `tmux kill-session -t vllm` after inspecting that the service is stopped or stuck. Avoid broad `pkill -f`.

## Install OneTrainer

Create the named env with Tk/Xft support:

```bash
source /opt/conda/etc/profile.d/conda.sh
conda create -y -n onetrain -c conda-forge --strict-channel-priority python=3.13 "tk[build=xft_*]"
conda install -y -n onetrain -c conda-forge --strict-channel-priority xorg-libxft xorg-libxrender fontconfig
```

Clone or update:

```bash
mkdir -p /home/jovyan/code/src
git clone https://github.com/Nerogar/OneTrainer.git /home/jovyan/code/src/OneTrainer
cd /home/jovyan/code/src/OneTrainer
git rev-parse HEAD
```

If the remote host cannot reach GitHub (`gnutls_handshake() failed`, connection reset, or similar), fetch source tarballs locally and `scp` them to the host:

```bash
mkdir -p /tmp/onetrainer_sources
curl -L --fail -o /tmp/onetrainer_sources/OneTrainer-master.tar.gz https://github.com/Nerogar/OneTrainer/archive/refs/heads/master.tar.gz
curl -L --fail -o /tmp/onetrainer_sources/diffusers-0f1abc4.tar.gz https://github.com/huggingface/diffusers/archive/0f1abc4.tar.gz
curl -L --fail -o /tmp/onetrainer_sources/mgds-9320a69.tar.gz https://github.com/Nerogar/mgds/archive/9320a69.tar.gz
curl -L --fail -o /tmp/onetrainer_sources/Muon-f90a42b.tar.gz https://github.com/KellerJordan/Muon/archive/f90a42b.tar.gz
scp -P <port> /tmp/onetrainer_sources/*.tar.gz <user>@<host>:/tmp/
```

Remote unpack pattern:

```bash
mkdir -p /home/jovyan/code/src /home/jovyan/code/src/onetrainer_vendor
rm -rf /home/jovyan/code/src/OneTrainer
tar -xzf /tmp/OneTrainer-master.tar.gz -C /tmp
mv /tmp/OneTrainer-master /home/jovyan/code/src/OneTrainer

install_tar() {
  tarball="$1"; dest="$2"; vendor=/home/jovyan/code/src/onetrainer_vendor
  list_file="/tmp/${tarball}.list"
  tar -tzf "/tmp/$tarball" > "$list_file"
  top="$(sed -n '1s#/.*##p' "$list_file")"
  rm -f "$list_file"
  rm -rf "$vendor/$dest" "/tmp/$top"
  tar -xzf "/tmp/$tarball" -C /tmp
  mv "/tmp/$top" "$vendor/$dest"
}
install_tar diffusers-0f1abc4.tar.gz diffusers
install_tar mgds-9320a69.tar.gz mgds
install_tar Muon-f90a42b.tar.gz Muon
```

Install requirements. Filter GitHub editable lines if using local vendor directories:

```bash
source /opt/conda/etc/profile.d/conda.sh
conda activate onetrain
cd /home/jovyan/code/src/OneTrainer
python -m pip install --upgrade --upgrade-strategy eager pip setuptools==81.0.0
grep -vE '^-e git\+https://github.com/(huggingface/diffusers|Nerogar/mgds|KellerJordan/Muon)\.git' requirements-global.txt > /tmp/onetrainer_requirements_global_no_git.txt
python -m pip install --upgrade --upgrade-strategy eager --timeout 120 --retries 10 --progress-bar off \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  -r /tmp/onetrainer_requirements_global_no_git.txt -r requirements-cuda.txt
export SETUPTOOLS_SCM_PRETEND_VERSION_FOR_MGDS="0.0.0+9320a69"
python -m pip install --upgrade --no-deps --timeout 120 --retries 10 --progress-bar off \
  -e /home/jovyan/code/src/onetrainer_vendor/diffusers \
  -e /home/jovyan/code/src/onetrainer_vendor/mgds \
  -e /home/jovyan/code/src/onetrainer_vendor/Muon
python -m pip install importlib-metadata -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 120 --retries 10 --progress-bar off
```

Known failures and workarounds:

- If `onnxruntime-gpu` downloads too slowly on the remote, download the matching Linux wheel locally, `scp` it to `/tmp/onetrain_wheelhouse`, and install it by direct file path with `--no-deps` before running requirements:

```bash
python3 -m pip download --only-binary=:all: --platform manylinux_2_28_x86_64 --python-version 3.13 --implementation cp --abi cp313 --dest /tmp/onetrain_wheelhouse onnxruntime-gpu==1.23.2 -i https://pypi.tuna.tsinghua.edu.cn/simple
scp -P <port> /tmp/onetrain_wheelhouse/onnxruntime_gpu-*.whl <user>@<host>:/tmp/onetrain_wheelhouse/
python -m pip install --upgrade --no-deps /tmp/onetrain_wheelhouse/onnxruntime_gpu-*.whl
```

- GitHub tarballs for `mgds` lack `.git` metadata; set `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_MGDS` before installing editable `mgds`.
- Do not run complex, long pip installs only in the SSH foreground if the connection is unstable. Write a remote `/tmp/onetrain_install.sh` and run it under a temporary tmux session, logging to `/home/jovyan/code/src/OneTrainer/onetrain_install.log`.
- Avoid `set -u` in scripts that call `conda activate`; conda hook scripts may reference unset variables.

## Verify OneTrainer

```bash
source /opt/conda/etc/profile.d/conda.sh
conda activate onetrain
cd /home/jovyan/code/src/OneTrainer
python --version
python - <<'PY'
import torch
print("torch", torch.__version__)
print("cuda runtime", torch.version.cuda)
print("cuda available", torch.cuda.is_available())
print("gpu count", torch.cuda.device_count())
if torch.cuda.is_available():
    print("gpu0", torch.cuda.get_device_name(0))
PY
python - <<'PY'
import diffusers, transformers, customtkinter, bitsandbytes, mgds
import onnxruntime as ort
import muon
print("diffusers", diffusers.__version__)
print("transformers", transformers.__version__)
print("onnxruntime", ort.__version__)
print("bitsandbytes", getattr(bitsandbytes, "__version__", "unknown"))
print("imports ok")
PY
python - <<'PY'
import tkinter, customtkinter
print("tk", tkinter.TkVersion)
print("gui imports ok")
PY
python scripts/train.py -h
python -m pip check
```

Prepare the CLI tmux session:

```bash
tmux new-session -d -s onetrain
tmux send-keys -t onetrain "source /opt/conda/etc/profile.d/conda.sh" C-m
tmux send-keys -t onetrain "conda activate onetrain" C-m
tmux send-keys -t onetrain "cd /home/jovyan/code/src/OneTrainer" C-m
tmux send-keys -t onetrain "export HF_HUB_DISABLE_XET=1" C-m
```

CLI training entrypoint:

```bash
python scripts/train.py --config-path <config.json>
```

## OneTrainer Shared Outputs

OneTrainer does not use ai-toolkit's `training_folder` field. The final model destination is configured in the training JSON as `output_model_destination`.

For ComfyUI/Juscent image training, set it to an absolute shared path:

```json
{
  "output_model_destination": "/home/share/game/juscent/train_outputs/onetrainer/<project>/<run>/<name>.safetensors"
}
```

The default presets often use a relative path such as `models/lora.safetensors`; if left unchanged, the output may land under the OneTrainer project tree instead of the shared store.

Optionally set workspace and cache paths when the user wants the whole run state on shared storage:

```json
{
  "workspace_dir": "/home/share/game/juscent/train_outputs/onetrainer/<project>/<run>/workspace",
  "cache_dir": "/home/share/game/juscent/train_outputs/onetrainer/<project>/<run>/cache"
}
```

Keep in mind that shared cache/workspace paths can increase JuiceFS I/O and space usage. The final model destination is the most important setting for handoff to ComfyUI. Publish only selected final artifacts into the ComfyUI taxonomy, preferably through symlinks:

```text
/home/share/game/juscent/models/loras/onetrainer/<name>.safetensors
/home/share/game/juscent/models/checkpoints/<name>.safetensors
```

## OneTrainer GUI over noVNC

### Day-2 control (preferred on Juscent)

```bash
bash /home/share/game/juscent/bin/onetrain.sh start
bash /home/share/game/juscent/bin/onetrain.sh status
bash /home/share/game/juscent/bin/onetrain.sh restart
bash /home/share/game/juscent/bin/onetrain.sh stop
```

Uses `/nfs/envs/onetrain`, session `onetrain-gui`, noVNC `127.0.0.1:6080`, VNC `5901`, log `/tmp/onetrain-gui.log`.  
Share-level wrappers under `juscent/bin/start_onetrainer_gui.sh` are **removed** — do not revive them as primary.

### First-time install of display packages

Install display bridge packages when passwordless sudo is available:

```bash
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y xvfb x11vnc novnc websockify fluxbox xterm
```

If sudo is unavailable, inspect conda-forge alternatives (`xpra`, `websockify`) and report before choosing a fallback. The tested path is `Xvfb + fluxbox + x11vnc + websockify/noVNC`.

### Legacy local wrappers (install/debug only)

Only use the following if `onetrain.sh` is missing on a non-Juscent host. On Juscent, prefer the share bin script.

Create `/home/jovyan/code/src/OneTrainer/start_onetrainer_gui.sh` (legacy):

```bash
#!/usr/bin/env bash
set -eo pipefail

APP_DIR=/home/jovyan/code/src/OneTrainer
DISPLAY_NUM=:10
GEOMETRY=1600x1000x24
VNC_PORT=5901
NOVNC_BIND=127.0.0.1:6080
LOG_DIR="$APP_DIR/gui_logs"
mkdir -p "$LOG_DIR"

cleanup() {
  set +e
  for f in "$LOG_DIR"/*.pid; do
    [ -f "$f" ] || continue
    pid="$(cat "$f" 2>/dev/null)"
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

rm -f "$LOG_DIR"/*.pid
rm -f /tmp/.X10-lock

cd "$APP_DIR"
source /opt/conda/etc/profile.d/conda.sh
conda activate onetrain
export HF_HUB_DISABLE_XET=1
export DISPLAY="$DISPLAY_NUM"

Xvfb "$DISPLAY_NUM" -screen 0 "$GEOMETRY" -ac >"$LOG_DIR/xvfb.log" 2>&1 &
echo $! > "$LOG_DIR/xvfb.pid"
sleep 2

fluxbox >"$LOG_DIR/fluxbox.log" 2>&1 &
echo $! > "$LOG_DIR/fluxbox.pid"
sleep 1

x11vnc -display "$DISPLAY_NUM" -localhost -nopw -forever -shared -rfbport "$VNC_PORT" >"$LOG_DIR/x11vnc.log" 2>&1 &
echo $! > "$LOG_DIR/x11vnc.pid"
sleep 2

websockify --web=/usr/share/novnc "$NOVNC_BIND" "127.0.0.1:$VNC_PORT" >"$LOG_DIR/novnc.log" 2>&1 &
echo $! > "$LOG_DIR/novnc.pid"
sleep 2

python scripts/train_ui.py >"$LOG_DIR/onetrainer_ui.log" 2>&1 &
echo $! > "$LOG_DIR/onetrainer_ui.pid"

echo "GUI stack is running. noVNC: http://127.0.0.1:6080/vnc.html"
wait "$(cat "$LOG_DIR/onetrainer_ui.pid")"
```

Create `/home/jovyan/code/src/OneTrainer/stop_onetrainer_gui.sh`:

```bash
#!/usr/bin/env bash
set +e
LOG_DIR=/home/jovyan/code/src/OneTrainer/gui_logs
for f in "$LOG_DIR"/*.pid; do
  [ -f "$f" ] || continue
  pid="$(cat "$f" 2>/dev/null)"
  [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
done
tmux kill-session -t onetrain-gui 2>/dev/null || true
```

Start GUI:

```bash
chmod +x /home/jovyan/code/src/OneTrainer/*onetrainer_gui.sh
tmux kill-session -t onetrain-gui 2>/dev/null || true
tmux new-session -d -s onetrain-gui /home/jovyan/code/src/OneTrainer/start_onetrainer_gui.sh
```

Verify:

```bash
tmux capture-pane -t onetrain-gui -p -S -60
ps -eo pid,ppid,stat,etime,cmd | grep -E '[X]vfb :10|[x]11vnc|[w]ebsockify|[t]rain_ui.py|[f]luxbox'
ss -ltnp | grep -E ':(5901|6080)'
curl -sI http://127.0.0.1:6080/vnc.html | sed -n '1,12p'
DISPLAY=:10 xdpyinfo | sed -n '1,20p'
DISPLAY=:10 xwininfo -root -tree | sed -n '1,80p'
```

Access from Mac:

```bash
ssh -L 16080:127.0.0.1:6080 -p <port> <user>@<host>
```

Then open:

```text
http://127.0.0.1:16080/vnc.html?host=127.0.0.1&port=16080&autoconnect=true&resize=scale
```

Management:

```bash
# Preferred
bash /home/share/game/juscent/bin/onetrain.sh status
bash /home/share/game/juscent/bin/onetrain.sh restart

# Debug
tmux attach -t onetrain-gui
# Legacy only:
# /home/jovyan/code/src/OneTrainer/stop_onetrainer_gui.sh
# /home/jovyan/code/src/OneTrainer/start_onetrainer_gui.sh
```

Logs:

```bash
/home/jovyan/code/src/OneTrainer/gui_logs/
```
