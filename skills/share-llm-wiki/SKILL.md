---
name: share-llm-wiki
description: Read the team's shared LLM-WIKI (VLA training knowledge base) over SSH on a shared drive — no VPN or SMB mount. Use to answer questions about training experiments, evaluations, datasets, findings and their evidence chain, or to trace a specific metric back to its raw record. Covers VeOmni / Qwen3-VL VLA experiments and metric provenance.
---

# Shared LLM-WIKI

团队共享知识库的检索入口。知识库是一个普通目录，**经 `ssh` 访问共享盘即可读，不需要 VPN、不需要 SMB 挂载**。

内容是单个 VLA 训练项目的沉淀：训练实验、评测、数据集、跨实验结论。页面以 Markdown 为主，证据还包括配置、表格和图片等资产。

## 🔴 上手前先知道的四条

1. **这是 rsync 副本，不是活 wiki。** 默认路径下**没有 `.git`**，原 wiki 那套「保存即 revision、误覆盖可恢复」的保护**不存在**。→ **按只读用**。写进去既不回流给团队，也恢复不了。先跑 `wiki.sh check`，它会告诉你当前这份有没有 `.git`。
2. **数字必须溯源到 `sources/`。** 这是知识库自己的硬规矩：`sources/` 是原始证据，`experiments/` `findings/` `topics/` 是综述层。**不要引用只在综述里见过的数字**——用 `wiki.sh trace` 会自动把两层分开显示。
3. **`sources/` 明确「不保证当前有效」**，且允许自相矛盾。多数页面位于 `sources/` 下。看到冲突是**设计如此**，不要替团队选一个，把矛盾连同各自证据一起报出来。
4. **结论有保质期，`status` 要看。** 存在 `status: superseded` 的页（如「历史上从未有 run 的 MFU 超过 0.36」已被推翻）。`wiki.sh cat` 会在读到 superseded 页时自动警告。

## 快速开始

所有 `./scripts/wiki.sh` 示例均相对于**本 SKILL.md 所在目录**，不是用户项目目录。
四端调用时先从已加载技能的路径解析出技能目录，使用脚本绝对路径；不要假设 shell
会自动切换目录，也不要硬编码某一端的 `~/.claude` 或 `~/.codex` 路径。
本地需 Bash/SSH，远端需 Bash、GNU grep/find/date 等工具及 `file`。

```bash
./scripts/wiki.sh check                    # 确认连通、内容修改时间、有无 .git
./scripts/wiki.sh nav 分辨率               # 从 index.md 导航找入口（首选）
./scripts/wiki.sh trace 'image_grid_thw'   # 数字溯源，分层显示
```

## 多项目

**一个容器目录下多个 wiki 项目**，各自带 `.wiki-project.toml`。
默认 `ssh vscode`、容器 `/home/share/user/chenkai/knowledge`、项目 `vla-training`
（即 `/home/share/user/chenkai/knowledge/vla-training`）。

```bash
./scripts/wiki.sh projects                       # 有哪些项目
WIKI_PROJECT=<别的项目> ./scripts/wiki.sh check   # 换项目
```

| 变量 | 默认 | 用途 |
|---|---|---|
| `WIKI_HOST` | `vscode` | ssh 目标 |
| `WIKI_PROJECT` | `vla-training` | **换项目改这个** |
| `WIKI_BASE` | `/home/share/user/chenkai/knowledge` | 容器目录 |
| `WIKI_ROOT` | —— | 完整路径；设了则**优先于** BASE/PROJECT |

新项目加进来**不需要改脚本**，`WIKI_PROJECT=<名字>` 即可。

> ⚠️ 路径已迁移过两次，旧的 `chenkai/VLA/knowledge`、`chenkai/VLA/vla-training` **均已失效**
> （`VLA/` 已清空，兼容 symlink 也已删除）。还在用这两个路径的 `WIKI_ROOT` 请改掉。演变史见 references。
> `find`/`du` 默认不跟随命令行 symlink，脚本已统一加 `-L`——`WIKI_ROOT` 指向 symlink 时仍然正确。

## 消费模型：结构路由 + 整篇读

这个库**刻意不做向量检索**，下游链路是固定的（来自其方法论文，`index.md` 标为本 wiki 自身工程方法的一手讨论）：

> 用户问题 → 沿 wiki 结构路由到目标对象 → **整篇读取**该对象正文 → 生成带原文锚点的答案

理由不是「embedding 不好」，而是：范围有界、结构在写作时就已存在，服务阶段再用向量去猜，会把「路由到正确对象」降级成「语义近似」——**那正是 Agent 用印象答题的入口**。

对本 skill 的两条直接约束：

- **页是完整理解的单位，不要仅凭检索片段作答。** 用检索定位到页之后，默认 `cat` 整页读，而不是只摘命中行。若页面超过工具输出预算，先用 `cat <路径> --lines 1:200`，再连续读取后续范围直到覆盖全文；每段标明总行数，工具若仍截断则缩小范围重读。未读完时明确说明范围，不能声称已完整核对。页面被设计成自包含（跨对象依赖显式写成 `[[wikilink]]`），只读命中行会丢掉页面自己声明的适用范围和反例。
- **别把 grep 当召回器。** grep 用来确认「这页存不存在」，导航用来决定「该读哪页」。

## 检索顺序（照抄知识库自己的 CLAUDE.md）

**先导航，再全文搜。** 这个库的 `index.md` 是人工维护的真入口，按主题/时间/来源三条路径组织，不是文件名清单。一上来就 grep 会淹没在 `sources/` 的大量文件里。

⚠️ **搜不到，先怀疑检索而不是知识库。** 所引方法论文的游戏 wiki 案例报告了检索假阴性（不是本 VLA 库的实测比例）。所以断言「库里没有」之前，至少换一次写法（`grepall`、换同义词、换 `trace`）。这条对本 skill 尤其适用——`grep` 默认域不含 `sources/`，而多数证据在那里。

1. `wiki.sh nav <词>` —— 在 index 导航里定位主题入口
2. `wiki.sh cat <路径>` —— 顺着链接读；`wiki.sh link <slug>` 解析 `[[wikilink]]`
3. 导航不够用了再 `wiki.sh grep`（默认跳过 `sources/`，只搜综述层）
4. 涉及具体数字 → `wiki.sh trace`，打开 `sources/` 原始记录核对
5. 回答时说明依据了哪些页，方便人顺着链子复核

## 子命令

| 命令 | 用途 |
|---|---|
| `projects` | 列容器目录下有哪些 wiki 项目 |
| `check` | 连通性、规模、最近改动、**有无 `.git`** |
| `index` / `nav <词>` | 读入口 / 在入口导航里搜 |
| `ls <目录>` | 列目录，带 `status` 与标题 |
| `cat <路径>` | 读一页或**文本资产**（yaml/csv/json），superseded 自动警告 |
| `assets [目录]` | 列非 `.md` 证据资产（训练 yaml、图表 svg/csv、pdf） |
| `link <slug>` | `[[wikilink]]` → 真实文件；悬空链接给近似匹配 |
| `grep <正则> [目录...]` | 全文检索，**默认跳过 `sources/`** |
| `grepall <正则>` | 含 `sources/` 的全量检索 |
| `trace <数字或词>` | 分层溯源：先 `sources/`+`evaluations/`，再综述层 |
| `stale` | 列出 `status: superseded` 的页（全部用 `--all`） |

`assets`、`link`、`grep`、`grepall`、`trace`、`stale` 默认每组最多显示 80 条；
超限在 stderr 提示总条数，`--limit N` 调整上限，`--all` 输出完整结果。
要接管道筛选，先用 `assets --all <目录> | grep <词>`，避免先截断后筛选。
无命中仍为退出码 0；非零表示查询/读取失败，不得解释成“库里没有”。
`link` 支持裸 slug、根目录相对路径和 `[[路径#标题|别名]]`；正文中的相对路径
须先按来源页目录解析。`cat` 空文件明确提示，二进制只显示类型、大小和下载命令。

⚠️ `grep` 默认域**不含 `sources/`**，而多数原始证据在那里。搜不到不等于没有——换 `grepall` 或 `trace` 再确认一次。远端用 `grep`（无 `rg`），走 BRE 语法，全库扫一次约 0.7–2.5s（搜索在服务端本地跑，不必吝惜）。

## 目录语义

| 目录 | 含义 | 写入原则 | 可信度 |
|---|---|---|---|
| `sources/` | 证据与输入，**不保证当前有效** | 只增不改；允许冲突过时 | 原始，数字以此为准 |
| `experiments/` | 单实验综合页，保留原生 run id（`v0021.md`） | 一实验一页，随认识更新 | 综述 |
| `evaluations/` | 评测解释与索引 | 指标必须能回溯 | 可回溯 |
| `findings/` | 跨实验、**当前仍成立**的结论 | **门槛最高**，须列支撑实验 | 综述，看 `status` |
| `topics/` | 持续演进的横切主题 | 允许长期改写，保留演变 | 综述 |
| `datasets/` | 数据集说明与引用 | 版本、来源、被谁使用 | 综述 |

## 知识库不只有 Markdown

配置与图表资产被 frontmatter 的 `sources:` 和正文链接引用；数量与格式快照见访问说明。

这条很实际：`findings/` 页的 `sources:` 常常指向一个 **yaml 而不是 md**（见
[`references/demos.md`](references/demos.md) 样例 3），要坐实「跑的是哪个配置」就得打开它。

```bash
./scripts/wiki.sh assets sources/experiment-runs   # 看有哪些资产
./scripts/wiki.sh cat '<上面列出的 yaml 路径>'      # 文本资产直接读
```

二进制（jpg/png/pdf）不回传，`cat` 会报大小并给出 `scp` 命令。
⚠️ `grep`/`grepall`/`trace` **只搜 `.md`**，搜不到的配置值可能在 yaml 里——用 `assets` 定位后 `cat`。

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

`check` 只报告 `.git` 是否存在，不能证明这是活 wiki 或 revision daemon 正常运行。
文件 mtime 也不是同步时间；没有同步记录时明确报告“同步时间未知”。
只有用户明确授权写入、确认目标为活 wiki 并核实其保护机制后，才依据目标库自己的 `CLAUDE.md` 操作：动手前重读目标页（别人可能刚改过）、优先更新已有页而不是新建重复知识、做合并不覆盖、不静默删除冲突的历史证据、**不在该目录执行任何 git 命令**（历史由后台 revision daemon 维护，手工 commit/checkout 会和它打架）。

## 回答前后自检

继承自项目《知识库原理说明书》的日常检查清单（只保留只读部分）：

**回答中**
- 是否从 `index.md` 进，而不是凭训练记忆？
- 具体数字是否打开了 `sources/` 或 `evaluations/` 原件？
- 是否标明事实 / 分析 / 推断？
- 冲突是否两份都在，而不是选了好看的那份？
- 是否列出依据页面？

**不要做的事**
- 把 `v000N` 当能力版本号；把 run 名当 as-run 配置。
- 把「数据已建 / smoke 已过」写成「模型已评测」。
- 自建本地 knowledge 目录冒充共享盘。

## 原始规范

操作规范以知识库正本 `AGENTS.md`、`CLAUDE.md` 为准；摘录和项目地图是快照。
当规则或当前结论影响回答时，按需重新读取：

```bash
./scripts/wiki.sh cat AGENTS.md
./scripts/wiki.sh cat CLAUDE.md
```

访问链路由来、上游对照和历史测量数据见 `references/access-and-troubleshooting.md`。

## 更多

- 六个真实使用样例（含反面样例与「别做」清单） → [`references/demos.md`](references/demos.md)
- 项目实况、已验证的重点结论、踩过的坑 → [`references/knowledge-map.md`](references/knowledge-map.md)
- 访问链路的由来（为什么不需要 VPN）、排障 → [`references/access-and-troubleshooting.md`](references/access-and-troubleshooting.md)
