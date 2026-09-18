# 使用样例

四个真实场景，命令与输出均为 2026-09-18 实跑，未经编造。
每个样例的重点不是「怎么敲命令」，而是**这套规范在什么地方救了你**。

---

## 样例 1：一条「待办」其实早就做完了

**问题**：动作串 token 优化还没落地吧？文档里说在等业主定鼠标键名。

```bash
./scripts/wiki.sh nav tokopt
```

导航直接给出「当前事实」入口：

```
40:- **当前事实**：[V0017D 已落地，鼠标键已定名，MMB/滚轮仍未定]
       (findings/tokopt-landed-in-v0017d-not-pending.md)
```

```bash
./scripts/wiki.sh cat findings/tokopt-landed-in-v0017d-not-pending.md
```

> 动作串 token 优化**早已落地在 V0017D 并实现在代码里**，不是待办；
> 《动作串token优化_v0.2》(2026-07-24) 是**被取代的旧文档**，照它读会凭空造出一个
> "等业主定鼠标键名"的假待决项——鼠标键已定为 `Primary`/`Secondary`

**这一条救了什么**：提问里的前提本身来自一份旧文档。如果按「我记得文档说……」
回答，会凭空产生一个不存在的待决项，甚至可能真的去推动一次不需要的决策。
页面还给出了**仍然真正未定**的部分（MMB/滚轮），以及一个**已知的错误答案**
（`MMB`→`Middle` 会导致 INVALID_KEY，全量 11.35M 行里有 135 条真实 MMB）——
「别抄」三个字是写在页面里的。

---

## 样例 2：读到一页正确的、但已经过期的结论

**问题**：这个项目的 MFU 上限大概在哪？

```bash
./scripts/wiki.sh cat findings/no-run-has-ever-exceeded-mfu-036.md
```

脚本先打出警告，再给正文：

```
>>> 本页 status: superseded，已被取代；引用前先看正文写明被什么取代 <<<
---
status: superseded
superseded_by: ../findings/h200-8card-mbs32-settled-profile.md
---
> **2026-09-18 更新（Hub 亲自上机实测）**：本页标题的「从未超过 0.36」断言已被推翻——
> …在 11,577 步上测得 MFU 均值 0.3617、最新 0.3694、峰值 0.3733，均高于 0.36。
```

**这一条救了什么**：页面正文读起来完全自洽、数据也没错——它描述的是
2026-09-17 之前的历史扫描结果，**本身没有错**，只是标题的断言不再成立。
不看 `status` 就会拿一条已被推翻的结论去做判断。

注意该库的处理方式：**表格和原结论保留不删**，只整页标 `superseded` 并写明
被什么取代。这就是「不静默删除冲突的历史证据」的实际样子。

---

## 样例 3：数字溯源，以及溯源失败时该怎么说

**问题**：MFU 0.3617 这个数字可靠吗？

```bash
./scripts/wiki.sh trace '0.3617'
```

```
### 原始记录 sources/ evaluations/ —— 引用数字以这里为准
（无命中）

### 综述层 experiments/ findings/ topics/ —— 不要只引用这里的数字
experiments/v0017b-hitl02-h200-mbs32.md:128:| **MFU** | **0.3617**（最新 0.3694，峰值 0.3733） | 0.2660 |
findings/h200-8card-mbs32-settled-profile.md:38:| MFU | **0.3617** …
```

**`sources/` 零命中。** 按该库规矩，这时**不能**直接引用这个数字就完事。
打开 findings 页看它自己怎么交代出处：

```yaml
sources:
  - ../sources/experiment-runs/…/assets/training/veomni_cli.runtime.yaml
  - ../sources/experiment-runs/…/assets/training/run_v0017.sh
```

```
### 如何证伪
- check: 读 run `…-h200-mbs32-20260917` 的 TensorBoard，丢弃前 10 步取 mfu 均值
- expect: 本轮均值 0.3617（11,577 步），历史 0.2660
```

**这一条救了什么**：页面是诚实的——它的 `sources:` 指向**配置文件**（证明跑的是
哪个配置），而 MFU 数值本身在 **TensorBoard 里，不在 wiki 的 `sources/` 中**。
所以正确的回答是：

> **事实**：findings 页记载 MFU 均值 0.3617（11,577 步，Hub 2026-09-18 上机实测）。
> **边界**：该数值在本 wiki 内没有原始记录副本，出处是 run 的 TensorBoard；
> wiki 里可核对的是训练配置。要坐实数值本身，按页面「如何证伪」去读 TensorBoard。

把「查不到原始记录」说出来，而不是默默引用，或默默认为数字是假的。

---

## 样例 4：先怀疑检索，再怀疑知识库

**问题**：库里好像没写每张图多少 token？

```bash
./scripts/wiki.sh grep '880 tok'        # 默认域
（无输出）
```

**此时不能下结论。** 默认域不含 `sources/`，而 90% 证据在那里：

```bash
./scripts/wiki.sh grepall '880 tok'     # 含 sources/
```

```
30 条命中
```

**这一条救了什么**：这正是方法论文的头条结论——约 **48–70%** 被报为
「wiki 缺失」的内容其实已经存在，只是检索没命中。第一次搜空，
换个写法或换 `grepall`/`trace` 再确认，再说「库里没有」。

同一个坑的另一种形态：`880` 是纯数字，会命中 `global_step_218800` 这类无关内容；
而 `880 tok`、`880 tokens/image`、`880 视觉 token` 在库里都有人写过。
**换写法比换结论便宜。**

---

## 一个反面样例：不要这样用

```bash
# ❌ 只读命中行就作答
./scripts/wiki.sh grepall '880' | head -3
```

该库的消费模型是**结构路由 + 整篇读**：页面被设计成自包含，跨对象依赖
显式写成 `[[wikilink]]`。只读命中行会丢掉页面自己声明的适用范围、反例和
「如何证伪」小节——样例 1 的「别抄 `Middle`」、样例 3 的「数值在 TensorBoard」
都在命中行之外。

正确做法是 `grep` 定位到**页**，然后 `cat` 整页。
