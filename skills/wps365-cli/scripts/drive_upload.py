#!/usr/bin/env python3
"""把本地文件上传到 WPS 云盘（xlsx / pptx / pdf / mp4 …），并校验完整性。

用法:
    python3 drive_upload.py <drive-id> <parent-folder-id> <本地文件> [--name 云上文件名]
                            [--on-name-conflict rename|fail|overwrite|replace]

CLI 没有 upload 精装命令（截至 v0.3.2），必须手写三步协议。这里把三步和校验固化：
  1. request_upload  → 拿 upload_id + store_request.url
  2. PUT 实体到该 url（必须带 delegated token）
  3. commit_upload   → 落盘，返回文件 id

🔴 第 1 步公网必须同时给 hashes(md5+sha256) 和 upload_scene:"normal_upload"，
   少任何一个都报 400000004「请求参数不支持」——那个报错看起来像"接口没开放"，
   其实只是参数不全。两个 api post 还必须显式 --token-type delegated，否则走 app 身份 403。
   （来源：上游 issue #25，本机已复现验证。）

🔴 on_name_conflict 只能是 rename / overwrite。spec 的枚举里还有 fail / replace，
   但上传端点实测拒绝它们（同样报 400000004）——同一个枚举在不同端点上可用值不同。
"""
import argparse, hashlib, json, os, subprocess, sys


def cli(*args):
    r = subprocess.run(["wps365-cli", *args], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        sys.exit(f"未拿到 JSON（命令名/参数可能有误）: {' '.join(args)}\n{r.stdout[:200]}{r.stderr[:200]}")
    if d.get("code") not in (0, None):
        sys.exit(f"接口报错: {json.dumps(d, ensure_ascii=False)[:300]}")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive"); ap.add_argument("parent"); ap.add_argument("path")
    # 🔴 上传端点只认 rename / overwrite；spec 枚举里的 fail / replace 会报 400000004
    ap.add_argument("--name")
    ap.add_argument("--on-name-conflict", default="rename", choices=["rename", "overwrite"])
    a = ap.parse_args()

    if not os.path.isfile(a.path):
        sys.exit(f"本地文件不存在: {a.path}")
    blob = open(a.path, "rb").read()
    name = a.name or os.path.basename(a.path)
    sha256, md5 = hashlib.sha256(blob).hexdigest(), hashlib.md5(blob).hexdigest()
    sha1 = hashlib.sha1(blob).hexdigest()   # 服务端 commit 返回的是 sha1，用它验完整性

    body = {"name": name, "size": len(blob), "on_name_conflict": a.on_name_conflict,
            "upload_scene": "normal_upload",           # 🔴 必须
            "hashes": [{"type": "sha256", "sum": sha256},
                       {"type": "md5", "sum": md5}]}   # 🔴 必须，且要两种
    d = cli("api", "post", f"/v7/drives/{a.drive}/files/{a.parent}/request_upload",
            "--token-type", "delegated", "--data", json.dumps(body, ensure_ascii=False), "-o", "json")["data"]

    token = subprocess.run(["wps365-cli", "auth", "token"], capture_output=True, text=True).stdout.strip()
    put = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                          "-X", d["store_request"]["method"], "--data-binary", "@" + a.path,
                          "-H", f"Authorization: Bearer {token}", d["store_request"]["url"]],
                         capture_output=True, text=True).stdout.strip()
    if put != "200":
        sys.exit(f"❌ 实体 PUT 失败 http={put}（403 多半是 token 没带上）")

    f = cli("api", "post", f"/v7/drives/{a.drive}/files/{a.parent}/commit_upload",
            "--token-type", "delegated", "--data", json.dumps({"upload_id": d["upload_id"]}), "-o", "json")["data"]

    ok_size = f.get("size") == len(blob)
    got = (f.get("hash") or {}).get("sum", "")
    ok_hash = got.lower() == sha1            # 服务端给的是 sha1
    print(f"✅ {f.get('name')}  ({len(blob)} bytes)")
    print(f"   id={f.get('id')}  {f.get('link_url','')}")
    print(f"   体积: {'一致' if ok_size else '❌ 不一致 云端=%s' % f.get('size')}"
          f" | 服务端 sha1: {'一致' if ok_hash else '❌ 不一致 云端=%s' % got}")
    if f.get("name") != name:
        print(f"   ⚠️  重名被改成 {f.get('name')}（原名已存在）")
    if not (ok_size and ok_hash):
        sys.exit("❌ 完整性校验未通过，请人工核对")


main()
