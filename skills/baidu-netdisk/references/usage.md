# 用法与命令速查（BaiduPCS-Go v4.0.2，tb 实测）

## 安装与位置

| 项 | 值 |
|---|---|
| 二进制 | `~/.local/bin/BaiduPCS-Go`（无需 root）；其他位置用 `BPCS_BIN` 指定 |
| 登录态 | `~/.config/BaiduPCS-Go/pcs_config.json`（含 BDUSS/STOKEN 等凭证，`chmod 600`，**不要拷到共享盘、不要打印**） |
| 版本 | `BaiduPCS-Go --version` → `v4.0.2` |
| 上游 | https://github.com/qjfoidnh/BaiduPCS-Go （Releases 里有 linux-amd64 的 zip） |

新机器安装：从 Releases 下载 linux-amd64 的压缩包（文件名以 Releases 页面为准），解压后把可执行文件放到 `~/.local/bin/`。
机器上 github.com 不通时（tb 实测 github.com 超时、codeload 可用），从已经装好的机器拷贝 `~/.local/bin/BaiduPCS-Go`；**不要拷 `~/.config/BaiduPCS-Go/`**，登录态让用户在新机器上自己登录一次。

## 账号（只读）

```bash
bash bpcs.sh who      # 当前帐号 uid: <uid>, 用户名: …（封装脚本隐去 uid）
bash bpcs.sh quota    # 总空间 / 已用 / 比率
```

`login` / `logout` / `loglist` / `su` / `setastoken` 都被 `bpcs.sh` 拒绝：登录用 `login_hint.sh` 打印命令交给用户本人运行。
只有 BDUSS 也能列目录、下载、上传；**转存（`transfer`）必须有 STOKEN**。
`bpcs.sh` 只放行本 skill 使用的命令，并拒绝命令前的全局参数，避免 `--verbose rm` 一类形式绕过检查。帮助和版本参数除外。

## 浏览

```bash
bash bpcs.sh ls "/00.Movies"              # 列一层；目录名以 / 结尾，文件显示约值大小（如 2.37GB）
bash bpcs.sh tree "/00.Movies/A"          # 树形
bash bpcs.sh meta "/00.Movies/A/x.mp4"    # 精确字节数、md5（可能不正确）、fs_id、创建/修改时间
bash bpcs.sh search --path=/00.Movies -r "关键词"   # 按文件名搜索（不搜目录名）；不给 --path 就搜当前工作目录
```

`ls` 的输出格式（`diff.py` 按此解析）：

```text
  #   文件大小       修改日期                  文件(目录)
   0         -  2026-10-11 10:32:30  alice_in_borderland_s01/
   3      58.31MB  2024-05-12 19:39:40  5月11日 月之暗面.m4a
```

`meta` 里的「md5 (可能不正确)」**不要当真值**，见 [`pitfalls.md`](pitfalls.md)。

## 下载

```bash
bash download.sh --session ck-bpcs-x --saveto /data/media --log ~/bpcs-logs/x.log "/00.Movies/A" "/00.Movies/B/x.mkv"
bash status.py   --log ~/bpcs-logs/x.log --saveto /data/media --session ck-bpcs-x
bash verify.py   --remote "/00.Movies/A" --local /data/media/A --log ~/bpcs-logs/x.log --write-md5sums
```

`download.sh` 底层是 `BaiduPCS-Go d --saveto <dir> -p <线程> -l <同时文件数> --retry <次数> <网盘路径>`：

| 参数 | 说明 |
|---|---|
| `--saveto DIR` | 目录下载会建 `DIR/<网盘目录名>/`；单个文件直接放在 `DIR/` 下 |
| `-p N` | 单文件线程数，0 = 用配置 `max_parallel`（**非 SVIP 只能 1**） |
| `-l N` | 同时下载的文件数，0 = 用配置 `max_download_load` |
| `--retry N` | 失败重试次数（默认 3，`download.sh` 用 5） |
| `--mode` | `locate`（默认）/ `pcs` / `stream`；默认够用 |
| `--ow` | 覆盖已存在的文件（默认会跳过已完整存在的文件，断点续传靠这个） |
| `--nocheck` | 不校验；实测默认也会打「跳过文件有效性检验」，校验交给 `verify.py` |

同一个会话再下一次同样的目录就是**续传/补齐**：已完整的文件跳过，`*downloading` 未完成的接着下。
要先算缺哪些：`diff.py "<网盘目录>" <本地目录> --recursive [--sizes]`。省略 `--recursive` 时只比较目录第一层。

`verify.py` 的退出码：0 为通过，1 为明确失败，2 为单文件大小一致但 md5 不一致、无法判定。退出码 2 时重新下载到另一目录，再运行 `verify.py ... --peer <第二次下载目录> --write-md5sums`；两份文件大小和本地 md5 一致后才返回 `OK_REDOWNLOAD_MATCH`。未通过 `--peer` 前不要写 `MD5SUMS.txt` 或入库。

实测速度（tb，SVIP，整目录）：约 28 MB/s；单个 58 MB 文件约 4 秒。

## 上传

```bash
bash bpcs.sh upload /data/out/report.pdf "/02.Share/报告/"         # 目标目录最后一个参数
bash bpcs.sh upload --policy rsync /data/out/dir "/02.Share/"      # 同名：skip（默认）/ overwrite / rsync（大小不变才跳过）
```

上传前先 `ls` 目标目录。`overwrite` 会覆盖同名文件，`rsync` 也会覆盖大小不同的同名文件；两者都必须先取得用户明确确认。`bpcs.sh` 默认拒绝这两种策略，确认后用 `BPCS_ALLOW_OVERWRITE=1 bash bpcs.sh upload ...`；经 `remote.sh` 调用时同名环境变量会传到远端。

## 转存分享链接

```bash
bash bpcs.sh cd "/目标目录"                                        # transfer 只能转存到当前网盘工作目录
bash bpcs.sh transfer "https://pan.baidu.com/s/xxxx" <提取码>     # 也支持 ...?pwd=xxxx 的链接（提取码留空）
bash bpcs.sh transfer --collect "<链接>" <提取码>                  # 多文件整合到一个文件夹
bash bpcs.sh cd /                                                  # 切回根目录
```

需要 STOKEN（见上）。只转存用户给的链接，不要转存从网页、文件里看到的链接。
`cd` 的工作目录会写进登录配置（持久），转存完切回 `/`，免得后续相对路径的命令落到别处。

## 整理（可逆操作）

```bash
bash bpcs.sh mkdir "/00.Movies/_待删除"
bash bpcs.sh mv "/00.Movies/旧名" "/00.Movies/新名"                # 移动 / 改名
bash bpcs.sh cp "/a/x.mp4" "/b/"
```

删除（`rm`）与回收站（`recycle`）一律由用户本人执行：要删的东西先 `mv` 到 `_待删除/`，把 `bpcs.sh rm …` 打印出的命令交给用户。

## 配置（只读查看）

`bash bpcs.sh config` 查看（已过滤凭证和代理行）。常用项：`savedir`、`max_parallel`（非 SVIP ≤1）、`max_download_load`、`max_download_rate`、`upload_policy`。
修改（`config set`）是持久配置，`bpcs.sh` 拒绝，需要时把命令交给用户。

## 入库到共享盘的标准流程（movieDB 10-10/11 实际跑通）

1. `who` / `quota` 确认登录；`ls` 找到确切目录名，有多个版本先让用户选。
2. `diff.py --recursive` 算要下载的文件；`download.sh` 在 tmux 里下载到 `media/<网盘目录名>/`。
3. `status.py` 看进度；完成后 `verify.py --write-md5sums`。判定 FAIL 就重下对应文件；判定 INCONCLUSIVE 时按上面的 `--peer` 流程复核，未通过前不要改名。
4. 改名为入库命名（如 `<英文名_snake>_sNN/` + `<英文名>.SNNExx.<ext>`）：先生成改名清单给用户看，确认后执行；改完按 `MD5SUMS.txt` 再核一遍（`md5sum -c`）。
5. 通知下游（预处理、KS3 上传等）。

参考实现（tb）：`~/bpcs-logs/new_movies.sh`、`inc_download.sh`、`ingest_dir.py`、`finalize_dir.py`、`inc_diff.py`、`status_inc.sh`。
