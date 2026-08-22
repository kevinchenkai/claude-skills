---
name: douyin-hd-downloader
description: Inspect and download a single public Douyin video from a full URL, short link, or copied share text. Use when the user wants source-quality analysis, original-first download, bitrate/codec comparison, or ffprobe verification. Do not use for private, paid, login-restricted, or bulk profile content.
---

# Douyin HD Downloader

解析公开单条抖音作品，枚举并探测实际视频源，默认优先上传原片；原片不可用或不优于最高转码档时自动回退。下载只做字节流保存，禁止转码。

只处理用户有权保存的公开内容。不要绕过登录、私密、付费、地区或其他访问控制；不要把脚本改造成任意 URL 代理或批量爬虫。

## 执行

入口是 [`scripts/douyin_hd.py`](scripts/douyin_hd.py)。先 `inspect`，确认候选和 provider，再下载：

```bash
python3 scripts/douyin_hd.py inspect '<URL 或分享文案>' --debug
python3 scripts/douyin_hd.py download '<URL 或分享文案>' --quality original
```

下载默认落到 `~/Downloads/douyin/<aweme_id>/`，用 `--output` 可改。

轻量 SSR 只返回页面壳时，用真实 Chrome 回退；它默认关闭，不要让每条请求都启动浏览器：

```bash
python3 scripts/douyin_hd.py inspect '<URL>' --browser-fallback --debug
```

需要比较 original 与 highest 时：

```bash
python3 scripts/douyin_hd.py compare '<URL>' --browser-fallback
```

完整参数、依赖、输出文件和故障排查见 [`references/usage.md`](references/usage.md)。需要修改 provider、original 策略、安全边界或下载逻辑时，先读 [`references/architecture.md`](references/architecture.md)。

## 必须保持的语义

- `original` 是 `ratio=default` 原片探测，不等于 `video.bit_rate[]` 的最高码率。
- original 只有在 probe 有效且实际体积大于最高转码档时才优先；否则回退 `highest`。
- **SSR 与 probe 的瞬时失败必须重试，不能当成结论。** SSR 单次成功率约 4/6（页面壳是常态抖动，不是风控）；original probe 的一次 ConnectTimeout 不代表原片不存在。
- **绝不静默产出带水印文件。** `bit_rate[]` 为空时 `highest` 会退化成 `playwm` 水印源；此时 `--quality original` 必须报错中止。水印以 URL 的 `/playwm/` 判定，`has_watermark` 字段不可信。
- 风控判据只认真正的挑战标记，不得用 `verifyCenter` 这类厂商 SDK 名（它在所有正常页面上都存在）。
- `highest` 只在 probe 成功的转码候选中按分辨率、码率、文件大小排序。
- 输出候选表与 JSON 时不得打印 CDN query、Cookie 或完整签名 URL。
- 媒体请求只能来自 Douyin metadata 或由其中的 video URI 构建；每次重定向都必须保持 HTTPS 且解析到公网地址。
- 下载写入 `.part`，校验长度后原子改名；中断或失败要清理 `.part`。
- `ffprobe` 只做验证，不用 `ffmpeg` 重编码。

## 验收

改动后运行：

```bash
python3 -m pytest -q tests
python3 /path/to/skill-creator/scripts/quick_validate.py .
```

涉及真实 provider 或候选逻辑的改动，还要按 `references/usage.md` 跑固定公开 URL 集成测试，并保存脱敏报告；不要在测试里写死 CDN、分辨率或码率。

**联网验证必须连续跑多次（建议 ≥5），确认每次结果一致。** 这条链路的失败是间歇性的，跑一次成功证明不了可用性——首版就是这样把 ~30% 的失败率漏过去的。
