#!/usr/bin/env bash
# BaiduPCS-Go 的安全封装：只放行本 skill 用到的命令；涉及凭证、永久删除、对外分享、改配置的命令一律拒绝。
# 凭证类命令绝不回显原参数。用 BPCS_BIN 指定二进制，默认 ~/.local/bin/BaiduPCS-Go。
#   bash bpcs.sh who | quota | ls <dir> | tree <dir> | meta <path> | search <kw> | d ... | u ... | mkdir | mv | cp | transfer
set -uo pipefail
BIN=${BPCS_BIN:-$HOME/.local/bin/BaiduPCS-Go}
[ -x "$BIN" ] || BIN=$(command -v BaiduPCS-Go 2>/dev/null || true)
[ -n "$BIN" ] && [ -x "$BIN" ] || { echo "找不到 BaiduPCS-Go（设 BPCS_BIN 或装到 ~/.local/bin/）" >&2; exit 127; }
[ $# -ge 1 ] || { "$BIN" help; exit 0; }

refuse() {
  echo "已拒绝：「$1」（$2）。" >&2
  exit 3
}

refuse_with_command() {
  local cmd=$1 reason=$2; shift 2
  echo "已拒绝：「$cmd」（$reason）。" >&2
  echo "如确需执行，请用户在 $(hostname) 的终端里自行核对并运行：" >&2
  printf '  %q' "$BIN" "$@" >&2; echo >&2
  exit 3
}

# BaiduPCS-Go 支持 "[global options] command"。不接受全局参数，避免危险命令绕过首参数检查；
# 帮助和版本是唯一例外。
case "$1" in
  --help|-h|--version|-v) exec "$BIN" "$@" ;;
  -*) refuse "$1" "本封装不接受全局参数，请直接使用受支持的命令" ;;
esac

cmd=$1
case "$cmd" in
  login|logout|loglist|setastoken|su)
    refuse "$cmd" "涉及账号凭证或切换账号；请运行 login_hint.sh，并且不要把凭证发到对话里" ;;
  rm)
    refuse_with_command "$cmd" "删除后会进入网盘回收站，清空或过期后不可恢复" "$@" ;;
  recycle)
    refuse_with_command "$cmd" "可能还原、永久删除或清空回收站" "$@" ;;
  share)
    refuse "$cmd" "会创建对外分享；请用户本人在终端操作" ;;
  config)
    if [ "$#" -ne 1 ]; then refuse "config" "本封装只允许查看配置，不接受 config 子命令或参数"; fi
    # 只读查看：去掉任何可能含凭证的行
    "$BIN" config 2>&1 | grep -v -i -E 'bduss|stoken|ptoken|cookie|token|sboxtkn|^[[:space:]]*proxy([[:space:]_]|$)' ; exit "${PIPESTATUS[0]}" ;;
  who)
    "$BIN" who 2>&1 | sed -E 's/(uid:? *)[0-9]+/\1<uid>/I'; exit "${PIPESTATUS[0]}" ;;
  help|'?'|'？'|quota|pwd|ls|l|ll|tree|t|meta|search|s|match|download|d|upload|u|mkdir|mv|cp|transfer|cd)
    ;;
  *)
    refuse "$cmd" "不在本 skill 的允许列表中" ;;
esac

if [ "$cmd" = upload ] || [ "$cmd" = u ]; then
  args=("$@")
  policy=""
  for ((i=1; i<${#args[@]}; i++)); do
    case "${args[$i]}" in
      --policy=*) policy=${args[$i]#--policy=} ;;
      --policy) policy=${args[$((i + 1))]:-} ;;
    esac
  done
  if [[ "$policy" =~ ^(overwrite|rsync)$ ]] && [ "${BPCS_ALLOW_OVERWRITE:-0}" != 1 ]; then
    refuse "upload --policy $policy" "可能覆盖远端同名文件；用户明确确认后设置 BPCS_ALLOW_OVERWRITE=1 再执行"
  fi
fi
exec "$BIN" "$@"
