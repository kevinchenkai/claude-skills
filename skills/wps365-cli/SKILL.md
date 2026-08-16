---
name: wps365-cli
description: Operate WPS 365 via official wps365-cli for cloud docs, AirPage/智能文档, drive folders, search, export, and import. Use when the user mentions WPS、金山文档、kdocs、协作文档、智能文档、otl、wps365-cli, or asks to read/export/create/move/organize files under 我的企业文档.
---

# WPS 365 CLI

用本机 `wps365-cli` 操作金山协作 / 智能文档。不要改走浏览器 Cookie CLI，不要手写未验证的 OpenAPI。

二进制：`~/.local/bin/wps365-cli`（已在 PATH，v0.3.1）。默认盘：`我的企业文档`，`drive_id=6lABZaR`。

## 0. 先鉴权

```bash
wps365-cli user me -o json
```

**用 `user me` 判活，不要用 `auth status` 判活。** access token 只有 2 小时，
`auth status` 天天显示 `expired`，但 refresh token 有效期一年、CLI 会在下一次真实调用时
自动续期——照着 `status` 判会天天误报要重新登录。`user me` 返回 `code:0` 就一切正常。

只有 `user me` 真的失败时才看 `auth status --jq '.delegated'`，缺 scope 再补：

```bash
wps365-cli auth login --device --scopes "kso.user_base.read,kso.file.readwrite,kso.drive.readwrite,kso.airpage.readwrite"
```

## 1. 统一话术 → 动作

用户怎么说，就怎么做。先定位，再动手；目录治理先出方案，**确认后再搬文件**。

| 用户说 | 动作 |
|---|---|
| 读取 / 打开 / 看一下「文档名」 | `search` 定位 → `file-content get --format markdown` |
| 导出 .md | 同上，写入本地 `.md` |
| 导出 .docx | 官方 `export_to_docx` **可用**，见 §6；不要默认走本地转换 |
| 生成智能文档 / 放到某目录 | 在目标夹 `POST /v7/airpage/files` 建 otl → convert+insert markdown（§4） |
| 整理 / 治理某目录 | 先递归清单 + 归位方案；用户确认后再 create folder + batch-move |
| 授权某某读写 | `auth login --device --scopes` 补齐 scope |

## 2. 🔴 drive_id 必须跟着文件走

**这是本 skill 最容易犯的错。** `search` 是**全公司跨盘**搜索，实测一次 20 条命中
横跨 8 个 drive，只有 8 条在默认盘。**绝不能搜到 file_id 后套用 `6lABZaR`。**

drive_id 用错的报错是 `400008009 文件不存在`——**看起来像文件被删了，其实是盘搞错了**。
遇到「文件不存在」先怀疑 drive_id，不要回去跟用户说文件没了。

```bash
# 搜索结果里 file_id 和 drive_id 必须成对取出，一起往下传
wps365-cli drive files search --type all --keyword "文档名" --page-size 20 -o json \
  --jq '.data.items[] | {name:.file.name, drive:.file.drive_id, id:.file.id, path:.file_src.path, url:.file.link_url}'
```

别人共享盘里的文件可读可导出，但**不要动原件**（见 §8）。

## 3. 定位与读写

```bash
# 搜（--type all 必填，漏了直接报 missing required flag）
wps365-cli drive files search --type all --keyword "文档名" --page-size 20 -o json

# 列目录（根用 parent-id=0）
wps365-cli drive files list 6lABZaR <parent-id> --page-size 100 -o json --jq '.data.items[] | {id,name,type}'

# 抽正文（otl 用 markdown；失败再试 plain）
wps365-cli drive file-content get <drive-id> <file-id> --format markdown -o json --jq '.data.markdown'
```

列目录返回的是 **`data.items`**（不是 `data.files`），分页吃 `data.next_page_token`。
搜索结果每条是 `{file, file_src, highlights}`，正文字段在 `.file` 下面，`file_src.path` 给你所在目录。

常用一级目录（`6lABZaR`，`parent_id=0`，2026-08-16 实测有效）：

| 目录 | folder_id |
|---|---|
| 00.个人文档 | `PjbYGr3XS1MTyQEZNP3krxXm4WpQX68RX` |
| 01.个人项目文档 | `reJo7APBY1MjDDSMZ3anxx6g158Y1QcED` |
| 01.游戏AI业务 | `FFarzp4xFrMs7HqCH3P7xxYPiT2ejBYag` |
| 02.重要纪要 | `hKaZkYmBY1MTMgG2MY2nxxqBAyiH8mvhE` |
| 03.技术交流文档 | `zBEGJgbUw1MCVfTSv3BW1xtWVvsjR99LX` |
| 01.技术交流文档 | `jSLJUdhx3rMyena6D8h3rxHLun5AdZTZ1` |

⚠️ **注意最后两行：`01.` 与 `03.技术交流文档` 是两个不同目录**，名字几乎一样但内容零重叠。
根目录还并存 `01.技术文档`。**用户说「技术文档」时必须先确认是哪一个**，别按名字猜。

ID 可能变；对不上就重新 search。上表 drive_id / folder_id 来自作者自己的企业盘，
**换环境必须整表替换**——没有 token 这些 ID 没有任何用处。

## 4. 新建智能文档并灌 Markdown

1. 建空 otl（`template_id` 用空字符串）。**返回值里就有 `link_url`，直接拿去回给用户，不用另外拼链接**：

```bash
wps365-cli api post "/v7/airpage/files" --data '{"drive_id":"6lABZaR","parent_id":"<folder-id>","name":"标题","template_id":"","on_name_conflict":"rename"}' -o json
# → data.id / data.link_url
```

2. `POST /v7/airpage/{file_id}/blocks/convert`，body `{"arg": base64(json({"format":"markdown","content":"..."}))}`。
3. base64-decode `data.result` → `{"attachments":..., "blocks":[...]}`，取 `blocks`。
4. `POST /v7/airpage/{file_id}/blocks/create`，`arg` = base64 of
   `{"blockId":"doc","index":1000000000,"content":<blocks>}`。

长文按 `##` 切块，每块 <18KB，顺序 insert 到末尾。

🔴 **`name` 必须自带 `.otl` 后缀**。接口按最后一个 `.` 切扩展名，所以本仓
`00.` / `01.` 这种编号前缀会被当成扩展名：`"00.目录治理报告"` 直接报
`400000002 invalid file extension: .目录治理报告, expected: .otl`。写成
`"00.目录治理报告.otl"` 就正常。**凡是名字里带点的都要显式补 `.otl`。**

`drive files create --file-type otl` 会 400（`400000004 请求参数不支持`），不要用；
otl 只能经 `/v7/airpage/files` 建。

## 5. 🔴 验证插入结果：不要用 markdown 抽取

**`file-content get --format markdown` 会静默丢表格**（`plain` 同样丢）。
实测：插入含表格的 markdown，convert 正确产出 `table` block、create 返回 `code:0`、
文档里表格确实存在——但 markdown 抽取的结果里完全没有表格。

**照着 markdown 抽取去"核对"，会误判成插入失败，然后重复插入插出重复内容。**（本 skill 标定时就这么踩过。）

要核对插入结果，用 blocks 查询看真实文档结构：

```bash
ARG=$(python3 -c "import base64,json;print(base64.b64encode(json.dumps({'blockId':'doc'}).encode()).decode())")
wps365-cli api post "/v7/airpage/<file-id>/blocks" --data "{\"arg\":\"$ARG\"}" -o json --jq '.data.result' \
  | tr -d '"' | python3 -c "import sys,base64,json;d=json.loads(base64.b64decode(sys.stdin.read()));print(json.dumps(d,ensure_ascii=False)[:2000])"
```

注意这个端点是 **POST**（不是 GET，GET 会被 CLI 的 spec 校验挡掉）。
返回里的 `version` 就是导出 docx 要用的版本号（§6）。
`POST /v7/airpage/{file_id}/export_to_json` 也能拿全量结构，不丢表格。

推论：**只要产物里有表格，就不能拿 markdown 抽取当验收判据**（导出 .md 交付给用户同理，会缺表）。

## 6. 导出 docx（官方接口可用）

旧版本说明称"官方 export_to_docx 常卡 Building/Failed"——**那是漏传 `version` 导致的**。
三个字段 `attrs` / `version` / `ai_check` **全部必填**，缺一个报 400。实测完整流程能拿到
带表格的真 .docx。

```bash
FID=<file-id>
# 1) 取当前文档 version（见 §5 的 blocks 查询，取 result.version）
# 2) 发起导出；status 变 Completed 时 data.url 就是下载地址
wps365-cli api post "/v7/airpage/$FID/export_to_docx" \
  --data "{\"attrs\":\"\",\"version\":\"$V\",\"ai_check\":false}" -o json > exp.json
# 3) 🔴 不要用 --jq 取 url：jq 输出会把 & 转成字面量 &，签名 URL 直接 AccessDenied
URL=$(python3 -c "import json;print(json.load(open('exp.json'))['data']['url'])")
curl -sL "$URL" -o out.docx
```

下载完 `file out.docx` 应为 `Microsoft OOXML`。**如果拿到的是 600 字节左右的 XML，
那是 `<Error>AccessDenied</Error>`，不是 docx**——多半就是上面 `&` 那个坑。

同样可用：`export_to_pdf`、`export_to_json`、`import_json_data`、`blocks/update`、`blocks/batch_delete`。
完整端点清单见本机 spec：`~/Library/Application Support/wps365-cli/spec/api.yaml`，
`grep -n "/v7/airpage" api.yaml`。写任何 airpage 请求前先查 spec 里的 required 字段，
不要凭印象发——本 skill 两次 400 都是漏必填字段。

## 7. 建目录 / 搬家 / 删除

```bash
wps365-cli drive files create 6lABZaR <parent-id> --name "01.会议纪要" --file-type folder --on-name-conflict fail
wps365-cli drive files batch-move 6lABZaR --file-ids id1,id2 --dst-drive-id 6lABZaR --dst-parent-id <folder-id>
wps365-cli drive files batch-delete 6lABZaR --file-ids id1,id2
```

- `batch-move` / `batch-delete` **异步**：轮询源目录变空再往下走。
- 单文件用 `drive files delete <drive-id> <file-id>`（实测返回 `code:0`）；
  但对 folder 会 403，空文件夹要用 `batch-delete`。
- 一次最多约 20 个 id。
- 🔴 **`batch-move` 会重写 mtime**：搬完所有文件的修改时间都变成搬家当天，
  原始日期**不可恢复**。治理前先把清单（名字/日期/体积）存下来，报告里用存下来的日期，
  否则用户的时间线信息就丢了。
- **删文件前先问用户**。空文件夹、明确的治理方案执行除外。
- 自己造的测试文件当场删干净，并列目录确认没有残留。

## 8. 目录治理约定

根目录不放正文。一级编号两位：`01.`…`07.`，临时用 `99.`。大附件（pptx/pdf/mp3，约 >20MB）进 `附件/`。
同文双格式优先留 `.otl`，`.docx` 进附件。

流程：递归清单 → 给归位表 → **等确认** → create + move → 删空旧夹 → 回传最终树。

## 9. 红线

- 只动用户企业盘里指定目录；不碰别人分享盘里的原件（可读可导出）。
- 不提交 `client_secret` / access token。
- **`code:0` 不等于内容到位**，`400008009 文件不存在` 不等于文件没了。
  报"完成"之前，按 §5 用 blocks/export_to_json 拿正面证据。
- 输出给用户：文档名、kdocs 链接（建档返回值里的 `link_url`）、本地路径、做了什么。
