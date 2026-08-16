---
name: wps365-cli
description: Operate WPS 365 via official wps365-cli for cloud docs, AirPage/智能文档, drive folders, search, export, and import. Use when the user mentions WPS、金山文档、kdocs、协作文档、智能文档、otl、wps365-cli, or asks to read/export/create/move/organize files under 我的企业文档.
---

# WPS 365 CLI

用本机 `wps365-cli` 操作金山协作 / 智能文档。不要改走浏览器 Cookie CLI，不要手写未验证的 OpenAPI。

二进制：`~/.local/bin/wps365-cli`（已在 PATH）。默认盘：`我的企业文档`，`drive_id=6lABZaR`。

## 0. 上游项目

**官方仓库：<https://github.com/wps365-open/cli>** —— 金山官方出品，覆盖日历、协作、
通讯录、邮件、云文档、多维表格、会议 7 个业务域。**本 skill 只用到云文档 + AirPage 那部分。**

| 想知道 | 去哪 |
|---|---|
| 官方使用手册 | <https://365.kdocs.cn/wiki/l/0lcqi8RexYzQKD> |
| 建应用 / 配权限前置步骤 | [`docs/prerequisites.md`](https://github.com/wps365-open/cli/blob/main/docs/prerequisites.md) |
| 版本与更新日志 | <https://github.com/wps365-open/cli/releases> |
| **本机 API spec（离线，最常用）** | `~/Library/Application Support/wps365-cli/spec/api.yaml` |

查端点和必填字段**优先查本机 spec**（`wps365-cli spec status` 看路径），
它和本机二进制版本严格对应；官方 wiki 讲的是概念和流程，不保证与本机版本一致。
`wps365-cli spec update` 可从远端更新 spec。

安装 / 升级（macOS，脚本只装二进制到 `~/.local/bin`，不碰 config 和已有授权）：

```bash
curl -fsSL https://raw.githubusercontent.com/wps365-open/cli/main/install.sh | bash
wps365-cli version && wps365-cli user me -o json --jq '.code'   # 升级后确认授权还在
```

全新环境三步走：`config init`（浏览器里一键注册应用）→ `auth login --device` → `user me`。
**本机已完成前两步，不要重跑 `config init`**——它会重新绑定应用，把现有授权弄乱。
实测原地升级不需要重新登录，`user me` 照常返回 `code:0`。

**本机 v0.3.2**（2026-08-16 升级，spec 已同步 `spec update`）。
v0.3.2 加了超时配置：全局 `--timeout`、环境变量 `WPS365_TIMEOUT`、`config set timeout`，
默认 30s，`0`/`none`/`unlimited` 为不限，写法如 `2m`/`2min`。

⚠️ **别拿文件体积估耗时**：实测那份 176MB 的 otl，`file-content get` **0.5 秒**就返回
（体积几乎全是内嵌图片，抽出来的正文只有约 33K）。**目前没有遇到过真正撞 30s 默认超时的操作**，
所以不要一看到大文件就去加 `--timeout`。真的超时了再加：

```bash
wps365-cli --timeout 2m drive file-content get <drive-id> <file-id> --format markdown -o json
```

🔴 **资源名一律用单数**：`drive file`、`drive file-version`、`drive link`。
v0.2.0 把所有复数资源名改成单数（`drive files *` → `drive file *`），
且 **`drive files ...` 不会报错**——它退回打印 `drive` 的帮助、**exit code 仍是 0**，
只在 stderr 留一句 `unknown flag`。**脚本里判 `$?` 会把这种失败当成成功。**
判命令是否可用要看真实调用有没有拿到 `code:0` 的 JSON，别只看退出码，
也别拿 `--help` 探测（错命令的 `--help` 同样返回 0）。

同时 v0.2.0 移除了一批精装命令，本 skill 涉及的是
`drive files batch-delete` / `batch-get` —— 改用 `api post` 打端点（见 §8）。
升级 CLI 后先按 [CHANGELOG](https://github.com/wps365-open/cli/blob/main/CHANGELOG.md)
核一遍本文档里的命令还在不在。

## 1. 先鉴权

```bash
wps365-cli user me -o json
```

**用 `user me` 判活，不要用 `auth status` 判活。** access token 只有 2 小时，
`auth status` 天天显示 `expired`，但 refresh token 有效期一年、CLI 会在下一次真实调用时
自动续期——照着 `status` 判会天天误报要重新登录。`user me` 返回 `code:0` 就一切正常。

只有 `user me` 真的失败时才排查，**先看缺什么再决定动作**，不要一上来整段重新登录：

```bash
wps365-cli auth status --jq '.delegated | {status, granted_scopes, has_refresh}'
```

- `granted_scopes` 缺哪条就补哪条（下面这行按需裁剪，不必每次全给）；
- `has_refresh:false` 或 refresh token 也过期了，才需要重新走 device login。

```bash
wps365-cli auth login --device --scopes "kso.user_base.read,kso.file.readwrite,kso.drive.readwrite,kso.airpage.readwrite"
```

## 2. 统一话术 → 动作

用户怎么说，就怎么做。先定位，再动手；目录治理先出方案，**确认后再搬文件**。

| 用户说 | 动作 |
|---|---|
| 读取 / 打开 / 看一下「文档名」 | `search` 定位 → `file-content get --format markdown`；**含表格要提醒会缺表**（§6） |
| 导出 .md | 同上写入本地 `.md`；**含表格时同时给 json 或 docx**，否则交付的是残缺内容 |
| 导出 .docx | 官方 `export_to_docx` **可用**，按 §7 轮询闭环；不要默认走本地转换 |
| 生成智能文档 / 放到某目录 | 在目标夹 `POST /v7/airpage/files` 建 otl → convert+insert markdown（§5） |
| 整理 / 治理某目录 | 先递归清单 + 归位方案；用户确认后再 create folder + batch-move |
| 授权某某读写 | `auth login --device --scopes` 补齐 scope |

## 3. 🔴 drive_id 必须跟着文件走

**这是本 skill 最容易犯的错。** `search` 是**全公司跨盘**搜索，实测一次 20 条命中
横跨 8 个 drive，只有 8 条在默认盘。**绝不能搜到 file_id 后套用 `6lABZaR`。**

drive_id 用错的报错是 `400008009 文件不存在`——**看起来像文件被删了，其实是盘搞错了**。
遇到「文件不存在」先怀疑 drive_id，不要回去跟用户说文件没了。

```bash
# 搜索结果里 file_id 和 drive_id 必须成对取出，一起往下传
wps365-cli drive file search --type all --keyword "文档名" --page-size 20 -o json \
  --jq '.data.items[] | {name:.file.name, drive:.file.drive_id, id:.file.id, path:.file_src.path, url:.file.link_url}'
```

**命中多条且用户没指定是哪一份时，列出 `name + path + drive_id + 修改时间` 让用户选，
不要自己挑"看起来最像的"那份就往下走**——尤其是跨盘命中，选错就是读了别人的同名文件。

**动手写之前先用 `file-path get` 确认这个 (drive_id, file_id) 到底落在哪**，
一次调用就能拿到完整祖先链，比事后发现搬错目录便宜得多：

```bash
wps365-cli drive file-path get <drive-id> <file-id> -o json --jq '[.data.paths[].name]|join(" / ")'
# → "01.技术交流文档 / 01.技术交流文档 治理报告.otl"
```

drive_id 配错时它同样报 `400008009 文件不存在`，所以**它也是那个报错的最快判别器**：
换正确的盘再打一次，能出路径就说明文件好好的，只是盘搞错了。

盘本身也不用背 ID，`drive list` 直接列出你能访问的盘：

```bash
wps365-cli drive list --page-size 50 -o json --jq '.data.items[] | {id,name}'
# → {"id":"6lABZaR","name":"我的企业文档"}
```

别人共享盘里的文件可读可导出，但**不要动原件**（见 §9）。

## 4. 定位与读写

```bash
# 搜（--type all 必填，漏了直接报 missing required flag）
wps365-cli drive file search --type all --keyword "文档名" --page-size 20 -o json

# 列目录（根用 parent-id=0）
wps365-cli drive file list 6lABZaR <parent-id> --page-size 100 -o json --jq '.data.items[] | {id,name,type}'

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

## 5. 新建智能文档并灌 Markdown

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

🔴 **`on_name_conflict:"rename"` 重名会静默变成 `xxx(1).otl`**（实测），
仍返回 `code:0`。**所以失败重试前必须先确认上一次是不是其实建成功了**，
否则会留下一份 `(1)` 副本。发现多余副本立刻 `delete` 掉。
怕重名就改用 `"fail"`，让它报错而不是偷偷改名。

`drive file create --file-type otl` 会 400（`400000004 请求参数不支持`），不要用；
otl 只能经 `/v7/airpage/files` 建。

## 6. 🔴 验证插入结果：不要用 markdown 抽取

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
`POST /v7/airpage/{file_id}/export_to_json` 也能拿全量结构，不丢表格；
`blocks/batch_get` 也可以，但 body 是 `{"blockIds":["doc"]}`（复数数组，传 `blockId` 报
`1001 blockId is required`），结果在 **`data.results`**（不是 `data.result`）。

🔴 **解码失败不等于插入失败。** 上面这串管道有 base64 + jq + json 三层，任何一层出问题都
只说明**你的读法**有问题。解不出来就直接打印原始 JSON 看，**绝不能据此判定内容没进去、
然后重插一遍**——重插会插出重复内容（本 skill 标定时踩过）。

推论：**只要产物里有表格，就不能拿 markdown 抽取当验收判据**（导出 .md 交付给用户同理，会缺表）。
读文档时若发现含表格，要跟用户说明「.md 会缺表，结构以 json/docx 为准」。

## 7. 导出 docx（官方接口可用）

旧版本说明称"官方 export_to_docx 常卡 Building/Failed"——**那是漏传 `version` 导致的**。
三个字段 `attrs` / `version` / `ai_check` **全部必填**，缺一个报 400。实测完整流程能拿到
带表格的真 .docx。

**第一次调用几乎必然返回 `Building` + 空 url，这是正常的，不是失败**——同一个请求
重发一次通常就 `Completed`。**必须轮询，不能只发一次就下结论。**

`version` 从 `GET /v7/airpage/{file_id}` 的 `data.version` 取（比 §6 那串 base64 管道简单）。
注意实测该字段**不做校验**，随便填一个数也能导出成功；所以它只是必填占位，
**不要因为"version 可能不对"去怀疑导出结果**。

```bash
FID=<file-id>
V=$(wps365-cli api get "/v7/airpage/$FID" -o json --jq '.data.version')

for i in $(seq 1 10); do
  wps365-cli api post "/v7/airpage/$FID/export_to_docx" \
    --data "{\"attrs\":\"\",\"version\":\"$V\",\"ai_check\":false}" -o json > exp.json
  read S U < <(python3 -c "import json;d=json.load(open('exp.json'))['data'];print(d['status'],len(d['url']))")
  echo "poll$i: $S url_len=$U"
  [ "$S" = "Completed" ] && [ "$U" != "0" ] && break
  python3 -c "import time;time.sleep(2)"
done

# 🔴 不要用 --jq 取 url：jq 会把 & 输出成字面量 &，签名 URL 直接 AccessDenied
URL=$(python3 -c "import json;print(json.load(open('exp.json'))['data']['url'])")
curl -sL "$URL" -o out.docx
file out.docx    # 必须是 Microsoft OOXML
```

**验收三连，缺一不可**：`status=Completed` → `url` 非空 → `file` 报 `Microsoft OOXML`。
拿到 600 字节左右的 XML 说明是 `<Error>AccessDenied</Error>` 而不是 docx，多半是上面 `&` 那个坑。
轮询 10 次仍 `Building`/`Failed` 或 url 始终为空，**才**回退本地转 docx，并明确告诉用户走了回退。

已实测可用：`export_to_docx`、`export_to_pdf`、`export_to_json`、`blocks`、`blocks/batch_get`、
`blocks/convert`、`blocks/create`。
spec 里还有 `import_json_data`、`blocks/update`、`blocks/batch_delete` 等，**本 skill 未跑通，
不要当默认路径用**；真要用先照 spec 查必填字段并小样本验证。
完整清单：`grep -n "/v7/airpage" ~/Library/"Application Support"/wps365-cli/spec/api.yaml`。
写任何 airpage 请求前先查 spec 的 required 字段——本 skill 数次 400 都是漏必填字段。

## 8. 建目录 / 搬家 / 删除

```bash
wps365-cli drive file create 6lABZaR <parent-id> --name "01.会议纪要" --file-type folder --on-name-conflict fail
wps365-cli drive file batch-move 6lABZaR --file-ids id1,id2 --dst-drive-id 6lABZaR --dst-parent-id <folder-id>

# batch-delete 精装命令已在 v0.2.0 移除，官方替代是直接打 API：
wps365-cli api post "/v7/drives/6lABZaR/files/batch_delete" --data '{"file_ids":["id1","id2"]}' -o json
```

- `batch-move` / `batch_delete` **异步**（返回 `task_id`）：轮询源目录变空再往下走。
- 单文件用 `drive file delete <drive-id> <file-id>`（实测返回 `code:0`）；
  但对 folder 会 403，空文件夹要用上面的 `batch_delete` API。
- 一次最多约 20 个 id。
- 🔴 **`batch-move` 会重写 mtime**：搬完所有文件的修改时间都变成搬家当天，
  原始日期**不可恢复**。治理前先把清单（名字/日期/体积）存下来，报告里用存下来的日期，
  否则用户的时间线信息就丢了。
- **删文件前先问用户**。空文件夹、明确的治理方案执行除外。
- 自己造的测试文件当场删干净，并列目录确认没有残留。
- 🔴 **批量搬/删前先加 `--dry-run` 看一遍请求**（官方全局 flag，只打印不发送）。
  确认 URL、`file_ids` 和目标 `parent_id` 都对，再去掉 `--dry-run` 真跑：

  ```bash
  wps365-cli --dry-run drive file batch-move 6lABZaR --file-ids id1,id2 \
    --dst-drive-id 6lABZaR --dst-parent-id <folder-id>
  ```

## 9. 目录治理约定

根目录不放正文。一级编号两位：`01.`…`07.`，临时用 `99.`。大附件（pptx/pdf/mp3，约 >20MB）进 `附件/`。
同文双格式优先留 `.otl`，`.docx` 进附件。

流程：递归清单 → 给归位表 → **等确认** → create + move → 删空旧夹 → 回传最终树。

## 10. 红线

- 只动用户企业盘里指定目录；不碰别人分享盘里的原件（可读可导出）。
- 不提交 `client_secret` / access token。
- **`code:0` 不等于内容到位**，`400008009 文件不存在` 不等于文件没了。
  报"完成"之前，按 §6 用 blocks/export_to_json 拿正面证据。
- 输出给用户：文档名、kdocs 链接（建档返回值里的 `link_url`）、本地路径、做了什么。
