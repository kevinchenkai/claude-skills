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

含本地图片、长 prompt、多张表格的报告改用富媒体 publisher：

```bash
python3 scripts/airpage_publish.py <folder-id> "模型效果对比报告" ./report.md \
  --drive 6lABZaR --on-name-conflict fail --result ./publish-result.json
```

它不是简单地把 Markdown 图片占位块插进去，而是先上传原生附件、绑定
`picture.attrs.sourceKey`，再回查 picture blocks 与 `export_to_json.attachment_list` 是否闭合。
协议细节见 [`airpage-rich-media.md`](airpage-rich-media.md)。

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

CLI 没有 upload 精装命令（上游 [issue #25](https://github.com/wps365-open/cli/issues/25)
已提但未实现），要手写三步协议。直接用脚本：

```bash
python3 scripts/drive_upload.py <drive-id> <parent-folder-id> ./报表.xlsx
```

实跑输出（自动校验体积和服务端 sha1）：

```
✅ 报表.xlsx  (102700 bytes)
   id=tqyLiiJuk9MD5uaVfqqZ1xnaWqd4uVq17  https://www.kdocs.cn/l/cv6fcQo73r0s
   体积: 一致 | 服务端 sha1: 一致
```

🔴 **如果你自己手写，`request_upload` 公网必须同时给 `hashes`（md5 + sha256 两种都要）
和 `upload_scene:"normal_upload"`**，少一个就报 `400000004 请求参数不支持` ——
这个报错**看着像接口没开放，其实只是参数不全**。两个 `api post` 还要显式
`--token-type delegated`。

🔴 **`on_name_conflict` 只能给 `rename` 或 `overwrite`** —— spec 枚举里的
`fail` / `replace` 会被上传端点拒掉（同样报 `400000004`）。脚本已挡掉非法值。

> 自己的盘和共享盘都实测通过；上传后用**服务端返回的 sha1**（不是 md5）验完整性。

> `.md` 想要**可编辑的智能文档**走 Demo 4；想**原样存档**就当二进制传。

---

## Demo 8：把别人共享给你的文档同步一份到自己的目录

```text
用 wps365-cli，把这份文档同步到 <目录>：<kdocs 链接>
```

skill 会用链接里的 id 定位到源文档，然后**读它的 blocks 原样插进新文档** ——
表格和图片都能保住。

🔴 **不要用 markdown 中转**（`file-content get` 丢表格，图片也带不过来），
也**不要指望 `batch-copy`**：从别人的共享盘往外复制会**静默失败** ——
返回 `code:0` + `task_id`，但目标目录什么都不会出现（换目标盘复现；
从自己盘内复制则立刻成功）。判成功必须回查目标目录。

实测：380KB 文档 225 个 block（56 标题 / 7 表格 / 4 图片）切成 11 块插入，
标题 56/56 逐条一致，表格 7/7、图片 4/4 齐全。

⚠️ **批注不会跟过来**。源文档里的评论锚点（`rangeMark`）接口明确拒绝插入
（`rangeMark can only be used in update_content`），只能丢掉。
它不含正文，内容不受影响，但交付时要跟用户说一声。

---

## Demo 9：把已有智能文档中的 `**文字**` 变成原生加粗

```text
把这份智能文档中类似 **文字** 的内容统一变成加粗：<kdocs 链接>
```

先用链接或精确名称搜索，拿到**真实 file id**（分享链接短码不能直接代替）。默认命令只预检：

```bash
python3 scripts/airpage_fix_markdown_bold.py <file-id>
```

输出会列出 `target_blocks`、`bold_pairs` 和被忽略的非段落标记。确认后执行：

```bash
python3 scripts/airpage_fix_markdown_bold.py <file-id> --apply \
  --backup-dir /tmp/wps-bold-backup
```

脚本会把每对标记拆成原生 text runs，并设置 `attrs.bold:true`；表格、图片、附件和其他结构不重建。
遇到批注锚点、未配对标记或协作者并发改动会停止。若上次恰好中断在“新块已建、旧块未删”，
检查后用 `--apply --resume-partial`，不要直接重复插入。

## 几句话总结怎么跟它说

| 你想干的 | 就这么说 |
|---|---|
| 找文档 | 「找一下叫 <关键词> 的文档在哪」 |
| 读 / 导出 md | 「把「<文档名>」导出成 markdown」 |
| 导出 docx | 「把「<文档名>」导出成 docx」 |
| 建智能文档 | 「把这份内容建成智能文档放到 <目录>」 |
| 整理目录 | 「整理 <目录名>，先给我方案」 |
| 批量搬家 | 「把 <目录> 里的 pptx 都挪到 附件/ 下」 |
| 上传本地文件 | 「把 <本地路径> 传到 <目录>」 |
| 同步别人的文档 | 「把这份文档同步到 <目录>：<链接>」 |
| 修复字面 Markdown 粗体 | 「把这份智能文档里的 `**文字**` 统一变成加粗」 |

**要它先给方案**：加一句「先给我方案，确认之后再执行」。
**要它别啰嗦直接干**：加一句「不用确认，直接执行」。
