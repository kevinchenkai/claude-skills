#!/usr/bin/env bash
# Read-only usage/task counts for ai-toolkit and ComfyUI on Juscent GPU hosts.
#
# ai-toolkit : rows in the persistent Job table (aitk_db.db) — AUTHORITATIVE task counts.
# ComfyUI    : in-process /history (RESETS on every service restart) + output/ artifact
#              files by mtime (artifacts, NOT tasks; output/ is a SHARED dir).
#
# Since 2026-07-17 both stacks live on train-1 (infer-1 decommissioned), so a single
# --ssh usually covers both. --train-ssh/--comfy-ssh remain for split-host setups.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  gpu_task_counts.sh --since "YYYY-MM-DD HH:MM:SS" --ssh "ssh train-1" [options]

  --since "YYYY-MM-DD HH:MM:SS"   window start, host localtime (required)
  --ssh CMD                       SSH command for BOTH stacks (train-1 default host)
  --train-ssh CMD                 override SSH for ai-toolkit only
  --comfy-ssh CMD                 override SSH for ComfyUI only
  --train-path PATH               ai-toolkit dir   (default /home/jovyan/code/src/ai-toolkit)
  --comfy-path PATH               ComfyUI dir      (default /home/jovyan/code/src/ComfyUI)
  --comfy-port PORT               ComfyUI port     (default 8188)
  --skip-comfy | --skip-train     count only one stack

Interpreting the output:
  ai-toolkit  -> "total/completed/running/error/stopped" is the real task count.
  ComfyUI     -> history_entries_* only covers the CURRENT process. If the service
                 was restarted inside the window, older prompts are GONE; trust the
                 output/ artifact counts instead, and remember output/ is shared so
                 files may come from more than one host/task.
USAGE
}

SINCE="" SSH_BOTH="" TRAIN_SSH="" COMFY_SSH=""
TRAIN_PATH="/home/jovyan/code/src/ai-toolkit"
COMFY_PATH="/home/jovyan/code/src/ComfyUI"
COMFY_PORT="8188" SKIP_COMFY=0 SKIP_TRAIN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --since) SINCE=${2:?}; shift 2 ;;
    --ssh) SSH_BOTH=${2:?}; shift 2 ;;
    --train-ssh) TRAIN_SSH=${2:?}; shift 2 ;;
    --comfy-ssh) COMFY_SSH=${2:?}; shift 2 ;;
    --train-path) TRAIN_PATH=${2:?}; shift 2 ;;
    --comfy-path) COMFY_PATH=${2:?}; shift 2 ;;
    --comfy-port) COMFY_PORT=${2:?}; shift 2 ;;
    --skip-comfy) SKIP_COMFY=1; shift ;;
    --skip-train) SKIP_TRAIN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$TRAIN_SSH" ]] || TRAIN_SSH="$SSH_BOTH"
[[ -n "$COMFY_SSH" ]] || COMFY_SSH="$SSH_BOTH"

if [[ -z "$SINCE" ]]; then usage >&2; exit 2; fi
if [[ $SKIP_TRAIN -eq 0 && -z "$TRAIN_SSH" ]]; then echo "need --ssh or --train-ssh" >&2; exit 2; fi
if [[ $SKIP_COMFY -eq 0 && -z "$COMFY_SSH" ]]; then echo "need --ssh or --comfy-ssh" >&2; exit 2; fi

run_remote() { printf '%s\n' "$2" | $1 'bash -s'; }

train_payload=$(cat <<REMOTE
set -e
SINCE='$SINCE'; APP='$TRAIN_PATH'
SQ=/opt/conda/bin/sqlite3; [ -x "\$SQ" ] || SQ=sqlite3
cd "\$APP"
DB=aitk_db.db; [ -f "\$DB" ] || DB=\$(ls -1 *.db 2>/dev/null | head -1)
echo "== ai-toolkit host =="; hostname; date '+%F %T %Z'; echo "db=\$DB"
echo "== ai-toolkit total (Job table = authoritative) =="
\$SQ -header -column "\$DB" "select count(*) total, sum(status='completed') completed, sum(status='running') running, sum(status='error') error, sum(status='stopped') stopped from Job where datetime(created_at/1000,'unixepoch','localtime') >= '\$SINCE';"
echo "== ai-toolkit daily =="
\$SQ -header -column "\$DB" "select date(datetime(created_at/1000,'unixepoch','localtime')) day, count(*) jobs, sum(status='completed') completed, sum(status='stopped') stopped, sum(status='error') error from Job where datetime(created_at/1000,'unixepoch','localtime') >= '\$SINCE' group by day order by day;"
echo "== ai-toolkit rows =="
\$SQ -header -column "\$DB" "select id, substr(name,1,36) name, status, step, datetime(created_at/1000,'unixepoch','localtime') created from Job where datetime(created_at/1000,'unixepoch','localtime') >= '\$SINCE' order by created_at;"
REMOTE
)

comfy_payload=$(cat <<REMOTE
set -e
export SINCE='$SINCE' APP='$COMFY_PATH' PORT='$COMFY_PORT'
cd "\$APP"
echo "== ComfyUI host =="; hostname; date '+%F %T %Z'
curl -fsS "http://127.0.0.1:\${PORT}/system_stats" -o /tmp/comfy_stats.json 2>/dev/null && \
  python3 -c "import json;d=json.load(open('/tmp/comfy_stats.json'));print('version',d.get('system',{}).get('comfyui_version'))" || echo "system_stats unavailable"
curl -fsS "http://127.0.0.1:\${PORT}/history" -o /tmp/comfy_hist.json 2>/dev/null || echo '{}' > /tmp/comfy_hist.json
OUT=\$(readlink -f "\$APP/output" 2>/dev/null || echo "\$APP/output")
export OUT
python3 <<'PY'
import collections, datetime, json, os
from pathlib import Path
since = datetime.datetime.strptime(os.environ["SINCE"], "%Y-%m-%d %H:%M:%S")
since_ts = since.timestamp()
out = Path(os.environ["OUT"])
hist = json.load(open("/tmp/comfy_hist.json"))
img = {".png",".jpg",".jpeg",".webp",".gif"}
files = [p for p in out.rglob("*") if p.is_file()] if out.exists() else []
recent = [p for p in files if p.stat().st_mtime >= since_ts]
recent_img = [p for p in recent if p.suffix.lower() in img]
# date the surviving history prompts by their output mtime
hdays = collections.Counter(); hmin = None
for pid, item in hist.items():
    mt = None
    for node in (item.get("outputs") or {}).values():
        if not isinstance(node, dict): continue
        for vals in node.values():
            if not isinstance(vals, list): continue
            for v in vals:
                if isinstance(v, dict) and v.get("filename"):
                    p = out / (v.get("subfolder") or "") / v["filename"]
                    if p.exists():
                        m = p.stat().st_mtime; mt = m if mt is None else max(mt, m)
    if mt:
        d = datetime.datetime.fromtimestamp(mt); hdays[d.date().isoformat()] += 1
        hmin = d if hmin is None else min(hmin, d)
print("== ComfyUI /history (IN-PROCESS; resets on restart) ==")
print("history_entries_total", len(hist))
if hist and hmin: print("history_earliest_prompt", hmin.strftime("%F %T"))
if hist and hmin and hmin > since:
    print("WARNING: earliest history prompt is AFTER window start -> service was")
    print("         restarted mid-window; older prompts lost. Use output artifacts below.")
print("== ComfyUI output artifacts (by mtime; SHARED dir; artifacts != tasks) ==")
print("output_dir", str(out))
print("all_output_files_recent", len(recent))
print("image_output_files_recent", len(recent_img))
by_day = collections.Counter(datetime.datetime.fromtimestamp(p.stat().st_mtime).date().isoformat() for p in recent)
for day, c in sorted(by_day.items()): print("  ", day, c)
PY
REMOTE
)

[[ $SKIP_TRAIN -eq 1 ]] || run_remote "$TRAIN_SSH" "$train_payload"
[[ $SKIP_COMFY -eq 1 ]] || run_remote "$COMFY_SSH" "$comfy_payload"
