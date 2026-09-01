#!/usr/bin/env python3
"""Shared helpers for safe additive edits to existing WPS AirPage documents."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def cli_binary():
    configured = os.environ.get("WPS365_CLI")
    if configured:
        return configured
    found = shutil.which("wps365-cli")
    if found:
        return found
    fallback = Path.home() / ".local/bin/wps365-cli"
    if fallback.is_file():
        return str(fallback)
    raise RuntimeError("找不到 wps365-cli；请设置 WPS365_CLI 或安装到 ~/.local/bin")


def cli(*args):
    proc = subprocess.run([cli_binary(), *args], capture_output=True, text=True)
    if not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or "wps365-cli returned no JSON")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"wps365-cli returned non-JSON for {' '.join(args)}: "
            f"{proc.stdout[:300]} {proc.stderr[:300]}"
        ) from exc
    if proc.returncode or data.get("code") not in (0, None):
        raise RuntimeError(json.dumps(data, ensure_ascii=False))
    return data


def b64(value):
    return base64.b64encode(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")


def unb64(value):
    return json.loads(base64.b64decode(value))


def read_top(file_id):
    response = cli(
        "api", "post", f"/v7/airpage/{file_id}/blocks",
        "--data", json.dumps({"arg": b64({"blockId": "doc"})}), "-o", "json",
    )
    decoded = unb64(response["data"]["result"])
    roots = decoded.get("blocks") or []
    if len(roots) != 1 or roots[0].get("type") != "doc":
        raise RuntimeError("unexpected AirPage blocks response: missing single doc root")
    return decoded, roots[0].get("content") or []


def create_blocks(file_id, index, blocks):
    response = cli(
        "api", "post", f"/v7/airpage/{file_id}/blocks/create",
        "--data", json.dumps({"arg": b64({
            "blockId": "doc", "index": index, "content": blocks,
        })}), "-o", "json",
    )
    return unb64(response["data"]["result"])


def export_attachments(file_id):
    exported = cli(
        "api", "post", f"/v7/airpage/{file_id}/export_to_json",
        "--data", "{}", "-o", "json",
    )["data"]
    result = {}
    for item in exported.get("attachment_list", []):
        attachment_id = item.get("id")
        if not attachment_id:
            continue
        digest = (item.get("hash") or {}).get("sum")
        result[attachment_id] = digest.lower() if isinstance(digest, str) else None
    return result


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def collect_text(value):
    return "".join(
        item.get("content", "")
        for item in walk(value)
        if item.get("type") == "text" and isinstance(item.get("content"), str)
    )


def picture_source_keys(value):
    return {
        item.get("attrs", {}).get("sourceKey")
        for item in walk(value)
        if item.get("type") == "picture" and item.get("attrs", {}).get("sourceKey")
    }


def wps_document_refs(value):
    return [
        item.get("attrs", {})
        for item in walk(value)
        if item.get("type") == "WPSDocument"
    ]


def resolve_anchor(top, mode, value=None):
    if mode == "append":
        return len(top)
    if mode.endswith("heading"):
        matches = [
            index for index, block in enumerate(top)
            if block.get("type") == "heading" and collect_text(block).strip() == value
        ]
    else:
        matches = [index for index, block in enumerate(top) if block.get("id") == value]
    if len(matches) != 1:
        raise RuntimeError(f"插入锚点必须唯一，当前命中 {len(matches)} 个：{value}")
    return matches[0] + (1 if mode.startswith("after") else 0)


def section_append_index(top, heading_text):
    matches = [
        index for index, block in enumerate(top)
        if block.get("type") == "heading" and collect_text(block).strip() == heading_text
    ]
    if len(matches) != 1:
        raise RuntimeError(f"章节标题必须唯一，当前命中 {len(matches)} 个：{heading_text}")
    start = matches[0]
    level = top[start].get("attrs", {}).get("level")
    end = len(top)
    for index in range(start + 1, len(top)):
        block = top[index]
        if block.get("type") != "heading":
            continue
        candidate = block.get("attrs", {}).get("level")
        if isinstance(level, int) and isinstance(candidate, int) and candidate <= level:
            end = index
            break
    while end > start + 1:
        block = top[end - 1]
        if block.get("type") == "paragraph" and not block.get("content"):
            end -= 1
        else:
            break
    return end


def canonical_link_id(url):
    if not isinstance(url, str):
        return None
    parts = [part for part in urlparse(url).path.split("/") if part]
    try:
        marker = parts.index("l")
        return parts[marker + 1]
    except (ValueError, IndexError):
        return None


def ensure_old_blocks_preserved(before, after, inserted_ids):
    if any(not item for item in inserted_ids):
        raise RuntimeError("新插入块缺少 id，不能验证原文保持不变")
    remaining = [block for block in after if block.get("id") not in inserted_ids]
    if remaining != before:
        raise RuntimeError("插入后原有顶层 blocks 内容或顺序发生变化")


def write_json(path, value):
    if not path:
        return
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cloud_path(drive_id, file_id):
    data = cli("drive", "file-path", "get", drive_id, file_id, "-o", "json")["data"]
    return " / ".join(item["name"] for item in data.get("paths", []))
