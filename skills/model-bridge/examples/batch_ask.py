#!/usr/bin/env python3
"""批量评审/标注：把一批独立样本分批交给一个或多个目标模型，收集 JSON 回答（经 call.py，认证与计费规则同 SKILL.md）。

用法：
  batch_ask.py --items items.jsonl --template template.txt \
      --models codex:gpt-6-luna:medium,agy:gemini-3.8-flash-medium: \
      --batch 10 --concurrency 4 --timeout 1200 --out /absolute/new_dir [--schema schema.json]
items.jsonl：每行 {"id": "S001", "text": "…一个样本的完整描述…"}；
template.txt：含占位符 {items}（会被替换成本批样本，按 id 编号）和 {ids}（逗号分隔的本批 id），
              并要求模型"只输出一个 JSON 数组，每个元素含 id"；
--models：逗号分隔的 provider:model:effort（effort 可空；cursor/agy 的 effort 在模型 ID 里）。
--schema：只对 claude/codex 生效（原生结构化输出）；顶层须为 {"items": [ {...含 id...} ]} 形状的 object。
          其它目标仍按模板要求输出 JSON 数组。
输出：<out>/<provider>_<model>/bNN-aK/（第 K 次尝试的 call.py 记录目录）与 <out>/<provider>_<model>.json（id → 回答）。
一批只有在 status=ok 且返回的 id 与本批完全一致（不缺、不多、不重复）时才算完成；否则重试，最多 1+--retries 次。
中断后用同样参数重跑：已完成的批跳过，其余批新开一次尝试（旧尝试目录保留作证据）。
"""
import argparse, concurrent.futures as cf, json, os, re, subprocess, sys
CALL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "call.py")


def parse_answers(res, ids):
    """返回 (id → 回答, 问题说明)；缺 id、多 id、重复 id 都算失败，不悄悄丢样本。"""
    if res.get("status") != "ok":
        return None, "status=%s：%s" % (res.get("status"), (res.get("error") or "")[:200])
    data = res.get("json")
    if isinstance(data, dict):
        data = data.get("items")
    if data is None:
        m = re.search(r"\[.*\]", res.get("text") or "", re.S)
        try:
            data = json.loads(m.group(0)) if m else None
        except ValueError:
            data = None
    if not isinstance(data, list):
        return None, "回答里没有可解析的 JSON 数组"
    got = {}
    for x in data:
        if not isinstance(x, dict) or "id" not in x:
            return None, "有元素不是含 id 的对象"
        key = str(x["id"])
        if key in got:
            return None, "id 重复：" + key
        got[key] = x
    missing = [i for i in ids if i not in got]
    extra = sorted(set(got) - set(ids))
    if missing or extra:
        return None, "缺 %s；多 %s" % (missing, extra)
    return got, None


def attempts(out, tag, bi):
    d = os.path.join(out, tag)
    names = os.listdir(d) if os.path.isdir(d) else []
    found = sorted((int(m.group(1)), n) for n in names if (m := re.fullmatch(r"b%02d-a(\d+)" % bi, n)))
    return [os.path.join(d, n) for _, n in found]


def done_answers(out, tag, bi, ids):
    for d in attempts(out, tag, bi):
        rj = os.path.join(d, "result.json")
        if os.path.exists(rj):
            got, _ = parse_answers(json.load(open(rj, encoding="utf-8")), ids)
            if got is not None:
                return got
    return None


def run_batch(spec, bi, batch, template, out, timeout, retries, schema, dry):
    prov, model, effort = (spec.split(":") + ["", ""])[:3]
    tag = f"{prov}_{model}".replace("/", "_")
    ids = [x["id"] for x in batch]
    if done_answers(out, tag, bi, ids) is not None:
        return spec, bi, "cached"
    os.makedirs(os.path.join(out, tag), exist_ok=True)
    prompt = template.replace("{items}", "\n\n".join(f"[{x['id']}] {x['text']}" for x in batch)).replace("{ids}", ",".join(ids))
    problem = None
    for _ in range(1 + retries):
        d = os.path.join(out, tag, "b%02d-a%d" % (bi, len(attempts(out, tag, bi)) + 1))
        pf = d + ".prompt.txt"
        open(pf, "w", encoding="utf-8").write(prompt)
        cmd = [sys.executable, CALL, "run", prov, "--task", "label", "--model", model, "--prompt-file", pf,
               "--output-dir", d, "--format", "json", "--timeout", str(timeout)]
        if effort:
            cmd += ["--effort", effort]
        if schema and prov in ("claude", "codex"):
            cmd += ["--schema", schema]
        if dry:
            cmd.append("--dry-run")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 300)
        if dry:
            return spec, bi, r.returncode
        rj = os.path.join(d, "result.json")
        if not os.path.exists(rj):
            problem = "没有 result.json（退出码 %s）：%s" % (r.returncode, r.stderr.strip()[-200:])
            continue
        got, problem = parse_answers(json.load(open(rj, encoding="utf-8")), ids)
        if got is not None:
            return spec, bi, "ok"
    return spec, bi, "failed: " + str(problem)


def collect(out, spec, batches):
    prov, model = spec.split(":")[:2]
    tag = f"{prov}_{model}".replace("/", "_")
    ans, failed = {}, []
    for bi, batch in enumerate(batches):
        got = done_answers(out, tag, bi, [x["id"] for x in batch])
        if got is None:
            failed.append(bi)
        else:
            ans.update(got)
    json.dump(ans, open(os.path.join(out, tag + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return tag, len(ans), failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True); ap.add_argument("--template", required=True)
    ap.add_argument("--models", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--batch", type=int, default=10); ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=1200); ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--schema", help="JSON Schema 文件，仅 claude/codex 使用"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    items = [json.loads(l) for l in open(a.items, encoding="utf-8") if l.strip()]
    ids = [str(x["id"]) for x in items]
    if len(set(ids)) != len(ids):
        sys.exit("items 里有重复 id")
    for x in items:
        x["id"] = str(x["id"])
    template = open(a.template, encoding="utf-8").read()
    schema = os.path.abspath(a.schema) if a.schema else None
    batches = [items[i:i + a.batch] for i in range(0, len(items), a.batch)]
    specs = a.models.split(",")
    os.makedirs(a.out, exist_ok=True)
    jobs = [(s, bi) for s in specs for bi in range(len(batches))]
    with cf.ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        for res in ex.map(lambda j: run_batch(j[0], j[1], batches[j[1]], template, a.out, a.timeout, a.retries, schema, a.dry_run), jobs):
            print(res, flush=True)
    if a.dry_run:
        return 0
    incomplete = False
    for s in specs:
        tag, n, failed = collect(a.out, s, batches)
        print("collected", tag, "%d/%d" % (n, len(items)), "未完成的批：%s" % failed if failed else "", flush=True)
        incomplete = incomplete or bool(failed)
    return 1 if incomplete else 0


if __name__ == "__main__":
    sys.exit(main())
