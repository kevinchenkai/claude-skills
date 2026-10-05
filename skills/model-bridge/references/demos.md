# 使用样例

五个真实场景 + 一组反面样例，输出为 2026-10-05 实跑快照（Codex 0.160.0 / Claude Code 2.1.289 /
Cursor Agent 2026.10.01）。模型回答较长的地方只**节选**并标注，没有改写措辞。
材料都在 [`../examples/`](../examples/)，可以原样复现；`SKILL_DIR` 指本技能目录：

```bash
SKILL_DIR=~/Work/claude-skills/skills/model-bridge
BRIDGE="$SKILL_DIR/scripts/call.py"
E="$SKILL_DIR/examples"
```

每个样例的重点不是「怎么敲命令」，而是**调用方拿到结果之后该怎么读**。

---

## 样例 1：请 Codex 评审一份方案

**场景**：一份给订单查询接口加进程内缓存的方案（[`cache-plan.md`](../examples/cache-plan.md)），
里面埋了几个常见的坑，上线前想要一个独立视角。

```bash
python3 "$BRIDGE" run codex --task plan-review \
  --model gpt-6.1-sol --effort medium \
  --prompt-file "$E/cache-plan-request.txt" --context "$E/cache-plan.md"
```

返回的 `result.json`：`status: ok`，`requested_model: gpt-6.1-sol`，耗时 **55 秒**。答案（节选前两条）：

> 1. **多实例失效不一致，可能长期返回旧订单**
>    - **触发条件：**实例 A、B 都缓存了订单，PUT 落到 A；A 删除缓存后，B 仍直接返回旧值。
>    - **可行修正：**……采用共享缓存或可靠的跨实例失效机制，覆盖所有写入口。TTL 可限制陈旧时间，但不能单独保证修改后立即读到新值。
> 2. **“修改成功后删除”存在并发回填竞态**
>    - **触发条件：**GET 未命中并读到旧值；PUT 随后提交并删除 key；该 GET 最后把旧值写回缓存。
>
> ……（另 4 条：缓存无容量上限、只按订单 id 缓存可能绕过权限、全量发布无开关、5 分钟 P95 验收证明不了持续达成）

**这一条给了你什么**：每条都带「依据」「触发条件」「可行修正」，因为 `plan-review` 任务就是这么要求的
（见 `scripts/call.py` 的 `TASKS`）。它不会去改你的方案——评审默认只读。

---

## 样例 2：两家评审同一份方案，看分歧

**场景**：同一份方案，再请 Cursor 上的 Grok 4.7 看一遍。材料与请求**完全相同**，
这样两份意见才有可比性。

```bash
python3 "$BRIDGE" run cursor --task plan-review \
  --model grok-4.7-high \
  --prompt-file "$E/cache-plan-request.txt" --context "$E/cache-plan.md"
```

耗时 **144 秒**（样例 1 是 55 秒）。Cursor 的 effort 编码在模型 ID 里，所以写 `grok-4.7-high`，
不能写 `grok-4.7 --effort high`（见样例 5）。

两家的结果对照：

| 问题 | Codex | Grok 4.7 |
| --- | --- | --- |
| 多实例失效不一致 | ✅ 第 1 条 | ✅ 第 1 条 |
| 回填竞态 | ✅ 第 2 条 | ✅ 第 2 条（并补充「其他写路径不会删缓存」） |
| 缓存无上限、内存涨 | ✅ | ✅ |
| 只按 id 缓存的权限/串响应风险 | ✅ | ✅（并指出就地修改缓存对象会污染缓存） |
| 全量发布无开关 | ✅ | ✅ |
| 验收无法证明目标 | ✅ | ✅ |
| **轮询下命中率撑不住 P95** | — | ✅ 独有，给了 `1 - 4/R` 的估算 |
| **先约定一致性契约（允许多久的陈旧）** | ✅ 独有 | — |
| **同一未命中 key 的并发回源合并** | — | ✅ 独有 |

**怎么读**：重合的部分（Codex 提的六条 Grok 全部也提到了）可信度最高，优先处理。
只有一家提的，不是「错」，而是**需要你自己核对**——例如 Grok 的 `1 - 4/R` 是在
「同一订单的读取均匀分散到 4 个进程」的假设下推出来的，假设成不成立要看真实访问分布。
调用方应当分别报告两家的意见和分歧，而不是只挑一家。评审意见**不是修改授权**：
哪一条要改、怎么改，由你决定。

---

## 样例 3：请 Claude 审一个 diff

**场景**：[`safe_divide.diff`](../examples/safe_divide.diff) 的 docstring 写着「除数为 0 时返回 None」，
代码却写成了 `return 0`。把**调用合同**放进请求里，让审查者有东西可对。

```bash
python3 "$BRIDGE" run claude --task code-review \
  --model claude-sonnet-5-5 --effort medium \
  --prompt-file "$E/safe_divide-request.txt" --context "$E/safe_divide.diff"
```

耗时 **9 秒**。答案（节选）：

> **[高] `calc.py:3-4`：除数为 0 时返回 `0`，违反 docstring 合同（应返回 `None`）**
> - 触发条件：`safe_divide(a, 0)`……
> - 影响：调用方按合同用 `if result is None` 判断除零，会漏判……`0` 与 `safe_divide(0, 5) == 0` 无法区分……
>
> **验证边界**：只依据所附 diff 评审，没有读取 `calc.py` 的完整文件、调用方代码或测试，也没有运行任何代码。

**这一条救了什么**：没有调用合同，`return 0` 看起来完全合理。把合同写进请求，审查者才能判断「对不对」。
另外注意最后一段——Claude 文本调用**关闭了全部工具**，只能审你交给它的材料，它老老实实报告了
自己没读完整文件。需要它看更多代码，就多传 `--context`，别指望它自己去翻。

> 💡 第一次跑这个样例时，Claude 指出 diff 的 hunk 头（`@@ -1,4 +1,8 @@`）与实际行数对不上，行号只能估算。
> 我们据此把样例修成了正确的 `@@ -1,2 +1,5 @@`——材料自身的瑕疵也会被审出来，所以材料要准备干净。

---

## 样例 4：请 Codex 出图，再编辑

**文生图**：

```bash
python3 "$BRIDGE" run codex --task image --model gpt-6.1-sol --effort medium \
  --prompt '生成一张写实摄影：深秋清晨的山间古寺，石阶覆满红叶，钟楼隐在薄雾中，柔和逆光，16:9 横幅，无文字无水印。'
```

**91 秒**，产物是 1672×941 的 PNG。`result.json` 的 `artifacts` 给出路径、格式、字节数和 SHA-256：

```json
{"path": ".../artifacts/autumn-mountain-temple.png", "format": "png",
 "bytes": 3105053, "sha256": "c23f649e…"}
```

**用上一张当参考做编辑**（`--image` 可重复）：

```bash
python3 "$BRIDGE" run codex --task image --model gpt-6.1-sol --effort medium \
  --image /absolute/path/autumn-mountain-temple.png \
  --prompt '保留构图与主体，改为夜晚，寺院灯笼点亮，其余不变。只生成一张。'
```

**82 秒**。左：原图；右：编辑结果（均缩到 960px 的 JPEG，原件为 PNG）。

| 原图 | 编辑后 |
| --- | --- |
| ![原图](../assets/demo-temple-day.jpg) | ![编辑后](../assets/demo-temple-night.jpg) |

构图、石阶、钟楼和树的位置都保持，只换成了夜景和灯笼。

**这一条的重点是「成功」怎么判**：脚本不只看「有没有一个 PNG」。它要求产物的 SHA-256
能在 Codex 的 `~/.codex/generated_images/` 里找到**本次运行期间**写入的同哈希文件，
并且不能与 `--image` 参考图相同——所以代码画的图、原样回传的参考图、历史上生成过的旧图都不会被当成成功。
这个校验依赖 Codex 的内部目录，Codex 升级后路径变了会**失败闭合**并给出提示，不会放行。
**尺寸由 Codex 自己定**：这里要求 16:9，实得 1672×941，不是整数比，需要精确尺寸请自己后处理。
最后一步仍是人看图——脚本验证的是「真实栅格图 + 来源可信」，不是「画面对不对」。

---

## 样例 5：反面样例——该拒绝的它真的拒绝了

这些都是**调用前就被拦下、没有发出模型请求**的情形，每条都有对应的真实输出。

**① Claude 的 effort 写错**：Claude CLI 对未知值只打印 warning、退出码 0、悄悄用默认档，
等于换掉了你指定的档位。脚本直接拒绝：

```bash
python3 "$BRIDGE" run claude --effort ultra --prompt x
```
```json
{"status": "error", "error": "Claude 的 --effort 只支持 low/medium/high/xhigh/max；ultra 会被 CLI 静默忽略，已拒绝。"}
```

**② Cursor 的 effort 用法不对**：本账号的 effort 编码在模型 ID 里，不存在 `grok-4.7` 这个裸 ID。
脚本不去猜、不自动换：

```bash
python3 "$BRIDGE" run cursor --model grok-4.7 --effort high --prompt x
```
```json
{"status": "error", "error": "Cursor 的 effort 通常编码在模型 ID 里，请直接用如 grok-4.7-high 这样的 ID（可用 cursor-agent --list-models 查看）；auto 不接受 effort。"}
```

**③ 子调用再委派**：被调用的模型不能再去调别的模型。环境里带着深度标记就拒绝：

```bash
MODEL_BRIDGE_DEPTH=1 python3 "$BRIDGE" run codex --prompt x
```
```json
{"status": "error", "error": "子调用禁止再次委派（MODEL_BRIDGE_DEPTH=1）；请让主调用方决定下一次任务。"}
```

**④ 参考图不存在**：

```bash
python3 "$BRIDGE" run codex --task image --image /nonexistent.png --prompt x
```
```json
{"status": "error", "error": "参考图片不存在：/nonexistent.png"}
```

**⑤ 模型名不存在，原因要给真的**：这一条**会**发出调用，但 Cursor 在启动时就拒绝了。
早期版本只回一句笼统的「未收到预期的 JSON」，真实原因被吞；现在 `error` 取 stderr 首行
（截断到约 300 字符，Cursor 的模型列表很长），完整输出仍在 `stderr.txt`：

```bash
python3 "$BRIDGE" run cursor --model nope-model --prompt x
```
```text
status: error
error:  Cannot use this model: nope-model. Available models: auto, gpt-5.3-codex-low, …
```

**这组样例的共同点**：失败**不会**悄悄变成成功，也不会自动换模型、换认证或改走收费 API。
想知道某次调用到底发生了什么，看那次的 `~/.cache/model-bridge/<provider>-<时间>-<随机>/`
下的 `request.txt`（实际发出去的请求）、`stdout.txt` / `stderr.txt`（CLI 原始输出）和 `result.json`。

---

## 没有样例的部分

**Grok CLI** 暂无实跑样例：本机账号的 Grok Build 额度用尽（`402 usage balance exhausted`），
成功路径只有离线假 CLI 测试覆盖。额度恢复后再补。
