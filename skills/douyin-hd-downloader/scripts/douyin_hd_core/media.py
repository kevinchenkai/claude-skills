from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

import httpx

from .models import ProbeResult, VideoVariant


class MediaError(RuntimeError):
    pass


def _as_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _normalise_media_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if value.startswith("//"):
        value = f"https:{value}"
    parsed = urlsplit(value)
    if parsed.scheme == "http":
        value = urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, parsed.fragment))
        parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    return value


def extract_urls(node: Any) -> list[str]:
    if not isinstance(node, dict):
        return []
    raw = node.get("url_list") or node.get("urlList") or []
    if isinstance(raw, str):
        raw = [raw]
    urls: list[str] = []
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict):
                urls.extend(extract_urls(entry))
                entry = entry.get("url") or entry.get("uri")
            normalised = _normalise_media_url(entry)
            if normalised and normalised not in urls:
                urls.append(normalised)
    for key in ("url",):
        normalised = _normalise_media_url(node.get(key))
        if normalised and normalised not in urls:
            urls.append(normalised)
    return urls


def infer_codec(entry: dict[str, Any], source_key: str = "") -> str | None:
    raw = str(
        entry.get("codec")
        or entry.get("codec_type")
        or entry.get("format")
        or ""
    ).lower()
    if entry.get("is_bytevc1") or entry.get("is_h265") or "265" in source_key:
        return "h265"
    if any(token in raw for token in ("h265", "hevc", "bytevc1")):
        return "h265"
    if any(token in raw for token in ("h264", "avc")) or "h264" in source_key:
        return "h264"
    if "is_bytevc1" in entry or "is_h265" in entry:
        return "h264"
    if source_key == "play_addr_265":
        return "h265"
    if source_key == "play_addr_h264":
        return "h264"
    return None


def _variant_from_addr(
    source_type: str,
    entry: dict[str, Any],
    addr: dict[str, Any],
    *,
    source_key: str = "",
) -> VideoVariant | None:
    urls = extract_urls(addr)
    if not urls:
        return None
    return VideoVariant(
        source_type=source_type,
        urls=urls,
        width=_as_int(addr.get("width") or entry.get("width")),
        height=_as_int(addr.get("height") or entry.get("height")),
        bitrate=_as_int(entry.get("bit_rate") or entry.get("bitrate")),
        codec=infer_codec(entry, source_key),
        gear_name=str(entry.get("gear_name") or "") or None,
        quality_type=_as_int(entry.get("quality_type")),
        file_size_hint=_as_int(addr.get("data_size") or entry.get("data_size")),
        uri=str(addr.get("uri") or "") or None,
        has_watermark=entry.get("has_watermark"),
    )


def build_variants(item: dict[str, Any]) -> list[VideoVariant]:
    video = item.get("video") if isinstance(item.get("video"), dict) else {}
    variants: list[VideoVariant] = []
    seen_logical: set[tuple[Any, ...]] = set()

    for entry in video.get("bit_rate") or []:
        if not isinstance(entry, dict):
            continue
        addr = entry.get("play_addr") or entry.get("playAddr")
        if not isinstance(addr, dict):
            continue
        variant = _variant_from_addr("bitrate", entry, addr)
        if not variant:
            continue
        key = (
            variant.gear_name,
            variant.width,
            variant.height,
            variant.bitrate,
            variant.codec,
        )
        if key not in seen_logical:
            variants.append(variant)
            seen_logical.add(key)

    known_url_sets = {tuple(v.urls) for v in variants}
    for source_key, source_type in (
        ("play_addr_h264", "play_addr"),
        ("play_addr_265", "play_addr"),
        ("play_addr", "play_addr"),
        ("download_addr", "download_addr"),
    ):
        addr = video.get(source_key)
        if not isinstance(addr, dict):
            continue
        variant = _variant_from_addr(source_type, video, addr, source_key=source_key)
        if not variant or tuple(variant.urls) in known_url_sets:
            continue
        variants.append(variant)
        known_url_sets.add(tuple(variant.urls))

    uri = next((variant.uri for variant in variants if variant.uri), None)
    if uri:
        params = {
            "video_id": uri,
            "ratio": "default",
            "line": "0",
            "is_play_url": "1",
            "watermark": "0",
            "source": "PackSourceEnum_PUBLISH",
        }
        original_url = f"https://www.douyin.com/aweme/v1/play/?{urlencode(params)}"
        variants.insert(
            0,
            VideoVariant(
                source_type="original",
                urls=[original_url],
                gear_name="ratio_default",
                uri=uri,
                has_watermark=False,
            ),
        )
    return variants


def _is_public_ip(ip_text: str) -> bool:
    address = ipaddress.ip_address(ip_text)
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


async def validate_public_media_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise MediaError("媒体 URL 必须是带主机名的 https 地址")
    if parsed.username or parsed.password:
        raise MediaError("媒体 URL 不能包含用户名或密码")
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        raise MediaError("媒体 URL 指向 localhost")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not _is_public_ip(str(literal)):
            raise MediaError("媒体 URL 指向非公网 IP")
        return

    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise MediaError(f"媒体域名 DNS 解析失败: {host}") from exc
    addresses = {info[4][0] for info in infos}
    if not addresses or any(not _is_public_ip(address) for address in addresses):
        raise MediaError(f"媒体域名解析到非公网地址: {host}")


def _content_total(headers: httpx.Headers, status_code: int) -> int | None:
    content_range = headers.get("content-range", "")
    if "/" in content_range:
        total = content_range.rsplit("/", 1)[-1]
        if total != "*":
            return _as_int(total)
    if status_code == 200:
        return _as_int(headers.get("content-length"))
    return None


def _looks_like_media(content_type: str, sample: bytes) -> bool:
    content_type = content_type.lower().split(";", 1)[0].strip()
    if content_type.startswith("video/"):
        return True
    if content_type in {"application/octet-stream", "binary/octet-stream"}:
        return b"ftyp" in sample[:64] or sample.startswith(b"\x1aE\xdf\xa3")
    return b"ftyp" in sample[:64] or sample.startswith(b"\x1aE\xdf\xa3")


async def _probe_url(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_redirects: int = 8,
    sample_limit: int = 65536,
) -> ProbeResult:
    current = url
    for _ in range(max_redirects + 1):
        try:
            await validate_public_media_url(current)
            async with client.stream(
                "GET",
                current,
                headers={"Range": f"bytes=0-{sample_limit - 1}", "Accept": "*/*"},
                follow_redirects=False,
            ) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        return ProbeResult(
                            status_code=response.status_code,
                            error="redirect without Location",
                        )
                    current = urljoin(current, location)
                    continue

                sample = bytearray()
                async for chunk in response.aiter_bytes():
                    sample.extend(chunk[: max(0, sample_limit - len(sample))])
                    if len(sample) >= sample_limit:
                        break
                content_type = response.headers.get("content-type", "")
                ok_status = response.status_code in {200, 206}
                ok = ok_status and _looks_like_media(content_type, bytes(sample))
                error = None
                if not ok_status:
                    error = f"HTTP {response.status_code}"
                elif not ok:
                    error = f"non-video response ({content_type or 'unknown content-type'})"
                return ProbeResult(
                    ok=ok,
                    status_code=response.status_code,
                    content_type=content_type or None,
                    content_length=_content_total(response.headers, response.status_code),
                    resolved_url=current,
                    sampled_bytes=len(sample),
                    error=error,
                )
        except (httpx.HTTPError, MediaError) as exc:
            return ProbeResult(error=f"{type(exc).__name__}: {str(exc)[:180]}")
    return ProbeResult(error=f"media redirect exceeded {max_redirects}")


def _is_transient_probe_error(result: ProbeResult) -> bool:
    """A network hiccup, not a verdict that the source is unavailable."""
    if result.ok:
        return False
    error = result.error or ""
    if any(
        token in error
        for token in ("ConnectTimeout", "ReadTimeout", "PoolTimeout", "ConnectError", "RemoteProtocolError")
    ):
        return True
    return result.status_code in {408, 425, 429, 500, 502, 503, 504}


async def probe_variant(
    client: httpx.AsyncClient,
    variant: VideoVariant,
    *,
    attempts: int = 6,
    retry_delay: float = 0.3,
) -> ProbeResult:
    """Probe a candidate, retrying transient failures before declaring it dead.

    A single ConnectTimeout used to mark the original source invalid, which then
    silently downgraded the selection to a watermarked play_addr. Measured
    2026-08-22: the same URL that timed out returned HTTP 206 with 45,562,198
    bytes on immediately following attempts.

    Failures are NOT evenly spread -- three consecutive timeouts were observed,
    and pausing 20s did not help, so this is flaky routing to a subset of edges
    rather than rate limiting. The fix pairs a short connect timeout (see
    CONNECT_TIMEOUT_SECONDS) with more attempts: 5/5 trials then succeeded,
    worst case 4.3s.
    """
    last = ProbeResult(error="candidate has no URL")
    for url in variant.urls:
        for attempt in range(attempts):
            last = await _probe_url(client, url)
            if last.ok:
                variant.probe = last
                if last.content_length:
                    variant.file_size_hint = last.content_length
                return last
            if not _is_transient_probe_error(last) or attempt + 1 >= attempts:
                break
            await asyncio.sleep(retry_delay * (attempt + 1))
    variant.probe = last
    return last


async def probe_all(client: httpx.AsyncClient, variants: Iterable[VideoVariant]) -> None:
    # Deliberately sequential: this is a single-item inspector, not a crawler.
    for variant in variants:
        await probe_variant(client, variant)


def _score(variant: VideoVariant) -> tuple[int, int, int]:
    pixels = (variant.width or 0) * (variant.height or 0)
    return pixels, variant.bitrate or 0, variant.file_size_hint or 0


def _normalise_codec(codec: str | None) -> str | None:
    value = (codec or "").lower()
    if value in {"h265", "hevc", "bytevc1"}:
        return "h265"
    if value in {"h264", "avc"}:
        return "h264"
    return value or None


def is_watermarked(variant: VideoVariant) -> bool:
    """Detect a watermarked source from the URL, not the metadata flag.

    Measured 2026-08-22: SSR leaves ``has_watermark`` unset (None) on the very
    candidate served from ``/aweme/v1/playwm/``, so the flag alone cannot be
    trusted. The ``playwm`` path segment is the reliable evidence.
    """
    if variant.has_watermark:
        return True
    return any("/playwm/" in url for url in variant.urls)


def _valid_transcodes(variants: Iterable[VideoVariant]) -> list[VideoVariant]:
    bitrates = [v for v in variants if v.source_type == "bitrate" and v.probe.ok]
    if bitrates:
        return bitrates
    return [v for v in variants if v.source_type == "play_addr" and v.probe.ok]


def select_variant(
    variants: list[VideoVariant],
    quality: str,
    codec: str | None = None,
) -> tuple[VideoVariant, str]:
    quality = quality.strip().lower()
    requested_codec = _normalise_codec(codec)
    transcodes = _valid_transcodes(variants)
    if requested_codec:
        transcodes = [v for v in transcodes if _normalise_codec(v.codec) == requested_codec]
    if not transcodes:
        suffix = f"（codec={requested_codec}）" if requested_codec else ""
        raise MediaError(f"没有 probe 成功的转码候选{suffix}")

    highest = max(transcodes, key=_score)
    if quality == "highest":
        return highest, "highest: probe 成功后按分辨率、码率、文件大小排序"

    if quality == "original":
        def _codec_matches(variant: VideoVariant) -> bool:
            return not requested_codec or _normalise_codec(variant.codec) == requested_codec

        # Keep the probe-failed candidate around separately so the error message can
        # distinguish "no original in metadata" from "original existed but timed out".
        original_candidates = [
            v for v in variants if v.source_type == "original" and _codec_matches(v)
        ]
        original = next((v for v in original_candidates if v.probe.ok), None)
        if original:
            original_size = original.file_size_hint or 0
            highest_size = highest.file_size_hint or 0
            if not highest_size or original_size > highest_size:
                return original, (
                    f"original: ratio=default 探测有效且体积 {original_size} "
                    f"> 最高转码档 {highest_size}"
                )
        # Refuse to pass off a watermarked file as the result of --quality original.
        # When video.bit_rate[] is empty, "highest" degrades to the watermarked
        # playwm address; silently returning it looked like success while handing
        # back 2.8 MiB instead of the 43.5 MiB source.
        if is_watermarked(highest):
            if original_candidates:
                failed = original_candidates[0]
                detail = f"候选存在但探测失败：{failed.probe.error or 'probe 未成功'}"
            else:
                detail = "元数据中没有 ratio=default 原片候选"
            raise MediaError(
                "original 不可用，且唯一可回退的候选是带水印的 playwm 地址，已中止以免产出假原片。"
                f"（原片探测：{detail}）"
                " 可重试；或显式用 --quality highest 接受带水印结果。"
            )
        return highest, "original fallback: 原片无效、体积未知或不优于最高转码档"

    if quality == "compatible":
        compatible = [v for v in transcodes if _normalise_codec(v.codec) == "h264"]
        if not compatible:
            raise MediaError("compatible 模式没有有效 H.264 候选")
        return max(compatible, key=_score), "compatible: 选择最高质量 H.264 MP4 候选"

    match = re.fullmatch(r"(\d{3,4})p", quality)
    if match:
        target = int(match.group(1))

        def matches(variant: VideoVariant) -> bool:
            short_edge = min(variant.width or 0, variant.height or 0)
            gear = (variant.gear_name or "").lower()
            return short_edge == target or bool(re.search(rf"(?:^|_){target}(?:_|$)", gear))

        matching = [variant for variant in transcodes if matches(variant)]
        if not matching:
            raise MediaError(f"没有 probe 成功的 {quality} 候选")
        return max(matching, key=_score), f"{quality}: 在目标分辨率内按码率和文件大小排序"

    if quality == "play_addr":
        candidates = [v for v in variants if v.source_type == "play_addr" and v.probe.ok]
        if not candidates:
            raise MediaError("没有有效 play_addr 候选")
        return max(candidates, key=_score), "play_addr: 显式对比普通播放地址"

    raise MediaError("quality 必须是 original/highest/compatible/1080p/720p/540p")


async def _stream_download_once(
    client: httpx.AsyncClient,
    url: str,
    part_path: Path,
    *,
    max_redirects: int = 8,
) -> tuple[int, str]:
    current = url
    for _ in range(max_redirects + 1):
        await validate_public_media_url(current)
        async with client.stream("GET", current, follow_redirects=False) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise MediaError(f"HTTP {response.status_code} missing Location")
                current = urljoin(current, location)
                continue
            if response.status_code not in {200, 206}:
                raise MediaError(f"HTTP {response.status_code}")
            expected = _content_total(response.headers, response.status_code)
            total = 0
            digest = hashlib.sha256()
            with part_path.open("wb") as output:
                first_chunk = True
                async for chunk in response.aiter_bytes(1024 * 1024):
                    if first_chunk:
                        first_chunk = False
                        content_type = response.headers.get("content-type", "")
                        if not _looks_like_media(content_type, chunk):
                            raise MediaError(
                                f"下载响应不是视频 ({content_type or 'unknown content-type'})"
                            )
                    output.write(chunk)
                    digest.update(chunk)
                    total += len(chunk)
            if total <= 0:
                raise MediaError("下载结果为空文件")
            if expected and total != expected:
                raise MediaError(f"Content-Length 不一致: expected={expected}, got={total}")
            return total, digest.hexdigest()
    raise MediaError(f"media redirect exceeded {max_redirects}")


async def download_variant(
    client: httpx.AsyncClient,
    variant: VideoVariant,
    destination: Path,
) -> tuple[int, str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    part_path = destination.with_name(f"{destination.name}.part")
    urls = [variant.best_download_url, *variant.urls]
    urls = list(dict.fromkeys(url for url in urls if url))
    last_error: Exception | None = None
    try:
        for url in urls:
            for delay in (0, 1, 2, 5):
                if delay:
                    await asyncio.sleep(delay)
                try:
                    total, digest = await _stream_download_once(client, url, part_path)
                    os.replace(part_path, destination)
                    return total, digest
                except (httpx.TransportError, httpx.TimeoutException) as exc:
                    last_error = exc
                    part_path.unlink(missing_ok=True)
                    continue
                except MediaError as exc:
                    last_error = exc
                    part_path.unlink(missing_ok=True)
                    # Persistent auth/not-found failures should move to the next mirror.
                    if "HTTP 403" in str(exc) or "HTTP 404" in str(exc):
                        break
                    continue
        raise MediaError(f"所有下载候选失败: {last_error}")
    except BaseException:
        part_path.unlink(missing_ok=True)
        raise


def run_ffprobe(path: Path) -> dict[str, Any]:
    executable = shutil.which("ffprobe")
    if not executable:
        raise MediaError("未找到 ffprobe；请先安装 ffmpeg（macOS: brew install ffmpeg）")
    command = [
        executable,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,bit_rate",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        error = " ".join(result.stderr.split())[:500]
        raise MediaError(f"ffprobe 失败: {error}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaError("ffprobe 返回了无效 JSON") from exc
    video_streams = [s for s in payload.get("streams", []) if s.get("codec_type") == "video"]
    if not video_streams:
        raise MediaError("ffprobe 未发现 video stream")
    return payload


def ffprobe_summary(payload: dict[str, Any]) -> dict[str, Any]:
    streams = payload.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    container = payload.get("format") or {}
    return {
        "resolution": (
            f"{video.get('width')}x{video.get('height')}"
            if video.get("width") and video.get("height")
            else None
        ),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "fps": video.get("avg_frame_rate") or video.get("r_frame_rate"),
        "video_bitrate": _as_int(video.get("bit_rate")),
        "container_bitrate": _as_int(container.get("bit_rate")),
        "duration_seconds": float(container["duration"]) if container.get("duration") else None,
        "file_size": _as_int(container.get("size")),
    }
