#!/usr/bin/env bash
# share-llm-wiki —— 在远端共享盘上检索 LLM-WIKI（只读）
#
# 所有子命令都是一次 ssh 往返，在远端执行，不把 797M 拉回本地。
#
#   WIKI_HOST     ssh 目标，默认 vscode
#   WIKI_BASE     多项目容器目录，默认 /home/share/user/chenkai/VLA
#   WIKI_PROJECT  项目名，默认 vla-training（即 $WIKI_BASE/$WIKI_PROJECT）
#   WIKI_ROOT     直接指定完整路径；设了就**优先于** BASE/PROJECT
#
# 上游 2026-09-20 起改成多项目布局：容器目录下一个子目录一个 wiki，
# 各自带 .wiki-project.toml。加新项目只需 WIKI_PROJECT=<名字>，不必改脚本。
# `wiki.sh projects` 列出当前有哪些。
#
# 用法见 `wiki.sh help`。

set -uo pipefail

HOST="${WIKI_HOST:-vscode}"
BASE="${WIKI_BASE:-/home/share/user/chenkai/VLA}"
PROJECT="${WIKI_PROJECT:-vla-training}"
ROOT="${WIKI_ROOT:-$BASE/$PROJECT}"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=15)

die() { printf '%s\n' "$*" >&2; exit 1; }

# 参数以 shell 引用传递；公共函数与命令正文经 stdin 送入同一个远端 Bash。
remote() {
  {
    cat <<'COMMON'
set -uo pipefail
# 消费完整输入，避免 head 提前退出导致 SIGPIPE；诊断写 stderr，便于管道筛选。
limited() {
  awk -v limit="$LIMIT" 'limit == 0 || NR <= limit {print}
    END {if (limit > 0 && NR > limit)
      printf "[截断] 共 %d 条，仅显示 %d 条；用 --all 或 --limit N。\n", NR, limit > "/dev/stderr"}'
}
status_of() {
  awk '
    NR == 1 {sub(/\r$/, ""); if ($0 != "---") exit; next}
    {sub(/\r$/, "")}
    /^---[[:space:]]*$/ || /^\.\.\.[[:space:]]*$/ {exit}
    /^status:[[:space:]]*/ {
      sub(/^status:[[:space:]]*/, ""); sub(/[[:space:]]+#.*$/, "")
      gsub(/^[[:space:]]+|[[:space:]]+$/, "")
      q = sprintf("%c", 39)
      if (($0 ~ /^".*"$/) || (substr($0,1,1) == q && substr($0,length,1) == q))
        $0 = substr($0,2,length-2)
      print; exit
    }' "$1"
}
search_md() {
  local rc path pattern="$1"
  shift
  for path in "$@"; do
    [ -e "$path" ] || { echo "路径不存在: $path" >&2; return 2; }
  done
  grep -rn --include='*.md' --exclude-dir=.obsidian --exclude-dir=.git -I -- "$pattern" "$@"
  rc=$?
  # grep 1 = 无命中；2+ = 错误。远端 pipefail 使错误穿过 limited。
  if [ "$rc" -eq 1 ]; then echo '(无命中)' >&2; return 0; fi
  return "$rc"
}
COMMON
    cat
  } | ssh "${SSH_OPTS[@]}" "$HOST" \
    "K=$(printf '%q' "$ROOT") LIMIT=$limit $* bash -s"
}

usage() {
  cat <<'EOF'
share-llm-wiki —— 远端 LLM-WIKI 检索（只读）

  wiki.sh check                    连通性 + 内容修改时间 + .git 存在性（保护状态未验证）
  wiki.sh index                    知识库入口（index.md）
  wiki.sh nav <关键词>             在 index.md 的导航里找入口（首选检索方式）
  wiki.sh ls <目录>                列目录，带每页 status 与标题
  wiki.sh cat <路径>               读一页或文本资产（相对 WIKI_ROOT）
  wiki.sh assets [目录]            列非 .md 证据资产（yaml/csv/svg/jpg…）
  wiki.sh link <slug或路径>              解析 [[wikilink]] 到真实文件
  wiki.sh grep <正则> [目录...]    全文检索，默认跳过 sources/
  wiki.sh grepall <正则>           含 sources/ 的全量检索
  wiki.sh trace <数字或词>         数字溯源：分层给出 sources/ 原始记录与综述层
  wiki.sh stale                    列出 status: superseded 的页

assets/link/grep/grepall/trace/stale 可用 --limit N（默认 80）、--all（完整输出）。选项可放在参数前后。
cat 可用 --lines 起始:结束（1 起，含两端）连续读取长页；默认整篇。
以 -- 结束选项解析，查询以 -- 开头的文本时使用。
退出码：0 = 完成（可无命中）；非 0 = 参数、连接或读取/查询失败。
环境变量：
  WIKI_HOST     ssh 目标（默认 vscode）
  WIKI_PROJECT  项目名（默认 vla-training）—— 换项目改这个
  WIKI_BASE     容器目录（默认 /home/share/user/chenkai/VLA）
  WIKI_ROOT     完整路径；设了则优先于 BASE/PROJECT
远端需 Bash、GNU 工具及 file。
EOF
}

cmd="${1:-help}"; shift || true
limit=80
lines=""
args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --all) limit=0 ;;
    --limit)
      [ $# -ge 2 ] || die '--limit 需要非负整数'
      shift; limit="$1"
      [[ "$limit" =~ ^[0-9]{1,9}$ ]] || die '--limit 需要非负整数（最多 9 位）'
      ;;
    --lines)
      [ $# -ge 2 ] || die '--lines 需要起始:结束'
      shift; lines="$1"
      [[ "$lines" =~ ^[1-9][0-9]{0,8}:[1-9][0-9]{0,8}$ ]] || die '--lines 需要正整数起始:结束'
      [ "${lines%:*}" -le "${lines#*:}" ] || die '--lines 起始不能大于结束'
      ;;
    --) shift; args+=("$@"); break ;;
    --*) die "未知选项: $1" ;;
    *) args+=("$1") ;;
  esac
  shift
done
# Bash 3.2 + nounset 下空数组需要显式分支。
if [ ${#args[@]} -gt 0 ]; then set -- "${args[@]}"; else set --; fi
[ -z "$lines" ] || [ "$cmd" = cat ] || die '--lines 只用于 cat'


case "$cmd" in

help|-h|--help) usage ;;

projects)
  # 列容器目录下的 wiki 项目（认 .wiki-project.toml）。symlink 单列，避免看成两个库。
  ssh "${SSH_OPTS[@]}" "$HOST" "B=$(printf '%q' "$BASE") bash -s" <<'EOS'
set -uo pipefail
[ -d "$B" ] || { echo "容器目录不可达: $B" >&2; exit 1; }
# 先收集别名：symlink 不单列成项目，挂到它指向的真实项目后面。
aliases=""
for d in "$B"/*; do
  [ -L "$d" ] || continue
  tgt=$(readlink -f "$d" 2>/dev/null) || continue
  [ -f "$tgt/.wiki-project.toml" ] || continue
  aliases="$aliases${tgt##*/}=${d##*/}
"
done
found=0
for d in "$B"/*/; do
  real=${d%/}
  [ -L "$real" ] && continue          # 别名已在上面收集
  [ -d "$real" ] || continue
  name=${real##*/}
  t="$real/.wiki-project.toml"
  [ -f "$t" ] || continue
  found=1
  desc=$(sed -n 's/^description *= *"\(.*\)"/\1/p' "$t" 2>/dev/null | sed -n 1p)
  alias=$(printf '%s' "$aliases" | sed -n "s|^$name=||p" | paste -sd, -)
  [ -n "$alias" ] && alias="  （别名: $alias）"
  n=$(find -L "$real" -name '*.md' -not -path '*/.obsidian/*' 2>/dev/null | wc -l)
  printf '%-18s %6s 个 .md  %s%s\n' "$name" "$n" "${desc:-（无描述）}" "$alias"
done
[ "$found" = 1 ] || echo "（$B 下没有带 .wiki-project.toml 的项目）"
echo
echo "用法: WIKI_PROJECT=<名字> wiki.sh <子命令>"
EOS
  ;;

check)
  remote <<'EOS'
if [ ! -d "$K" ]; then echo "不可达: $K" >&2; exit 1; fi
[ -r "$K/index.md" ] || { echo "缺少可读 index.md" >&2; exit 1; }
echo "root   : $K"
echo "规模   : $(find -L "$K" -name '*.md' -not -path '*/.obsidian/*' 2>/dev/null | wc -l) 个 .md / $(du -Lsh "$K" 2>/dev/null | cut -f1)"
echo "index  : $(date -r "$K/index.md" '+%Y-%m-%d %H:%M' 2>/dev/null)"
newest=$(find -L "$K" -name '*.md' -not -path '*/.obsidian/*' -printf '%T@ %p\n' 2>/dev/null | sort -rn | sed -n '1p' | cut -d' ' -f2-)
[ -n "$newest" ] && echo "最新改 : $(date -r "$newest" '+%Y-%m-%d %H:%M')  ${newest#$K/}"
echo "同步   : 时间未知；文件 mtime 不证明与上游同步"
if [ -e "$K/.git" ]; then
  echo "历史   : 有 .git；是否活 wiki、revision daemon 及恢复保护均未验证"
else
  echo "历史   : 无 .git；未发现本地 Git 历史，按只读用"
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
grep -n -i -- "$Q" "$K/index.md"
rc=$?
if [ "$rc" -eq 1 ]; then
  echo "(index.md 导航里没有「$Q」——改用 wiki.sh grep 全文检索，或 wiki.sh index 看有哪些主题)"
elif [ "$rc" -ne 0 ]; then
  exit "$rc"
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
  s=$(status_of "$f") || exit $?
  printf '%-50s %-11s %s\n' "${f##*/}" "${s:--}" "$t"
done
EOS
  ;;

cat)
  [ $# -ge 1 ] || die "用法: wiki.sh cat <路径>"
  remote "P=$(printf '%q' "$1") H=$(printf '%q' "$HOST") LINES=$(printf '%q' "$lines")" <<'EOS'
f="$K/$P"
[ -f "$f" ] || { echo "找不到: $P（试 wiki.sh link / assets / grep）"; exit 1; }
# 空文件是有效文本；类型检测优先拦截 PDF、图片等无 NUL 的二进制资产。
[ -s "$f" ] || { echo "(空文件：$P)"; exit 0; }
mime=$(file -b --mime-type -- "$f") || exit $?
case "$mime" in
  text/*|application/json|application/*+json|application/xml|application/*+xml|application/x-empty|application/x-shellscript|application/yaml|application/x-yaml|image/svg+xml) ;;
  *)
    echo "二进制资产，不回传：$P（$(du -h "$f" | cut -f1)，$mime）"
    printf '取回（使用 SFTP 模式的 scp）：scp -- %q .\n' "$H:$f"
    exit 0 ;;
esac
status=$(status_of "$f") || exit $?
[ "$status" != superseded ] || \
  echo ">>> 本页 status: superseded，已被取代；引用前先看正文写明被什么取代 <<<"
if [ -n "$LINES" ]; then
  total=$(awk 'END {print NR}' "$f") || exit $?
  start=${LINES%:*}; end=${LINES#*:}
  [ "$start" -le "$total" ] || { echo '起始行超出文件范围' >&2; exit 1; }
  echo "[分段] $P 行 $start:$end / 共 $total 行；尚未读取部分须继续读取。" >&2
  sed -n "${start},${end}p" "$f"
else
  cat "$f"
fi
EOS
  ;;

assets)
  # 列被正文当证据引用的非 .md 资产（训练 yaml / 图表 / 导出数据）
  remote "D=$(printf '%q' "${1:-.}")" <<'EOS'
cd "$K" || exit 1
[ -d "$D" ] || { echo "不是目录: $D" >&2; exit 1; }
find -L "$D" -type d \( -name .obsidian -o -name .git \) -prune -o -type f ! -name '*.md' -print \
  | sed 's|^\./||' | sort | limited
EOS
  ;;

link)
  [ $# -ge 1 ] || die "用法: wiki.sh link <slug>"
  s="${1#\[\[}"; s="${s%\]\]}"
  remote "S=$(printf '%q' "$s")" <<'EOS'
cd "$K" || exit 1
# 支持 [[目录/页#标题|别名]]；路径相对于 WIKI_ROOT。
S=${S%%|*}; S=${S%%#*}; S=${S%.md}; S=${S#./}
[ -n "$S" ] || { echo '链接缺少页面名' >&2; exit 1; }
if [ -f "$S.md" ]; then
  printf '%s.md\n' "$S"
else
  files=$(find -L . -type d \( -name .obsidian -o -name .git \) -prune -o -type f -name '*.md' -print) || exit $?
  hit=$(printf '%s\n' "$files" | awk -v s="$S.md" '{n=split($0,a,"/"); if(a[n]==s) print substr($0,3)}')
  if [ -n "$hit" ]; then
    printf '%s\n' "$hit" | sort | limited
  else
    echo "[[$S]] 无同名文件；可能为待写页。近似匹配：" >&2
    printf '%s\n' "$files" | awk -v s="${S##*/}" 'index($0,s) {print substr($0,3)}' | sort | limited
  fi
fi
EOS
  ;;

grep|grepall)
  [ $# -ge 1 ] || die "用法: wiki.sh $cmd <正则> [目录...]"
  pat="$1"; shift
  if [ "$cmd" = "grepall" ]; then
    [ $# -eq 0 ] || die 'grepall 不接受目录参数；限定目录请用 grep'
    set -- .
  elif [ $# -eq 0 ]; then
    set -- index.md log.md AGENTS.md experiments findings topics evaluations datasets
  fi
  # 逐参数引用，保留带空格的目录名，避免 $* 分词。
  dirs=""
  for dir in "$@"; do dirs="$dirs $(printf '%q' "$dir")"; done
  remote "PAT=$(printf '%q' "$pat") DIRS=$(printf '%q' "$dirs")" <<'EOS'
cd "$K" || exit 1
eval "set -- $DIRS"
search_md "$PAT" "$@" | limited
EOS
  ;;

trace)
  [ $# -ge 1 ] || die "用法: wiki.sh trace <数字或词>"
  remote "PAT=$(printf '%q' "$1")" <<'EOS'
cd "$K" || exit 1
echo "### 原始记录 sources/ evaluations/ —— 引用数字以这里为准"
search_md "$PAT" sources evaluations | limited || exit $?
echo
echo "### 综述层 experiments/ findings/ topics/ —— 不要只引用这里的数字"
search_md "$PAT" experiments findings topics | limited
EOS
  ;;

stale)
  remote <<'EOS'
cd "$K" || exit 1
find -L . -type d \( -name .obsidian -o -name .git \) -prune -o -type f -name '*.md' -print0 | {
  while IFS= read -r -d '' f; do
    status=$(status_of "$f") || exit $?
    [ "$status" != superseded ] || printf '%s\n' "${f#./}"
  done
  true
} | limited
EOS
  ;;

*) die "未知子命令: ${cmd}（看 wiki.sh help）" ;;
esac
