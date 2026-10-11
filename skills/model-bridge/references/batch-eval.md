# 批量评审 / 标注（多模型、多样本）

适用：把几十到几百个**相互独立**的小样本（对局决策点、答案对、标注项）交给一个或多个目标模型打分/标注，再统计一致性。
一次调用 = 一批样本（不要每个样本调一次：CLI 启动与登录开销远大于推理）。入口是 `scripts/call.py batch`，
它在内部逐批调用 `call.py run --task label`，认证与计费规则同 SKILL.md。

```bash
python3 "$BRIDGE" batch --items items.jsonl --template template.txt \
  --model-spec claude:claude-haiku-5-5:low:4:10 \
  --model-spec codex:gpt-6-luna:low:4:10 \
  --model-spec grok:grok-4.7:high:3:5 \
  --item-schema item.schema.json --claude-settings project --out /abs/new_or_resume_dir
```

- `items.jsonl`：每行 `{"id": "S001", "text": "…一个样本的完整描述…"}`，id 唯一。
- `template.txt`：含 `{items}`（替换成本批样本，每条一段 `[id] text`），可含 `{ids}`（逗号分隔的本批 id）；
  写明"只输出一个 JSON 数组，每个元素含 id 和……"。
- `--model-spec provider:model[:effort[:并发[:批大小]]]`：可重复或逗号分隔；**每个目标一个独立并发池**，
  慢模型（grok、cursor 的 grok）给小批和低并发，不拖住快模型。缺省用 `--batch`（10）和 `--concurrency`（4）。
- `--item-schema`：单条结果的 JSON Schema（须含 `id`），自动包成 `{"items": [...]}`。claude/codex 用原生结构化输出约束；
  grok/agy/cursor 把 schema 写进提示词，回答在本地校验（`type`/`required`/`enum`/`additionalProperties`/`minimum`/`maximum` 等常用子集）。
  不给 schema 时只校验 id。
- 产物：`<out>/<tag>.json`（id → 回答）、`<out>/<tag>.report.json`（完成数、被拒 id、失败批、是否停下、本次调用数与估算费用）、
  `<out>/<tag>/bNNN[-拆分路径]-aK/`（每次尝试的 `call.py run` 记录）、`manifest.json`。退出码：全部完成或只剩被拒条目为 0，否则 1。

## 1. 失败怎么处理（按 `result.json` 的 `error_kind`）

| error_kind | 处理 | 说明 |
| --- | --- | --- |
| `transient` / `timeout` / `invalid_output` / `unknown_model` / `other` | 重试（`--retries`，默认 1 次） | 格式不对、id 不齐（缺、多、重复）、不符合 schema 都算 `invalid_output` |
| `refusal` | **不重试，二分拆批** | 直到定位到单条，记进 `refused_ids`，其余条目照常拿到结果 |
| `quota` / `auth` / `policy` | **停掉该目标的后续批** | 其他目标不受影响；agy 限额时报告里提示用 `agy-switch` 换账号后重跑续上 |

拒绝是实际遇到过的：Haiku 5.5 的安全过滤会因为一条普通样本拦下整批（10-08 cls 实验里 `train-169` 是一道化学文本翻译题，
报 `can't help with this … [bio]`），重试结果一样。以前的写法会丢掉整批 25 条，现在只丢这一条。

**续跑**：用同样参数重跑同一个 `--out`，已完成的批（包括拆分后的子批）直接跳过，被拒的不再打。
样本、模板、schema 或某个目标的批大小变了会拒绝续跑（`manifest.json` 校验），换一个 `--out`。

**清理**：结果是交付物，留在 `--out`；各次调用在 CLI 里留下的东西（agy 会话、Claude 空项目目录）
用 `call.py prune --older-than 14 --batch-out <out> --apply` 清。Codex 文本调用带 `--ephemeral`，本来就不留会话。

## 2. 先确认精确模型 ID（用户口头说的名字常和 CLI 里的 ID 不同）
| 目标 | 怎么查 | 备注 |
|---|---|---|
| cursor | `cursor-agent --list-models` | effort 在 ID 里。例：口头"cursor-grok-4.7-high" = `grok-4.7-high`；`gpt-5.6-luna-medium`、`cursor-grok-4.5-high` 等都在列表里 |
| codex | `~/.codex/models_cache.json` 里的 `slug` | 例：`gpt-6-luna`、`gpt-6-sol`、`gpt-6.1-sol`、`gpt-5.6-luna`；effort 用 `--effort` |
| claude | 模型 ID 如 `claude-haiku-5-5`、`claude-sonnet-5-5` | effort 只接受 `low/medium/high/xhigh/max` |
| grok | `grok models` | `grok-4.7` + `--effort high` |
| agy | `agy models` | `gemini-3.8-flash-medium` 等，档位写在 ID 里 |

`call.py doctor` 会同时检查各家是否已登录。

## 3. 实测耗时与成本

2026-10-08，每批 10 个决策点，输入约 2.4k token，输出为 JSON 数组：

| 目标 / 模型 | 单批耗时（均值 / 中位 / 最大） | 备注 |
|---|---|---|
| codex `gpt-6-luna` medium | 33 / 34 / 48 s | 稳定；有 token 用量 |
| agy `gemini-3.8-flash-medium` | 25 / 18 / 76 s | 最快；无失败；agy 非只读，只给它自己的提示词材料 |
| cursor `gpt-5.6-luna-medium` | 53 / 52 / 73 s | 用量字段为空 |
| cursor `grok-4.7-high` | 411 / 397 / 553 s | **12 批里 2 批超过默认 600 s 超时** → `--timeout 1500` |
| grok `grok-4.7` high | 约 327 s / 5 个决策点 | 推理很长（输出 token 约为输入的 1.6 倍）；小批（5）+ `--timeout 1500`；平凡问题也要 ~47 s |

Haiku 5.5 对 gpt-6-luna（2026-10-08/09 评测与标注实验，low 档，每批 8–25 条，同时跑 6–8 个任务，倍数只作量级参考）：

| | 每次调用耗时 | 按官方标价算的费用（每千项） | 可用性问题 |
|---|---|---|---|
| claude `claude-haiku-5-5` | 19–32 s | $0.15–0.29 | 安全过滤偶尔整批拒绝（现由二分拆批处理）；偶发键名偏差（`質量分`，8/751） |
| codex `gpt-6-luna` | 53–75 s | $0.05–0.10 | 评测里偶尔不按要求的 X/Y 作答、直接写标签（16 次） |

两者官方单价相同（输入 $0.10、输出 $0.50 每百万 token），Haiku 实际贵约 3 倍：Claude Code 每次约 9–10k token
按 1 小时缓存写入价（输入价的 2 倍）计费，且输出更长。用 `--item-schema` 和 `label` 任务能挡住键名、取值偏差，并减少多余输出。
单次调用的 `result.json` 有 `cost_estimate`（价目表里有的模型），batch 报告汇总为 `cost_estimate_usd_this_run`。

## 4. 写法要点（都是踩过的）
1. **一批 ≤10 个样本**（长样本更少），每个样本带唯一 id。**返回的 id 必须与本批完全一致**才算完成——
   模型偶尔少答几条，只看 status=ok 会悄悄丢样本；`batch` 已按此校验。
2. **用 `label` 任务**（`batch` 固定使用）：`ask` 的"说明事实与不确定项"会让模型在 JSON 外写说明。
   能用 schema 就用 schema：10-08 实验里 luna 把标签当判决写了 16 次、Haiku 把键名写成繁体"質量分"8 次。
3. **超时也会留下 `result.json`（status=timeout）**：自己写批量时，"已有结果"要看 status 和 id 完整性，不能只看文件存在。
4. 并发 4–6 即可；慢模型 2–3。一家失败不要掩盖另一家的成功，分别记录（`batch` 每个目标单独出报告）。
5. **偏差控制**：A/B 位置随机并记录；同一批再跑一遍把 A/B 对调，用"对调前后选到同一实质动作的比例"衡量稳定性；保持样本盲评（不告诉模型哪个来自谁）。
6. **提示词写规则时要核对实现**：模型在规则细节上会一本正经地错（如炸弹大小顺序）。把你声称的规则对照真实数据/引擎核一遍再写进提示词。
7. 记录：模型 ID/effort、提示词版本、日期、原始回复（每次尝试的 `result.json` 都在），别只留统计。
8. 材料边界：只给与任务相关、允许外发的内容（对局状态可以；代码、凭据、内部文档不要）；agy 不是只读，不给不可信材料。
9. 评审者的"一致性"和"对真值的对齐"是两回事：先看两遍一致率和模型间一致率；真值如果只是聚合层面的（不是逐样本），只能当"有没有信号"用，别当准确率。
