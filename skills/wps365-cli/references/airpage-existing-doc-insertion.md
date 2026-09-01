# 已有 AirPage 安全增量插入协议

只在向一份**已有**智能文档追加原生图片或 `WPSDocument` 引用时读取。新建富媒体报告走
`airpage_publish.py`；替换已有正文块走 `airpage-block-editing.md`。

## 授权与目标确认

- 自有盘：用户指定文档并要求修改即可执行。
- 共享盘原件：默认只读；只有用户明确指定目标文档并要求修改时才写入。
- 短链先经 `/v7/links/{link_id}/meta` 解析，`drive_id` 与 `file_id` 必须成对使用。
- 写前调用 `drive file-path get`，把真实云端路径放进预检结果；路径不符就停止。

两个脚本都**默认只预检**，只有显式 `--apply` 才产生云端写入：

```bash
python3 scripts/airpage_insert_images.py <drive-id> <file-id> ./figure.png \
  --after-heading "四、模型训练"
python3 scripts/airpage_add_references.py <drive-id> <file-id> ./references.json \
  --section "参考文档"
```

## 通用事务边界

AirPage 没有覆盖“上传附件 + 插入 block”的单一事务，安全性靠以下顺序建立：

1. 回读顶层 blocks，并用 `export_to_json` 保存附件 ID 与 SHA1；可选 `--backup-dir` 落本地快照。
2. 以**唯一标题文字或 block id**解析锚点，预检时记录 index；禁止把历史 block 总数写死。
3. 写前完成所有权限、类型、输入重复和既有内容幂等检查。
4. 产生外部副作用后、调用 `blocks/create` 前，再回读 blocks；引用插入还要重读附件集合。
5. 预检快照发生任何漂移就停写，不根据旧 index 猜测新位置。
6. 只调用 `blocks/create` 做增量插入，不重建整篇文档。
7. 写后回读真实 blocks，检查新块位于预期切片；移除新块 ID 后，旧顶层 blocks 必须与写前逐项相等。
8. 再次导出附件，核对 `picture.attrs.sourceKey` 唯一集合与附件 ID 集合闭合。

WPS 编辑器可能自动裁掉文末空段落，因此顶层 blocks 从 221 变 220 不等于正文丢失。章节尾插入应从
当前结构解析：找到目标 heading，插在下一个同级或更高级 heading 前；仅把章节末尾空段落视为可越过的
占位，不能依赖它一定存在。

## 已有文档插图

```bash
python3 scripts/airpage_insert_images.py <drive-id> <file-id> ./a.png ./b.jpg \
  --after-heading "四、模型训练" --apply --backup-dir /tmp/wps-images
```

位置参数必须且只能选一个：`--before-heading`、`--after-heading`、`--before-block`、
`--after-block`、`--append`。标题必须精确且唯一；容易重名时用 block id。

图片幂等与恢复规则：

- 本地二进制同时计算 SHA1/SHA256；`export_to_json.attachment_list[].hash.sum` 实测为 SHA1。
- 同 SHA1 的图片已被 picture 引用时默认跳过。明确需要重复展示才用 `--allow-duplicate`。
- 同 SHA1 附件已经上传但没有 picture 引用时，视为上次中断留下的可恢复附件，直接复用。
- 存在与本次输入无关的孤立附件，或同 SHA1 对应多个无法唯一选择的附件时停止，不猜。
- 上传后若 blocks 漂移，附件可能已经留在云端，但没有插入图片；重新运行脚本会按 SHA1 复用它。
- 写后要求所有 picture sourceKey 与所有导出附件 ID 完全闭合，且附件集合只增加本次上传所得 ID。

picture 保存原始 `width/height`，渲染尺寸按比例缩放，最长边默认不超过 740。

## 原生 WPSDocument 引用

输入 JSON 是非空数组：

```json
[
  {
    "url": "https://www.kdocs.cn/l/xxxxxxxx?from=share",
    "category": "任务说明书",
    "description": "环境、数据和验收口径"
  }
]
```

短链域名、query、fragment 都不参与身份判断，统一按 URL path 中的 `/l/{link_id}` 去重。每条引用必须：

1. `links/meta` 为 `status=open`；
2. `drive file get` 可读且文件名以 `.otl` 结尾；
3. `GET /v7/airpage/{file_id}` 返回数字 `data.id`。

原生节点形状：

```json
{
  "type": "WPSDocument",
  "attrs": {
    "version": 1,
    "wpsDocumentId": "<GET /v7/airpage/{file_id} 的数字 data.id>",
    "wpsDocumentLink": "https://365.kdocs.cn/l/<link_id>",
    "wpsDocumentName": "<不含 .otl 的文件名>",
    "wpsDocumentType": "otl"
  }
}
```

不要把 AirPage file id 或短链码填进 `wpsDocumentId`。已有引用同时按规范化 link id 和数字文档 ID
去重。`file-content get --format markdown` 可能不呈现这个节点的文档名或链接，验收必须读 blocks。

引用文档的全文可读，不代表 `links/meta`、`drive file get` 和 AirPage metadata 都有权限。默认任何一条
403/失效/非 otl 都让整批在写前停止；用户明确接受可访问项部分成功时，才使用
`--skip-inaccessible`，并在结果中保留失败条目。

## 报告完成的最低证据

- 写前与写后云端完整路径一致；
- 插入切片的类型、顺序、图片 sourceKey 或 WPSDocument 身份与计划一致；
- 去掉新 block 后旧顶层 blocks 精确保持；
- picture sourceKey 与附件 ID 闭合，引用操作不改变附件集合；
- 结果明确列出 inserted、skipped、failures，而不是只报告接口 `code:0`。
