# 安装、认证与故障排查

仅在安装、升级、认证或命令行为异常时读取本文件。

## 1. 上游与本机约定

- 官方仓库：<https://github.com/wps365-open/cli>
- 官方手册：<https://365.kdocs.cn/wiki/l/0lcqi8RexYzQKD>
- 应用与权限前置步骤：<https://github.com/wps365-open/cli/blob/main/docs/prerequisites.md>
- 版本记录：<https://github.com/wps365-open/cli/releases>
- 默认二进制：`~/.local/bin/wps365-cli`
- 当前已验证版本：v0.3.4
- 本地 OpenAPI 规格：`~/Library/Application Support/wps365-cli/spec/api.yaml`
- 默认企业盘：`6lABZaR`

本地规格与当前二进制版本匹配，查端点和 required 字段时优先使用它。用 `wps365-cli spec status`
确认实际路径，用 `wps365-cli spec update` 同步规格。

macOS 安装或原地升级不会主动改现有授权：

```bash
curl -fsSL https://raw.githubusercontent.com/wps365-open/cli/main/install.sh | bash
```

升级后先验证：

```bash
hash -r
~/.local/bin/wps365-cli version
~/.local/bin/wps365-cli user me
```

Bash 会缓存命令路径；如果升级后仍显示旧版本，先执行 `hash -r`，再检查 `type -a wps365-cli`。不要通过反复覆盖配置来解决路径缓存问题。

## 2. 认证

日常任务的最小检查：

```bash
WPS=~/.local/bin/wps365-cli
$WPS user me
```

只有 `user me` 失败时才继续：

```bash
$WPS auth status
$WPS config show
```

access token 过期不等于登录失效：refresh token 有效时，真实 API 调用会自动续期。因此不要只因
`auth status` 显示 expired 就重登。只有 `user me` 失败后，确认缺 scope 或没有 refresh token，才按需处理：

```bash
$WPS auth status --jq '.delegated | {status, granted_scopes, has_refresh}'
$WPS auth login --device \
  --scopes "kso.user_base.read,kso.file.readwrite,kso.drive.readwrite,kso.airpage.readwrite"
```

保留已有 scopes，只补任务缺少的项。不要无故执行 `config init`；它会重新绑定应用，可能扰乱已有授权。

任何输出都要隐藏 token、client secret、Authorization header 和完整凭据配置。CLI access token 仅用于 WPS OpenAPI；对象存储下载/上传可能使用独立的签名 URL，不要混用 Bearer token。

## 3. 命令发现的陷阱

资源名通常是单数：

```text
drive file
drive file-version
drive link
airpage block
```

`drive files`、`airpage blocks` 等错误命令可能只打印帮助文本，却仍以退出码 0 结束。因此探测命令不能只看 `$?`，还要检查输出是否包含真实数据或预期字段。

可靠的探测顺序：

1. 从已知的父命令逐层执行 `--help`。
2. 核对命令树中的单数资源名和参数名。
3. 执行只读小请求。
4. 验证输出中有业务字段，而不是 Usage/Commands 帮助页。
5. 批量探测时，检查 `Usage:` 下一行是否以完整命令路径开头，并用一个已知不存在的命令做阴性对照。

当 CLI 尚未封装某个已存在于规格中的端点时，可以查本地 `api.yaml` 确认路径、方法和字段；优先补进仓库脚本，避免在每个任务里临时拼接请求。

## 4. 超时与异步任务

- 默认超时为 30 秒，可用全局 `--timeout 2m`、环境变量 `WPS365_TIMEOUT` 或配置项调整；
  `0` / `none` / `unlimited` 表示不限时。
- 不要只凭文件体积预判超时。大型 `.otl` 的体积可能主要来自图片，而正文抽取很快；真实超时后再增加时限。
- 导出、批量复制、批量移动等任务可能异步完成；保存 task id，并按接口状态轮询。
- 轮询应设置总时限和间隔，不要高频请求。
- HTTP 200、CLI 退出码 0 或响应 `code: 0` 只表示本次请求被接受。最终状态、目标文件和内容仍需回读。

## 5. v0.3.3 / v0.3.4 已验证能力与限制

以下命令可用于更精细的读取：

```bash
$WPS drive doclib list --page-size 100
$WPS airpage get <file_id>
$WPS airpage block get <file_id> --block-id <block_id>
$WPS airpage create --drive-id <drive_id> --parent-id <folder_id> --name "标题.otl" \
  --template-id "" --on-name-conflict rename
```

注意：

- AirPage v2 数据结构主要使用 `snake_case`，正文层级可能在 `doc_children` 中，标题字段与正文块分离。
- v2 在根块创建子块时使用 `block_id` 与 `doc_children.children`；不能把 v1 convert 结果直接塞进
  `content`。v2 `title` 独立于 children，统计时不要重复计算。
- `airpage block create` 只写**一段纯文本**。以下两条是实测结论，不是"可能"：
  - 内容带换行 → 报 `400445004 InvalidInlineElement: newline is only allowed in text within code_block`；
  - 传 Markdown（如 `# 标题 含**加粗**`）→ 返回 `code:0`，但**原样存成字面字符**，回读 bold runs 为空。
- 省略 `--index` 时**插到首位**，不是追加：连写三次得到的是倒序。要追加必须先
  `airpage block get` 读出当前 `doc` children 数量，再显式传给 `--index`，写后回读确认位置。
- 灌 Markdown 文档一律走 `scripts/airpage_put.py`（convert → create），它才会把标题/表格/粗体真正转成块。
- CLI 没有覆盖所有二进制上传细节；上传请用 `scripts/drive_upload.py`。
- AirPage 导出通常是“创建导出任务 → 轮询 → 获取下载 URL”，不是一次命令立即返回文件。

## 6. 常见故障定位

### `400008009`

通常是 `file_id` 与 `drive_id` 不配对。回到搜索结果、短链解析或 `file-path get`，找出真实盘符。不要先重登。

### 命令成功但没有产物

检查输出是否其实是帮助页；若为异步任务，检查任务状态；若为创建，列出目标目录并核对名称、类型与路径。

### 短链可打开但 CLI 找不到

短链可能指向团队盘或别人共享盘。先解析短链元信息，再保留返回的 `drive_id + file_id`；不要用默认企业盘硬套。

### 升级后行为仍旧

运行 `hash -r`、`type -a wps365-cli` 和绝对路径版本检查，排除 shell 命令缓存或多个二进制并存。

## 7. 维护本 skill 的脚本

AirPage 脚本的认证、请求、短链解析和块遍历共用 `scripts/_airpage_common.py`。新增脚本应优先复用公共 helper，不复制 token 读取、HTTP 错误处理或附件解析逻辑。

`upload_attachment()` 的统一签名是 `(file_id, path, upload_name)`。历史上曾出现参数顺序相反的同名实现，
会让文件名与内容静默对调且仍返回 `code:0`；不要重新引入副本。`airpage_put.py` 和
`drive_upload.py` 则刻意保留单文件示例式 `cli()` 与 `sys.exit` 语义，不应机械改成公共 helper。

变更脚本后至少运行：

```bash
python3 -m pytest skills/wps365-cli/tests
```

同时检查 `--help`、preview/apply 边界、错误码语义和敏感信息脱敏。
