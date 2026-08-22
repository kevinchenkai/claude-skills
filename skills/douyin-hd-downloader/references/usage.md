# 使用与排查

以下命令都在本 skill 目录执行。Python 需要 3.11+。

## 依赖

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
python3 scripts/douyin_hd.py inspect \
  'https://www.douyin.com/video/7667208299670554725' \
  --browser-fallback --debug
```

保存脱敏检查结果：

```bash
python3 scripts/douyin_hd.py inspect '<INPUT>' \
  --browser-fallback --save-json /tmp/douyin-inspection.json
```

下载模式：

```bash
python3 scripts/douyin_hd.py download '<INPUT>' --quality original --browser-fallback
python3 scripts/douyin_hd.py download '<INPUT>' --quality highest --browser-fallback
python3 scripts/douyin_hd.py download '<INPUT>' --quality 1080p --codec h264 --browser-fallback
python3 scripts/douyin_hd.py download '<INPUT>' --quality compatible --browser-fallback
```

比较模式：

```bash
python3 scripts/douyin_hd.py compare '<INPUT>' --browser-fallback --debug
python3 scripts/douyin_hd.py compare '<INPUT>' --browser-fallback --include-play-addr
```

默认输出：

```text
downloads/<aweme_id>/
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
python3 scripts/douyin_hd.py inspect '<INPUT>' --browser-fallback
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
python3 scripts/douyin_hd.py compare \
  'https://www.douyin.com/video/7667208299670554725' \
  --browser-fallback --debug --output /tmp/douyin-hd-integration
```

只固定断言 `aweme_id`、至少一个有效候选、original 探测路径和 ffprobe 可读；不要固定 CDN、档位数、分辨率、码率或文件大小。

首版固定视频的已验证结果见 [`integration-report-2026-08-22.md`](integration-report-2026-08-22.md)。

## 常见失败

- `SSR ... page shell contained no video item`：当前 SSR 只返回壳；加 `--browser-fallback`。
- `无法启动 Chrome/Chromium`：安装 Chrome，或执行 `python3 -m playwright install chromium`。
- `Chrome 等待 aweme detail 响应超时`：检查网络/WAF；需要用户会话时再提供 `DOUYIN_COOKIE`，不要切第三方在线解析 API。
- `original fallback`：不是失败。原片 probe 失败、体积未知或不大于最高转码档时，按定义回退。
- `ffprobe 未发现 video stream`：下载内容不是有效视频；保留脱敏 debug 信息，检查 candidate probe 与长度。
- `媒体域名解析到非公网地址`：安全拦截生效；不要关闭校验来下载来源不明的 URL。
