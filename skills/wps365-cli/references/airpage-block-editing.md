# AirPage 已有正文块的安全替换协议

只在修改**已有**智能文档正文、且不能靠新建文档解决时读取。当前已验证的封装是
`scripts/airpage_fix_markdown_bold.py`：把顶层段落或引用中的字面量 `**文字**` 转成原生加粗。
它不是通用富文本编辑器。

## 结论

2026-08-27 实测，`POST /v7/airpage/{file_id}/blocks/update` 对普通 paragraph 仍返回
`1002 invalid operation`。以下三种形状均失败：

```json
{"blockId":"<id>","block":{"type":"paragraph","content":[]}}
{"blockId":"<id>","type":"paragraph","content":[]}
{"blockId":"<id>","content":[]}
```

可工作的原子步骤是：**同位置创建替换块，再按父块的子区间删除旧块**。

## 已验证请求顺序

1. 查询最新顶层 blocks，定位旧块 id 和当前 index；
2. 递归移除替换块里的所有 `id`；
3. 在旧块当前 index 创建替换块：

```json
{
  "blockId": "doc",
  "index": 12,
  "content": [{"type":"paragraph","content":[]}]
}
```

上面整个对象需 JSON → base64，作为 `blocks/create` body 的 `arg`。

4. 立即回读；新块应位于 index 12，旧块 id 应移到 index 13；
5. 删除旧块时，必须以父块 `doc` 指定半开区间：

```json
{"blockId":"doc","startIndex":13,"endIndex":14}
```

把旧子块 id 当作 `blockId` 并省略 `startIndex/endIndex` 会报
`Invalid parameter: startIndex or endIndex is invalid`。

6. 再次回读，确认旧 id 消失、新块仍在预期位置。

每次操作前重新按 id 定位，不沿用较早读取的 index；这样能发现协作者插入内容导致的位置变化。
如果同一目标块内容本身发生变化，停止而不是覆盖。

## 为什么脚本默认只预检

替换由 create + delete 两个请求组成，不是事务。create 成功而 delete 失败时，正文会暂时出现一新一旧
两块。脚本会明确报出旧 block id；下次只有同时传 `--apply --resume-partial`，且旧块前一位与预期
替换块去除 id 后完全相同，才会只删旧块。不要在状态不明时盲目重跑 create。

## 粗体转换边界

- 只处理顶层 `paragraph` 和 `blockQuote`；
- 每个 text 节点中的 `**…**` 必须配对，支持一个节点内多对；
- 命中文字继承原 text attrs，并额外设置 `bold:true`；
- 三连星号、嵌套或未配对标记直接拒绝；
- `codeBlock`、表格等其他块里的星号不改，只计入 ignored；
- 目标块含 `rangeMarkBegin` / `rangeMarkEnd` 时拒绝修改。

最后一条很重要：rangeMark 是评论/批注锚点。创建替换块时服务端不允许重新插入这种锚点，直接
去掉会让批注脱锚，所以修改已有文档时不能沿用“跨文档复制时删 rangeMark”的策略。

## 验收不变量

应用后至少同时满足：

1. 可处理块中不再有字面量 `**`；
2. 全文 text 拼接值等于预检时按规则去标记后的文本；
3. 除 text 外的 block 类型计数不变；
4. picture `attrs.sourceKey` 集合不变；
5. `export_to_json.attachment_list` 的附件 ID 集合不变；
6. 每个旧 block id 已消失。

可选的 `--backup-dir` 会保存 `before.json`、`after.json` 和 `result.json`，便于审计；它只是快照，
不是自动回滚机制。备份目录可能含文档正文，不要放进 Git。
