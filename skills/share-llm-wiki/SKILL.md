---
name: share-llm-wiki
description: Read the team's shared LLM-WIKI (VLA training knowledge base) over SSH on a shared drive — no VPN or SMB mount. Use to answer questions about training experiments, evaluations, datasets, findings and their evidence chain, or to trace a specific metric back to its raw record. Covers VeOmni / Qwen3-VL VLA runs (v0002–v0023), image tokens, MFU, instruction following, inference latency.
---

# Shared LLM-WIKI

团队共享知识库的检索入口。知识库是一个普通目录，**经 `ssh` 访问共享盘即可读，不需要 VPN、不需要 SMB 挂载**。

内容是单个 VLA 训练项目的沉淀：训练实验、评测、数据集、跨实验结论。载体全是 Markdown。

## 🔴 上手前先知道的四条

1. **这是 rsync 副本，不是活 wiki。** 默认路径下**没有 `.git`**，原 wiki 那套「保存即 revision、误覆盖可恢复」的保护**不存在**。→ **按只读用**。写进去既不回流给团队，也恢复不了。先跑 `wiki.sh check`，它会告诉你当前这份有没有 `.git`。
2. **数字必须溯源到 `sources/`。** 这是知识库自己的硬规矩：`sources/` 是原始证据，`experiments/` `findings/` `topics/` 是综述层。**不要引用只在综述里见过的数字**——用 `wiki.sh trace` 会自动把两层分开显示。
3. **`sources/` 明确「不保证当前有效」**，且允许自相矛盾。1491/1607 个文件都在 `sources/` 下。看到冲突是**设计如此**，不要替团队选一个，把矛盾连同各自证据一起报出来。
4. **结论有保质期，`status` 要看。** 存在 `status: superseded` 的页（如「历史上从未有 run 的 MFU 超过 0.36」已被推翻）。`wiki.sh cat` 会在读到 superseded 页时自动警告。

## 快速开始

```bash
./scripts/wiki.sh check                    # 先确认连通、新鲜度、有无 .git
./scripts/wiki.sh nav 分辨率               # 从 index.md 导航找入口（首选）
./scripts/wiki.sh trace 'image_grid_thw'   # 数字溯源，分层显示
```

默认 `ssh vscode`、路径 `/home/share/user/chenkai/VLA/knowledge`。
换机器或换路径用环境变量，脚本不写死：

```bash
WIKI_HOST=train-1 WIKI_ROOT=/path/to/knowledge ./scripts/wiki.sh check
```

## 检索顺序（照抄知识库自己的 CLAUDE.md）

**先导航，再全文搜。** 这个库的 `index.md` 是人工维护的真入口，按主题/时间/来源三条路径组织，不是文件名清单。一上来就 grep 会淹没在 `sources/` 的 1491 个文件里。

1. `wiki.sh nav <词>` —— 在 index 导航里定位主题入口
2. `wiki.sh cat <路径>` —— 顺着链接读；`wiki.sh link <slug>` 解析 `[[wikilink]]`
3. 导航不够用了再 `wiki.sh grep`（默认跳过 `sources/`，只搜综述层）
4. 涉及具体数字 → `wiki.sh trace`，打开 `sources/` 原始记录核对
5. 回答时说明依据了哪些页，方便人顺着链子复核

## 子命令

| 命令 | 用途 |
|---|---|
| `check` | 连通性、规模、最近改动、**有无 `.git`** |
| `index` / `nav <词>` | 读入口 / 在入口导航里搜 |
| `ls <目录>` | 列目录，带 `status` 与标题 |
| `cat <路径>` | 读一页，superseded 自动警告 |
| `link <slug>` | `[[wikilink]]` → 真实文件；悬空链接给近似匹配 |
| `grep <正则> [目录...]` | 全文检索，**默认跳过 `sources/`** |
| `grepall <正则>` | 含 `sources/` 的全量检索 |
| `trace <数字或词>` | 分层溯源：先 `sources/`+`evaluations/`，再综述层 |
| `stale` | 列出所有 `status: superseded` 的页 |

⚠️ `grep` 默认域**不含 `sources/`**，而 90% 的原始证据在那里。搜不到不等于没有——换 `grepall` 或 `trace` 再确认一次。远端用 `grep`（无 `rg`），走 BRE 语法，全库扫一次约 0.2s，不必吝惜。

## 目录语义

| 目录 | 含义 | 写入原则 | 可信度 |
|---|---|---|---|
| `sources/` | 证据与输入，**不保证当前有效** | 只增不改；允许冲突过时 | 原始，数字以此为准 |
| `experiments/` | 单实验综合页，保留原生 run id（`v0021.md`） | 一实验一页，随认识更新 | 综述 |
| `evaluations/` | 评测解释与索引 | 指标必须能回溯 | 可回溯 |
| `findings/` | 跨实验、**当前仍成立**的结论 | **门槛最高**，须列支撑实验 | 综述，看 `status` |
| `topics/` | 持续演进的横切主题 | 允许长期改写，保留演变 | 综述 |
| `datasets/` | 数据集说明与引用 | 版本、来源、被谁使用 | 综述 |

## 转述时照搬这三条

以下继承自知识库正本 `AGENTS.md`（**原文**，非转述）。读和答的时候照用，
因为它们决定了一句话可不可信，不只是写页面时才管用。

**metric 引用规则**

> 1. 正文中出现的每个具体数字，必须能沿链接找到 `sources/` 或 `evaluations/` 中的原始记录。
> 2. 写清楚 metric 名称和取数口径（哪个 eval suite、哪个 checkpoint）。
> 3. 不同来源数字不一致时，**两个都写出来并说明差异**，不要静默选一个。

**事实 / 分析 / 推断**——写作时必须可区分，建议用固定措辞：

> - **事实**：`eval-348 报告 Code Eval 74.8`
> - **分析**：`相比 exp-098，唯一显著变化是 code 数据占比 30% -> 45%`
> - **推断**：`因此倾向认为提高 code 占比改善了当前 code eval，但本实验不能证明对全部能力正向`

知识库正文大量使用 `**事实：**` / `**推断：**` 前缀，**转述时保留这个层级**——
把原文标为「推断」的东西说成事实，是这套规范唯一真正防的错误。

**冲突与过时**——旧资料不删除，判断过时标 `status: superseded` 并写明被什么取代；
发现两份资料矛盾时记录矛盾本身和各自证据，**在有新证据之前不要替团队做判断**。

## 写入

**默认不写**，本 skill 不提供写入命令。这份副本没有 revision 保护，且不回流团队。

产生了值得沉淀的认知，按上面那三条规范写成**草稿交给用户**，由用户决定怎么回流到活 wiki。草稿要带 frontmatter（`type` / `status` / `tags` / `sources`，过时页加 `superseded_by`），并说明该挂到 `index.md` 的哪一节——该库的规矩是「新页必须挂进 `index.md`，否则等于不存在」。

如果 `check` 显示当前 `WIKI_ROOT` **有 `.git`**，那才是活 wiki。此时遵循它自己的 `CLAUDE.md`：动手前重读目标页（别人可能刚改过）、优先更新已有页而不是新建重复知识、做合并不覆盖、不静默删除冲突的历史证据、**不在该目录执行任何 git 命令**（历史由后台 revision daemon 维护，手工 commit/checkout 会和它打架）。

## 关于这个 skill 的来历

上游有一套 `enrollment token → WireGuard → SMB 挂载` 的接入流程，其中**挂载部分已被本 skill 用共享盘直读替代**（内容同一份，见 references）。

上游那份「如何操作一个 LLM-WIKI」的 SKILL.md 只在 VPN 内的 `10.88.0.1:8080/SKILL.md` 提供，公网与共享盘均不可得，**因此本 skill 的操作规范不继承自它**，而是直接继承知识库自带的正本 `AGENTS.md` + `CLAUDE.md`——按该库自己的说法，这两份定义「这个 wiki 是什么」与「怎么读写它」，是更权威的来源。需要完整原文时直接读：

```bash
./scripts/wiki.sh cat AGENTS.md
./scripts/wiki.sh cat CLAUDE.md
```

## 更多

- 项目实况、已验证的重点结论、踩过的坑 → [`references/knowledge-map.md`](references/knowledge-map.md)
- 访问链路的由来（为什么不需要 VPN）、排障 → [`references/access-and-troubleshooting.md`](references/access-and-troubleshooting.md)
