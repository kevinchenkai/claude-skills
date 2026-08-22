from __future__ import annotations

import json
from urllib.parse import quote

from douyin_hd_core.providers import extract_embedded_data, find_aweme


AWEME_ID = "7667208299670554725"
ITEM = {
    "aweme_id": AWEME_ID,
    "desc": "brace } inside a JSON string",
    "video": {"bit_rate": []},
}


def test_router_data_balanced_parser_handles_brace_in_string() -> None:
    payload = {"loaderData": {"video_(id)/page": {"videoInfoRes": {"item_list": [ITEM]}}}}
    page = f"<script>window._ROUTER_DATA = {json.dumps(payload)};</script>"
    parsed = extract_embedded_data(page)
    assert parsed is not None
    assert find_aweme(parsed, AWEME_ID) == ITEM


def test_render_data_percent_decoding() -> None:
    payload = {"aweme": ITEM}
    page = f'<script id="RENDER_DATA" type="application/json">{quote(json.dumps(payload))}</script>'
    parsed = extract_embedded_data(page)
    assert parsed is not None
    assert find_aweme(parsed, AWEME_ID) == ITEM


def test_page_shell_is_not_mistaken_for_aweme() -> None:
    shell = {"loaderData": {"video_(id)/page": {"itemId": AWEME_ID}}}
    assert find_aweme(shell, AWEME_ID) is None
