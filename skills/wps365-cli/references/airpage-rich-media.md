# AirPage 富媒体报告发布协议

只在 Markdown 含本地图片，或报告同时包含大量图片、表格、长 prompt 时读取。普通纯文本建档继续用
`scripts/airpage_put.py`。若目标是给**已有**文档补图，不要重建整篇报告，改用
`scripts/airpage_insert_images.py` 和
[`airpage-existing-doc-insertion.md`](airpage-existing-doc-insertion.md)。

> ⚠️ `airpage_publish.py` 和 `airpage_insert_images.py` 需要 **Pillow**（`pip install Pillow`，
> 用于读图片原始宽高）；缺了会给出明确提示而不是 traceback。

## 已验证场景

2026-08-26 在两份生产报告上实测：

- 五模型文生图对比：21 张原生图片、多个表格与 prompt；
- MiniMax-H3 文生视频复现：19 张原生图片、18 个完整 prompt code block、5 张表格，
  文档约 3.3MB。

两份文档均以 blocks + `export_to_json` 回查，图片的 `sourceKey` 与附件 ID 一一闭合。

## 为什么普通 Markdown 流程不够

`POST /v7/airpage/{fid}/blocks/convert` 遇到 Markdown 图片时会返回：

- 一个 `picture` block；
- `attachments` 映射，记录 picture block id 与原始 URI。

它不会读取本地文件、不会上传二进制，也不会自动填有效的 `attrs.sourceKey`。因此不能把
convert 结果直接 create 后就宣称图片发布成功。实测 `anchor_attachment_replace` 不能把这种空壳图片
补成原生可导出附件，不要走这条回填路径。

## 正确顺序

优先调用 `scripts/airpage_publish.py`。需要调试协议时，顺序必须是：

1. 用 `/v7/airpage/files` 建空 otl，推荐 `on_name_conflict:"fail"`；
2. 按 H2 将 Markdown 切为不超过 17.5KB 的块，并逐块 convert；
3. 从每块 convert 返回的 `attachments` 收集 URI，按 Markdown 文件所在目录解析本地路径；
4. 每个唯一图片只上传一次，记录 `URI → attachment_id`；
5. 递归定位 convert blocks 中对应的 picture block，填 `attrs.sourceKey`、原始宽高、渲染宽高和
   `version:3`；
6. 按原顺序 create blocks；
7. 回读 blocks 并调用 `export_to_json`，做结构闭环；
8. 用 `drive file-path get` 确认实际云端路径。

如果任一步失败，删除本次新建的半成品文档。清理目标只能是本次调用返回的精确 file id。

## 图片附件三步协议

### 1. 申请上传地址

```text
POST /v7/coop/files/{file_id}/attachments/upload/address
token-type: delegated
```

body：

```json
{
  "name": "<稳定且唯一的图片名>",
  "size": 123456,
  "content_type": "image/jpeg",
  "md5": "<图片二进制 md5>",
  "internal": false
}
```

响应提供 `upload_id` 与 `request.{method,url,headers}`。

### 2. 上传二进制

按响应给出的 method、url、headers 原样 PUT/POST 图片。完成时必须读取**存储服务响应头**，不能用申请
上传地址时的请求字段代替：

- `etag`；
- `newfilename`，若没有则读取 `x-asimov-request-id2`。

### 3. 完成附件

```text
POST /v7/coop/files/{file_id}/attachments/upload/complete
token-type: delegated
```

body：

```json
{
  "upload_id": "...",
  "params": {
    "etag": "<存储响应头 etag>",
    "key": "<newfilename 或 x-asimov-request-id2>"
  }
}
```

保存响应中的 `attachment_id`，它就是 picture block 的 `attrs.sourceKey`。

## Picture block 绑定

convert 返回的 `attachments` 形如：

```json
{
  "<旧 picture block id>": [
    {"uri": "outputs/filmstrips/C-001.jpg"}
  ]
}
```

递归遍历 blocks，命中该 block id 后写入：

```json
{
  "attrs": {
    "sourceKey": "<attachment_id>",
    "width": 1920,
    "height": 360,
    "renderWidth": 740,
    "renderHeight": 139,
    "version": 3
  }
}
```

渲染尺寸按原比例缩放，建议最长边不超过 740；不要覆盖原始 width/height。相同 URI 重复出现时只需上传
一次，但会有多个 picture blocks 共享一个 sourceKey。不同目录下同名文件不能仅按 basename 关联，应以
convert 返回的完整 URI 为键。

当前脚本只接受本地图片；HTTP(S) 图片先显式下载为受控本地资产，再发布。这样才能做二进制哈希、尺寸
校验和附件闭环。

## 长文分块

- 优先在 `##` 边界切分，单块保守限制为 17.5KB；
- 不要把 fenced code block 从中间切开；
- 如果单个 H2 章节已经超过限制，先在源 Markdown 中拆成多个 H2/H3 章节，不要静默截断；
- 所有 chunk 都插入到 `blockId:"doc"` 的末尾，保持原顺序；
- convert 上限与“原生 blocks 跨文档复制”的安全块大小不是一回事；跨盘复制脚本仍按约 9KB
  的已验证请求体经验值分块，见 [`airpage-workflows.md`](airpage-workflows.md)。

## 验收闭环

发布成功至少满足：

1. 回读真实 blocks，递归统计 `picture`、`table`、`codeBlock` 等关键类型；
2. picture block 数等于 Markdown 中实际出现次数；
3. `export_to_json.attachment_list` 的附件 ID 集合，等于所有 picture `attrs.sourceKey` 的唯一集合；
4. 表格数、code block 数与 convert 阶段的发送值一致；
5. `drive file-path get` 返回用户指定目录；
6. 对展示关键的总览图、横图、竖图至少各抽一张做本地视觉检查。

注意：重复使用同一图片时，picture block 数可以大于附件数；应比较 sourceKey 的**唯一集合**，不能强求
两个数量相等。`file-content get --format markdown` 仍会丢表格，也不能证明图片附件闭合。

## 失败与重试

- 创建时优先用 `on_name_conflict:"fail"`，避免不知情地产生 `(1).otl`；
- 上传、转换、插入或验收任一步失败，删除本次精确 file id；
- 如果上一次执行结果不确定，先按文件名搜索并用 `file-path get` 确认，不能盲目重跑；
- `code:0` 只表示接口调用被接受，不表示图片可见、表格齐全或路径正确。

上面“失败就删除半成品”只适用于本脚本刚创建的新文档。已有文档不可这样清理；附件上传成功但插块
失败时，应按 `export_to_json` 中的附件 SHA1 恢复并复用，禁止删除原文或盲目再传一份。
