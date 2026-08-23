#!/usr/bin/env bash
# Pick a Python that can actually run this tool, then exec it.
#
# Why this exists: the interpreter on PATH is not necessarily a usable one.
# Measured on a macOS box 2026-08-23: /usr/bin/python3 is 3.9.6 without httpx,
# so an agent following "python3 scripts/douyin_hd.py" from the docs would fail
# on both counts. Requirements are Python >= 3.10 (dataclass slots=) and httpx.
#
# Override with DOUYIN_PYTHON=/path/to/python3 to force a specific interpreter.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usable() {
    [ -x "$1" ] || command -v "$1" >/dev/null 2>&1 || return 1
    "$1" - <<'PY' >/dev/null 2>&1
import sys
if sys.version_info < (3, 10):
    raise SystemExit(1)
import httpx  # noqa: F401
PY
}

if [ -n "${DOUYIN_PYTHON:-}" ]; then
    if usable "$DOUYIN_PYTHON"; then
        exec "$DOUYIN_PYTHON" "$HERE/douyin_hd.py" "$@"
    fi
    echo "错误: DOUYIN_PYTHON=$DOUYIN_PYTHON 不满足要求（需 Python >= 3.10 且已装 httpx）。" >&2
    exit 1
fi

# Candidates in preference order; first usable one wins.
for candidate in \
    python3 python3.13 python3.12 python3.11 python3.10 \
    /opt/homebrew/bin/python3 /usr/local/bin/python3 /opt/anaconda3/bin/python3
do
    resolved="$(command -v "$candidate" 2>/dev/null || true)"
    [ -n "$resolved" ] || continue
    if usable "$resolved"; then
        exec "$resolved" "$HERE/douyin_hd.py" "$@"
    fi
done

cat >&2 <<'MSG'
错误: 没找到可用的 Python（需 >= 3.10 且已安装 httpx）。

已尝试 PATH 上的 python3 及常见位置。请任选其一：
  1) 装依赖：  <你的python3> -m pip install -r requirements.txt
  2) 指定解释器： DOUYIN_PYTHON=/path/to/python3 scripts/run.sh ...

注意系统自带的 /usr/bin/python3 常是 3.9 且不带 httpx，不能直接用。
MSG
exit 1
