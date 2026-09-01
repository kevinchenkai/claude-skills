#!/usr/bin/env python3
"""Copy one native WPS AirPage document across drives.

The command is read-only by default. Pass --apply to create the destination.
It preserves native blocks, tables, formatting, WPS document/user nodes and
pictures. Picture attachments are downloaded from the source, uploaded to the
new document, and rebound to newly allocated attachment ids.

Comments, version history and sharing permissions are not copied. Range-mark
comment anchors are removed because the AirPage create API rejects them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import urllib.request
from collections import Counter
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("需要 Pillow：pip install Pillow（用于验证源图与复制后图片像素一致）")

from _airpage_common import (
    cli, cloud_path, create_blocks, picture_source_keys, read_top,
    upload_attachment, walk, write_json,
)


RANGE_MARK_TYPES = {"rangeMarkBegin", "rangeMarkEnd"}
CHUNK_LIMIT = 9_000
IMAGE_SUFFIXES = {
    "PNG": ".png", "JPEG": ".jpg", "GIF": ".gif", "WEBP": ".webp",
    "BMP": ".bmp", "TIFF": ".tiff",
}


def list_folder(drive_id, parent_id):
    items = []
    page_token = None
    while True:
        args = [
            "drive", "file", "list", drive_id, parent_id,
            "--page-size", "100", "-o", "json",
        ]
        if page_token:
            args.extend(["--page-token", page_token])
        data = cli(*args)["data"]
        items.extend(data.get("items") or [])
        page_token = data.get("next_page_token")
        if not page_token:
            return items


def export_document(file_id):
    return cli(
        "api", "post", f"/v7/airpage/{file_id}/export_to_json",
        "--data", "{}", "-o", "json",
    )["data"]


def attachment_identity(exported):
    return {
        item.get("id"): (item.get("hash") or {}).get("sum")
        for item in exported.get("attachment_list") or []
        if item.get("id")
    }


def strip_for_copy(value, attachment_map=None):
    """Remove source-only ids/comment anchors and optionally remap pictures."""
    attachment_map = attachment_map or {}
    if isinstance(value, dict):
        if value.get("type") in RANGE_MARK_TYPES:
            return None
        result = {}
        for key, child in value.items():
            if key == "id":
                continue
            cleaned = strip_for_copy(child, attachment_map)
            if cleaned is not None:
                result[key] = cleaned
        if result.get("type") == "picture":
            attrs = result.setdefault("attrs", {})
            old_key = attrs.get("sourceKey")
            if old_key in attachment_map:
                attrs["sourceKey"] = attachment_map[old_key]
        return result
    if isinstance(value, list):
        result = []
        for child in value:
            cleaned = strip_for_copy(child, attachment_map)
            if cleaned is not None:
                result.append(cleaned)
        return result
    return value


def canonicalize(value):
    """Normalize harmless service defaults before exact structural comparison."""
    if isinstance(value, dict):
        if value.get("type") in RANGE_MARK_TYPES:
            return None
        result = {}
        for key, child in value.items():
            if key == "id" or (key == "styleFormat" and child == 1):
                continue
            cleaned = canonicalize(child)
            if cleaned is not None:
                result[key] = cleaned
        return result
    if isinstance(value, list):
        result = []
        for child in value:
            cleaned = canonicalize(child)
            if cleaned is not None:
                result.append(cleaned)
        return result
    return value


def chunk_blocks(blocks, limit=CHUNK_LIMIT):
    """Keep top-level native blocks intact while limiting each request payload."""
    chunks = []
    current = []
    for block in blocks:
        block_size = len(json.dumps(block, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        candidate = current + [block]
        candidate_size = len(
            json.dumps(candidate, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        if current and candidate_size > limit:
            chunks.append(current)
            current = []
        current.append(block)
        # Tables cannot safely be split. Send an oversized single block alone.
        if block_size > limit:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def download_bytes(url):
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        raise RuntimeError(f"invalid attachment download URL: {url!r}")
    request = urllib.request.Request(url, headers={"User-Agent": "wps365-airpage-copy/1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def image_signature(raw):
    with Image.open(BytesIO(raw)) as image:
        image.load()
        rgba = image.convert("RGBA")
        return {
            "format": image.format,
            "width": image.width,
            "height": image.height,
            "pixel_sha256": hashlib.sha256(rgba.tobytes()).hexdigest(),
        }


def visual_signature(signature):
    return {
        "width": signature["width"],
        "height": signature["height"],
        "pixel_sha256": signature["pixel_sha256"],
    }


def type_counts(value):
    return Counter(
        item.get("type") for item in walk(value)
        if isinstance(item.get("type"), str)
    )


def range_mark_count(value):
    return sum(1 for item in walk(value) if item.get("type") in RANGE_MARK_TYPES)


def validate_source_attachments(body, exported):
    picture_keys = picture_source_keys(body)
    attachments = {
        item.get("id"): item
        for item in exported.get("attachment_list") or []
        if item.get("id")
    }
    if picture_keys != set(attachments):
        raise RuntimeError(
            "源文档附件未闭合或含暂不支持的非图片附件："
            f"picture_source_keys={sorted(picture_keys)}, "
            f"attachment_ids={sorted(attachments)}"
        )
    return attachments


def validate_copied_blocks(expected, actual):
    checks = {
        "top_blocks": len(expected) == len(actual),
        "type_counts": type_counts(expected) == type_counts(actual),
        "canonical_structure": canonicalize(expected) == canonicalize(actual),
    }
    if not all(checks.values()):
        raise RuntimeError("复制后 blocks 验收失败：" + json.dumps(checks, ensure_ascii=False))
    return checks


def output_result(result, path=None):
    if path:
        write_json(path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="跨盘复制原生 WPS 智能文档；默认只预检")
    parser.add_argument("source_drive_id")
    parser.add_argument("source_file_id")
    parser.add_argument("destination_drive_id")
    parser.add_argument("destination_parent_id")
    parser.add_argument("--name", help="目标文件名；默认沿用源文件名")
    parser.add_argument("--on-name-conflict", choices=["fail", "rename"], default="fail")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--result", help="可选：把预检或执行结果另存为 JSON")
    args = parser.parse_args()

    source_meta = cli(
        "drive", "file", "get", args.source_drive_id, args.source_file_id, "-o", "json"
    )["data"]
    source_name = source_meta.get("name")
    if not isinstance(source_name, str) or not source_name.endswith(".otl"):
        raise RuntimeError(f"只支持智能文档 .otl，当前源文件：{source_name!r}")
    target_name = args.name or source_name
    if not target_name.endswith(".otl"):
        target_name += ".otl"

    source_doc, source_top = read_top(args.source_file_id)
    source_body = [block for block in source_top if block.get("type") != "title"]
    source_export = export_document(args.source_file_id)
    source_attachments = validate_source_attachments(source_body, source_export)
    source_path = cloud_path(args.source_drive_id, args.source_file_id)
    destination_path = cloud_path(args.destination_drive_id, args.destination_parent_id)
    destination_items = list_folder(args.destination_drive_id, args.destination_parent_id)
    exact_conflicts = [item for item in destination_items if item.get("name") == target_name]
    if exact_conflicts and args.on_name_conflict == "fail":
        raise RuntimeError(
            f"目标目录已存在同名文件 {target_name}："
            f"{[item.get('id') for item in exact_conflicts]}"
        )

    counts = type_counts(source_body)
    preview = {
        "mode": "apply" if args.apply else "preview",
        "source": {
            "drive_id": args.source_drive_id,
            "file_id": args.source_file_id,
            "name": source_name,
            "cloud_path": source_path,
        },
        "destination": {
            "drive_id": args.destination_drive_id,
            "parent_id": args.destination_parent_id,
            "parent_path": destination_path,
            "name": target_name,
            "on_name_conflict": args.on_name_conflict,
        },
        "top_blocks": len(source_body),
        "block_types": dict(sorted(counts.items())),
        "pictures": counts.get("picture", 0),
        "unique_attachments": len(source_attachments),
        "range_marks_removed": range_mark_count(source_body),
        "not_copied": ["comments", "version_history", "sharing_permissions"],
    }
    if not args.apply:
        output_result(preview, args.result)
        return

    target_file_id = None
    try:
        created = cli(
            "api", "post", "/v7/airpage/files",
            "--data", json.dumps({
                "drive_id": args.destination_drive_id,
                "parent_id": args.destination_parent_id,
                "name": target_name,
                "template_id": "",
                "on_name_conflict": args.on_name_conflict,
            }, ensure_ascii=False), "-o", "json",
        )["data"]
        target_file_id = created["id"]
        _, baseline = read_top(target_file_id)

        attachment_map = {}
        source_signatures = {}
        with tempfile.TemporaryDirectory(prefix="wps-airpage-copy-") as temp_dir:
            for index, (source_key, item) in enumerate(source_attachments.items(), 1):
                raw = download_bytes(item.get("download_url"))
                signature = image_signature(raw)
                picture_attrs = next(
                    node.get("attrs", {}) for node in walk(source_body)
                    if node.get("type") == "picture"
                    and node.get("attrs", {}).get("sourceKey") == source_key
                )
                expected_size = (picture_attrs.get("width"), picture_attrs.get("height"))
                actual_size = (signature["width"], signature["height"])
                if all(isinstance(value, (int, float)) for value in expected_size) and expected_size != actual_size:
                    raise RuntimeError(
                        f"源图片 {source_key} 尺寸不一致：block={expected_size}, download={actual_size}"
                    )
                source_signatures[source_key] = signature
                suffix = IMAGE_SUFFIXES.get(signature["format"], ".img")
                image_path = Path(temp_dir) / f"source-{index}{suffix}"
                image_path.write_bytes(raw)
                attachment_map[source_key] = upload_attachment(target_file_id, image_path)
                print(f"uploaded source image {index}/{len(source_attachments)}", flush=True)

        # Stop if the shared source changed while its attachments were being copied.
        current_source_doc, _ = read_top(args.source_file_id)
        current_source_export = export_document(args.source_file_id)
        source_blocks_changed = current_source_doc != source_doc
        source_attachments_changed = (
            attachment_identity(current_source_export) != attachment_identity(source_export)
        )
        if source_blocks_changed or source_attachments_changed:
            raise RuntimeError("复制期间源文档发生并发修改，已停止并清理目标半成品")
        _, current_target = read_top(target_file_id)
        if current_target != baseline:
            raise RuntimeError("上传附件期间目标文档 blocks 发生并发修改")

        copied_body = strip_for_copy(source_body, attachment_map)
        chunks = chunk_blocks(copied_body)
        for index, chunk in enumerate(chunks, 1):
            create_blocks(target_file_id, 1_000_000_000, chunk)
            print(f"inserted block chunk {index}/{len(chunks)}", flush=True)

        _, target_top = read_top(target_file_id)
        if target_top[:len(baseline)] != baseline:
            raise RuntimeError("复制后目标文档初始 blocks 被意外改动")
        inserted = target_top[len(baseline):]
        checks = validate_copied_blocks(copied_body, inserted)

        target_export = export_document(target_file_id)
        target_items = {
            item.get("id"): item
            for item in target_export.get("attachment_list") or []
            if item.get("id")
        }
        target_picture_keys = picture_source_keys(inserted)
        expected_target_keys = set(attachment_map.values())
        checks["attachment_closure"] = (
            set(target_items) == target_picture_keys == expected_target_keys
        )
        if not checks["attachment_closure"]:
            raise RuntimeError(
                "复制后图片附件未闭合："
                f"export={sorted(target_items)}, pictures={sorted(target_picture_keys)}, "
                f"uploaded={sorted(expected_target_keys)}"
            )

        reverse_map = {target: source for source, target in attachment_map.items()}
        checks["image_pixels"] = all(
            visual_signature(image_signature(download_bytes(item.get("download_url"))))
            == visual_signature(source_signatures[reverse_map[target_key]])
            for target_key, item in target_items.items()
        )
        if not checks["image_pixels"]:
            raise RuntimeError("复制后至少一张图片的尺寸或像素与源图不一致")

        final_path = cloud_path(args.destination_drive_id, target_file_id)
        final_items = list_folder(args.destination_drive_id, args.destination_parent_id)
        created_matches = [item for item in final_items if item.get("id") == target_file_id]
        if len(created_matches) != 1:
            raise RuntimeError("目标目录回查没有唯一找到新文档")
        actual_name = created_matches[0].get("name")
        if args.on_name_conflict == "fail" and actual_name != target_name:
            raise RuntimeError(f"目标文件名异常：expected={target_name}, actual={actual_name}")

        result = {
            **preview,
            "status": "ok",
            "destination": {
                **preview["destination"],
                "file_id": target_file_id,
                "name": actual_name,
                "cloud_path": final_path,
                "link_url": created.get("link_url") or created_matches[0].get("link_url"),
            },
            "chunks": len(chunks),
            "checks": checks,
        }
        output_result(result, args.result)
    except Exception:
        if target_file_id:
            try:
                cli(
                    "drive", "file", "delete",
                    args.destination_drive_id, target_file_id, "-o", "json",
                )
                print(f"deleted partial document {target_file_id}", file=sys.stderr)
            except Exception as cleanup_error:
                print(
                    f"failed to delete partial document {target_file_id}: {cleanup_error}",
                    file=sys.stderr,
                )
        raise


if __name__ == "__main__":
    main()
