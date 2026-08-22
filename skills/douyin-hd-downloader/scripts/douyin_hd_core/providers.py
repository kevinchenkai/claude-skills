from __future__ import annotations

import asyncio
import html
import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

import httpx


MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
    "Mobile/15E148 Safari/604.1"
)


class ProviderError(RuntimeError):
    pass


@dataclass(slots=True)
class ProviderResult:
    item: dict[str, Any]
    provider: str
    browser_used: bool
    failures: list[str]


def _balanced_json_object(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def extract_embedded_data(page_html: str) -> dict[str, Any] | None:
    for marker in ("window._ROUTER_DATA", "_ROUTER_DATA"):
        marker_index = page_html.find(marker)
        if marker_index < 0:
            continue
        equals_index = page_html.find("=", marker_index)
        brace_index = page_html.find("{", equals_index)
        if equals_index < 0 or brace_index < 0:
            continue
        raw = _balanced_json_object(page_html, brace_index)
        if raw:
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value

    marker = 'id="RENDER_DATA"'
    marker_index = page_html.find(marker)
    if marker_index >= 0:
        tag_end = page_html.find(">", marker_index)
        script_end = page_html.find("</script>", tag_end)
        if tag_end >= 0 and script_end >= 0:
            raw = html.unescape(page_html[tag_end + 1 : script_end]).strip()
            for candidate in (raw, unquote(raw)):
                try:
                    value = json.loads(candidate)
                except (json.JSONDecodeError, ValueError):
                    continue
                if isinstance(value, dict):
                    return value
    return None


def _looks_like_aweme(value: Any, aweme_id: str) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("video"), dict):
        return False
    item_id = str(value.get("aweme_id") or value.get("awemeId") or "")
    return not item_id or item_id == aweme_id


def find_aweme(data: Any, aweme_id: str) -> dict[str, Any] | None:
    """Locate an exact video item in changing ROUTER_DATA response shapes."""
    preferred: list[dict[str, Any]] = []
    fallback: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if _looks_like_aweme(value, aweme_id):
                item_id = str(value.get("aweme_id") or value.get("awemeId") or "")
                (preferred if item_id == aweme_id else fallback).append(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    return (preferred or fallback or [None])[0]


# A blocked page is one that actually asks the client to solve a challenge.
# Do NOT key off vendor SDK names such as "verifyCenter": measured 2026-08-22,
# that string is present on 6/6 share pages, including every page that parsed
# cleanly, so treating it as a block marker misreports ordinary flakiness as WAF
# and sends the reader off chasing cookies and proxies instead of retrying.
WAF_MARKERS = ("waf_js", "wafchallengeid", "/waf-jschallenge/", "/captcha/", "slardar_captcha")


def is_waf_page(page_html: str) -> bool:
    prefix = page_html[:8000].lower()
    return any(marker in prefix for marker in WAF_MARKERS)


async def _fetch_ssr_once(aweme_id: str, client: httpx.AsyncClient) -> tuple[dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    for kind in ("video", "note"):
        url = f"https://www.iesdouyin.com/share/{kind}/{aweme_id}/"
        try:
            response = await client.get(
                url,
                headers={
                    "User-Agent": MOBILE_UA,
                    "Accept": "text/html",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Referer": "https://www.douyin.com/",
                },
            )
        except httpx.HTTPError as exc:
            reasons.append(f"{kind}: {type(exc).__name__}")
            continue
        if response.status_code != 200:
            reasons.append(f"{kind}: HTTP {response.status_code}")
            continue
        if is_waf_page(response.text):
            reasons.append(f"{kind}: WAF challenge")
            continue
        embedded = extract_embedded_data(response.text)
        if not embedded:
            reasons.append(f"{kind}: no embedded data")
            continue
        item = find_aweme(embedded, aweme_id)
        if item:
            return item, reasons
        # The usual failure: SSR served the page shell before hydrating the item.
        # It is transient and independent per request, so the caller retries.
        reasons.append(f"{kind}: page shell contained no video item")
    return None, reasons


async def fetch_from_ssr(
    aweme_id: str,
    client: httpx.AsyncClient,
    *,
    attempts: int = 3,
    retry_delay: float = 0.8,
) -> dict[str, Any]:
    """Fetch one item from iesdouyin SSR, retrying the transient empty-shell response.

    Measured 2026-08-22 on a public link: a single request succeeds ~4/6 of the
    time, while <=3 independent attempts succeeded 6/6. Retrying is what makes
    this provider usable; without it a normal run fails outright about a third
    of the time.
    """
    last_reasons: list[str] = []
    for attempt in range(attempts):
        item, reasons = await _fetch_ssr_once(aweme_id, client)
        if item:
            return item
        last_reasons = reasons
        if attempt + 1 < attempts:
            await asyncio.sleep(retry_delay * (attempt + 1))
    raise ProviderError(
        f"iesdouyin SSR {attempts} 次尝试均未返回完整作品数据；" + "; ".join(last_reasons)
    )


def parse_cookie_header(raw_cookie: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in (raw_cookie or "").split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        if name:
            result[name] = value.strip()
    return result


async def fetch_from_browser(
    aweme_id: str,
    *,
    cookie_header: str | None = None,
    timeout_seconds: float = 35,
) -> dict[str, Any]:
    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise ProviderError(
            "浏览器回退需要 Python Playwright：python3 -m pip install playwright"
        ) from exc

    target = f"https://www.douyin.com/video/{aweme_id}"
    channel = (os.environ.get("DOUYIN_BROWSER_CHANNEL") or "chrome").strip()
    timeout_ms = int(timeout_seconds * 1000)

    async with async_playwright() as playwright:
        launch_errors: list[str] = []
        browser = None
        for launch_kwargs in (
            {"channel": channel, "headless": True},
            {"headless": True},
        ):
            try:
                browser = await playwright.chromium.launch(**launch_kwargs)
                break
            except Exception as exc:  # browser availability differs per workstation
                launch_errors.append(f"{type(exc).__name__}: {str(exc).splitlines()[0]}")
        if browser is None:
            raise ProviderError("无法启动 Chrome/Chromium：" + " | ".join(launch_errors))

        try:
            context = await browser.new_context(
                locale="zh-CN",
                viewport={"width": 1280, "height": 720},
            )
            cookies = parse_cookie_header(cookie_header)
            if cookies:
                await context.add_cookies(
                    [
                        {
                            "name": name,
                            "value": value,
                            "domain": ".douyin.com",
                            "path": "/",
                            "secure": True,
                        }
                        for name, value in cookies.items()
                    ]
                )
            page = await context.new_page()
            try:
                async with page.expect_response(
                    lambda response: "/aweme/v1/web/aweme/detail/" in response.url,
                    timeout=timeout_ms,
                ) as response_info:
                    await page.goto(target, wait_until="domcontentloaded", timeout=timeout_ms)
                response = await response_info.value
                payload = await response.json()
            except PlaywrightTimeoutError as exc:
                raise ProviderError("Chrome 等待 aweme detail 响应超时") from exc
            except Exception as exc:
                raise ProviderError(f"Chrome 读取 aweme detail 失败: {type(exc).__name__}") from exc

            item = payload.get("aweme_detail") if isinstance(payload, dict) else None
            if not _looks_like_aweme(item, aweme_id):
                status = payload.get("status_code") if isinstance(payload, dict) else None
                raise ProviderError(f"Chrome 响应缺少目标 aweme_detail（status_code={status}）")
            return item
        finally:
            await browser.close()


async def fetch_metadata(
    aweme_id: str,
    client: httpx.AsyncClient,
    *,
    browser_fallback: bool,
    cookie_header: str | None,
    timeout_seconds: float,
) -> ProviderResult:
    failures: list[str] = []
    try:
        item = await fetch_from_ssr(aweme_id, client)
        video = item.get("video") if isinstance(item.get("video"), dict) else {}
        if video.get("bit_rate") or not browser_fallback:
            return ProviderResult(item, "iesdouyin_ssr", False, failures)
        failures.append("iesdouyin SSR 返回可播放地址，但缺少 video.bit_rate 阶梯")
    except ProviderError as exc:
        failures.append(str(exc))

    if not browser_fallback:
        raise ProviderError(
            f"{failures[-1]}。可加 --browser-fallback，让真实 Chrome 生成当前有效签名后读取元数据。"
        )

    try:
        item = await fetch_from_browser(
            aweme_id,
            cookie_header=cookie_header,
            timeout_seconds=timeout_seconds,
        )
        return ProviderResult(item, "douyin_browser", True, failures)
    except ProviderError as exc:
        failures.append(str(exc))
        raise ProviderError("所有 metadata provider 均失败：" + " | ".join(failures)) from exc
