#!/usr/bin/env bash
# 在远端 tmux 里后台下载网盘目录/文件，日志按行写（\r 进度条换成换行），带本次运行标记。
#   bash download.sh --session ck-bpcs-x --saveto /data/media --log ~/bpcs-logs/x.log [-p 0] [-l 0] [--retry 5] "/网盘/目录A" "/网盘/目录B" ...
# 注意：BaiduPCS-Go 会在 --saveto 下建与网盘同名的子目录。下载完用 status.py 看进度、verify.py 校验。
set -euo pipefail
SESSION="" SAVETO="" LOG="" P=0 L=0 RETRY=5; PATHS=()
need_value() {
  [ $# -ge 2 ] && [ -n "$2" ] || { echo "$1 缺少参数" >&2; exit 2; }
}
while [ $# -gt 0 ]; do
  case "$1" in
    --session) need_value "$@"; SESSION=$2; shift 2 ;;
    --saveto) need_value "$@"; SAVETO=$2; shift 2 ;;
    --log) need_value "$@"; LOG=$2; shift 2 ;;
    -p) need_value "$@"; P=$2; shift 2 ;;
    -l) need_value "$@"; L=$2; shift 2 ;;
    --retry) need_value "$@"; RETRY=$2; shift 2 ;;
    -*) echo "未知参数 $1" >&2; exit 2 ;; *) PATHS+=("$1"); shift ;;
  esac
done
[ -n "$SESSION" ] && [ -n "$SAVETO" ] && [ -n "$LOG" ] && [ ${#PATHS[@]} -gt 0 ] || { sed -n 2,4p "$0" 2>/dev/null; echo "缺 --session/--saveto/--log/网盘路径" >&2; exit 2; }
[[ "$SESSION" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || { echo "非法 tmux 会话名: $SESSION" >&2; exit 2; }
for pair in "-p:$P" "-l:$L" "--retry:$RETRY"; do
  key=${pair%%:*}; value=${pair#*:}
  [[ "$value" =~ ^[0-9]+$ ]] || { echo "$key 必须是非负整数: $value" >&2; exit 2; }
done
for value in "$SAVETO" "$LOG" "${PATHS[@]}"; do
  case "$value" in *$'\n'*|*$'\r'*) echo "路径不能包含换行符" >&2; exit 2 ;; esac
done
SAVETO=${SAVETO/#\~/$HOME}; LOG=${LOG/#\~/$HOME}
BIN=${BPCS_BIN:-$HOME/.local/bin/BaiduPCS-Go}
[ -x "$BIN" ] || { echo "找不到 BaiduPCS-Go: $BIN" >&2; exit 127; }
command -v tmux >/dev/null || { echo "找不到 tmux" >&2; exit 127; }
command -v stdbuf >/dev/null || { echo "找不到 stdbuf" >&2; exit 127; }
tmux has-session -t "$SESSION" 2>/dev/null && { echo "tmux 会话 $SESSION 已存在，换个名字或先看 status.py" >&2; exit 1; }
WHO=$("$BIN" who 2>&1) || { echo "未登录或登录失效：运行 login_hint.sh 让用户本人登录" >&2; exit 4; }
grep -q "用户名" <<<"$WHO" || { echo "未登录或登录失效：运行 login_hint.sh 让用户本人登录" >&2; exit 4; }
mkdir -p "$SAVETO" "$(dirname "$LOG")"
[ -w "$SAVETO" ] || { echo "目录不可写: $SAVETO" >&2; exit 1; }
RUN=$(date +%Y%m%d-%H%M%S)-$$
RUNNER=$(dirname "$LOG")/.bpcs_run_${SESSION}.sh
{
  echo '#!/usr/bin/env bash'
  # 路径放进数组再循环：直接把 printf %q 的结果嵌进双引号 echo，非 UTF-8 locale 下中文会变成 $'\345…' 字面量
  printf 'PATHS=('; for p in "${PATHS[@]}"; do printf ' %q' "$p"; done; echo ')'
  echo "BIN=$(printf '%q' "$BIN"); SAVETO=$(printf '%q' "$SAVETO"); RUN=$RUN"
  cat <<'BODY'
failed=0
echo "RUN_START $RUN $(date '+%F %T') saveto=$SAVETO"
for p in "${PATHS[@]}"; do
  echo "DIR_START $RUN $p $(date '+%F %T')"
BODY
  echo "  \"\$BIN\" d --saveto \"\$SAVETO\" -p $P -l $L --retry $RETRY \"\$p\" 2>&1 | stdbuf -o0 tr '\\r' '\\n'"
  cat <<'BODY'
  rc=${PIPESTATUS[0]}
  echo "DIR_DONE $RUN $p rc=$rc $(date '+%F %T')"
  if [ "$rc" -ne 0 ]; then failed=$((failed + 1)); fi
done
echo "RUN_DONE $RUN failed=$failed $(date '+%F %T')"
if [ "$failed" -gt 0 ]; then exit 1; fi
BODY
} > "$RUNNER"
chmod +x "$RUNNER"
tmux new-session -d -s "$SESSION" "bash $(printf '%q' "$RUNNER") >> $(printf '%q' "$LOG") 2>&1 < /dev/null"
echo "已启动：tmux $SESSION  run=$RUN  log=$LOG  saveto=$SAVETO  路径数=${#PATHS[@]}"
