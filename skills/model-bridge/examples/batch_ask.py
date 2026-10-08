#!/usr/bin/env python3
"""批量评审/标注：把一批独立样本分批交给一个或多个目标模型，收集 JSON 回答（经 call.py，认证与计费规则同 SKILL.md）。

用法：
  batch_ask.py --items items.jsonl --template template.txt \
      --models codex:gpt-6-luna:medium,agy:gemini-3.8-flash-medium: \
      --batch 10 --concurrency 4 --timeout 1200 --out /absolute/new_dir
items.jsonl：每行 {"id": "S001", "text": "…一个样本的完整描述…"}；
template.txt：含占位符 {items}（会被替换成本批样本，按 id 编号）和 {ids}（逗号分隔的本批 id），
              并要求模型"只输出一个 JSON 数组，每个元素含 id"；
--models：逗号分隔的 provider:model:effort（effort 可空；cursor/agy 的 effort 在模型 ID 里）。
输出：<out>/<provider>_<model>/bNN/（call.py 的记录目录）与 <out>/<provider>_<model>.json（id → 解析后的回答）。
注意：--out 必须是尚不存在的目录；中断后重跑会跳过 status=ok 的批、清掉并重跑其它批（timeout 也会留下 result.json）。
"""
import argparse, concurrent.futures as cf, json, os, re, shutil, subprocess, sys
CALL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "call.py")


def run_batch(spec, bi, batch, template, out, timeout, dry):
    prov, model, effort = (spec.split(":") + ["", ""])[:3]
    tag = f"{prov}_{model}".replace("/", "_")
    d = os.path.join(out, tag, f"b{bi:02d}")
    rj = os.path.join(d, "result.json")
    if os.path.exists(rj) and json.load(open(rj)).get("status") == "ok":
        return spec, bi, "cached"
    if os.path.isdir(d):
        shutil.rmtree(d)                       # 只清本脚本自己建的残目录
    os.makedirs(os.path.dirname(d), exist_ok=True)
    prompt = template.replace("{items}", "\n\n".join(f"[{x['id']}] {x['text']}" for x in batch)).replace("{ids}", ",".join(x["id"] for x in batch))
    pf = d + ".prompt.txt"
    open(pf, "w", encoding="utf-8").write(prompt)
    cmd = [sys.executable, CALL, "run", prov, "--task", "ask", "--model", model, "--prompt-file", pf, "--output-dir", d, "--format", "text", "--timeout", str(timeout)]
    if effort:
        cmd += ["--effort", effort]
    if dry:
        cmd.append("--dry-run")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 300)
    return spec, bi, r.returncode


def collect(out, spec):
    prov, model = spec.split(":")[:2]
    tag = f"{prov}_{model}".replace("/", "_")
    ans = {}
    for name in sorted(os.listdir(os.path.join(out, tag))):
        rj = os.path.join(out, tag, name, "result.json")
        if not os.path.exists(rj):
            continue
        res = json.load(open(rj))
        m = re.search(r"\[.*\]", res.get("text") or "", re.S)
        if res.get("status") != "ok" or not m:
            continue
        try:
            for x in json.loads(m.group(0)):
                ans[str(x["id"])] = x
        except (ValueError, KeyError, TypeError):
            pass
    json.dump(ans, open(os.path.join(out, tag + ".json"), "w"), ensure_ascii=False, indent=1)
    return tag, len(ans)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True); ap.add_argument("--template", required=True)
    ap.add_argument("--models", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--batch", type=int, default=10); ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=1200); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    items = [json.loads(l) for l in open(a.items, encoding="utf-8") if l.strip()]
    template = open(a.template, encoding="utf-8").read()
    batches = [items[i:i + a.batch] for i in range(0, len(items), a.batch)]
    specs = a.models.split(",")
    os.makedirs(a.out, exist_ok=False) if not os.path.exists(a.out) else None
    jobs = [(s, bi) for s in specs for bi in range(len(batches))]
    with cf.ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        for res in ex.map(lambda j: run_batch(j[0], j[1], batches[j[1]], template, a.out, a.timeout, a.dry_run), jobs):
            print(res, flush=True)
    if not a.dry_run:
        for s in specs:
            print("collected", *collect(a.out, s))


if __name__ == "__main__":
    main()
