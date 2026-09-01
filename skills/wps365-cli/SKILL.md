---
name: wps365-cli
description: Operate WPS 365 via official wps365-cli for cloud docs, AirPage/智能文档, drive folders, search, download, export, and import. Use when the user mentions WPS、金山文档、kdocs、协作文档、智能文档、otl、wps365-cli, or asks to read/download/export/create/move/organize files under 我的企业文档.
---

# WPS 365 CLI

使用官方 `wps365-cli` 操作 WPS 365。默认二进制为 `~/.local/bin/wps365-cli`，默认企业盘 `drive_id=6lABZaR`。本机已验证版本为 v0.3.4；安装、升级和故障诊断见 [setup-and-troubleshooting.md](references/setup-and-troubleshooting.md)。

只读取当前任务需要的参考文档，不要一次性加载全部 references。

## 1. 任务路由

| 用户意图 | 首选入口 | 按需读取 |
|---|---|---|
| 登录、升级、命令异常 | CLI 原生命令 | [setup-and-troubleshooting.md](references/setup-and-troubleshooting.md) |
| 搜索、列目录、读正文、下载、导出 | CLI 原生命令 | [drive-operations.md](references/drive-operations.md) |
| 上传 PDF、DOCX、图片等二进制文件 | `scripts/drive_upload.py` | [drive-operations.md](references/drive-operations.md) |
| 新建纯文本/Markdown 智能文档 | `scripts/airpage_put.py` | [airpage-workflows.md](references/airpage-workflows.md) |
| 从 Markdown 发布含图片/附件的智能文档 | `scripts/airpage_publish.py` | [airpage-rich-media.md](references/airpage-rich-media.md) |
| 跨盘复制智能文档 | `scripts/airpage_copy.py` | [airpage-workflows.md](references/airpage-workflows.md) |
| 修复正文中的 `**粗体**` | `scripts/airpage_fix_markdown_bold.py` | [airpage-block-editing.md](references/airpage-block-editing.md) |
| 向现有智能文档插图 | `scripts/airpage_insert_images.py` | [airpage-existing-doc-insertion.md](references/airpage-existing-doc-insertion.md) |
| 向现有智能文档追加参考文档 | `scripts/airpage_add_references.py` | [airpage-existing-doc-insertion.md](references/airpage-existing-doc-insertion.md) |
| 目录整理、去重、移动、删除 | CLI 原生命令 | [drive-governance.md](references/drive-governance.md) |
| 用户要求完整案例 | — | [demos.md](references/demos.md) |

## 2. 每次都遵守的规则

### 2.1 认证与命令

```bash
WPS=~/.local/bin/wps365-cli
$WPS user me
```

- 先运行 `user me`；只有失败时才检查 `auth status`，不要无故重新 `config init` 或登录。`auth status` 的 `expired` 和 `has_refresh: true` 都不足以判断是否需要重登，以 `user me` 为准。
- 资源名使用单数，如 `drive file`、`drive file-version`、`drive link`、`airpage block`。错误复数命令可能打印帮助却返回退出码 0。
- 网络命令设置合理超时；导出和异步任务按状态轮询，不要把一次 HTTP 成功当成完成。
- 不输出 access token、refresh token、Authorization header 或完整配置文件。

### 2.2 文件身份与路径

- `file_id` 只能和它所属的 `drive_id` 配对使用。搜索是全局的，返回结果后必须保留两者。
- 写入前运行 `drive file-path get <drive_id> <file_id>` 核验目标路径。
- `400008009` 通常意味着 `drive_id` 错误；先修正盘符，不要猜测权限或重登。
- `drive list` 主要列本人空间；团队文档用 `drive doclib list`。别人共享的单文件优先从短链或搜索结果解析真实身份。
- 默认只读取共享原件。复制、备份或整理时写入用户指定目录；只有用户明确要求时才修改共享原件。

### 2.3 写入与验收

- 修改现有智能文档的脚本默认先 preview，确认命中范围后再加 `--apply`。
- 创建前检查同名项。发生 `name conflict` 时不得把旧文件当作本次产物；复用、改名或覆盖必须符合用户意图。
- `code: 0`、HTTP 200 或脚本无异常只表示请求成功，不表示任务完成。
- 写后至少回读一次：文件存在、路径正确、标题/正文正确；移动后再次核验路径。
- 表格、图片、附件和 `WPSDocument` 不能只靠 Markdown 回读验收；使用 `airpage block get`、导出 JSON 或 DOCX 检查结构。
- 删除只限已确认范围；先列目标 ID，完成后复查幸存集合。不要因同名就删除。
- 最终报告文档名、链接、保存路径和关键验收证据；部分成功必须明确列出未完成项。

## 3. 常用盘与基础查询

常用企业盘目录 ID（目录重建后可能变化，使用前仍应核验路径）：

| 路径 | folder_id |
|---|---|
| `00.个人文档` | `PjbYGr3XS1MTyQEZNP3krxXm4WpQX68RX` |
| `01.个人项目文档` | `reJo7APBY1MjDDSMZ3anxx6g158Y1QcED` |
| `01.游戏AI业务` | `FFarzp4xFrMs7HqCH3P7xxYPiT2ejBYag` |
| `02.重要纪要` | `hKaZkYmBY1MTMgG2MY2nxxqBAyiH8mvhE` |
| `03.技术交流文档` | `zBEGJgbUw1MCVfTSv3BW1xtWVvsjR99LX` |
| `01.技术交流文档` | `jSLJUdhx3rMyena6D8h3rxHLun5AdZTZ1` |

注意 `01.技术交流文档` 与 `03.技术交流文档` 是不同目录。

```bash
# 全局搜索；保留结果中的 drive_id + file_id
$WPS drive file search --type all --keyword "关键词" --page-size 100

# 列目录、核验路径、读取智能文档正文
$WPS drive file list 6lABZaR <folder_id> --page-size 100
$WPS drive file-path get <drive_id> <file_id>
$WPS drive file-content get <drive_id> <file_id> --format markdown
```

精确搜索、分页、下载、导出和上传见 [drive-operations.md](references/drive-operations.md)。

## 4. 智能文档常用入口

```bash
# 新建一篇纯 Markdown 智能文档
python3 scripts/airpage_put.py <folder_id> "标题" /abs/path/content.md \
  --drive <drive_id>

# 发布含本地图片或附件的 Markdown
python3 scripts/airpage_publish.py <folder_id> "标题" /abs/path/content.md \
  --drive <drive_id>

# 跨盘复制；先预览，确认后执行
python3 scripts/airpage_copy.py <src_drive_id> <src_file_id> \
  <dst_drive_id> <dst_folder_id>
python3 scripts/airpage_copy.py <src_drive_id> <src_file_id> \
  <dst_drive_id> <dst_folder_id> --apply
```

- 新建智能文档优先使用仓库脚本，不要手写底层转换/上传协议。
- `.otl` 是智能文档文件类型；标题与正文首个标题块是两个概念，发布后都要检查。
- 同盘复制可用官方批量复制接口；跨盘复制使用 `airpage_copy.py` 重建正文和媒体。
- 跨盘复制不承诺保留评论、历史版本、原权限或所有不可见元数据。
- 详细创建、复制、导出和结构验收见 [airpage-workflows.md](references/airpage-workflows.md)。

## 5. 整理与高风险操作

- 先生成清单和计划，再移动或删除；用户只说“梳理”时，默认做只读盘点。
- 同名、带 `(1)` 后缀或旧日期都不能单独证明重复；比较正文块、文件大小和来源后再判断。
- 移动可能更新 mtime，不要把 mtime 当唯一的新旧依据。
- 目录治理、批量移动和删除验收见 [drive-governance.md](references/drive-governance.md)。

## 6. 红线

- 不绕过 WPS 权限，不替用户扩大共享范围。
- 不在未核验 `drive_id + file_id + path` 时写入。
- 不把共享原件当作默认编辑目标。
- 不因命令退出码为 0 就跳过语义验收。
- 不在未确认范围内批量删除、覆盖或移动。
