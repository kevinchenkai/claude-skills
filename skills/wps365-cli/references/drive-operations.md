# Drive 搜索、读写、下载与上传

用于云盘文件级操作。任何文件操作都把 `drive_id` 与 `file_id` 视为不可拆分的身份对。

## 1. 盘与目录边界

```bash
WPS=~/.local/bin/wps365-cli

# 本人可见盘
$WPS drive list

# 团队文档库
$WPS drive doclib list --page-size 100

# 列目录
$WPS drive file list <drive_id> <folder_id> --page-size 100

# 核验文件真实路径
$WPS drive file-path get <drive_id> <file_id>
```

`drive list` 不等于全部可访问空间。团队文档、共享盘和别人共享的单文件可能只会通过 `drive doclib list`、全局搜索或短链解析暴露。不要把默认盘 `6lABZaR` 套到所有 `file_id` 上。

## 2. 搜索

```bash
$WPS drive file search --type all --keyword "关键词" --page-size 100
```

搜索后：

1. 保存每条结果的 `drive_id`、`file_id`、名称、类型和父目录信息。
2. 搜索显式使用 `--type all`。精确标题查询仍可能返回部分匹配；在本地按“去最后一个扩展名、trim、casefold”后的标题做精确筛选。
3. 多条同名结果用路径、创建者、修改时间、正文摘要区分，不凭第一条猜测。
4. 检查分页字段，结果超过单页时继续拉取；“当前页没有”不等于不存在。
5. 内容检索命中后，再用 AirPage 正文或导出文件确认上下文。`highlights.file_content` 可能拼接相距很远的词，不能证明完整短语连续出现。

搜索结果每项的主要结构是 `{file, file_src, highlights}`：文件字段在 `.file`，目录线索在
`.file_src.path`，下一页令牌为 `data.next_page_token`。报告数量时区分 `NAME-exact`、
`NAME-partial` 与 `content`，不要把三类混成一个数。

短链中的 `/l/<link_id>` 不是关键词，也不是 file id。忽略 query/fragment，调用：

```bash
$WPS api get "/v7/links/<link_id>/meta" --token-type delegated -o json
$WPS drive file get <drive_id> <file_id> -o json
```

只有 meta 返回 `status=open` 时继续，并始终使用响应中的身份对。`drive link` 只有 open/close，
不能代替 meta。meta 403 时再检查是否确实缺 `kso.file_link.readwrite`，不要预先重登或重置配置。

## 3. 读取正文和元数据

智能文档正文：

```bash
$WPS drive file-content get <drive_id> <file_id> --format markdown
```

Markdown 适合阅读和文本比对，但会丢失部分结构。表格、图片、附件、WPSDocument、标题块和复杂布局应读取块结构：

```bash
$WPS airpage get <file_id>
$WPS airpage block get <file_id> --block-id <block_id>
```

必要时导出 JSON 或 DOCX 进行二次验收。

## 4. 下载

普通二进制文件优先使用 Drive 下载能力：

```bash
$WPS drive file download <drive_id> <file_id> --with-hash -o json
```

Drive 普通下载 URL 需要 delegated Bearer。必须从完整 JSON 解析 URL，避免 shell/JQ 改写签名字符：

```bash
URL=$($WPS drive file download <drive_id> <file_id> --with-hash -o json \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"]["url"])')
curl -sSL -H "Authorization: Bearer $($WPS auth token)" "$URL" -o "$OUT"
```

不要混淆两种 URL：Drive `download` URL 不带 token 可能返回很小的
`{"result":"userNotLogin"}`；AirPage 导出完成后的签名 URL 则裸下载，不要再加 Bearer。

下载后：

1. 检查 HTTP 状态、Content-Type、文件大小和本地文件格式。
2. 对关键备份计算 SHA-1/SHA-256，必要时与来源哈希比对。
3. 同名本地目标使用 `文件名 (1).ext` 递增，不覆盖。

智能文档 `.otl` 的普通下载会报不支持；要用 AirPage 导出流程并保存为 `.docx`，见
[airpage-workflows.md](airpage-workflows.md)。`.ksheet` 默认保留原扩展名，只有用户明确要求时另存为 xlsx。

## 5. 上传二进制文件

使用封装脚本：

```bash
python3 scripts/drive_upload.py <drive_id> <folder_id> /abs/path/report.pdf
```

上传实现必须遵循官方三步语义：

1. 申请上传：提交名称、大小、MD5、SHA-256 和 `upload_scene`，获得上传地址或委托信息。
2. 上传字节：按响应的 method/url 上传，并携带 delegated access token；不要泄露 token。
3. 完成上传：用 `upload_id` 调用 `commit_upload`，并回读云端文件。

关键约束：

- 使用文件原始字节计算 MD5、SHA-256 和 SHA-1；申请上传使用前两者，完成后用服务端 SHA-1 与本地 SHA-1 验证，并核对大小。
- 冲突策略必须使用 API 接受的枚举，不凭自然语言猜值。
- `request_upload` 已验证只接受 `rename` / `overwrite`；`fail` / `replace` 会报 `400000004`。
- delegated upload 的字段和 URL 以申请响应为准。
- 响应 `code: 0` 后仍要列目标目录并核对文件名、类型、大小和路径。
- 上传脚本不得打印 token、完整签名 URL 查询参数或敏感 header。

`400000004 请求参数不支持` 常表示参数组合不完整，不足以证明接口未开放。两个 API 请求都要
`--token-type delegated`。`POST .../files/{parent_id}/create` 只能生成空占位文件，不能冒充上传成功。

## 6. 新建目录、移动与删除

先用父命令 `--help` 确认本机版本的精确参数。基本流程：

```bash
# 创建目录
$WPS drive file create <drive_id> <parent_id> --name "目录名" --file-type folder

# 移动前核验源和目标
$WPS drive file-path get <drive_id> <file_id>
$WPS drive file list <drive_id> <target_folder_id> --page-size 100
```

批量移动优先使用 CLI 的正式 batch-move 能力：

```bash
$WPS --dry-run drive file batch-move <src_drive_id> --file-ids id1,id2 \
  --dst-drive-id <dst_drive_id> --dst-parent-id <folder_id>
```

确认后去掉 `--dry-run`。字段是 `dst_drive_id + dst_parent_id`，不要猜成 `target_parent_id`。
batch-move 是异步操作，保存 task id 并回读目录；单批按已验证经验控制在约 20 个 ID。

批量删除精装命令已移除；确需批量删除时，对已确认 ID 使用
`POST /v7/drives/{drive_id}/files/batch_delete`，同样按异步任务验收。单文件用
`drive file delete <drive_id> <file_id>`；文件夹单删可能 403，空文件夹按已验证批量删除流程处理。

移动可能刷新 mtime，因此整理后的 mtime 不能证明内容更新。删除前必须列出精确 ID，删除后复查目标目录和幸存集合。完整治理流程见 [drive-governance.md](drive-governance.md)。

## 7. 验收清单

- 身份：`drive_id + file_id` 来自真实结果。
- 路径：`file-path get` 与用户目标一致。
- 类型：普通文件、文件夹、`.otl` 未混淆。
- 内容：正文、块结构或本地文件可打开。
- 完整性：大小/哈希合理，无 HTML 错误页伪装成文件。
- 结果：最终链接、路径和失败项清楚报告。
