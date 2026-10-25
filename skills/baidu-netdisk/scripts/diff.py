"""网盘目录 vs 本地目录：列出网盘有、本地没有（该补下的）和本地多出的文件。
  python3 diff.py "/00.Movies/A" /data/media/A [--recursive] [--sizes] [--ext mp4,mkv] [--json]
--sizes 对两边都有的文件用 meta 取精确字节数比大小（每个文件一次请求，文件多时慢）。
"""
import argparse, json, os, re, subprocess

ap = argparse.ArgumentParser()
ap.add_argument("remote"); ap.add_argument("local")
ap.add_argument("--recursive", action="store_true"); ap.add_argument("--sizes", action="store_true")
ap.add_argument("--ext", default=""); ap.add_argument("--json", action="store_true")
a = ap.parse_args()
BIN = os.environ.get("BPCS_BIN", os.path.expanduser("~/.local/bin/BaiduPCS-Go"))
if not os.path.isfile(BIN) or not os.access(BIN, os.X_OK):
    raise SystemExit(f"找不到可执行的 BaiduPCS-Go: {BIN}")
LINE = re.compile(r"^\s*\d+\s+(\S+)\s+\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\s+(.+?)\s*$")
exts = tuple("." + e.strip().lstrip(".").lower() for e in a.ext.split(",") if e.strip())

def ls(path):
    r = subprocess.run([BIN, "ls", path], capture_output=True, text=True)
    if r.returncode != 0 or "错误" in r.stdout[:200]:
        raise SystemExit(f"ls 失败 {path}: {(r.stdout + r.stderr)[:300]}")
    files, dirs = [], []
    for l in r.stdout.splitlines():
        m = LINE.match(l)
        if m:
            (dirs if m.group(2).endswith("/") else files).append(m.group(2).rstrip("/"))
    return files, dirs

def walk(path, rel=""):
    files, dirs = ls(path)
    out = [os.path.join(rel, f) for f in files]
    if a.recursive:
        for d in dirs:
            child = f"/{d}" if path == "/" else f"{path}/{d}"
            out += walk(child, os.path.join(rel, d))
    return out

remote = a.remote.rstrip("/") or "/"; local = os.path.expanduser(a.local)
rfiles = set(walk(remote))
lfiles = set()
if os.path.isdir(local):
    for root, _, fs in os.walk(local):
        for f in fs:
            rel = os.path.relpath(os.path.join(root, f), local)
            if rel != "MD5SUMS.txt" and "downloading" not in f and (a.recursive or os.sep not in rel):
                lfiles.add(rel)
if exts:
    rfiles = {f for f in rfiles if f.lower().endswith(exts)}; lfiles = {f for f in lfiles if f.lower().endswith(exts)}
res = {"remote": remote, "local": local, "remote_n": len(rfiles), "local_n": len(lfiles),
       "missing_local": sorted(rfiles - lfiles), "extra_local": sorted(lfiles - rfiles),
       "size_mismatch": [], "meta_errors": []}
if a.sizes:
    for f in sorted(rfiles & lfiles):
        remote_file = f"/{f}" if remote == "/" else f"{remote}/{f}"
        proc = subprocess.run([BIN, "meta", remote_file], capture_output=True, text=True)
        out = proc.stdout
        m = re.search(r"文件大小\s+(\d+),", out)
        if proc.returncode != 0 or not m:
            res["meta_errors"].append({"file": f, "error": (proc.stdout + proc.stderr).strip()[:300] or "无法解析文件大小"})
        elif int(m.group(1)) != os.path.getsize(os.path.join(local, f)):
            res["size_mismatch"].append({"file": f, "remote": int(m.group(1)), "local": os.path.getsize(os.path.join(local, f))})
if a.json:
    print(json.dumps(res, ensure_ascii=False, indent=1))
else:
    print(f"网盘 {res['remote_n']} 个 | 本地 {res['local_n']}{'' if os.path.isdir(local) else '（目录不存在）'} | "
          f"需下载 {len(res['missing_local'])} | 本地多出 {len(res['extra_local'])}" +
          (f" | 大小不符 {len(res['size_mismatch'])} | meta 失败 {len(res['meta_errors'])}" if a.sizes else ""))
    for k in ("missing_local", "extra_local"):
        for f in res[k][:10]: print(f"  {k}: {f}")
    for item in res["meta_errors"][:10]: print(f"  meta_error: {item['file']}: {item['error']}")
raise SystemExit(1 if res["meta_errors"] else 0)
