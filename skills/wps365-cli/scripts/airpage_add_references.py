#!/usr/bin/env python3
"""Safely add native WPSDocument references to an existing AirPage section.

The command is read-only by default. Pass --apply to insert references. Input is
a JSON array whose items contain a kdocs short link plus optional category and
description fields.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _airpage_common import (
    canonical_link_id, cli, cloud_path, create_blocks,
    ensure_old_blocks_preserved, export_attachments, picture_source_keys,
    read_top, section_append_index, wps_document_refs, write_json,
)


def data_object(response):
    data = response.get("data") or {}
    return data.get("file") or data


def resolve_reference(item):
    if not isinstance(item, dict):
        raise RuntimeError("每条引用必须是 JSON object")
    url = item.get("url")
    link_id = canonical_link_id(url)
    if not link_id:
        raise RuntimeError(f"不是有效的 kdocs 短链：{url!r}")

    link = cli(
        "api", "get", f"/v7/links/{link_id}/meta",
        "--token-type", "delegated", "-o", "json",
    )["data"]
    if link.get("status") != "open":
        raise RuntimeError(f"短链不是 open 状态：{url}")
    drive_id = link.get("drive_id")
    file_id = link.get("file_id")
    if not drive_id or not file_id:
        raise RuntimeError(f"短链 meta 缺少 drive_id/file_id：{url}")

    file_data = data_object(cli("drive", "file", "get", drive_id, file_id, "-o", "json"))
    name = file_data.get("name")
    if not name:
        raise RuntimeError(f"无法读取引用文档名称：{url}")
    if not name.casefold().endswith(".otl"):
        raise RuntimeError(f"原生 WPSDocument 引用当前只支持智能文档 .otl：{name}")

    airpage = cli("api", "get", f"/v7/airpage/{file_id}", "-o", "json")["data"]
    document_id = str(airpage.get("id", ""))
    if not document_id.isdigit():
        raise RuntimeError(f"AirPage metadata 缺少数字 id：{url}")

    return {
        "link_id": link_id,
        "url": f"https://365.kdocs.cn/l/{link_id}",
        "drive_id": drive_id,
        "file_id": file_id,
        "name": name[:-4],
        "document_id": document_id,
        "category": str(item.get("category") or "").strip(),
        "description": str(item.get("description") or "").strip(),
    }


def reference_block(item):
    content = []
    if item["category"]:
        content.append({"type": "text", "content": f"【{item['category']}】"})
    content.append({
        "type": "WPSDocument",
        "attrs": {
            "version": 1,
            "wpsDocumentId": item["document_id"],
            "wpsDocumentLink": item["url"],
            "wpsDocumentName": item["name"],
            "wpsDocumentType": "otl",
        },
    })
    if item["description"]:
        content.append({"type": "text", "content": f" — {item['description']}"})
    return {"type": "paragraph", "attrs": {"align": 1}, "content": content}


def reference_identity(attrs):
    return canonical_link_id(attrs.get("wpsDocumentLink")), str(attrs.get("wpsDocumentId") or "")


def main():
    parser = argparse.ArgumentParser(description="向已有 WPS 智能文档安全添加原生文档引用；默认只预检")
    parser.add_argument("drive_id")
    parser.add_argument("file_id", help="目标 AirPage file id，不是短链码")
    parser.add_argument("references_json", help="JSON 数组：url/category/description")
    parser.add_argument("--section", default="参考文档", help="唯一的目标章节标题")
    parser.add_argument("--skip-inaccessible", action="store_true",
                        help="跳过无权读取 metadata 的引用；默认任一失败即停止")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir")
    parser.add_argument("--result")
    args = parser.parse_args()

    source = Path(args.references_json).expanduser().resolve()
    raw_items = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw_items, list) or not raw_items:
        parser.error("references_json 必须是非空 JSON 数组")

    before_doc, before = read_top(args.file_id)
    before_attachments = export_attachments(args.file_id)
    before_keys = picture_source_keys(before)
    if before_keys != set(before_attachments):
        raise RuntimeError("写入前 picture.sourceKey 与 export attachment_list 未闭合")
    index = section_append_index(before, args.section)

    existing_attrs = wps_document_refs(before)
    existing_link_ids = {
        link_id for link_id, _ in map(reference_identity, existing_attrs) if link_id
    }
    existing_document_ids = {
        document_id for _, document_id in map(reference_identity, existing_attrs) if document_id
    }

    resolved = []
    failures = []
    seen_link_ids = set()
    seen_document_ids = set()
    for position, item in enumerate(raw_items):
        try:
            reference = resolve_reference(item)
        except Exception as exc:  # Keep per-item evidence for optional skip mode.
            failure = {"index": position, "input": item, "error": str(exc)}
            failures.append(failure)
            if not args.skip_inaccessible:
                print(json.dumps({"failures": failures}, ensure_ascii=False, indent=2))
                raise RuntimeError("引用预检失败；未执行写入") from exc
            continue
        if reference["file_id"] == args.file_id:
            raise RuntimeError("不能把目标文档自身加入参考文档")
        if reference["link_id"] in seen_link_ids or reference["document_id"] in seen_document_ids:
            raise RuntimeError(f"输入中存在重复引用：{reference['url']}")
        seen_link_ids.add(reference["link_id"])
        seen_document_ids.add(reference["document_id"])
        reference["action"] = "skip-existing" if (
            reference["link_id"] in existing_link_ids
            or reference["document_id"] in existing_document_ids
        ) else "insert"
        resolved.append(reference)

    to_insert = [item for item in resolved if item["action"] == "insert"]
    plan = {
        "mode": "apply" if args.apply else "preview",
        "cloud_path": cloud_path(args.drive_id, args.file_id),
        "section": args.section,
        "index": index,
        "references": resolved,
        "failures": failures,
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if not args.apply:
        return

    backup = Path(args.backup_dir).expanduser().resolve() if args.backup_dir else None
    if backup:
        backup.mkdir(parents=True, exist_ok=True)
        write_json(backup / "before.json", before_doc)

    current_doc, current = read_top(args.file_id)
    current_attachments = export_attachments(args.file_id)
    if current != before or current_attachments != before_attachments:
        raise RuntimeError("预检后目标文档或附件被并发修改；未执行写入")
    current_index = section_append_index(current, args.section)
    blocks = [reference_block(item) for item in to_insert]
    if blocks:
        create_blocks(args.file_id, current_index, blocks)

    after_doc, after = read_top(args.file_id)
    inserted = after[current_index:current_index + len(blocks)]
    expected = [(item["link_id"], item["document_id"]) for item in to_insert]
    actual = []
    for block in inserted:
        refs = wps_document_refs(block)
        if len(refs) != 1:
            raise RuntimeError("新插入段落没有且仅有一个 WPSDocument 节点")
        actual.append(reference_identity(refs[0]))
    if actual != expected:
        raise RuntimeError("插入位置或 WPSDocument 回读不符合预期")
    inserted_ids = {block.get("id") for block in inserted}
    ensure_old_blocks_preserved(current, after, inserted_ids)

    after_attachments = export_attachments(args.file_id)
    if after_attachments != before_attachments:
        raise RuntimeError("添加引用后附件集合发生变化")
    if picture_source_keys(after) != set(after_attachments):
        raise RuntimeError("添加引用后 picture.sourceKey 与附件未闭合")

    result = {
        "drive_id": args.drive_id,
        "file_id": args.file_id,
        "cloud_path": cloud_path(args.drive_id, args.file_id),
        "section": args.section,
        "before_top_blocks": len(before),
        "after_top_blocks": len(after),
        "inserted": [item["url"] for item in to_insert],
        "skipped": [item["url"] for item in resolved if item["action"] == "skip-existing"],
        "failures": failures,
    }
    if backup:
        write_json(backup / "after.json", after_doc)
        write_json(backup / "result.json", result)
    write_json(args.result, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
