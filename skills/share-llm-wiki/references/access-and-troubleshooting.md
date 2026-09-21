# 访问链路与排障

## 为什么不需要 VPN

存在一套「enrollment token → WireGuard → SMB 挂载 `\\10.88.0.1\knowledge`」的安装流程。
**对本 skill 不适用**：知识库内容已经 rsync 到共享盘，`ssh` 直读即可，
拿到的是同一份 wiki。VPN 那条链在功能上不提供任何额外内容。

2026-09-18 对该安装链做过只读调研，记录几条事实备查（**不是**推荐执行）：

- 入口 `http://43.139.59.140/install.txt` 指向二阶段 `INSTALL_SKILL.md`，
  后者要求装 WireGuard、起全局隧道、取 SMB 明文口令、挂载远端共享，
  并**把一个下载来的 `SKILL.md` 原样写进 `~/.claude/skills/`**。
- 该 IP 属**腾讯云北京**公网，非公司内网；纯 HTTP 无 TLS。
- `/enroll` 与 `/SKILL.md` 只在 VPN 内的 `10.88.0.1:8080` 暴露，
  **后半条链在接入 VPN 之前无法审计**。
- VPN 的 `AllowedIPs` 由服务端下发、文档未写死。该服务选用的 `10.88.0.1`
  与公司内网 aTrust 已持有的 `10.88.2.91/32`、`10.88.2.92/32` **同段**；
  若服务端下发 `10.88.0.0/16` 或更宽，会静默劫持公司内网路由。
- 该机器已同时运行 aTrust（`utun8`）与 v2rayN sing-box TUN（`utun43`），
  三个 TUN 叠加时路由优先级由掩码长度决定，不由意图决定。

→ 结论：**用 `ssh` 读共享盘，不装 WireGuard。** 若要接入活 wiki，先带外核实。

## 操作规范为什么不继承自上游 SKILL.md

上游流程 Step 8 要装一份「如何操作一个 LLM-WIKI」的 SKILL.md。2026-09-18 实测：
公网 `43.139.59.140` 上 `/SKILL.md`、`/wiki/SKILL.md`、`/knowledge/SKILL.md` 全部 404
（只有 `/install.txt` 与 `/INSTALL_SKILL.md` 是 200），共享盘上也没有副本。

**⚠️ 状态已变（2026-09-18 晚）**：该文件**已由用户带外取得**（`~/Downloads/shared-llm-wiki/SKILL.md`，
175 行，mtime 2026-09-17）。所以「不可得」只对**公网与共享盘**成立，不再是绝对结论。
逐条比对结果见下节。

即便如此，本 skill 的操作规范**仍直接继承知识库自带的正本** `AGENTS.md` + `CLAUDE.md`。
这不是退而求其次：按 `AGENTS.md` 开头自己的说法——

> `SKILL.md`（Agent 侧安装）定义**如何操作一个 LLM-WIKI**；
> 本文件定义**这个 wiki 是什么**。两者不要混写。

——两份正本合起来覆盖的正是上游 SKILL.md 那一份的职责，且随知识库一起演进，
比一份装在本地就不再更新的副本更可信。`SKILL.md` 里继承的 metric 三条、
事实/分析/推断三条、冲突与过时一条均为**原文逐字**（2026-09-18 比对确认）。
需要完整规范时直接读源头，不必依赖本 skill 的摘录：

```bash
./scripts/wiki.sh cat AGENTS.md
./scripts/wiki.sh cat CLAUDE.md
```

### 与上游 SKILL.md 的逐条比对（2026-09-18）

拿到原文后做了一次完整比对，结论分三类：

| 上游条款 | 处置 | 理由 |
|---|---|---|
| Read 1–2（index 进入、先跟 wikilink） | **已有** | `CLAUDE.md` 同构，已写进检索顺序 |
| Read 4（数字开原件）、Report 5（列依据页） | **已有** | 即 metric 三条 + 自检清单 |
| Write 1–7、Safety、Page shape | **已有**（以 `CLAUDE.md` 为准） | 两者逐条同构；本副本只读，写入段已标明前提 |
| **Layout 中的非 Markdown 资产** | 🆕 **本次吸收** | 本 skill 此前只字未提，且工具链读不到——真实缺口 |
| Read 3（`rg` 优先、禁 `grep -r`） | **不继承** | 其三个数字测自 SMB 跨网络；本架构搜索在服务端本地跑（见下节实测） |
| Finding the wiki（`K:\` / `/knowledge` 挂载点解析） | **不适用** | 本 skill 用 `ssh` + 共享盘路径，无挂载点 |
| Recovering a mistake（找管理员按 sha 恢复） | **不适用** | 本副本无 `.git`，无 revision 可恢复 |

**唯一的实质收获是资产那一条**：实测默认路径下有 **397 个非 `.md` 文件**
（yaml 140 / jpg 100 / jinja 80 / json 25 / csv 25 / png 20 / svg 3 / pdf 3 / sh 1）。
此前 `wiki.sh cat` 只读 `.md`，`grep` 系一律 `--include='*.md'`，
**导致 `references/demos.md` 样例 3 让读者去核对的那个 `veomni_cli.yaml` 根本打不开**。
已修：`cat` 支持文本资产、新增 `assets` 子命令、二进制给 `scp` 路径。

### 上游 SKILL.md 的上游，反而在库里

上游 SKILL.md 曾需带外取得，它的**思想来源在共享盘上也可读**——
`index.md` 把这篇标为「本 wiki 自身工程方法的一手讨论」：

```bash
./scripts/wiki.sh cat 'sources/wps365/personal/AI/Wiki/从源材料到可消费 wiki（面向 LLM 下游的知识库工程方法）.md'
```

本 skill 的「结构路由 + 整篇读」「48–70% 缺口其实是检索假阴性」两条即来自它。
注意该文是**通用方法论**（写于 2026-06-11，案例是 5.9 万页的游戏 wiki），
其中「内容哈希 ID」「22 种 type 模板」等**并非 VLA wiki 现状**——
说明书已核对：VLA 活页用路径 + 原生 run id，综合页 frontmatter 上没有哈希 id。
**引用该文时要区分「方法论主张」与「本项目现状」。**

本机 `VLA/docs/` 下另有三份人类阅读版说明文档（原理说明书、阅读版、设计取舍），
适合了解背景；它们同样是 2026-09-18 的快照，不替代 wiki 原页。

## 连接

```bash
./scripts/wiki.sh check
```

默认 `WIKI_HOST=vscode`、`WIKI_ROOT=/home/share/user/chenkai/VLA/knowledge`。
`vscode` 是 `~/.ssh/config` 的别名（等同 `ultra`），完整形式见 `gpu-llm-service-ops` skill。

共享盘是 JuiceFS（`/home/share`，144T），多台机器都挂着，所以
`WIKI_HOST` 换成 `train-1` 等同机群里的其它机器通常也能读到同一路径——
**但要用 `check` 确认，不要假设**。

## 排障

| 现象 | 判断与处理 |
|---|---|
| `check` 报「不可达」 | 先 `ssh <host> 'ls /home/share'`。共享盘未挂 vs 路径不对是两回事 |
| ssh 卡住不返回 | 脚本带 `BatchMode=yes` `ConnectTimeout=15`，不会挂死在密码提示上。真卡住多半是 pod IP 漂移，重连即可 |
| `grep` 搜不到确定存在的词 | **默认域不含 `sources/`**，而 90% 证据在那里。换 `grepall` 或 `trace` |
| 正则不生效 | 远端是 `grep`（**无 `rg`**），BRE 语法。`+` `?` `\|` 需转义，或改用 `grep -E` 等价写法 |
| `link` 说「无同名文件」 | 本 wiki **允许悬空 wikilink**（标记待写的页），不是错误。脚本会给近似匹配 |
| `check` 报「0 个 .md / 0」但 `cat` 能读 | **`WIKI_ROOT` 是个 symlink。** `find`/`du` 默认不跟随，会把整个库报成空。脚本已加 `-L` 修复（2026-09-21）；若自己写命令务必带 `-L` |
| 读到的结论与现实不符 | 看 `status:`；`wiki.sh stale` 列全部 superseded。`sources/` 本就「不保证当前有效」 |
| 同一数字两处不一致 | **设计如此**。两个都写出来并说明差异，不要静默选一个 |

## ⚠️ 默认路径是一个 symlink（2026-09-21 起）

共享盘上的实际目录**已改名**：

```
/home/share/user/chenkai/VLA/vla-training      ← 真实目录
/home/share/user/chenkai/VLA/knowledge -> vla-training   （2026-09-20 18:01 建立的 symlink）
```

默认 `WIKI_ROOT` 仍指向 `knowledge`，**经 symlink 可正常读写**，不必改配置。
但这引入了一个真实的坑：**`find` 和 `du` 默认不跟随命令行上的 symlink**，
于是 `check` 曾把 1623 个 .md 报成 `0 个 .md / 0`、`stale` 返回空——
**看起来像「库空了」或「没有过时页」，实际是工具没走进去**。

已修：`check` / `stale` / `link` / `assets` 的 `find` 全部加 `-L`，`du` 加 `-L`。
自己写命令时同理。

新库带 `.wiki-project.toml`（`name = "vla-training"`），是上游改用项目化命名的迹象；
**如果哪天 symlink 被删**，把 `WIKI_ROOT` 指到 `vla-training` 即可：

```bash
WIKI_ROOT=/home/share/user/chenkai/VLA/vla-training ./scripts/wiki.sh check
```

## 新鲜度

`check` 报告 `index.md` 与全库最新内容的修改时间，**不是最后同步时间**。
rsync 可以保留原始 mtime，因此这些时间不能证明副本与上游一致；无同步记录时报告
“同步时间未知”。需要最新现状但副本证据不足时说明限制；同步须先明确源、目标和方向。
`.git` 存在也不能证明这是活 wiki，或 revision daemon 正在提供恢复保护。

## 性能：上游的搜索纪律对本 skill 不适用

上游 SKILL.md 有一条写进协议的硬数据（转引自《知识库原理说明书》）：

| 做法 | 上游实测 | 上游结论 |
|---|---|---|
| `rg -l --glob '*.md'` | 5.2 s | 可接受的全库搜索 |
| PowerShell `Get-ChildItem -Recurse \| Select-String` | 93.8 s | 约 19 倍，Agent 会放弃搜索改用印象 |
| 普通 `grep -r` | 90 s 仍未完成 | 因此**禁止验收脚本用 `grep -r`** |

由此上游要求「优先用 Agent 自带的 ripgrep 搜索工具，不要假设机器上有 `rg`」。

**这套纪律的前提是 SMB 挂载**——那三个数字都是 Windows `K:\` 跨网络扫小文件测出来的。
本 skill 的架构不同：**搜索在服务端本地执行**，只把命中行回传。
2026-09-18 实测同一个库（1607 个 .md / 797M，JuiceFS）：

```
ssh + grep -rl 全库：2.49s（冷）/ 0.72s（热）
```

即上游认定「90s 仍未完成、必须禁用」的 `grep -r`，在服务端本地是**亚秒级**。
差异来自执行位置，不是工具优劣。

→ 因此本 skill **不继承那条 `rg` 纪律**：远端没有 `rg`，也不需要。
真正的成本是把大页拉回本地——`cat` 一个大 `sources/` 文档可能几千行，
默认整篇读；超出工具预算时用 `cat <路径> --lines 起始:结束` 连续读取至完整覆盖，不能只读命中行就作答。

**这也是放弃 SMB 挂载换来的实际收益之一**，不只是省掉安装步骤：
挂载方案把每次搜索变成跨网络扫 1607 个小文件，直读方案把搜索留在数据所在的机器上。
