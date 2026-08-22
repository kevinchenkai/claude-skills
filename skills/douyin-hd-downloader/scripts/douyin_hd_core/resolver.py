from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx


ALLOWED_HOSTS = frozenset(
    {
        "douyin.com",
        "www.douyin.com",
        "v.douyin.com",
        "iesdouyin.com",
        "www.iesdouyin.com",
        "v.iesdouyin.com",
    }
)
URL_RE = re.compile(r"https?://[^\s<>\"'，。；：！？、）】》〉」』〕］}]+", re.IGNORECASE)
ID_PATTERNS = (
    re.compile(r"/(?:share/)?(?:video|note|slides)/(\d+)", re.IGNORECASE),
    re.compile(r"[?&](?:aweme_id|item_ids|modal_id)=(\d+)", re.IGNORECASE),
)
TRAILING_PUNCTUATION = "，。；：！？、）】》〉」』〕］}>,.;:!?)]"


class ResolveError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ResolvedInput:
    extracted_url: str
    resolved_url: str
    aweme_id: str


def _hostname(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().rstrip(".")


def validate_input_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise ResolveError("只支持 http/https 抖音链接")
    if _hostname(url) not in ALLOWED_HOSTS:
        raise ResolveError(f"不允许的域名: {_hostname(url) or '<empty>'}")
    if parsed.username or parsed.password:
        raise ResolveError("链接中不能包含用户名或密码")
    return url


def extract_url(text: str) -> str:
    for match in URL_RE.finditer(text):
        candidate = match.group(0).rstrip(TRAILING_PUNCTUATION)
        try:
            return validate_input_url(candidate)
        except ResolveError:
            continue
    raise ResolveError("输入中没有找到允许的抖音公开链接")


def extract_aweme_id(url: str) -> str | None:
    for pattern in ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


async def resolve_input(
    text: str,
    client: httpx.AsyncClient,
    *,
    max_redirects: int = 8,
) -> ResolvedInput:
    extracted = extract_url(text)
    direct_id = extract_aweme_id(extracted)
    if direct_id:
        return ResolvedInput(extracted, extracted, direct_id)

    current = extracted
    for _ in range(max_redirects + 1):
        validate_input_url(current)
        try:
            response = await client.get(
                current,
                headers={"Range": "bytes=0-0", "Accept": "text/html,*/*"},
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            raise ResolveError(f"短链请求失败: {type(exc).__name__}") from exc

        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("location")
            if not location:
                raise ResolveError(f"短链返回 HTTP {response.status_code} 但没有 Location")
            current = urljoin(current, location)
            validate_input_url(current)
            aweme_id = extract_aweme_id(current)
            if aweme_id:
                return ResolvedInput(extracted, current, aweme_id)
            continue

        aweme_id = extract_aweme_id(str(response.url)) or extract_aweme_id(current)
        if aweme_id:
            return ResolvedInput(extracted, str(response.url), aweme_id)
        raise ResolveError(f"短链未解析出 aweme_id（HTTP {response.status_code}）")

    raise ResolveError(f"短链重定向超过 {max_redirects} 次")
