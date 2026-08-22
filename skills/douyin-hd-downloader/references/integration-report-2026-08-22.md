# 固定视频真实网络报告（2026-08-22）

测试输入：`https://www.douyin.com/video/7667208299670554725`

本报告记录一次真实网络运行，用于证明首版链路可工作；CDN、档位、大小和编码都可能随平台重新转码而变化，不能作为单元测试常量。

## Provider

- `aweme_id`：`7667208299670554725`
- provider：`douyin_browser`
- Cookie：不需要
- browser fallback：需要。此次 SSR 返回可播放地址但缺少 `video.bit_rate[]`，所以显式回退 Chrome。
- `video.bit_rate[]`：12 档
- original：探测成功，`ratio=default` 最终响应 HTTP 206，15,864,119 bytes。

## 转码候选

所有档位 probe 均为 HTTP 206：

| gear | resolution | codec | metadata bitrate | Content-Length |
| --- | ---: | --- | ---: | ---: |
| `normal_1080_0` | 1920×1080 | H.264 | 4,202,130 | 6,601,022 |
| `1080_1_1` | 1920×1080 | HEVC | 4,054,474 | 6,369,073 |
| `normal_720_0` | 1280×720 | H.264 | 3,223,611 | 5,063,890 |
| `normal_540_0` | 1024×576 | H.264 | 2,902,632 | 4,559,673 |
| `low_720_0` | 1280×720 | H.264 | 2,799,397 | 4,397,504 |
| `720_1_1` | 1280×720 | HEVC | 2,663,206 | 4,183,564 |
| `low_540_0` | 1024×576 | H.264 | 2,510,099 | 3,943,053 |
| `720_2_1` | 1280×720 | HEVC | 2,088,243 | 3,280,369 |
| `lower_540_0` | 1024×576 | H.264 | 1,903,181 | 2,989,660 |
| `adapt_low_540_0` | 1024×576 | H.264 | 1,622,225 | 2,548,313 |
| `720_3_1` | 1280×720 | HEVC | 1,538,660 | 2,417,043 |
| `540_3_1` | 960×540 | HEVC | 1,013,230 | 1,591,659 |

另发现一个 `download_addr`，probe 为 5,063,890 bytes；它不参与 `highest` 的 `bit_rate[]` 排序。

## 下载与 ffprobe

| mode | selected source | bytes | video | fps | video bitrate | audio | duration | container bitrate |
| --- | --- | ---: | --- | ---: | ---: | --- | ---: | ---: |
| original | `ratio=default` | 15,864,119 | HEVC 1920×1080 | ≈60 | 10,003,677 | AAC 123,057 | 12.516667s | 10,139,516 |
| highest | `normal_1080_0` | 6,601,022 | H.264 1920×1080 | 30 | 4,143,582 | AAC 51,366 | 12.566667s | 4,202,242 |

SHA-256：

- original：`e665d65fbfad90129a238d2f1a23fdcc4a8ac3a42e4f60747d00276ff625a1e5`
- highest：`ce6e3689e39996dfacc3df99c6d1b30852cc7bf44053301dde897ebdd8917569`

## 默认选择结论

默认选择 original。原因不是标签，而是它 probe 成功且实际文件大小 15,864,119 bytes，大于最高转码档的 6,601,022 bytes；下载后的 ffprobe 又确认 original 为 1920×1080 HEVC、约 60fps、约 10.14 Mbps 容器码率，而 highest 为 1920×1080 H.264、30fps、约 4.20 Mbps。

运行产物位于测试机临时目录 `/tmp/douyin-hd-integration/7667208299670554725/`，未提交视频文件或带 query 的 CDN URL。
