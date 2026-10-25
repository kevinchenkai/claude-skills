"""校验网盘下载的完整性，通过后写 MD5SUMS.txt（本地真实 md5）。
  python3 verify.py --remote "/00.Movies/A" --local /data/media/A [--log ~/bpcs-logs/x.log ...] [--meta] [--peer /data/redownload/A] [--write-md5sums] [--force]
网盘记录（大小、md5）来源：下载日志里 BaiduPCS-Go 打印的「文件路径/文件大小/md5」块；--meta 时对日志里没有的文件现查 meta。
判定：
  - 有残留的 *downloading 标记、本地缺文件或多文件、任何文件大小不符 → FAIL
  - 大小全对且 md5 全部一致 → OK
  - 多文件目录大小全对、md5 全部不一致 → OK_REMOTE_MD5_UNUSABLE（以本地 md5 为准）
  - 单文件大小一致但 md5 不一致 → INCONCLUSIVE_SINGLE_MD5；提供相同的第二次下载 --peer 后可判 OK_REDOWNLOAD_MATCH
  - 大小全对、md5 有的一致有的不一致 → FAIL（更可能是真损坏）
退出码 0 = 通过，1 = FAIL，2 = 无法判定。--write-md5sums 只在通过时写，已存在不覆盖（除非 --force）。
"""
import argparse, hashlib, json, os, re, subprocess, tempfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor

ap = argparse.ArgumentParser()
ap.add_argument("--remote", required=True); ap.add_argument("--local", required=True)
ap.add_argument("--log", action="append", default=[]); ap.add_argument("--meta", action="store_true")
ap.add_argument("--peer", help="第二次下载的本地目录，用于确认单文件 md5 不一致")
ap.add_argument("--write-md5sums", action="store_true"); ap.add_argument("--force", action="store_true")
ap.add_argument("--workers", type=int, default=6); ap.add_argument("--json", action="store_true")
a = ap.parse_args()
if a.workers < 1:
    ap.error("--workers 必须大于 0")
remote = a.remote.rstrip("/") or "/"; local = os.path.expanduser(a.local)
remote_prefix = "/" if remote == "/" else remote + "/"
BIN = os.environ.get("BPCS_BIN", os.path.expanduser("~/.local/bin/BaiduPCS-Go"))
if a.meta and (not os.path.isfile(BIN) or not os.access(BIN, os.X_OK)):
    raise SystemExit(f"找不到可执行的 BaiduPCS-Go: {BIN}")
BLOCK = re.compile(r"文件路径\s+(/.+?)\s*\n\s*文件名称.*?\n\s*文件大小\s+(\d+),.*?\n\s*md5[^\n]*?\s([0-9a-f]{32})(?:\s*\n|\s*$)", re.IGNORECASE)

rec = {}   # 相对路径 -> (size, md5)
for lg in a.log:
    window = deque(maxlen=4)
    with open(os.path.expanduser(lg), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            window.append(line.rstrip("\n"))
            m = BLOCK.search("\n".join(window))
            if m:
                p = m.group(1).strip()
                if p.startswith(remote_prefix):
                    rec[p[len(remote_prefix):]] = (int(m.group(2)), m.group(3).lower())

files = []
for root, _, fs in os.walk(local):
    for f in fs:
        rel = os.path.relpath(os.path.join(root, f), local)
        if rel != "MD5SUMS.txt":
            files.append(rel)
files.sort()
leftover = [f for f in files if "downloading" in f]
files = [f for f in files if "downloading" not in f]

meta_errors = []
if a.meta:
    for f in files:
        if f in rec:
            continue
        remote_file = f"/{f}" if remote == "/" else f"{remote}/{f}"
        proc = subprocess.run([BIN, "meta", remote_file], capture_output=True, text=True)
        out = proc.stdout
        m = BLOCK.search(out + "\n")
        if proc.returncode == 0 and m:
            rec[f] = (int(m.group(2)), m.group(3).lower())
        else:
            meta_errors.append({"file": f, "error": (proc.stdout + proc.stderr).strip()[:300] or "无法解析 meta"})

missing = sorted(set(rec) - set(files)); extra = sorted(set(files) - set(rec))

def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()

def chk(f):
    p = os.path.join(local, f); sz = os.path.getsize(p); e = rec.get(f)
    if not e:
        return {"file": f, "status": "NO_REMOTE_RECORD", "size": sz}
    if sz != e[0]:
        return {"file": f, "status": "SIZE_MISMATCH", "size": sz, "remote_size": e[0]}
    h = md5(p)
    return {"file": f, "status": "MD5_MATCH" if h == e[1] else "MD5_DIFF", "size": sz, "md5": h, "remote_md5": e[1]}

with ThreadPoolExecutor(a.workers) as ex:
    res = list(ex.map(chk, [f for f in files if f in rec]))
sized = [r for r in res if r["status"] in ("MD5_MATCH", "MD5_DIFF")]
n_match = sum(r["status"] == "MD5_MATCH" for r in res); n_diff = sum(r["status"] == "MD5_DIFF" for r in res)
size_bad = [r for r in res if r["status"] == "SIZE_MISMATCH"]
reasons = []
if leftover: reasons.append(f"残留未完成标记 {len(leftover)} 个")
if missing: reasons.append(f"网盘有、本地缺 {len(missing)} 个")
if extra: reasons.append(f"本地有、网盘无记录 {len(extra)} 个（加 --meta 现查，或补 --log）")
if size_bad: reasons.append(f"大小不符 {len(size_bad)} 个")
if not files: reasons.append("本地目录为空")
if n_match and n_diff: reasons.append(f"md5 部分一致（{n_match}）部分不一致（{n_diff}），疑似真损坏")
if meta_errors: reasons.append(f"meta 查询或解析失败 {len(meta_errors)} 个")
if reasons:
    verdict = "FAIL"
elif n_diff == 0:
    verdict = "OK"
elif len(sized) == 1:
    verdict = "INCONCLUSIVE_SINGLE_MD5"
    if a.peer:
        peer_file = os.path.join(os.path.expanduser(a.peer), sized[0]["file"])
        if not os.path.isfile(peer_file):
            reasons.append(f"第二份下载不存在: {peer_file}")
            verdict = "FAIL"
        elif os.path.getsize(peer_file) != sized[0]["size"]:
            reasons.append("第二份下载大小不同")
            verdict = "FAIL"
        elif md5(peer_file) != sized[0]["md5"]:
            reasons.append("两次下载的本地 md5 不同")
            verdict = "FAIL"
        else:
            verdict = "OK_REDOWNLOAD_MATCH"
else:
    verdict = "OK_REMOTE_MD5_UNUSABLE"
summary = {"verdict": verdict, "remote": remote, "local": local, "files": len(files), "records": len(rec),
           "md5_match": n_match, "md5_diff": n_diff, "reasons": reasons, "missing": missing[:20], "extra": extra[:20],
           "leftover": leftover[:20], "size_mismatch": size_bad[:20], "meta_errors": meta_errors[:20],
           "bytes": sum(r["size"] for r in sized)}
if verdict in ("OK", "OK_REMOTE_MD5_UNUSABLE", "OK_REDOWNLOAD_MATCH") and a.write_md5sums:
    out = os.path.join(local, "MD5SUMS.txt")
    if os.path.exists(out) and not a.force:
        summary["md5sums"] = "已存在，未覆盖（--force 覆盖）"
    else:
        fd, tmp = tempfile.mkstemp(prefix=".MD5SUMS.", dir=local, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                for r in sorted(sized, key=lambda r: r["file"]):
                    fh.write(f"{r['md5']}  {r['file']}\n")
            os.replace(tmp, out)
        except BaseException:
            try: os.unlink(tmp)
            except FileNotFoundError: pass
            raise
        summary["md5sums"] = f"已写 {out}（{len(sized)} 行，本地 md5）"
if a.json:
    print(json.dumps(summary, ensure_ascii=False, indent=1))
else:
    print(f"[{verdict}] {local}：本地 {len(files)} 个 / 网盘记录 {len(rec)} 个；md5 一致 {n_match}、不一致 {n_diff}；"
          f"{summary['bytes'] / 2**30:.2f} GiB")
    for r in reasons: print("  -", r)
    if verdict == "OK_REMOTE_MD5_UNUSABLE": print("  - 网盘 md5 全部对不上但大小全对：按网盘 md5 不可用处理，以本地 md5 为准")
    if verdict == "INCONCLUSIVE_SINGLE_MD5": print("  - 单文件大小一致但 md5 不一致：请重新下载到另一目录并用 --peer 比较两份本地文件")
    if verdict == "OK_REDOWNLOAD_MATCH": print("  - 网盘 md5 不可用，但两次独立下载的大小和本地 md5 一致")
    if "md5sums" in summary: print("  -", summary["md5sums"])
raise SystemExit(0 if verdict in ("OK", "OK_REMOTE_MD5_UNUSABLE", "OK_REDOWNLOAD_MATCH") else (2 if verdict == "INCONCLUSIVE_SINGLE_MD5" else 1))
