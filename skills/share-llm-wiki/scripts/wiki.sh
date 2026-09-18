#!/usr/bin/env bash
# share-llm-wiki —— 在远端共享盘上检索 LLM-WIKI（只读）
#
# 所有子命令都是一次 ssh 往返，在远端执行，不把 797M 拉回本地。
#
#   WIKI_HOST  ssh 目标，默认 vscode
#   WIKI_ROOT  知识库路径，默认 /home/share/user/chenkai/VLA/knowledge
#
# 用法见 `wiki.sh help`。

set -uo pipefail

HOST="${WIKI_HOST:-vscode}"
ROOT="${WIKI_ROOT:-/home/share/user/chenkai/VLA/knowledge}"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=15)

die() { printf '%s\n' "$*" >&2; exit 1; }

# 远端执行。参数一律经 env 传递（A=... B=... bash -s），不做字符串插值，
# 因此 heredoc 全部用引号形式，本地不展开任何变量 —— 正则里的 $ [ ] \ 也就不会被吃掉。
remote() {
  ssh "${SSH_OPTS[@]}" "$HOST" \
    "K=$(printf '%q' "$ROOT") $* bash -s"
}

usage() {
  cat <<'EOF'
share-llm-wiki —— 远端 LLM-WIKI 检索（只读）

  wiki.sh check                    连通性 + 新鲜度 + 是否带 revision 历史
  wiki.sh index                    知识库入口（index.md）
  wiki.sh nav <关键词>             在 index.md 的导航里找入口（首选检索方式）
  wiki.sh ls <目录>                列目录，带每页 status 与标题
  wiki.sh cat <路径>               读一页（相对 WIKI_ROOT）
  wiki.sh link <slug>              解析 [[wikilink]] 到真实文件
  wiki.sh grep <正则> [目录...]    全文检索，默认跳过 sources/
  wiki.sh grepall <正则>           含 sources/ 的全量检索
  wiki.sh trace <数字或词>         数字溯源：分层给出 sources/ 原始记录与综述层
  wiki.sh stale                    列出 status: superseded 的页

环境变量：WIKI_HOST（默认 vscode）、WIKI_ROOT
EOF
}

cmd="${1:-help}"; shift || true

case "$cmd" in

help|-h|--help) usage ;;

check)
  remote <<'EOS'
if [ ! -d "$K" ]; then echo "不可达: $K"; exit 1; fi
echo "root   : $K"
echo "规模   : $(find "$K" -name '*.md' | wc -l) 个 .md / $(du -sh "$K" 2>/dev/null | cut -f1)"
echo "index  : $(date -r "$K/index.md" '+%Y-%m-%d %H:%M' 2>/dev/null)"
newest=$(find "$K" -name '*.md' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
[ -n "$newest" ] && echo "最新改 : $(date -r "$newest" '+%Y-%m-%d %H:%M')  ${newest#$K/}"
if [ -d "$K/.git" ]; then
  echo "历史   : 有 .git —— 活 wiki，写入受 revision daemon 保护"
else
  echo "历史   : 无 .git —— rsync 副本，写入不回流且不可恢复，按只读用"
fi
EOS
  ;;

index)
  remote <<'EOS'
cat "$K/index.md"
EOS
  ;;

nav)
  [ $# -ge 1 ] || die "用法: wiki.sh nav <关键词>"
  remote "Q=$(printf '%q' "$1")" <<'EOS'
if ! grep -n -i -- "$Q" "$K/index.md"; then
  echo "(index.md 导航里没有「$Q」——改用 wiki.sh grep 全文检索，或 wiki.sh index 看有哪些主题)"
fi
EOS
  ;;

ls)
  remote "D=$(printf '%q' "${1:-.}")" <<'EOS'
d="$K/$D"
[ -d "$d" ] || { echo "不是目录: $D"; exit 1; }
for f in "$d"/*.md; do
  [ -e "$f" ] || continue
  t=$(grep -m1 -E '^#{1,2} ' "$f" 2>/dev/null | sed -E 's/^#{1,2} //')
  s=$(grep -m1 '^status:' "$f" 2>/dev/null | sed 's/^status: *//' | tr -d '\r')
  printf '%-50s %-11s %s\n' "${f##*/}" "${s:--}" "$t"
done
EOS
  ;;

cat)
  [ $# -ge 1 ] || die "用法: wiki.sh cat <相对路径>"
  remote "P=$(printf '%q' "$1")" <<'EOS'
f="$K/$P"
[ -f "$f" ] || { echo "找不到: $P（试 wiki.sh link 或 wiki.sh grep）"; exit 1; }
grep -q '^status: superseded' "$f" && \
  echo ">>> 本页 status: superseded，已被取代；引用前先看正文写明被什么取代 <<<"
cat "$f"
EOS
  ;;

link)
  [ $# -ge 1 ] || die "用法: wiki.sh link <slug>"
  s="${1#\[\[}"; s="${s%\]\]}"
  remote "S=$(printf '%q' "$s")" <<'EOS'
hit=$(find "$K" -name "${S}.md" -not -path '*/.obsidian/*' 2>/dev/null | head -5)
if [ -n "$hit" ]; then
  printf '%s\n' "$hit" | sed "s|$K/||"
else
  echo "[[$S]] 无同名文件 —— 本 wiki 允许悬空链接（标记待写的页）。近似匹配："
  find "$K" -name "*${S}*.md" -not -path '*/.obsidian/*' 2>/dev/null | sed "s|$K/||" | head -10
fi
EOS
  ;;

grep|grepall)
  [ $# -ge 1 ] || die "用法: wiki.sh $cmd <正则> [目录...]"
  pat="$1"; shift
  if [ "$cmd" = "grepall" ]; then
    dirs="."
  elif [ $# -gt 0 ]; then
    dirs="$*"
  else
    dirs="index.md log.md AGENTS.md experiments findings topics evaluations datasets"
  fi
  remote "PAT=$(printf '%q' "$pat") DIRS=$(printf '%q' "$dirs")" <<'EOS'
cd "$K" || exit 1
grep -rn --include='*.md' -I -- "$PAT" $DIRS 2>/dev/null | grep -v '/\.obsidian/' | head -80
EOS
  ;;

trace)
  [ $# -ge 1 ] || die "用法: wiki.sh trace <数字或词>"
  remote "PAT=$(printf '%q' "$1")" <<'EOS'
cd "$K" || exit 1
echo "### 原始记录 sources/ evaluations/ —— 引用数字以这里为准"
grep -rn --include='*.md' -I -- "$PAT" sources evaluations 2>/dev/null | head -30
echo
echo "### 综述层 experiments/ findings/ topics/ —— 不要只引用这里的数字"
grep -rn --include='*.md' -I -- "$PAT" experiments findings topics 2>/dev/null | head -20
EOS
  ;;

stale)
  remote <<'EOS'
cd "$K" || exit 1
grep -rln '^status: superseded' --include='*.md' . 2>/dev/null | grep -v '/\.obsidian/' | sed 's|^\./||'
EOS
  ;;

*) die "未知子命令: ${cmd}（看 wiki.sh help）" ;;
esac
