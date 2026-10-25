"""下载进度（只看本次运行）：最近一次 RUN_START 之后的日志 + 本地目录统计 + tmux 是否在。
  python3 status.py --log ~/bpcs-logs/x.log --saveto /data/media [--session ck-bpcs-x] [--json]
完成的判据是本次运行的 RUN_DONE（不会被日志里更早的完成标记骗）；字节数用 Python 累加（不用 awk，避免大数变科学计数法）。
"""
import argparse, json, os, re, subprocess
from collections import deque

ap = argparse.ArgumentParser()
ap.add_argument("--log", required=True); ap.add_argument("--saveto", required=True)
ap.add_argument("--session"); ap.add_argument("--json", action="store_true")
a = ap.parse_args()
log, saveto = os.path.expanduser(a.log), os.path.expanduser(a.saveto)
# 日志会长期追加且进度条被转成逐行文本；只累计最新一次运行的统计，不把进度行保存在内存。
run = None; dirs = []; done = []; bad_rc = []; finished = False; ok_files = 0; error_count = 0
errs = deque(maxlen=5)
start_re = re.compile(r"^DIR_START\s+\S+\s+(.*?)\s+\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")
if os.path.exists(log):
    with open(log, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line.startswith("RUN_START "):
                run = line.split()[1]
                dirs = []; done = []; bad_rc = []; finished = False; ok_files = 0; error_count = 0; errs.clear()
                continue
            if not run:
                continue
            if m := start_re.match(line): dirs.append(m.group(1))
            if line.startswith("DIR_DONE "):
                done.append(line)
                if not re.search(r" rc=0 ", line): bad_rc.append(line)
            if line.startswith("RUN_DONE "): finished = True
            if "下载完成" in line: ok_files += 1
            if re.search(r"错误|失败|error", line, re.IGNORECASE) and "跳过文件有效性检验" not in line:
                error_count += 1; errs.append(line.strip())
tot, nfile, marks = 0, 0, 0
for d in dirs:
    p = os.path.join(saveto, os.path.basename(d.rstrip("/")))   # 目录：saveto 下建同名子目录；单个文件：直接放在 saveto 下
    if os.path.isfile(p):
        tot += os.path.getsize(p); nfile += 1; continue
    for root, _, fs in os.walk(p):
        for f in fs:
            fp = os.path.join(root, f)
            if "downloading" in f:   # BaiduPCS-Go 的未完成标记
                marks += 1; continue
            try:
                tot += os.path.getsize(fp); nfile += 1
            except OSError:
                pass
alive = None
if a.session:
    alive = subprocess.run(["tmux", "has-session", "-t", a.session], capture_output=True).returncode == 0
res = {"run": run, "dirs_total": len(dirs), "dirs_done": len(done), "dirs_bad_rc": bad_rc, "finished": finished,
       "tmux_alive": alive, "files_reported_done": ok_files, "local_files": nfile, "local_bytes": tot,
       "local_gib": round(tot / 2**30, 2), "downloading_markers": marks, "error_count": error_count, "error_lines": list(errs),
       "current": dirs[len(done)] if len(done) < len(dirs) else None}
if a.json:
    print(json.dumps(res, ensure_ascii=False, indent=1))
else:
    if not run:
        state = "未找到运行记录"
    elif finished and bad_rc:
        state = "完成但有失败"
    elif finished:
        state = "完成"
    else:
        state = "进行中" if alive or alive is None else "tmux 已退出但未见 RUN_DONE（异常结束）"
    print(f"[{state}] run={run} 目录 {len(done)}/{len(dirs)} 当前={res['current']} 本地 {nfile} 个文件 {res['local_gib']} GiB "
          f"未完成标记 {marks} 报完成 {ok_files} rc≠0 {len(bad_rc)} 错误行 {error_count}")
    for e in list(errs)[-3:]:
        print("  ", e[:200])
