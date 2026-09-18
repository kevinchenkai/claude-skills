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

## 性能

全库 `grep` 约 **0.2s**（1607 个 .md / 797M，JuiceFS 有缓存），
检索不必吝惜。真正的成本是把大页拉回本地——`cat` 一个大 `sources/` 文档可能几千行，
先用 `grep -n` 定位行号，再按需读。
