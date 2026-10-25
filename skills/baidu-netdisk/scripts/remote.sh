#!/usr/bin/env bash
# 在远端机器上执行本 skill 的脚本（经 ssh 标准输入传过去，不需要先部署）。
#   bash remote.sh <host> <script> [args...]
#   bash remote.sh tb bpcs.sh ls /00.Movies
#   bash remote.sh tb verify.py --log ~/bpcs-logs/x.log --remote /00.Movies/A --local /data/A
# 参数里的 ~/ 原样传给远端，由远端脚本自己展开。本机的 BPCS_BIN 会一并传过去。
set -euo pipefail
[ $# -ge 2 ] || { echo "用法: $0 <host> <script> [args...]" >&2; exit 2; }
host=$1; script=$2; shift 2
dir=$(cd "$(dirname "$0")" && pwd)

case "$host" in
  ''|-*|*[!A-Za-z0-9_.@:-]*) echo "非法 host: $host" >&2; exit 2 ;;
esac
case "$script" in
  bpcs.sh|diff.py|download.sh|login_hint.sh|status.py|verify.py) ;;
  *) echo "不支持的脚本: $script" >&2; exit 2 ;;
esac

src=$dir/$script
[ -f "$src" ] || { echo "没有这个脚本: $src" >&2; exit 2; }
args=""
for a in "$@"; do args+=" $(printf '%q' "$a")"; done
env_prefix=""
[ -n "${BPCS_BIN:-}" ] && env_prefix="BPCS_BIN=$(printf '%q' "$BPCS_BIN") "
[ -n "${BPCS_ALLOW_OVERWRITE:-}" ] && env_prefix+="BPCS_ALLOW_OVERWRITE=$(printf '%q' "$BPCS_ALLOW_OVERWRITE") "
case "$script" in
  *.py) exec ssh -o ConnectTimeout=20 "$host" "${env_prefix}python3 -${args}" < "$src" ;;
  *.sh) exec ssh -o ConnectTimeout=20 "$host" "${env_prefix}bash -s --${args}" < "$src" ;;
  *) echo "只支持 .py / .sh" >&2; exit 2 ;;
esac
