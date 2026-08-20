# wps365-cli 使用案例

**给用户的用法：直接说人话，不用给命令、不用先查 file_id。** 下面每个 Demo 的
「你就这么说」可以原样复制，尖括号换成自己的内容。

命令块是 skill 内部实际会跑的东西，贴出来是为了让你知道它在干什么、
以及你想自己跑时该怎么写。

---

## Demo 1：找一份文档在哪

```text
用 wps365-cli，找一下叫「研学」的文档都在哪。
```

**为什么值得单独走一步**：`search` 是**全公司跨盘**的，同名/近名文档很常见。
skill 会把 `drive_id` 和 `path` 一起列出来让你确认是哪一份。

```bash
wps365-cli drive file search --type all --keyword "研学" --page-size 5 -o json \
  --jq '.data.items[] | {name:.file.name, drive:.file.drive_id, path:.file_src.path}'
```

实跑结果（注意最后一条在**另一个盘** `3VWLEdA`，是别人共享给我的）：

```
{"drive":"6lABZaR","name":"珠海WPS研学分享.otl","path":"我的企业文档/01.技术交流文档/星云训练营 2025"}
{"drive":"6lABZaR","name":"美国研学笔记－2025.otl","path":"我的企业文档/01.技术交流文档/05.学习笔记"}
{"drive":"3VWLEdA","name":"硅谷研学二期笔记汇总（春季GDC+GTC）.otl","path":"美国研学/研学二期-2603"}
```

> 命中多条时 skill 会停下来问你要哪一份，不会自己挑。

---

## Demo 2：读一份文档 / 导出成 md

```text
用 wps365-cli，把「美国研学笔记－2025」导出成 markdown 存到本地。
```

```bash
wps365-cli drive file-content get <drive-id> <file-id> --format markdown -o json --jq '.data.markdown'
```

🔴 **含表格的文档会缺表**。实测那份治理报告有 2 个表格，导出的 .md 里
一个 `|---|` 都没有。所以：

- 只是想读内容 → .md 够用；
- **要完整交付 → 让它同时给 docx**（Demo 3），或说明「表格以原文为准」。

skill 遇到含表文档会主动提醒你这件事。

---

## Demo 3：导出成 docx（表格完整）

```text
用 wps365-cli，把「<文档名>」导出成 docx。
```

官方接口可用，但**必须轮询**：第一次调用几乎必然返回 `Building` + 空 url，
重发一次才 `Completed`。只发一次会误判成"导出失败"。

```bash
FID=<file-id>
V=$(wps365-cli api get "/v7/airpage/$FID" -o json --jq '.data.version')
for i in $(seq 1 10); do
  wps365-cli api post "/v7/airpage/$FID/export_to_docx" \
    --data "{\"attrs\":\"\",\"version\":\"$V\",\"ai_check\":false}" -o json > exp.json
  read S U < <(python3 -c "import json;d=json.load(open('exp.json'))['data'];print(d['status'],len(d['url']))")
  [ "$S" = "Completed" ] && [ "$U" != "0" ] && break
  python3 -c "import time;time.sleep(2)"
done
URL=$(python3 -c "import json;print(json.load(open('exp.json'))['data']['url'])")  # 不能用 --jq，会毁掉签名
curl -sL "$URL" -o out.docx && file out.docx   # 必须是 Microsoft OOXML
```

---

## Demo 4：把本地 Markdown 变成智能文档

```text
用 wps365-cli，把这份内容建成智能文档，放到 00.个人文档 下面。

<直接粘贴你的 markdown>
```

或者已经有本地文件，直接用脚本（建档 → 转换 → 插入 → **验收**一条龙）：

```bash
python3 scripts/airpage_put.py <parent-folder-id> "周报-20260816" ./report.md
```

实跑输出：

```
送入 6 block / 文档实有 8 block  {'title': 1, 'paragraph': 4, 'heading': 2, 'table': 1}
表格: 送入 1 / 实有 1
✅ zz-script-demo.otl
   https://www.kdocs.cn/l/ci1xdRx4kwJh
```

脚本替你挡掉三个坑：名字带点必须补 `.otl`、重名会静默变 `(1).otl`、
以及**验收必须回读 blocks**（用 markdown 抽取核对会因为丢表格而误判成失败，
然后重复插入插出两份内容）。

**放到共享盘 / 团队盘**（不是自己的企业盘）：加 `--drive`，盘 id 从 `search` 结果里拿。

```bash
python3 scripts/airpage_put.py <folder-id> "标题" ./x.md --drive 1XQAjDl
```

实测在 `西山居AI项目/router`（别人共享给我的盘）下建 12KB、3 个表格的文档成功，
表格 3/3 全保留。⚠️ `drive list` **列不出共享盘**，别以为盘不存在。

🔴 **建完在网页打开，标题栏是灰色的 `Enter title` —— 这是正常的，不是插入失败。**
API 建的文档 title block 一定为空（`blocks/convert` 从不产出 `title` 类型，
`# 一级标题` 只会变成正文里的 `heading`）。**首次在网页打开时编辑器会自动用第一个 H1
补上标题，并把文件名一并改成它** —— 所以 md 开头记得写 `# 标题`。
⚠️ 副作用：文件名会被改掉，如果你靠 `00.` / `01.` 这类编号前缀排序，打开后要检查名字。

---

## Demo 5：整理一个目录

```text
用 wps365-cli，整理一下 01.技术交流文档。
```

**skill 会先给方案再动手**：递归清单 → 归位表 → 等你确认 → 建夹 + 搬家 → 回传最终树。
想跳过确认就明说「不用确认，直接执行」。

真实案例（本仓 2026-08-16 跑过）：`01.技术交流文档` 根目录散着 15 个文件，
沿用同级 `03.技术交流文档` 已有的编号体系建了 5 个子目录归位，
**39 个文件零丢失**，并产出一份治理报告文档。

要它先出方案不动手：

```text
用 wps365-cli，整理 01.技术交流文档，先给我方案，别动文件。
```

🔴 **`batch-move` 会重写 mtime 且不可恢复**——所有搬过的文件修改时间都变成搬家当天。
skill 会在动手前先存一份清单，报告里用原始日期。你如果自己搬，记得先存清单。

---

## Demo 6：动手前确认位置 / 出错了怎么办

```bash
# 一次拿到完整祖先链，写之前确认没搞错目录
wps365-cli drive file-path get <drive-id> <file-id> -o json --jq '[.data.paths[].name]|join(" / ")'
# → "01.技术交流文档 / 01.技术交流文档 治理报告.otl"

# 忘了 drive_id 就直接列
wps365-cli drive list --page-size 50 -o json --jq '.data.items[] | {id,name}'

# 批量搬/删之前先看请求长什么样（只打印不发送）
wps365-cli --dry-run drive file batch-move <drive> --file-ids id1,id2 \
  --dst-drive-id <drive> --dst-parent-id <folder>
```

**报「文件不存在」先别慌**：`400008009` 十有八九是 `drive_id` 配错了而不是文件没了。
拿正确的盘再打一次 `file-path get`，能出路径就说明文件好好的。

---

## Demo 7：上传本地文件（xlsx / pptx / pdf）

```text
用 wps365-cli，把 <本地路径> 传到 <目录>。
```

🔴 **当前传不了二进制文件** —— 官方 spec 有完整的三步上传，但实测
`request_upload` / `rapid_upload` / `create_multipart_upload_task` **全部被服务端拒绝**
（`400000004 请求参数不支持`）。已排除权限、共享盘、CLI 拼错三种可能：
所需 scope 已授权、打到自己的盘报一样的错、`--dry-run` 显示请求完全正确。
属于"spec 里有，但这个应用的档位没放开"。

**遇到这类需求直接走网页拖拽**（<https://www.kdocs.cn/>），skill 不会反复试端点。

> **例外：`.md` 不受此限**。用户给 `.md` 时走 Demo 4 建成智能文档，是通的。

---

## 几句话总结怎么跟它说

| 你想干的 | 就这么说 |
|---|---|
| 找文档 | 「找一下叫 <关键词> 的文档在哪」 |
| 读 / 导出 md | 「把「<文档名>」导出成 markdown」 |
| 导出 docx | 「把「<文档名>」导出成 docx」 |
| 建智能文档 | 「把这份内容建成智能文档放到 <目录>」 |
| 整理目录 | 「整理 <目录名>，先给我方案」 |
| 批量搬家 | 「把 <目录> 里的 pptx 都挪到 附件/ 下」 |

**要它先给方案**：加一句「先给我方案，确认之后再执行」。
**要它别啰嗦直接干**：加一句「不用确认，直接执行」。
