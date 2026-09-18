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

上游流程 Step 8 要装一份「如何操作一个 LLM-WIKI」的 SKILL.md，但它**只在 VPN 内的
`10.88.0.1:8080/SKILL.md` 提供**。2026-09-18 实测：公网 `43.139.59.140` 上
`/SKILL.md`、`/wiki/SKILL.md`、`/knowledge/SKILL.md` 全部 404（只有 `/install.txt`
与 `/INSTALL_SKILL.md` 是 200），共享盘上也没有副本。`INSTALL_SKILL.md` 对它的描述
只有安装路径，**没有任何内容**。

因此本 skill 的操作规范**直接继承知识库自带的正本** `AGENTS.md` + `CLAUDE.md`。
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

### 上游 SKILL.md 的上游，反而在库里

上游 SKILL.md 本身拿不到，但它的**思想来源在共享盘上可读**——
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
| 读到的结论与现实不符 | 看 `status:`；`wiki.sh stale` 列全部 superseded。`sources/` 本就「不保证当前有效」 |
| 同一数字两处不一致 | **设计如此**。两个都写出来并说明差异，不要静默选一个 |

## 新鲜度

`check` 会报 `index.md` 时间与全库最新改动时间。这是 **rsync 快照**，
不会自动跟进活 wiki。用之前扫一眼时间戳；隔了一段时间要用，
先问用户是否需要重新 rsync。

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
先用 `grep -n` 定位行号，再按需读。

**这也是放弃 SMB 挂载换来的实际收益之一**，不只是省掉安装步骤：
挂载方案把每次搜索变成跨网络扫 1607 个小文件，直读方案把搜索留在数据所在的机器上。
