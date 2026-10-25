---
name: baidu-netdisk
description: Operate a Baidu Netdisk (百度网盘) account through BaiduPCS-Go on a Linux host — browse, inspect, download whole folders to shared storage in tmux, verify integrity, diff remote vs local for incremental sync, upload, and transfer share links. Use when the user mentions 百度网盘 / 网盘 / BaiduPCS / pan.baidu.com or wants files moved between the netdisk and a server. Never handles login credentials or permanent deletion on the user's behalf.
---

# 百度网盘（BaiduPCS-Go）

用 [BaiduPCS-Go](https://github.com/qjfoidnh/BaiduPCS-Go)（实测 v4.0.2）在一台 Linux 机器上操作百度网盘：列目录、看元信息、整目录下载到共享盘、校验、增量补齐、上传、转存分享链接。
默认机器是 **`tb`**（CPU 机，能出外网，二进制在 `~/.local/bin/BaiduPCS-Go`，登录态在 `~/.config/BaiduPCS-Go/`）。其他机器把 `BPCS_HOST` / `BPCS_BIN` 换掉即可。

## 🔴 上手前先知道的几条

1. **登录凭证只由用户本人输入。** BDUSS / STOKEN / 密码 / Cookies 一律不经过 AI：不要让用户把它们贴进对话，不要替用户执行 `login`。要登录时运行 `scripts/login_hint.sh`，把它打印的命令交给用户在终端里自己跑（`read -rsp` 不回显、不进 shell 历史）。**转存分享链接需要 STOKEN**，只有 BDUSS 时 `transfer` 会失败。
2. **永久删除、清空回收站、退出登录、对外分享只由用户本人做。** `scripts/bpcs.sh` 使用命令允许列表，并拒绝 `rm`、`recycle`、`logout`、`login`、`loglist`、`setastoken`、`share`、`config set`。凭证类命令不会回显原参数；网盘里"移走待删"用 `mv` 到 `_待删除/` 目录，删除交给用户。
3. **网盘给的 md5 不可信。** `meta` 里明写"md5 (可能不正确)"：不少文件网盘记录的 md5 与真实 md5 完全不同（实测《鱿鱼游戏》S02 整季、`/01.LLM` 下一个 m4a；《王国》S01 则一致），已知的两种还原变换都对不上。BaiduPCS-Go 下载时还会对每个文件打"跳过文件有效性检验"——**它自己不校验**。完整性用 `scripts/verify.py`：大小必须一致；md5 一致记 OK；多文件目录 md5 全部不一致但大小全对，记"网盘 md5 不可用"；单文件 md5 不一致只能记无法判定，需重新下载到另一目录并用 `--peer` 比较两份本地文件。
4. **目录名以网盘实际为准。** 用户说"庆余年 S01"，网盘可能是 `庆余年S01`。先 `ls` 再下载；同一文件夹里可能有两套版本（如顶层 1080p + 子目录 4K），先列出来让用户选，别全量下。
5. **`d --saveto DIR /网盘/某目录` 会在 DIR 下建同名子目录**，不是把内容平铺进 DIR。
6. **长下载一律进远端 tmux。** 经跳板机的长 ssh 命令会被断开（"Connection closed by remote host"）。用 `scripts/download.sh`，它自带运行标记，`scripts/status.py` 只认**本次运行之后**的完成标记，不会被日志里的旧 `ALL_DONE` 骗。
7. **非 SVIP 下载并发上限是 1**（`config` 里 `max_parallel` 的说明：非 svip 不可 >1）。实测 SVIP 账号整目录约 28 MB/s（10-10 tb）。

## 执行

脚本都在**装了 BaiduPCS-Go 的机器上**运行。从本机调用用 `scripts/remote.sh`，它把脚本经 ssh 标准输入送过去执行，不需要先部署：

```bash
S=<本 skill 目录>/scripts
bash $S/remote.sh tb bpcs.sh who                     # 当前账号（只显示用户名，不显示凭证）
bash $S/remote.sh tb bpcs.sh quota
bash $S/remote.sh tb bpcs.sh ls "/00.Movies"
bash $S/remote.sh tb bpcs.sh meta "/00.Movies/xxx/a.mp4"

# 增量：网盘有、本地没有的文件
bash $S/remote.sh tb diff.py "/00.Movies/squid_game_s02" /home/share/user/<me>/media/squid_game_s02 --recursive

# 下载（后台 tmux，日志带运行标记）
bash $S/remote.sh tb download.sh --session ck-bpcs-x --saveto /home/share/user/<me>/media \
     --log ~/bpcs-logs/x.log "/00.Movies/目录A" "/00.Movies/目录B"
bash $S/remote.sh tb status.py --log ~/bpcs-logs/x.log --saveto /home/share/user/<me>/media --session ck-bpcs-x

# 校验并写 MD5SUMS.txt（大小必须全对；md5 处理见上面第 3 条）
bash $S/remote.sh tb verify.py --log ~/bpcs-logs/x.log --remote "/00.Movies/目录A" \
     --local /home/share/user/<me>/media/目录A --write-md5sums
```

流程固定为：**`who`/`quota` 确认登录 → `ls` 核对目录名与版本 → `diff.py --recursive` 算缺什么 → `download.sh` 后台下载 → `status.py` 看进度 → `verify.py` 校验并写 `MD5SUMS.txt`**。改名、搬目录这类入库动作在校验通过之后做，并且改名前后都按 `MD5SUMS.txt` 对一遍。`verify.py` 退出码 2 表示单文件 md5 无法判定，不能视为校验通过。

登录失效（`who` 报错或下载报 `user not exists` 类错误）时：运行 `bash $S/remote.sh tb login_hint.sh`，把输出原样给用户，等用户回复"已登录"后再 `who` 复核。

## 参考

- 命令速查、下载/上传/转存参数、配置项：[`references/usage.md`](references/usage.md)
- 踩过的坑与监控误报：[`references/pitfalls.md`](references/pitfalls.md)
