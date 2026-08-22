from __future__ import annotations

from douyin_hd_core.media import build_variants, select_variant
from douyin_hd_core.models import ProbeResult, VideoVariant


def _variant(
    source: str,
    *,
    width: int | None = None,
    height: int | None = None,
    bitrate: int | None = None,
    size: int | None = None,
    codec: str | None = "h264",
    gear: str | None = None,
) -> VideoVariant:
    return VideoVariant(
        source_type=source,
        urls=[f"https://v.example.test/{source}-{bitrate or 0}.mp4"],
        width=width,
        height=height,
        bitrate=bitrate,
        codec=codec,
        file_size_hint=size,
        gear_name=gear,
        probe=ProbeResult(ok=True, status_code=206, content_length=size),
    )


def test_highest_prefers_resolution_then_bitrate() -> None:
    candidates = [
        _variant("bitrate", width=1080, height=1920, bitrate=8_000_000),
        _variant("bitrate", width=720, height=1280, bitrate=12_000_000),
    ]
    selected, _ = select_variant(candidates, "highest")
    assert selected.width == 1080
    assert selected.bitrate == 8_000_000


def test_original_only_promoted_when_larger() -> None:
    highest = _variant(
        "bitrate", width=1920, height=1080, bitrate=4_200_000, size=6_600_000
    )
    original = _variant("original", size=15_800_000, codec=None)
    selected, reason = select_variant([original, highest], "original")
    assert selected is original
    assert "15800000" in reason


def test_original_falls_back_when_smaller() -> None:
    highest = _variant(
        "bitrate", width=1920, height=1080, bitrate=4_200_000, size=47_000_000
    )
    original = _variant("original", size=31_000_000, codec=None)
    selected, reason = select_variant([original, highest], "original")
    assert selected is highest
    assert "fallback" in reason


def test_compatible_prefers_h264() -> None:
    h265 = _variant("bitrate", width=1920, height=1080, bitrate=5_000_000, codec="h265")
    h264 = _variant("bitrate", width=1920, height=1080, bitrate=4_000_000, codec="h264")
    selected, _ = select_variant([h265, h264], "compatible")
    assert selected is h264


def test_builds_original_and_all_bitrate_tiers() -> None:
    item = {
        "aweme_id": "1",
        "video": {
            "bit_rate": [
                {
                    "gear_name": "normal_1080_0",
                    "bit_rate": 8_000_000,
                    "is_h265": 0,
                    "play_addr": {
                        "uri": "video-uri",
                        "width": 1920,
                        "height": 1080,
                        "url_list": ["https://v.example.test/1080.mp4"],
                    },
                },
                {
                    "gear_name": "720_1_1",
                    "bit_rate": 4_000_000,
                    "is_h265": 1,
                    "play_addr": {
                        "uri": "video-uri",
                        "width": 1280,
                        "height": 720,
                        "url_list": ["https://v.example.test/720.mp4"],
                    },
                },
            ]
        },
    }
    variants = build_variants(item)
    assert [variant.source_type for variant in variants] == ["original", "bitrate", "bitrate"]
    assert variants[2].codec == "h265"
    assert "ratio=default" in variants[0].urls[0]
