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

| 目录 | 含义 | 可信度 |
|---|---|---|
| `sources/` | 证据与输入，**不保证当前有效**，允许冲突过时 | 原始，数字以此为准 |
| `experiments/` | 单实验综合页，保留原生 run id（`v0021.md`） | 综述 |
| `evaluations/` | 评测解释与索引 | 指标可回溯 |
| `findings/` | 跨实验、**当前仍成立**的结论，门槛最高 | 综述，看 `status` |
| `topics/` | 持续演进的横切主题 | 综述 |
| `datasets/` | 数据集说明与引用 | 综述 |

## 写入

**默认不写。** 这份副本没有 revision 保护，且不回流团队。

产生了值得沉淀的认知，按该库规范（区分事实/分析/推断、每个数字留出处、新页要挂进 `index.md`）写成草稿交给用户，由用户决定怎么回流到活 wiki。如果 `check` 显示当前 `WIKI_ROOT` **有 `.git`**，那才是活 wiki，此时遵循它自己的 `CLAUDE.md`：改前重读目标页、做合并不覆盖、**不在该目录执行任何 git 命令**。

## 更多

- 项目实况、已验证的重点结论、踩过的坑 → [`references/knowledge-map.md`](references/knowledge-map.md)
- 访问链路的由来（为什么不需要 VPN）、排障 → [`references/access-and-troubleshooting.md`](references/access-and-troubleshooting.md)
