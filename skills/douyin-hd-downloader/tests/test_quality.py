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


def test_vendor_sdk_names_are_not_treated_as_waf() -> None:
    """Vendor SDK names appear on healthy pages; only real challenges count.

    Two markers have been falsified this way. "verifyCenter" went first
    (measured 2026-08-22, present on 6/6 share pages). Then "/captcha/", which
    is merely the preload URL of that same SDK -- measured 2026-09-01 it fires
    on the /share/video/ page of every sample, including one whose item parsed
    cleanly in the same request. A marker that fires while the page parses is
    not a block marker; it defeats the retry that page-shell flakiness needs.
    """
    from douyin_hd_core.providers import is_waf_page

    healthy = '<script>window.TTGCaptcha = {}; verifyCenter: { init: function () {} }</script>'
    assert is_waf_page(healthy) is False

    # Verbatim shape of the SDK preload list served on healthy pages.
    sdk_preload = (
        '<script>srcList: ["https://lf-rc1.yhgfb-cn-static.com/obj/rc-verifycenter'
        '/sec_sdk_build/4.0.10/captcha/index.js"]</script>'
    )
    assert is_waf_page(sdk_preload) is False

    for challenge in (
        '<script src="/waf-jschallenge/x.js"></script>',
        '<script>var wafChallengeId = "x";</script>',
        '<script>waf_js()</script>',
    ):
        assert is_waf_page(challenge) is True


def test_waf_markers_hold_no_vendor_sdk_names() -> None:
    """Guard the marker list itself, so the same class of bug cannot return."""
    from douyin_hd_core.providers import WAF_MARKERS

    for banned in ("verifycenter", "/captcha/", "ttgcaptcha", "sec_sdk"):
        assert banned not in WAF_MARKERS, (
            f"{banned!r} names a vendor SDK, not a challenge; it fires on healthy pages"
        )


def test_watermarked_detected_from_playwm_path_when_flag_missing() -> None:
    """SSR leaves has_watermark unset on the playwm candidate, so trust the URL."""
    from douyin_hd_core.media import is_watermarked

    wm = VideoVariant(
        source_type="play_addr",
        urls=["https://aweme.snssdk.com/aweme/v1/playwm/?video_id=x"],
        has_watermark=None,
    )
    clean = VideoVariant(
        source_type="play_addr",
        urls=["https://aweme.snssdk.com/aweme/v1/play/?video_id=x"],
        has_watermark=None,
    )
    assert is_watermarked(wm) is True
    assert is_watermarked(clean) is False


def test_original_refuses_to_downgrade_to_watermarked_source() -> None:
    """A failed original probe must not silently yield a watermarked file."""
    import pytest

    from douyin_hd_core.media import MediaError

    watermarked = VideoVariant(
        source_type="play_addr",
        urls=["https://aweme.snssdk.com/aweme/v1/playwm/?video_id=x"],
        width=1440,
        height=2560,
        file_size_hint=2_987_248,
        probe=ProbeResult(ok=True, status_code=206, content_length=2_987_248),
    )
    original = VideoVariant(
        source_type="original",
        urls=["https://www.douyin.com/aweme/v1/play/?ratio=default"],
        probe=ProbeResult(ok=False, error="ConnectTimeout: "),
    )
    with pytest.raises(MediaError, match="带水印"):
        select_variant([original, watermarked], "original")


def test_transient_probe_errors_are_retried_not_fatal() -> None:
    from douyin_hd_core.media import _is_transient_probe_error

    assert _is_transient_probe_error(ProbeResult(error="ConnectTimeout: ")) is True
    assert _is_transient_probe_error(ProbeResult(status_code=503)) is True
    assert _is_transient_probe_error(ProbeResult(status_code=403, error="HTTP 403")) is False
    assert _is_transient_probe_error(ProbeResult(ok=True, status_code=206)) is False


def test_trimmed_table_keeps_original_and_all_failures() -> None:
    """A shorter table must not read as healthier than the full one.

    Truncating to the head of the list would satisfy `highest` (it is sorted)
    but would drop probe failures, which are exactly the rows a reader needs
    when a run misbehaves. Selection is by relevance, not position.
    """
    import douyin_hd

    broken = _variant("bitrate", width=640, height=360, bitrate=500_000, gear="low")
    broken.probe = ProbeResult(ok=False, status_code=403, error="HTTP 403")
    variants = [
        _variant("bitrate", width=1920, height=1080, bitrate=4_200_000, gear="a"),
        _variant("bitrate", width=1280, height=720, bitrate=3_200_000, gear="b"),
        _variant("bitrate", width=1024, height=576, bitrate=2_900_000, gear="c"),
        _variant("bitrate", width=960, height=540, bitrate=1_000_000, gear="d"),
        broken,
        _variant("original", size=40_000_000, codec=None),
    ]
    shown = douyin_hd._rows_to_show(variants, 3)

    assert 5 in shown, "original must never be hidden"
    assert 4 in shown, "a failed probe must never be hidden"
    assert len(shown) < len(variants), "the table should actually be shorter"
    assert shown == sorted(shown), "row order must follow the original indices"


def test_trimmed_table_is_a_noop_when_it_would_not_help() -> None:
    import douyin_hd

    variants = [_variant("original", size=1), _variant("bitrate", width=720, height=1280)]
    assert douyin_hd._rows_to_show(variants, 3) == [0, 1]
    # top=0 is the explicit "show everything" contract used by --all-candidates.
    assert douyin_hd._rows_to_show(variants * 4, 0) == list(range(8))
