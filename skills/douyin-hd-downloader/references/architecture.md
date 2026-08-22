# 首版架构与不变量

## 调用链

```text
share text / URL
  → exact-domain URL resolver
  → aweme_id
  → iesdouyin SSR
  → optional real-Chrome aweme-detail response
  → normalized logical candidates
  → sequential Range probes
  → quality selector
  → .part streaming download + length check + atomic rename
  → ffprobe JSON
```

第一版不实现 Web API、任意媒体代理、主页批量、收藏、评论、直播或多平台支持。

## Provider

`iesdouyin_ssr` 是无签名快路径，解析 `_ROUTER_DATA` 与 `RENDER_DATA`。解析器用字符串感知的大括号深度匹配，不能用会被嵌套 JSON 截断的惰性正则。

`douyin_browser` 只在显式 `--browser-fallback` 时启动。它等待页面自己发出的 `/aweme/v1/web/aweme/detail/` 响应并读取 JSON；这让抖音页面生成当时有效的签名，项目本身不复制或维护易失的 `a_bogus` 实现。

Provider 返回的数据必须匹配请求的 `aweme_id`。页面壳只有 `itemId` 而没有 `video` 时，不得误判为完整作品数据。

SSR **必须重试**。实测 2026-08-22：单次请求成功率约 4/6，而 ≤3 次独立尝试成功率 6/6，每次尝试相互独立。页面壳是常态抖动，不是风控。

风控判据只认真正的挑战标记（`waf_js` / `wafchallengeid` / `/waf-jschallenge/` / `/captcha/`）。**不得**用 `verifyCenter` 之类的厂商 SDK 名做判据——实测它在 6/6 的页面上都存在，包括全部解析成功的页面，用它会把普通抖动误报成 WAF，把排查方向带到 cookie 和代理上。

## Candidate

`video.bit_rate[]` 每个档位生成一个逻辑 candidate，保留多个 CDN mirror。额外的 `play_addr*` / `download_addr` 仅在 URL 集合不与转码档重复时加入。

original 由 metadata 中的 video URI 构建：

```text
/aweme/v1/play/?video_id=<uri>&ratio=default&line=0
&is_play_url=1&watermark=0&source=PackSourceEnum_PUBLISH
```

这是 best-effort probe，不是永久 CDN 拼接规则。端点失效只让 `original` 回退，不能中断 `highest`。

## Probe 与选择

Probe 对每个逻辑 candidate 的 mirrors 依次发 `Range: bytes=0-65535`，只接受 200/206 和视频内容；HTML/JSON 风控页即使 HTTP 200 也失败。总大小优先读 `Content-Range`，200 时读 `Content-Length`。

`highest` 排序键为：

```text
(width × height, bitrate, probed file size)
```

`original` 先得到 `highest`，再比较 original 的真实 probe 体积。original 只有在有效且更大时胜出，避免超分转码档反而大于上传原片的反例。

Probe 失败要区分**瞬时**与**终局**。ConnectTimeout / ReadTimeout / 5xx / 429 会重试至多 3 次；403、404 之类不重试。实测 2026-08-22：一次 10.4s 的 ConnectTimeout 曾让 original 被判无效，静默降级到 2.8 MiB 的水印档，而紧接着重探同一 URL 两次都是 206 / 45,562,198 bytes。**一次网络抖动不能当成「原片不存在」的结论。**

当 `video.bit_rate[]` 为空时，`highest` 会退化成带水印的 `playwm` 地址。此时 `--quality original` **必须报错中止**，不得静默返回水印文件。水印判定以 URL 里的 `/playwm/` 路径为准，不能只信 `has_watermark` 字段——实测该字段在水印候选上是 `None`。

`compatible` 在有效 H.264 候选中用同一质量排序；它不转码，也不谎称已经验证 AAC。真实音视频 codec 以下载后的 ffprobe 为准。

## 安全与隐私

- 输入域名是精确白名单，短链每次跳转都重验。
- 媒体 URL 只能由 provider 数据或其中的 URI 产生。
- 媒体每次跳转都要求 HTTPS；域名解析结果不得包含私网、回环、链路本地、保留或 metadata-service 地址。
- 控制台与 JSON 不输出 CDN query、签名、Cookie。
- Cookie 只从指定环境变量读取，不落盘。

## 参考而非复制

设计行为参考了以下公开项目，但首版代码为独立实现，没有复制其签名源码：

- <https://github.com/jiji262/douyin-downloader>：original 与 highest 的语义、原片体积比较。
- <https://github.com/qgeng1465/douyin-watermark-free-downloader>：分享页嵌入数据解析思路。
- <https://github.com/xlongDev/shiying>：SSR → 浏览器回退和响应提取思路。
