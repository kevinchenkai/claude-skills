---
name: wps365-cli
description: Operate WPS 365 via official wps365-cli for cloud docs, AirPage/智能文档, drive folders, search, download, export, and import. Use when the user mentions WPS、金山文档、kdocs、协作文档、智能文档、otl、wps365-cli, or asks to read/download/export/create/move/organize files under 我的企业文档.
---

# WPS 365 CLI

用本机 `wps365-cli` 操作金山协作 / 智能文档。不要改走浏览器 Cookie CLI，不要手写未验证的 OpenAPI。

二进制：`~/.local/bin/wps365-cli`（已在 PATH）。默认盘：`我的企业文档`，`drive_id=6lABZaR`。

📖 **用法案例见 [`references/demos.md`](references/demos.md)**（找文档 / 短链下载 / 导出 md·docx /
建智能文档 / 整理目录 / 出错排查，均为本机实跑）。
普通 Markdown 建档用 [`scripts/airpage_put.py`](scripts/airpage_put.py)；包含本地图片、长 prompt、
多表格的报告用 [`scripts/airpage_publish.py`](scripts/airpage_publish.py)。后者会把附件上传、
`picture.sourceKey` 绑定、分块插入、失败清理和结构验收串成一条。
富媒体协议与验收不变量见 [`references/airpage-rich-media.md`](references/airpage-rich-media.md)。
把别人共享盘中的原生智能文档复制到自己的盘，用
[`scripts/airpage_copy.py`](scripts/airpage_copy.py)：它会重传图片附件、重绑 `sourceKey`，
失败时清理半成品；默认只预检，显式 `--apply` 才创建目标文档。
已有文档里出现字面量 `**文字**` 时，用
[`scripts/airpage_fix_markdown_bold.py`](scripts/airpage_fix_markdown_bold.py)；安全替换协议见
[`references/airpage-block-editing.md`](references/airpage-block-editing.md)。
向已有文档增量插图或添加原生文档引用时，分别用
[`scripts/airpage_insert_images.py`](scripts/airpage_insert_images.py) 和
[`scripts/airpage_add_references.py`](scripts/airpage_add_references.py)；两者默认只预检，统一安全协议见
[`references/airpage-existing-doc-insertion.md`](references/airpage-existing-doc-insertion.md)。

🔴 **改脚本前先看 [`scripts/_airpage_common.py`](scripts/_airpage_common.py)**：`cli()`、
`read_top()`、`create_blocks()`、`upload_attachment()` 等都在那里，**别在各自脚本里再抄一份**。
附件上传曾经有两份同名实现且**参数顺序相反**（`(file_id, path, upload_name)` vs
`(file_id, upload_name, path)`）——各自独立时没出错，但只要有人改成从公共模块导入，
文件名和内容就会静默对调，且照样返回 `code:0`。现已统一，并由
`tests/test_shared_helpers.py` 钉住签名和调用顺序。
（`airpage_put.py` / `drive_upload.py` 保留各自的 `cli()`：它们是刻意做成
单文件可读示例、用 `sys.exit` 报错，与公共模块的 `raise` 语义不同。）

## 0. 上游项目

**官方仓库：<https://github.com/wps365-open/cli>** —— 金山官方出品，v0.3.3 起覆盖日历、协作、
通讯录、邮件、云文档、多维表格、会议、**智能文档、智能表格** 9 个业务域。
**本 skill 只用到云文档 + AirPage 那部分。**

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

**本机 v0.3.4**（2026-09-01 升级，spec 已同步 `spec update`，端点 799 → 814，无删除）。
v0.3.2 加了超时配置：全局 `--timeout`、环境变量 `WPS365_TIMEOUT`、`config set timeout`，
默认 30s，`0`/`none`/`unlimited` 为不限，写法如 `2m`/`2min`。
v0.3.3 新增 `airpage` / `airsheet` / `drive doclib` 精装命令（见 §9.5），
v0.3.4 修了 macOS keychain 回写校验，并把权益点 403 与 OAuth scope 分开提示。

⚠️ **升级后必须换一个新 shell 再验证**。实测踩过：`cp` 覆盖二进制后在**同一次 bash 调用**里
接着跑 `wps365-cli airpage --help`，bash 的命令哈希仍指向旧二进制，于是新命令全部报
`unknown command`，我据此得出「release notes 名不副实」的**错误结论**。
用绝对路径 `/Users/kk/.local/bin/wps365-cli --version` 复核才发现命令都在。
**升级后的第一条验证命令一律用绝对路径**，或先 `hash -r`。

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

**非要批量核命令存在性时，唯一可靠的判据是「`Usage:` 下一行是否以该命令全路径开头」**：

```bash
check() {   # 用法: check "drive file search"
  usage=$(wps365-cli $1 --help 2>&1 | grep -A1 '^Usage:' | tail -1 | sed 's/^ *//')
  [[ "$usage" == "wps365-cli $1"* ]] && echo "OK: $1" || echo "MISSING: $1 [=> $usage]"
}
```

不存在的命令会回落到父命令的帮助，`Usage` 行变成 `wps365-cli drive [command]`，据此可判。
⚠️ 别用 `grep -q "wps365-cli $1"` 匹配整段帮助——**帮助正文和 Examples 里也含命令全名**，
实测这样会把 `drive doclib list` 之外的错命令也判成存在。
**任何探测脚本都要先跑一遍已知不存在的命令做阴性对照**，只看阳性会自我欺骗。

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
| 下载到本机 / 给了 `kdocs.cn/l/...` 短链 | 短码先经 `links/meta` 换成 `(drive_id,file_id)`，再按类型下载（§4.6）；不要拿短码去 `search` |
| 检索「有几个叫 X」/ 同名文件 | `search` 后区分**精确文件名、部分文件名、正文候选**并翻完分页（§4） |
| 生成智能文档 / 放到某目录 | 纯文本用 `airpage_put.py`；含本地图片/长报告用 `airpage_publish.py`（§5） |
| 把已有智能文档里的 `**文字**` 变成加粗 | 先运行 `airpage_fix_markdown_bold.py <file-id>` 预检，再显式 `--apply`（§5.6） |
| 给已有智能文档补本地配图 | `airpage_insert_images.py` 先预检锚点、SHA1 与附件闭环，再显式 `--apply`（§5.7） |
| 把链接文档加入「参考文档」 | `airpage_add_references.py` 解析短链并插入原生 `WPSDocument`，按短链/文档 ID 去重（§5.7） |
| **上传本地文件**（xlsx/pptx/pdf…） | 用 [`scripts/drive_upload.py`](scripts/drive_upload.py)（三步协议已封装），见 §4.5 |
| 上传本地 `.md` | 想要**可编辑的智能文档**走 §5 建 otl；想**原样存档**就当二进制传（§4.5） |
| **同步/复制一份已有智能文档到别的盘** | 用 `airpage_copy.py` 预检后 `--apply`（§5.5）；它复制原生 blocks 并重传图片，**别用 markdown 中转** |
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

🔴 **`drive list` 只列出你自己名下的盘，看不到共享盘。** 实测只返回
`6lABZaR 我的企业文档` / `4lnrWwm 自动备份` 两个，而别人共享给你的团队盘
（如 `1XQAjDl 西山居AI项目`）**根本不在列表里**——但它可读、也**可写**。
v0.3.3+ 要枚举团队盘，优先用 `drive doclib list` 取 `items[].drive.id`（§9.5）；按具体文档
反查时，再从 **`search` 结果或短链 `links/meta` 响应**里把 `drive_id` 与 `file_id` 成对取出。
禁止猜成默认盘 `6lABZaR`；更不能因为 `drive list` 里没有就判定团队盘不存在。

往共享盘里**新建**文档是可以的（本仓实测：在 `西山居AI项目/router` 下建 otl 成功，
`airpage_put.py --drive <共享盘 id>` 走得通）。但**别人已有的原件不要改不要删**——
新增自己的产物 OK，动存量要先问。

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

🔴 **`search` 是分词后的文件名 + 正文全文检索，不是按文件名查找。**
`highlights.file_content` 命中只说明正文候选，甚至可能把相距很远的多个词拼进同一摘要，
不能证明完整短语连续出现。列出时标 `NAME-exact`、`NAME-partial` 或 `content`，并按用户意图分开：

- “有几个叫 X / 同名 X”——文件名去掉最后一个扩展名并 trim/casefold 后，只计**精确等于** X 的文件；
- “文件名包含 X”——另计文件名部分命中；
- “哪些文档提到 X”——列正文候选；若用户要精确短语次数，回读正文再验证；
- “有几个『X』”语义不清——同时报告精确文件名数、部分文件名数和全文候选数，不擅自混为一个数。

计数必须沿 `data.next_page_token` 继续传 `--page-token`，直到 token 为空；不能只数第一页。
短链中的 `/l/<短码>` 不是搜索关键词：拿它 search 可能为空，也可能返回无关全文结果，
都不能用来解析链接。短链统一走 §4.6。

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

## 4.5 二进制上传（xlsx/pptx/pdf…）：能传，但必须手写三步

CLI **没有 upload 精装命令**（v0.3.4 实测仍无，上游 [issue #25](https://github.com/wps365-open/cli/issues/25)
已提但未实现），必须手写三步协议。直接用
[`scripts/drive_upload.py`](scripts/drive_upload.py)，它把三步 + 完整性校验固化好了：

```bash
python3 scripts/drive_upload.py <drive-id> <parent-folder-id> ./本地文件.xlsx
# ✅ 文件名.xlsx (102700 bytes)
#    id=... https://www.kdocs.cn/l/...
#    体积: 一致 | 服务端 sha1: 一致
```

自己的盘和**共享盘都已实测通过**（共享盘同样可写，见 §3）。

🔴 **`400000004 请求参数不支持` 不代表接口没开放，多半是参数不全。**
第 1 步 `request_upload` 在公网**必须同时**给：

- `hashes`：**md5 和 sha256 两种都要**（只给一种会失败）；
- `upload_scene: "normal_upload"`。

少任何一个都报 `400000004`。**本 skill 曾据此错误地判定"应用档位没放开、只能走网页拖拽"，
是错的** —— 补齐这两个字段后一次就通。（教训：`400000004` 只说明参数组合不对，
不能推断成能力未授权；官方 spec 的 `required` 只列了 `size`，**公网实际要求比 spec 更严**。）

🔴 **`on_name_conflict` 在上传端点只认 `rename` / `overwrite`。**
spec 的枚举里还有 `fail` / `replace`，但上传端点实测**拒绝**它们（同样是 `400000004`）。
**同一个枚举在不同端点上的可用值不一样**——`drive file create` 建文件夹时 `fail` 是好用的。
`drive_upload.py` 已在参数层挡掉非法值，不会等到打接口才失败。

另外两个 `api post` 都要显式 `--token-type delegated`，否则走 app 身份报 403；
第 2 步 PUT 实体也要带 `wps365-cli auth token` 拿到的 token。

三步流程（脚本已封装，手写时照此）：

```bash
# 1) 申请上传位
wps365-cli api post "/v7/drives/$D/files/$P/request_upload" --token-type delegated \
  --data '{"name":"x.xlsx","size":102700,"on_name_conflict":"rename",
           "upload_scene":"normal_upload",
           "hashes":[{"type":"sha256","sum":"..."},{"type":"md5","sum":"..."}]}'
# → data.upload_id + data.store_request.{method,url}

# 2) PUT 实体（必须带 delegated token）
curl -X PUT --data-binary @x.xlsx -H "Authorization: Bearer $(wps365-cli auth token)" "$URL"

# 3) 落盘
wps365-cli api post "/v7/drives/$D/files/$P/commit_upload" --token-type delegated \
  --data '{"upload_id":"..."}'
```

**验完整性用 `commit_upload` 返回的 `data.hash.sum`——它是 sha1**（不是 md5/sha256），
和本地 `shasum -a 1` 比对即可。**不要靠下载回来比对**：`download` 给的 url 需要额外鉴权，
直接 curl 会拿到一个 46 字节的 `{"result":"userNotLogin"}`，
拿它算 md5 会得出"文件损坏"的假结论（本 skill 踩过）。

⚠️ `POST /v7/drives/{drive_id}/files/{parent_id}/create` 只建**空占位文件**，
不含内容——别拿它冒充上传成功。

## 4.6 短链解析与下载

用户给 `https://365.kdocs.cn/l/<短码>`、`https://www.kdocs.cn/l/<短码>` 或同类 kdocs
短链时，先从 URL path 取 `link_id`（忽略 query / fragment），**禁止**把短码当 file id，
也不要 `search --keyword "<短码>"`。

```bash
wps365-cli api get "/v7/links/<link-id>/meta" --token-type delegated -o json
# → data.drive_id + data.file_id + data.status；仅 status=open 时继续

wps365-cli drive file get <drive-id> <file-id> -o json
# → 确认 name、扩展名、size、hash.sum
```

`drive link` 只有 `open/close`，没有 get。meta 若返回 403，再在**保留已有 scopes**的前提下补
`kso.file_link.readwrite`；不要一上来重跑 `config init` 或把该 scope 塞进每次默认登录。
（本机实测：`granted_scopes` 里**没有** `kso.file_link.readwrite` 时该接口照样返回 `code:0` ——
spec 标注的 scope 比实际强制的更严，所以**别看到 spec 写了就先去补 scope**，先直接调。）
后续始终使用 meta 返回的 `(drive_id,file_id)`，不能套默认盘。

| 文件类型 | 本地获取方式 |
|---|---|
| `.otl` | `drive file download` 实测报 `403008042 不支持的文件类型`；按 §7 轮询 `export_to_docx`，保存为 `{stem}.docx`，并明确告诉用户这是导出转换 |
| 其他文件 | 调用 `drive file download <drive> <file> --with-hash -o json`；只有成功返回 `data.url` 才继续，不能预设所有扩展名都支持 |

二进制 `download` 返回的 URL 必须带 delegated Bearer；从完整 JSON 用 Python 取 URL，避免
`--jq` HTML 转义签名参数：

```bash
URL=$(wps365-cli drive file download <drive> <file> --with-hash -o json \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"]["url"])')
curl -sSL -H "Authorization: Bearer $(wps365-cli auth token)" "$URL" -o "$OUT"
```

这和 §7 不同：`export_to_docx` 完成后的签名 URL 可以裸 `curl`，不要额外加 Bearer；
而 `download` URL 不带 token 可能只拿到 `{"result":"userNotLogin"}`，不能冒充下载成功。

落地目录优先使用用户指定路径；只说“下载到本机”时用 `~/Downloads/`。同名目标已存在就依次用
`文件名 (1).ext`、`文件名 (2).ext`，禁止覆盖。完成后必须比较本地字节数与云端 `size`，
有 `hash.type=sha1` 和 `hash.sum` 时再比较本地 SHA1；已知格式再用 `file` 检查类型。`.ksheet` 保留原扩展名，
用户明确要 Excel 版本时可另存 `.xlsx`，仍不能覆盖已有文件。整个流程只读/导出，不改共享盘原件。

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

长文按 `##` 切块，每块保守控制在 **17.5KB** 内，顺序 insert 到末尾。

### 含本地图片的富媒体报告

Markdown 的图片语法只会让 `blocks/convert` 产出一个 `picture` 占位块，**不会把本地图片自动上传**。
只插入 convert 返回的 blocks，会得到“有图片块、没有可用图片附件”的空壳文档；事后走
`anchor_attachment_replace` 也不能补成可导出的原生图片。

这类报告直接用：

```bash
python3 scripts/airpage_publish.py <parent-folder-id> "报告标题" ./report.md \
  --drive 6lABZaR --on-name-conflict fail
```

脚本按已实测协议先上传图片附件，再把每个 `picture.attrs.sourceKey` 绑定到真实
`attachment_id`，最后同时核对 picture blocks、`export_to_json.attachment_list` 和 sourceKey 集合。
**这三个集合必须闭合**；仅看到 `blocks/create code:0` 或 picture 数量正确，都不能证明图片可见。
详细端点、响应头和重复图片规则只在做富媒体报告时读取
[`references/airpage-rich-media.md`](references/airpage-rich-media.md)。

富媒体发布过程中任一步失败，脚本会删除自己刚建的半成品 otl；不要在失败后直接重跑并使用
`on_name_conflict:"rename"`，否则容易留下 `(1)` 副本。发布成功后仍用 `file-path get` 回查云端路径。

🔴 **`name` 必须自带 `.otl` 后缀**。接口按最后一个 `.` 切扩展名，所以本仓
`00.` / `01.` 这种编号前缀会被当成扩展名：`"00.目录治理报告"` 直接报
`400000002 invalid file extension: .目录治理报告, expected: .otl`。写成
`"00.目录治理报告.otl"` 就正常。**凡是名字里带点的都要显式补 `.otl`。**

🔴 **API 建的文档，正文标题栏（title block）一定是空的**——打开会显示灰色的
`Enter title` 占位符。这**不是插入失败**，正文是好的。

原因：`/v7/airpage/files` 只设**文件名**，文档内的 title block 是另一块内容；
而 `blocks/convert` **从不产出 `title` 类型的 block**，markdown 里的 `# 一级标题`
一律转成 `heading` 接在 title 后面。所以 title 始终没人写。

实测这几条路都**填不上**：`blocks/update` 改 title block 报 `1002 invalid operation`
（试过 `block{type,content}` / `content+type` / `blockId:doc` 三种 payload）；
`drive file rename` 只改文件名不动 title；`export_to_docx` 也不会回写。
2026-08-27 又在普通 `paragraph` 上验证了三种 payload，`blocks/update` 同样报
`1002 invalid operation`，所以它也不能当成已有正文块的通用替换接口。

**目前唯一能填上的是在网页里打开一次**——编辑器会自动用第一个 H1 补上 title，
并把文件名一并同步过去。（本仓证据：一份建时叫 `00.目录治理报告-20260816.otl` 的文档，
在网页打开后文件名变成了 `01.技术交流文档 治理报告.otl`，正好等于它的 H1，
version 也从 2 涨到 3。**注意这会悄悄改掉你的文件名**，如果你依赖 `00.` 这类编号前缀排序，
打开后要检查名字有没有被改。）

所以：交付时**用 `# H1` 起头**（网页打开后就是标题），并跟用户说明
"标题栏首次在网页打开时自动补齐"，不要因为看到 `Enter title` 就重插一遍。

🔴 **`on_name_conflict:"rename"` 重名会静默变成 `xxx(1).otl`**（实测），
仍返回 `code:0`。**所以失败重试前必须先确认上一次是不是其实建成功了**，
否则会留下一份 `(1)` 副本。发现多余副本立刻 `delete` 掉。
怕重名就改用 `"fail"`，让它报错而不是偷偷改名。

`drive file create --file-type otl` 会 400（`400000004 请求参数不支持`），不要用；
otl 只能经 `/v7/airpage/files` 建。

## 5.5 跨盘同步一份已有文档（复制别人共享给你的文档）

**别用 markdown 中转**——`file-content get` 丢表格，图片也带不过来。跨盘复制直接用：

```bash
# 默认只预检：源盘、源文件、目标盘、目标目录
python3 scripts/airpage_copy.py <src-drive> <src-file> <dst-drive> <dst-parent>

# 确认预检里的路径、文件名、block/图片数后执行
python3 scripts/airpage_copy.py <src-drive> <src-file> <dst-drive> <dst-parent> --apply
```

同一盘内、权限明确时可优先用官方 `drive file batch-copy`，但它是异步任务，仍须回查目标目录；
从别人共享盘复制到另一个盘时不要走它，直接用上面的脚本。

🔴 **`batch-copy` 从别人的共享盘往外复制会静默失败。** 实测返回 `code:0` + `task_id`，
但轮询 30 秒目标目录什么都没有，全库搜也只有原件。**换目标盘复现，换成从自己盘内复制
则立刻成功**——所以是"源在别人共享盘"这一条被限制，且**不报错**。
（又一个 `code:0` ≠ 事情做成了的实例；判成功必须回查目标目录。）

脚本固化了下面这条已实测闭环：

1. `POST /v7/airpage/{源file_id}/blocks` 拿 `blocks[0].content`（§6 的读法）；
2. 丢掉源文档的 `title` block（目标文档有自己的）；
3. **递归删掉每个 block 的 `id`**，让服务端重新分配；
4. 🔴 **同时删掉所有 `rangeMarkBegin` / `rangeMarkEnd` 节点**——那是**评论/批注锚点**，
   接口明确拒绝：`1011 invalid RangeMark: rangeMark can only be used in update_content`。
   它只是批注高亮、**不含正文**，丢掉不影响内容，但**目标文档不会继承原文的批注**，
   交付时要说明这一点；
5. 对每个 `picture.sourceKey`，从源 `export_to_json.attachment_list` 下载原图，上传到目标文档，
   再把图片块重绑到新的 attachment ID；**只复制 blocks 不重传附件会留下图片空壳**；
6. 按序列化体积切块（每块 ≤9KB；不可拆的超大 table 单独一块），顺序插入；
7. 写前复查源文档没有并发变化；写后精确核对规范化 blocks、附件 ID 闭环和图片像素；任一步失败，
   自动删除本次创建的半成品。

附件清单里的声明 SHA1 可能与 `download_url` 返回的规范化 PNG 字节不同，上传后服务端还可能再次
规范化；所以跨文档复制不能强求三段 SHA1 相等。正确验收是 sourceKey/附件 ID 闭合，并比较源、目标
下载图片的尺寸与 RGBA 像素哈希。

正常差异只有：目标多一个 API 建档自带的空段落，标题栏为空（首次网页打开时自动补，见 §5）。
评论、版本历史和分享权限不会继承，脚本会在结果中明确列出。当前脚本只接受
`picture.sourceKey` 与附件清单完全闭合的文档；若存在非图片附件或孤立附件会停下，不猜测处理。

实测样本一：380KB、225 blocks（56 标题 / 7 表格 / 4 图片）；样本二：107 个顶层 blocks
（22 标题 / 3 表格 / 10 个 WPSDocument / 2 图片）。后者逐块结构一致，2 张图像素一致。

## 5.6 修复已有文档中的字面 Markdown 粗体

智能文档中若直接显示 `**文字**`，不要导出 Markdown 后整篇重建，也不要调用未跑通的
`blocks/update`。先对**搜索结果里的真实 AirPage file id**做只读预检：

```bash
python3 scripts/airpage_fix_markdown_bold.py <file-id>
```

确认目标块数和配对数后再修改；需要本地留存前后 blocks 时加 `--backup-dir`：

```bash
python3 scripts/airpage_fix_markdown_bold.py <file-id> --apply \
  --backup-dir /tmp/wps-bold-backup
```

脚本只处理顶层 `paragraph` / `blockQuote` 的 text 节点，保留原 attrs，并把命中的文字合并
`bold:true`。遇到三连星号、未配对标记或批注锚点会在写入前拒绝；代码块等其他类型中的
`**` 只报告、不修改。

替换协议是：回读最新 blocks → 在旧块位置 create 无 id 的新块 → 回读确认旧块移到后一位 →
以 `blockId:"doc"` 的 `startIndex/endIndex` 删除旧块。不能把旧子块 id 直接传给 delete。
每块完成后再次回读，最终核对全文语义、非 text 结构计数、图片 sourceKey 和附件 ID 集合。

若创建成功后删除失败，文档会暂时同时存在新旧两块；排查后显式恢复：

```bash
python3 scripts/airpage_fix_markdown_bold.py <file-id> --apply --resume-partial
```

脚本只会在旧块前一位恰好是等价替换块时执行恢复删除。完整边界、请求形状和失败处理见
[`references/airpage-block-editing.md`](references/airpage-block-editing.md)。

## 5.7 向已有智能文档安全增量插入

只有用户明确要求修改这份存量文档时才写入，尤其是共享盘原件。先解析短链并用
`file-path get` 确认 `(drive_id,file_id)` 与云端路径，再运行脚本的默认预检；确认计划后显式加
`--apply`。不要硬编码顶层 block 数或插入 index：编辑器可能自动裁掉尾部空段落。

给已有文档插入原生本地图片：

```bash
python3 scripts/airpage_insert_images.py <drive-id> <file-id> ./血缘图.png \
  --after-heading "四、模型训练"
python3 scripts/airpage_insert_images.py <drive-id> <file-id> ./血缘图.png \
  --after-heading "四、模型训练" --apply --backup-dir /tmp/vla-images
```

图片用本地 SHA1 对照 `export_to_json.attachment_list[].hash.sum` 做幂等判断。若附件上传成功、
插块前发生并发漂移，脚本会停写；重跑时复用同 SHA1 的孤立附件，不盲目重复上传。默认同图已展示则
跳过，只有用户明确需要重复展示时才加 `--allow-duplicate`。

向唯一的「参考文档」章节添加原生文档卡片，先准备 JSON：

```json
[
  {
    "url": "https://365.kdocs.cn/l/xxxxxxxx",
    "category": "评测",
    "description": "线上回归结果与指标口径"
  }
]
```

```bash
python3 scripts/airpage_add_references.py <drive-id> <file-id> ./references.json
python3 scripts/airpage_add_references.py <drive-id> <file-id> ./references.json --apply
```

脚本会验证每个链接可访问且确为 `.otl`，从 `/v7/airpage/{file_id}` 取数字文档 ID，生成原生
`WPSDocument` 节点，并按规范化短链 ID 与文档 ID 双重去重。默认任一引用无权读取就整批停止；只有
用户接受部分成功时才加 `--skip-inaccessible`。锚点、并发检查、附件不变量、失败恢复和节点形状见
[`references/airpage-existing-doc-insertion.md`](references/airpage-existing-doc-insertion.md)。

## 6. 🔴 验证插入结果：不要用 markdown 抽取

**`file-content get --format markdown` 会静默丢表格**（`plain` 同样丢），还可能省略原生
`WPSDocument` 节点里的文档名和链接。
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

推论：**只要产物里有表格或原生文档引用，就不能拿 markdown 抽取当验收判据**（导出 .md 交付给
用户同理，会缺结构）。读文档时若发现这些结构，要跟用户说明「结构以 blocks/json/docx 为准」。

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
`blocks/convert`、`blocks/create`、按父块子区间调用的 `blocks/delete`。
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

## 9.5 v0.3.3+ 精装命令：能省掉 base64，但别当银弹

v0.3.3 起有了 `airpage` / `airsheet` / `drive doclib`。**2026-09-01 在 v0.3.4 上逐条实测过**，
下面写的是实测结论，不是 release notes 的转述。

### 可以直接用的

```bash
# 团队文档库：一步拿到「西山居AI项目」这类团队盘的 drive_id，不用再靠搜索猜
wps365-cli drive doclib list --page-size 20 -o json --jq '.data.items[] | {drive:.drive.id, name:.drive.name}'

# 读块：等价于手写 v2 blocks，但不用 base64
wps365-cli airpage block get <file-id> -o json          # --block-id 默认 doc，title 读标题块
wps365-cli airpage get <file-id> -o json                # 文档元信息（title/size/version）
wps365-cli airpage create --drive-id <d> --parent-id <p> --name X.otl --template-id "" --on-name-conflict rename
```

实测 `airpage block get` 与手写 `POST /v7/airpage/v2/{id}/blocks` 返回**完全一致**
（同一份文档都是 64 children、15 heading / 46 paragraph / 2 table / 1 blockquote）。

### 🔴 `airpage block create` 是「一段纯文本」，不是 Markdown 通道

实测两条硬限制，**都会让人误以为写成功了**：

| 传入 | 实际结果 |
|---|---|
| 带换行的内容 | **报错** `400445004 InvalidInlineElement: newline is only allowed in text within code_block` |
| `# 标题 含**加粗**` | `code:0`，但**原样存成字面文本**，回读 bold runs 为空 |

所以它只适合**插入**一段纯文本，不能默认理解成追加：省略 `--index` 时服务端会插到首位。
要追加必须先用 `airpage block get` 回读最新 `doc` children 数量，将其显式传给 `--index`，写后再回读
确认位置；高价值存量文档仍按 §5.7 的并发检查与验收协议执行。**灌 Markdown 文档仍然必须走 §5 的
`convert` → `create`（`scripts/airpage_put.py`）**，那条链会把标题/表格/粗体真正转成块。

### v2 API 手写时的三个坑（精装命令帮你绕开了，直接调 api 时会撞）

1. 字段是 **snake_case `block_id`**，不是 v1 的 `blockId`（传错直接被客户端拦下）。
2. create **按父块类型分派**：插到根下要 `{"block_id":"doc","doc_children":{"children":[...]}}`，
   直接把 convert 的结果塞进 `content` 会报 `400445001 invalid create children`。
3. v2 的 `title` **独立于 `children`**（v1 是 children 里的第一个 block）。
   遍历统计时不注意会把标题多数一次——我就据此误判过"v1/v2 内容不一致"，
   实际逐字符比对是完全等价的（正文 2133 字符、title 均一致）。

### 仍然没有的

`drive file` 下**依然没有 upload**（v0.3.4 实测），二进制上传照旧走 §4.5 三步协议。
`airpage export` 仍是 create + get 两步，**必须轮询**，见 §7。

## 10. 红线

- 只动用户企业盘里指定目录。共享盘原件默认只读/导出；用户明确指定目标文档并要求修改时，才允许
  按 §5.7 的预检、并发检查与回读验收协议做增量写入。
- 不提交 `client_secret` / access token。
- **`code:0` 不等于内容到位**，`400008009 文件不存在` 不等于文件没了。
  报"完成"之前，按 §6 用 blocks/export_to_json 拿正面证据。
- 输出给用户：文档名、kdocs 链接（建档返回值里的 `link_url`）、本地路径、做了什么。
