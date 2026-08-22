from __future__ import annotations

from typing import Any

import httpx

from .media import build_variants, probe_all
from .models import Aweme, Inspection
from .providers import fetch_metadata, parse_cookie_header
from .resolver import resolve_input


CONNECT_TIMEOUT_SECONDS = 3.5

DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
)


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def normalize_aweme(
    item: dict[str, Any],
    *,
    provider: str,
    cookie_used: bool,
    browser_used: bool,
) -> Aweme:
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    video = item.get("video") if isinstance(item.get("video"), dict) else {}
    duration = item.get("duration") or video.get("duration")
    return Aweme(
        aweme_id=str(item.get("aweme_id") or item.get("awemeId") or ""),
        desc=str(item.get("desc") or "").strip() or None,
        author_name=str(author.get("nickname") or author.get("unique_id") or "").strip() or None,
        duration_ms=_positive_int(duration),
        provider=provider,
        cookie_used=cookie_used,
        browser_fallback_used=browser_used,
        variants=build_variants(item),
    )


def make_client(*, timeout_seconds: float, cookie_header: str | None) -> httpx.AsyncClient:
    # Cap the connect phase well below the read timeout. Measured 2026-08-22: a
    # healthy edge connects in ~0.3s while a bad one hangs until the ceiling, so a
    # 10s connect budget let one flaky edge burn the whole retry allowance. With a
    # short ceiling the retry lands on another edge almost immediately.
    timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, CONNECT_TIMEOUT_SECONDS))
    return httpx.AsyncClient(
        headers={
            "User-Agent": DESKTOP_UA,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            "Referer": "https://www.douyin.com/",
        },
        cookies=parse_cookie_header(cookie_header),
        timeout=timeout,
        follow_redirects=False,
    )


async def inspect_public_aweme(
    input_text: str,
    *,
    browser_fallback: bool = False,
    cookie_header: str | None = None,
    timeout_seconds: float = 35,
) -> Inspection:
    async with make_client(timeout_seconds=timeout_seconds, cookie_header=cookie_header) as client:
        resolved = await resolve_input(input_text, client)
        provider = await fetch_metadata(
            resolved.aweme_id,
            client,
            browser_fallback=browser_fallback,
            cookie_header=cookie_header,
            timeout_seconds=timeout_seconds,
        )
        aweme = normalize_aweme(
            provider.item,
            provider=provider.provider,
            cookie_used=bool(cookie_header),
            browser_used=provider.browser_used,
        )
        if not aweme.aweme_id:
            aweme.aweme_id = resolved.aweme_id
        if aweme.aweme_id != resolved.aweme_id:
            raise RuntimeError(
                f"metadata aweme_id 不匹配: expected={resolved.aweme_id}, got={aweme.aweme_id}"
            )
        if not aweme.variants:
            raise RuntimeError("metadata 中没有发现任何可用视频 candidate")
        await probe_all(client, aweme.variants)
        return Inspection(
            input_text=input_text,
            extracted_url=resolved.extracted_url,
            resolved_url=resolved.resolved_url,
            aweme=aweme,
            provider_failures=provider.failures,
        )
