from __future__ import annotations

import pytest

from douyin_hd_core.resolver import ResolveError, extract_aweme_id, extract_url


FIXED_ID = "7667208299670554725"


def test_full_video_url() -> None:
    url = f"https://www.douyin.com/video/{FIXED_ID}"
    assert extract_url(url) == url
    assert extract_aweme_id(url) == FIXED_ID


def test_note_url() -> None:
    assert extract_aweme_id(f"https://www.douyin.com/note/{FIXED_ID}") == FIXED_ID


def test_share_copy_removes_chinese_punctuation() -> None:
    text = "3.45 复制打开抖音 https://v.douyin.com/AbCdEf/，看看作品"
    assert extract_url(text) == "https://v.douyin.com/AbCdEf/"


def test_rejects_non_douyin_url() -> None:
    with pytest.raises(ResolveError):
        extract_url("https://example.com/video/7667208299670554725")


def test_rejects_deceptive_subdomain() -> None:
    with pytest.raises(ResolveError):
        extract_url("https://douyin.com.example.com/video/7667208299670554725")
