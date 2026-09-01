# 智能文档创建、复制、导出与验收

本文件覆盖 AirPage/智能文档的通用工作流。富媒体协议细节见 [airpage-rich-media.md](airpage-rich-media.md)，定点修改见 [airpage-block-editing.md](airpage-block-editing.md) 和 [airpage-existing-doc-insertion.md](airpage-existing-doc-insertion.md)。

## 1. 创建纯 Markdown 智能文档

优先使用确定性脚本：

```bash
python3 scripts/airpage_put.py <folder_id> "文档标题" /abs/path/content.md \
  --drive <drive_id>
```

脚本应负责创建 `.otl`、转换 Markdown、写入正文和回读验收。只有排查协议或维护脚本时，才直接研究底层 create/convert/upload 请求。

创建前先列目标目录并处理同名：

- 需要跳过：确认同名文档内容符合目标，再报告已存在。
- 需要新副本：使用明确的新名称。
- 需要替换：必须有用户授权，并采用可恢复或受控流程。
- API 返回 `name conflict` 时，不得把旧文件链接当成本次新建结果。

文档名称必须带 `.otl`。接口按最后一个 `.` 判断扩展名，所以 `00.报告` 这类带编号点号的名称也要
显式补成 `00.报告.otl`；`drive file create --file-type otl` 不能替代 AirPage 创建接口。

API 创建只设置文件名，正文 `title` block 仍可能为空，网页显示 `Enter title`。Markdown 的 `# H1`
会转成 heading，不会自动写 title；这不是正文插入失败。首次在网页打开时，编辑器可能用第一个 H1
补 title，并同步改写文件名和版本，因此依赖数字前缀排序时要再次核对名称。不要因 title 为空重复灌正文。

### 仅用于诊断的底层流程

底层通常包含：创建空 AirPage → Markdown 转内部块 → 分批上传块/正文 → 回读。纯 Markdown 转换结果
若带 `attachments`，说明含图片占位；`airpage_put.py` 应删除本次空壳并让调用方改走富媒体脚本。
转换后的请求体可能较大，分片阈值和块层级应由脚本维护，不能把 Markdown 原文塞进普通文本块来替代转换。

## 2. 发布图片和附件

```bash
python3 scripts/airpage_publish.py <folder_id> "文档标题" /abs/path/content.md \
  --drive <drive_id>
```

发布前确保 Markdown 中的本地资源使用可解析路径。脚本会创建文档、解析资源、上传附件并替换占位块；协议、图片块、附件块、哈希和失败恢复见 [airpage-rich-media.md](airpage-rich-media.md)。

## 3. 跨盘复制智能文档

官方同盘批量复制可以保留更多内部结构；跨盘或共享来源复制使用：

```bash
# 只读预览
python3 scripts/airpage_copy.py <src_drive_id> <src_file_id> \
  <dst_drive_id> <dst_folder_id>

# 确认后执行
python3 scripts/airpage_copy.py <src_drive_id> <src_file_id> \
  <dst_drive_id> <dst_folder_id> --apply
```

复制脚本应：

1. 解析来源真实 `drive_id + file_id`，读取但不修改原件。
2. 预览来源标题、块数量、媒体数量和目标路径。
3. 在目标盘创建新文档并重建正文结构。
4. 重新上传目标盘需要的图片/附件，不能沿用来源盘的私有资源 ID。
5. 回读目标块结构，比较文本、关键块类型、媒体数量和资源可用性。

目标边界：正文、常见格式、表格、图片和附件应尽量保真；评论锚点（rangeMark）、历史版本、原分享权限、
协作者和部分隐藏元数据通常不会复制。rangeMark 不含正文，目标创建接口会拒绝它，复制脚本会移除并在
结果中说明。若同盘 batch-copy 对共享来源返回 `code:0` 却迟迟没有目标产物，不要不断重试；改走重建复制。

复制脚本按序列化体积分批（约 9KB）；不可拆分的大 table 单块发送。若来源附件清单含非图片附件、
孤立附件或与 picture sourceKey 不闭合，脚本停止而不是猜测。

图片服务可能规范化图片字节或尺寸元数据，因此不能只比较上传前后的原始文件哈希。优先比较块类型、可访问性、像素维度/像素哈希和视觉内容。

## 4. 修改现有文档

修改现有文档必须先 preview，再 `--apply`：

```bash
python3 scripts/airpage_fix_markdown_bold.py <file_id>
python3 scripts/airpage_fix_markdown_bold.py <file_id> --apply

python3 scripts/airpage_insert_images.py <drive_id> <file_id> /abs/path/figure.png
python3 scripts/airpage_insert_images.py <drive_id> <file_id> /abs/path/figure.png \
  --after-heading "目标章节" --apply

python3 scripts/airpage_add_references.py <drive_id> <file_id> /abs/path/refs.json
python3 scripts/airpage_add_references.py <drive_id> <file_id> /abs/path/refs.json --apply
```

脚本使用说明和定位边界见对应专题参考。修改后必须回读实际命中块，确保没有误改代码块、链接或相似文本。

## 5. 结构化验收

Markdown 回读只适合文本。以下内容必须检查块结构或导出物：

- 表格行列、合并关系和单元格文本。
- 图片块、附件块及其资源状态。
- `WPSDocument` 或嵌入对象。
- 标题层级、列表、引用和复杂布局。
- 复制前后的块类型分布与关键顺序。

可用：

```bash
$WPS airpage get <file_id>
$WPS airpage block get <file_id> --block-id <block_id>
$WPS drive file-content get <drive_id> <file_id> --format markdown
```

AirPage v2 常见字段使用 `snake_case`，正文子块可能在 `doc_children` 中。不要假设所有块都在单一 `children` 字段。

低层 v1 `blocks` 是 POST 且返回 base64；`blocks/batch_get` 请求字段为复数 `blockIds`，结果在
`data.results`。解码管道失败只证明读法有问题，不能据此重插正文。

## 6. 导出 DOCX

优先使用 v0.3.4 精装命令：

```bash
$WPS airpage export create <file_id> --format docx -o json
$WPS airpage export get <file_id> --format docx \
  --version <version> --task-id <task_id> -o json
```

`version` 从 `$WPS airpage get <file_id> -o json` 的文档元数据取得；不要凭空猜版本。

智能文档导出是异步协议：

1. 提交导出任务，格式指定 DOCX。
2. 保存返回的 task id。
3. 轮询任务状态，直到成功、失败或超时。
4. 获取一次性签名下载 URL。
5. 下载到临时路径并验证，再移动到用户目标路径。

第一次查询为 Building、URL 为空通常是正常状态；只有达到轮询上限仍未完成才判失败。精装命令不可用时，
低层 `export_to_docx` 请求的 `attrs`、`version`、`ai_check` 三个字段都必填。

完成后的签名 URL 不需要 WPS Bearer token。不要用会把 `&` 转义成字面量的输出路径提取 URL；从原始
JSON 安全解析。若下载得到约几百字节的 XML `AccessDenied`，先检查 URL 是否被改写。下载后检查：

```bash
file /abs/path/output.docx
unzip -t /abs/path/output.docx
```

对关键文档再检查 OOXML：`word/document.xml` 存在、正文非空、图片关系和 `word/media/` 数量合理。必要时渲染 DOCX 做视觉验收。不要只根据扩展名判断成功，防止把 JSON/HTML 错误响应保存成 `.docx`。

## 7. API 能力边界

- `airpage create/get/block get` 已适合基础读取和空文档创建；Markdown 抽取属于 `drive file-content get`。
- 单次 `airpage block create` 不适合作为完整 Markdown 导入器。
- 复杂块、富媒体、复制和导出应走仓库脚本或已验证协议。
- 已验证低层能力包括 docx/pdf/json 导出、blocks、batch_get、convert、create 和按父块区间 delete。
- `import_json_data`、通用 blocks/update、blocks/batch_delete 等不得默认假设可用。
- 未验证的新端点先对照本地 `api.yaml`，用只读或临时文档最小验证，再纳入脚本和测试。
