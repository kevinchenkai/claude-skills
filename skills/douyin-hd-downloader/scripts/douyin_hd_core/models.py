from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlsplit


def safe_url_parts(url: str | None) -> dict[str, str | None]:
    """Return useful URL diagnostics without leaking query signatures."""
    if not url:
        return {"host": None, "path": None}
    parsed = urlsplit(url)
    path = parsed.path or "/"
    if len(path) > 96:
        path = f"{path[:93]}..."
    return {"host": parsed.hostname, "path": path}


@dataclass(slots=True)
class ProbeResult:
    ok: bool = False
    status_code: int | None = None
    content_type: str | None = None
    content_length: int | None = None
    resolved_url: str | None = None
    sampled_bytes: int = 0
    error: str | None = None

    def public_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.pop("resolved_url", None)
        result["resolved"] = safe_url_parts(self.resolved_url)
        return result


@dataclass(slots=True)
class VideoVariant:
    source_type: str
    urls: list[str]
    width: int | None = None
    height: int | None = None
    bitrate: int | None = None
    codec: str | None = None
    gear_name: str | None = None
    quality_type: int | None = None
    file_size_hint: int | None = None
    uri: str | None = None
    has_watermark: bool | None = None
    probe: ProbeResult = field(default_factory=ProbeResult)

    @property
    def resolution(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "unknown"

    @property
    def best_download_url(self) -> str:
        return self.probe.resolved_url or (self.urls[0] if self.urls else "")

    def public_dict(self, index: int | None = None) -> dict[str, Any]:
        value: dict[str, Any] = {
            "source_type": self.source_type,
            "resolution": self.resolution,
            "width": self.width,
            "height": self.height,
            "bitrate": self.bitrate,
            "codec": self.codec,
            "gear_name": self.gear_name,
            "quality_type": self.quality_type,
            "file_size_hint": self.file_size_hint,
            "has_watermark": self.has_watermark,
            "mirrors": [safe_url_parts(url) for url in self.urls],
            "probe": self.probe.public_dict(),
        }
        if index is not None:
            value = {"index": index, **value}
        return value


@dataclass(slots=True)
class Aweme:
    aweme_id: str
    desc: str | None
    author_name: str | None
    duration_ms: int | None
    provider: str
    cookie_used: bool
    browser_fallback_used: bool
    variants: list[VideoVariant] = field(default_factory=list)

    def public_dict(self) -> dict[str, Any]:
        return {
            "aweme_id": self.aweme_id,
            "desc": self.desc,
            "author_name": self.author_name,
            "duration_ms": self.duration_ms,
            "provider": self.provider,
            "cookie_used": self.cookie_used,
            "browser_fallback_used": self.browser_fallback_used,
        }


@dataclass(slots=True)
class Inspection:
    input_text: str
    extracted_url: str
    resolved_url: str
    aweme: Aweme
    provider_failures: list[str] = field(default_factory=list)

    def public_dict(self) -> dict[str, Any]:
        return {
            "input_url": self.extracted_url,
            "resolved_input_url": self.resolved_url,
            **self.aweme.public_dict(),
            "provider_failures": list(self.provider_failures),
            "candidates": [v.public_dict(i) for i, v in enumerate(self.aweme.variants)],
        }
