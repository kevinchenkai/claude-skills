# 使用与排查

以下命令都在本 skill 目录执行。

## 解释器：用 `scripts/run.sh`，别直接调 `python3`

**PATH 上的 `python3` 不一定能用。** 实测 2026-08-23（macOS）：
`/usr/bin/python3` 是 **3.9.6 且不带 `httpx`**，照文档直接跑 `python3 scripts/douyin_hd.py`
会以 `ModuleNotFoundError: No module named 'httpx'` 失败；同机的
`/opt/anaconda3/bin/python3` 是 3.12.4，装了 httpx，可用。

所以入口统一走 [`scripts/run.sh`](../scripts/run.sh)，它会按顺序探测候选解释器，
挑第一个**同时满足 Python >= 3.10 且能 `import httpx`** 的：

```bash
./scripts/run.sh inspect '<INPUT>'
```

想固定某个解释器：

```bash
DOUYIN_PYTHON=/opt/anaconda3/bin/python3 ./scripts/run.sh inspect '<INPUT>'
```

挑不到时它不会静默失败，而是打印该装什么、该怎么指定。

## 依赖

**最低 Python 3.10**（`dataclass(slots=True)` 需要它；3.9 会直接 `TypeError`）。
实测 3.10 与 3.12 均通过全部单测。

基础解析与下载只依赖 `httpx`：

```bash
python3 -m pip install -r requirements.txt
```

当 SSR 没有完整作品数据时，安装浏览器回退并确保本机有 Chrome；也可安装 Playwright 自带 Chromium：

```bash
python3 -m pip install 'playwright>=1.50,<2'
python3 -m playwright install chromium
```

下载验证需要 `ffprobe`：

```bash
brew install ffmpeg
```

默认尝试 Playwright 的 `chrome` channel。需要改用其他 channel 时设置 `DOUYIN_BROWSER_CHANNEL`。

## 命令

完整 URL、短链和整段分享文案都可直接作为输入：

```bash
./scripts/run.sh inspect \
  'https://www.douyin.com/video/7667208299670554725' \
  --browser-fallback --debug
```

保存脱敏检查结果：

```bash
./scripts/run.sh inspect '<INPUT>' \
  --browser-fallback --save-json /tmp/douyin-inspection.json
```

下载模式：

```bash
./scripts/run.sh download '<INPUT>' --quality original --browser-fallback
./scripts/run.sh download '<INPUT>' --quality highest --browser-fallback
./scripts/run.sh download '<INPUT>' --quality 1080p --codec h264 --browser-fallback
./scripts/run.sh download '<INPUT>' --quality compatible --browser-fallback
```

比较模式：

```bash
./scripts/run.sh compare '<INPUT>' --browser-fallback --debug
./scripts/run.sh compare '<INPUT>' --browser-fallback --include-play-addr
```

默认输出目录是 `~/Downloads/douyin/<aweme_id>/`，用 `--output` 可改：

```text
~/Downloads/douyin/<aweme_id>/
├── <aweme_id>.mp4
├── metadata.json
├── candidates.json
└── ffprobe.json
```

`compare` 改为 `original.mp4`、`highest.mp4`、各自 ffprobe JSON 和 `comparison.json`。候选 JSON 只保存 host 与截断 path，不保存 query。

## Cookie

公开内容优先不带 Cookie。若用户明确允许使用自己的会话，可只通过环境变量传入：

```bash
export DOUYIN_COOKIE='<Cookie header>'
./scripts/run.sh inspect '<INPUT>' --browser-fallback
```

不要把 Cookie 写进仓库、命令日志、候选 JSON 或对话输出。`--cookie-env` 可改变量名。

## 固定集成测试

单元测试不联网：

```bash
python3 -m pytest -q tests
```

真实网络测试：

```bash
DOUYIN_INTEGRATION=1 python3 -m pytest -q tests/test_integration.py -s
./scripts/run.sh compare \
  'https://www.douyin.com/video/7667208299670554725' \
  --browser-fallback --debug --output /tmp/douyin-hd-integration
```

只固定断言 `aweme_id`、至少一个有效候选、original 探测路径和 ffprobe 可读；不要固定 CDN、档位数、分辨率、码率或文件大小。

判稳定性不能只跑一次。SSR 与 original probe 都会间歇失败，**必须连续跑多次看是否每次一致**——单次成功证明不了可用性。

已验证结果见 [`integration-report.md`](integration-report.md)：三条视频、两种形态（12 档 bit_rate 走浏览器回退；0 档 bit_rate 纯 SSR）。两种形态的失败模式不同，改动后都要覆盖。

## 常见失败

- `ModuleNotFoundError: No module named 'httpx'` 或 `TypeError: dataclass() got an unexpected keyword argument 'slots'`：跑到了错的解释器（前者缺依赖，后者是 Python 3.9）。用 `./scripts/run.sh` 而不是直接 `python3 scripts/douyin_hd.py`；或 `DOUYIN_PYTHON=/path/to/python3` 指定。
- `没找到可用的 Python`：`run.sh` 探完候选都不满足。按提示装依赖，或用 `DOUYIN_PYTHON` 指定一个 >= 3.10 且有 httpx 的解释器。
- `iesdouyin SSR 3 次尝试均未返回完整作品数据`：SSR 有约 20-30% 概率只返回页面壳，脚本已自动重试 3 次。仍然失败再加 `--browser-fallback`。单次 `page shell contained no video item` 是正常抖动，不代表被风控。
- `无法启动 Chrome/Chromium`：安装 Chrome，或执行 `python3 -m playwright install chromium`。
- `Chrome 等待 aweme detail 响应超时`：检查网络/WAF；需要用户会话时再提供 `DOUYIN_COOKIE`，不要切第三方在线解析 API。
- `original fallback`：不是失败。原片体积未知或不大于最高转码档时，按定义回退到无水印转码档。
- `original 不可用，且唯一可回退的候选是带水印的 playwm 地址`：这是**有意中止**。当 `video.bit_rate[]` 为空时，唯一的回退是带水印源；与其静默产出「假原片」，不如报错。通常重跑即可（原片探测失败多为一次性 ConnectTimeout）；确实要带水印结果时显式用 `--quality highest`。
- `ffprobe 未发现 video stream`：下载内容不是有效视频；保留脱敏 debug 信息，检查 candidate probe 与长度。
- `媒体域名解析到非公网地址`：安全拦截生效；不要关闭校验来下载来源不明的 URL。
