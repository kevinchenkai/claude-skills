---
name: douyin-hd-downloader
description: Inspect and download a single public Douyin video from a full URL, short link, or copied share text. Use when the user wants source-quality analysis, original-first download, bitrate/codec comparison, or ffprobe verification. Do not use for private, paid, login-restricted, or bulk profile content.
---

# Douyin HD Downloader

解析公开单条抖音作品，枚举并探测实际视频源，默认优先上传原片；原片不可用或不优于最高转码档时自动回退。下载只做字节流保存，禁止转码。

只处理用户有权保存的公开内容。不要绕过登录、私密、付费、地区或其他访问控制；不要把脚本改造成任意 URL 代理或批量爬虫。

## 执行

入口是 [`scripts/run.sh`](scripts/run.sh)，它负责挑一个可用解释器。**不要直接用 `python3`** ——系统自带的常是 3.9 且不带 `httpx`。要固定解释器就设 `DOUYIN_PYTHON`。

```bash
./scripts/run.sh inspect '<URL 或分享文案>'
./scripts/run.sh download '<URL 或分享文案>' --quality original
```

下载默认落到 `~/Downloads/douyin/<aweme_id>/`，用 `--output` 可改。

候选表默认只列最相关的几档（原片、最高档，以及任何探测失败的档位），
加 `--all-candidates` 看全部，加 `--debug` 看脱敏 URL 细节。

轻量 SSR 只返回页面壳时，用真实 Chrome 回退；它默认关闭，不要让每条请求都启动浏览器：

```bash
./scripts/run.sh inspect '<URL>' --browser-fallback
```

需要比较 original 与 highest 时用 `compare`。

失败先重试——SSR 与 original probe 都会间歇性失败，单次失败不是结论。

完整参数、依赖与故障排查见 [`references/usage.md`](references/usage.md)。
要改 provider、original 策略、安全边界或下载逻辑，**必须先读**
[`references/architecture.md`](references/architecture.md)：那里有不能破坏的语义、
验收要求，以及已被实测证伪的假设。三条视频的实测数据见
[`references/integration-report.md`](references/integration-report.md)。
