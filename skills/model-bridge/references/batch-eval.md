# 批量评审 / 标注（多模型、多样本）

适用：把几十到几百个**相互独立**的小样本（对局决策点、答案对、标注项）交给一个或多个目标模型打分/标注，再统计一致性。
一次调用 = 一批样本（不要每个样本调一次：CLI 启动与登录开销远大于推理），入口仍是 `scripts/call.py run`；
可直接用 [`examples/batch_ask.py`](../examples/batch_ask.py)（分批、并发、跳过已成功的批、解析 JSON 数组）。

## 1. 先确认精确模型 ID（用户口头说的名字常和 CLI 里的 ID 不同）
| 目标 | 怎么查 | 备注 |
|---|---|---|
| cursor | `cursor-agent --list-models` | effort 在 ID 里。例：口头"cursor-grok-4.7-high" = `grok-4.7-high`；`gpt-5.6-luna-medium`、`cursor-grok-4.5-high` 等都在列表里 |
| codex | `~/.codex/models_cache.json` 里的 `slug` | 例：`gpt-6-luna`、`gpt-6-sol`、`gpt-6.1-sol`、`gpt-5.6-luna`；effort 用 `--effort` |
| grok | `grok models` | `grok-4.7` + `--effort high` |
| agy | `agy models` | `gemini-3.8-flash-medium` 等，档位写在 ID 里 |

## 2. 实测耗时（2026-10-08，每批 10 个决策点，输入约 2.4k token，输出为 JSON 数组）
| 目标 / 模型 | 单批耗时（均值 / 中位 / 最大） | 备注 |
|---|---|---|
| codex `gpt-6-luna` medium | 33 / 34 / 48 s | 稳定；有 token 用量 |
| agy `gemini-3.8-flash-medium` | 25 / 18 / 76 s | 最快；无失败；agy 非只读，只给它自己的提示词材料 |
| cursor `gpt-5.6-luna-medium` | 53 / 52 / 73 s | 用量字段为空 |
| cursor `grok-4.7-high` | 411 / 397 / 553 s | **12 批里 2 批超过默认 600 s 超时** → 批量时 `--timeout 1500` |
| grok `grok-4.7` high | 约 327 s / 5 个决策点 | 推理很长（输出 token 约为输入的 1.6 倍）；用小批（5）+ `--timeout 1500`；平凡问题也要 ~47 s |
慢模型放进单独的批次/并发池，不要和快模型一起排队等。

## 3. 写法要点（都是这次踩过的）
1. **一批 ≤10 个样本**，每个样本带唯一 id；要求"只输出一个 JSON 数组，每个元素含 id"。解析用正则取第一个 `[...]`，取不到或 status≠ok 的批按失败处理。
2. **`--output-dir` 必须是尚不存在的目录**：重跑前先删掉自己建的残目录；**超时也会留下 `result.json`（status=timeout）**，所以"已有结果"要看 `status == "ok"`，不能只看文件存在。
3. 并发 4–6 即可；慢模型 3–4。一家失败不要掩盖另一家的成功，分别记录。
4. **偏差控制**：A/B 位置随机并记录；同一批再跑一遍把 A/B 对调，用"对调前后选到同一实质动作的比例"衡量稳定性；保持样本盲评（不告诉模型哪个来自谁）。
5. **提示词写规则时要核对实现**：模型在规则细节上会一本正经地错（如炸弹大小顺序）。把你声称的规则对照真实数据/引擎核一遍再写进提示词。
6. 记录：模型 ID/effort、提示词版本、日期、原始回复（`result.json` 已含），别只留统计。
7. 材料边界：只给与任务相关、允许外发的内容（对局状态可以；代码、凭据、内部文档不要）；agy 不是只读，不给不可信材料。
8. 评审者的"一致性"和"对真值的对齐"是两回事：先看两遍一致率和模型间一致率；真值如果只是聚合层面的（不是逐样本），只能当"有没有信号"用，别当准确率。

## 4. 调用示例
```bash
python3 examples/batch_ask.py --items items.jsonl --template template.txt \
  --models codex:gpt-6-luna:medium,agy:gemini-3.8-flash-medium: --batch 10 --concurrency 4 --out /abs/new_dir
# 慢模型单独、小批、长超时
python3 examples/batch_ask.py --items items.jsonl --template template.txt \
  --models grok:grok-4.7:high --batch 5 --concurrency 4 --timeout 1500 --out /abs/new_dir2
```
