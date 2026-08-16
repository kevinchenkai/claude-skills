#!/usr/bin/env python3
"""把本地 Markdown 灌进一个新建的 WPS 智能文档（otl），并验证内容真的到位。

用法:
    python3 airpage_put.py <parent-folder-id> <标题> <本地.md> [--drive 6lABZaR]

为什么要有这个脚本：建档 → convert → create 三步都要 base64 套 JSON，
手写极易出错；而且必须用 blocks 查询验收（markdown 抽取会丢表格，
照它核对会误判成失败并重复插入）。这里把整条链和验收一起固化。
"""
import base64, json, subprocess, sys, argparse

def cli(*args, stdin=None):
    r = subprocess.run(["wps365-cli", *args], capture_output=True, text=True, input=stdin)
    if r.returncode != 0 and not r.stdout.strip():
        sys.exit(f"命令失败: {' '.join(args)}\n{r.stderr.strip()}")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        # 错命令会退回打印帮助且 exit 0 —— 必须当失败处理
        sys.exit(f"未拿到 JSON（多半是命令名或参数错了）: {' '.join(args)}\n{r.stdout[:300]}")

def b64(obj):
    return base64.b64encode(json.dumps(obj, ensure_ascii=False).encode()).decode()

def unb64(s):
    return json.loads(base64.b64decode(s))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parent"); ap.add_argument("title"); ap.add_argument("md")
    ap.add_argument("--drive", default="6lABZaR")
    a = ap.parse_args()

    name = a.title if a.title.endswith(".otl") else a.title + ".otl"  # 带点的名字必须显式补 .otl
    content = open(a.md, encoding="utf8").read()

    d = cli("api", "post", "/v7/airpage/files", "--data", json.dumps({
        "drive_id": a.drive, "parent_id": a.parent, "name": name,
        "template_id": "", "on_name_conflict": "rename"}, ensure_ascii=False), "-o", "json")["data"]
    fid, url = d["id"], d["link_url"]
    if d["name"] != name:
        print(f"⚠️  重名被静默改成 {d['name']}（原名已存在）—— 如不需要请删掉这份")

    blocks = unb64(cli("api", "post", f"/v7/airpage/{fid}/blocks/convert",
                       "--data", json.dumps({"arg": b64({"format": "markdown", "content": content})}),
                       "-o", "json")["data"]["result"])["blocks"]

    rc = cli("api", "post", f"/v7/airpage/{fid}/blocks/create",
             "--data", json.dumps({"arg": b64({"blockId": "doc", "index": 1000000000, "content": blocks})}),
             "-o", "json")["code"]

    # 验收：code:0 不算数，必须回读真实结构（且不能用 markdown 抽取，它丢表格）
    got = unb64(cli("api", "post", f"/v7/airpage/{fid}/blocks",
                    "--data", json.dumps({"arg": b64({"blockId": "doc"})}), "-o", "json")["data"]["result"])
    top = got["blocks"][0]["content"]
    kinds = {}
    for b in top:
        kinds[b.get("type")] = kinds.get(b.get("type"), 0) + 1

    print(f"送入 {len(blocks)} block / 文档实有 {len(top)} block  {kinds}")
    print(f"表格: 送入 {sum(1 for b in blocks if b.get('type')=='table')} / 实有 {kinds.get('table',0)}")
    print(f"✅ {d['name']}\n   {url}")
    if kinds.get("table", 0) < sum(1 for b in blocks if b.get("type") == "table"):
        sys.exit("❌ 表格数量对不上，请人工核对（不要盲目重插，会插出重复内容）")

main()
