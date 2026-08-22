from __future__ import annotations

import asyncio
import os

import pytest

from douyin_hd_core.pipeline import inspect_public_aweme


FIXED_URL = "https://www.douyin.com/video/7667208299670554725"


@pytest.mark.skipif(
    os.environ.get("DOUYIN_INTEGRATION") != "1",
    reason="set DOUYIN_INTEGRATION=1 to run the real public-network test",
)
def test_fixed_video_with_browser_fallback() -> None:
    inspection = asyncio.run(inspect_public_aweme(FIXED_URL, browser_fallback=True))
    assert inspection.aweme.aweme_id == "7667208299670554725"
    assert any(v.source_type == "bitrate" and v.probe.ok for v in inspection.aweme.variants)
    assert any(v.source_type == "original" for v in inspection.aweme.variants)
