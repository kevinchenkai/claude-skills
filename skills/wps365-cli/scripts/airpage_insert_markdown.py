#!/usr/bin/env python3
"""Insert a Markdown section (optionally with local images) into an existing AirPage doc.

Read-only by default; pass --apply to write. The document keeps its file id and
link. Typical use: add a new chapter or subsection to a published report.

    python3 airpage_insert_markdown.py <drive-id> <file-id> section.md \
        --section-end "三、知识库" [--expect-path "router / 报告.otl"] \
        [--apply] [--backup-dir DIR] [--result result.json]

Exactly one position: --before-heading / --after-heading / --before-block /
--after-block / --section-end (end of that heading's section) / --append.

Safety: cloud path check, refusal when any heading of the new Markdown already
exists (re-run guard), pre-existing attachment closure, re-read before insert,
old top-level blocks preserved exactly, attachment closure after insert, and
inserted picture/table/codeBlock/heading counts equal to what convert produced.
Numbered headings ("### 3.5 标题") keep their literal numbers unless
--keep-auto-numbering.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from _airpage_common import (
    b64, cli, cloud_path, collect_text, create_blocks, ensure_old_blocks_preserved,
    export_attachments, list_numbered_headings, markdown_headings, markdown_inline_plain,
    picture_source_keys, read_top, resolve_anchor, restore_numbered_headings,
    section_append_index, unb64, upload_attachment, write_json,
)
from airpage_publish import (  # also enforces the Pillow dependency
    Image, count_types, patch_picture_blocks, resolve_local_asset, split_markdown,
)


_LEADING_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)*[.)]?\s*")


def parse_position(parser, args):
    choices = [
        ("before-heading", args.before_heading), ("after-heading", args.after_heading),
        ("before-block", args.before_block), ("after-block", args.after_block),
        ("section-end", args.section_end), ("append", True if args.append else None),
    ]
    selected = [(mode, value) for mode, value in choices if value is not None]
    if len(selected) != 1:
        parser.error(
            "必须且只能指定一个插入位置：--before/after-heading、--before/after-block、"
            "--section-end 或 --append"
        )
    return selected[0]


def insert_index(top, mode, value):
    if mode == "section-end":
        return section_append_index(top, value)
    return resolve_anchor(top, mode, value)


def existing_heading_clashes(top, markdown):
    """Headings of the new Markdown already present in the doc (re-run guard).

    Compares with numbers stripped too, because a previous run may have produced
    either "3.5 标题" or the auto-numbered "标题".
    """
    present = {collect_text(block).strip() for block in top if block.get("type") == "heading"}
    clashes = []
    for _level, text in markdown_headings(markdown):
        plain = markdown_inline_plain(text).strip()
        bare = _LEADING_NUMBER_RE.sub("", plain).strip()
        if plain in present or (bare and bare != plain and bare in present):
            clashes.append(plain)
    return clashes


def convert_chunks(file_id, markdown, keep_auto_numbering):
    converted = []
    restored = 0
    for chunk in split_markdown(markdown):
        result = unb64(cli(
            "api", "post", f"/v7/airpage/{file_id}/blocks/convert",
            "--data", json.dumps({"arg": b64({"format": "markdown", "content": chunk})}),
            "-o", "json",
        )["data"]["result"])
        if not keep_auto_numbering:
            restored += restore_numbered_headings(result["blocks"], chunk)
        converted.append(result)
    return converted, restored


def main():
    parser = argparse.ArgumentParser(description="向已有 WPS 智能文档插入一段 Markdown（可含本地图片）；默认只预检")
    parser.add_argument("drive_id")
    parser.add_argument("file_id", help="AirPage file id，不是短链码")
    parser.add_argument("markdown")
    parser.add_argument("--before-heading")
    parser.add_argument("--after-heading")
    parser.add_argument("--before-block")
    parser.add_argument("--after-block")
    parser.add_argument("--section-end", help="插到该标题所在章节末尾（下一个同级或更高级标题之前）")
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--asset-root", help="图片相对路径的根目录，默认 Markdown 所在目录")
    parser.add_argument("--expect-path", help="云端完整路径必须等于此值，例如 'router / 报告.otl'")
    parser.add_argument("--allow-duplicate-heading", action="store_true",
                        help="新内容的标题已存在于文档时仍然插入（默认拒绝，防止重复执行）")
    parser.add_argument("--keep-auto-numbering", action="store_true",
                        help="保留 convert 生成的标题自动编号（默认写回编号文字）")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir")
    parser.add_argument("--result")
    args = parser.parse_args()
    mode, anchor = parse_position(parser, args)

    md_path = Path(args.markdown).expanduser().resolve()
    markdown = md_path.read_text(encoding="utf-8")
    if not markdown.strip():
        parser.error("Markdown 为空")
    asset_root = Path(args.asset_root).expanduser().resolve() if args.asset_root else md_path.parent

    path = cloud_path(args.drive_id, args.file_id)
    if args.expect_path and path != args.expect_path:
        raise SystemExit(f"云端路径不符：实际 {path!r}，期望 {args.expect_path!r}")
    before_doc, before = read_top(args.file_id)
    clashes = existing_heading_clashes(before, markdown)
    if clashes and not args.allow_duplicate_heading:
        raise SystemExit(f"文档里已有同名标题，疑似重复执行：{clashes[:5]}（确需重复请加 --allow-duplicate-heading）")
    before_attachments = export_attachments(args.file_id)
    if picture_source_keys(before) != set(before_attachments):
        raise SystemExit(
            "写入前附件未闭合（有孤立或缺失附件）；先按 airpage-existing-doc-insertion.md 处理后再插入"
        )
    index = insert_index(before, mode, anchor)

    converted, restored = convert_chunks(args.file_id, markdown, args.keep_auto_numbering)
    uri_paths = {}
    for result in converted:
        for refs in result.get("attachments", {}).values():
            if len(refs) != 1 or not refs[0].get("uri"):
                raise SystemExit(f"convert 返回的图片引用异常：{refs}")
            uri = refs[0]["uri"]
            uri_paths.setdefault(uri, resolve_local_asset(uri, asset_root))
    new_blocks = [block for result in converted for block in result["blocks"]]
    expected = count_types(new_blocks)
    plan = {
        "mode": "apply" if args.apply else "preview",
        "cloud_path": path,
        "position": {"mode": mode, "anchor": anchor, "index": index},
        "neighbour_before": collect_text(before[index - 1])[:60] if index > 0 else None,
        "neighbour_after": collect_text(before[index])[:60] if index < len(before) else None,
        "top_blocks_before": len(before),
        "new_top_blocks": len(new_blocks),
        "chunks": len(converted),
        "numbered_headings_restored": restored,
        "new_types": {k: expected.get(k, 0) for k in ("heading", "paragraph", "table", "picture", "codeBlock")},
        "images": {uri: str(p) for uri, p in uri_paths.items()},
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if not args.apply:
        return

    backup = Path(args.backup_dir).expanduser().resolve() if args.backup_dir else None
    if backup:
        backup.mkdir(parents=True, exist_ok=True)
        write_json(backup / "before.json", before_doc)

    uploaded, dimensions = {}, {}
    for uri, image_path in uri_paths.items():
        with Image.open(image_path) as image:
            image.verify()
        with Image.open(image_path) as image:
            dimensions[uri] = image.size
        digest = hashlib.sha256(image_path.read_bytes()).hexdigest()[:12]
        uploaded[uri] = upload_attachment(args.file_id, image_path, f"{digest}-{image_path.name}")
        print(f"uploaded image: {uri}", flush=True)
    for result in converted:
        patch_picture_blocks(result["blocks"], result.get("attachments", {}), uploaded, dimensions)

    _, current = read_top(args.file_id)
    if current != before:
        raise SystemExit(
            "上传期间文档被修改，未插入任何块；新上传的附件已留在云端，"
            f"重跑前先用 export_to_json 核对：{sorted(uploaded.values())}"
        )
    offset = index
    for result in converted:
        create_blocks(args.file_id, offset, result["blocks"])
        offset += len(result["blocks"])

    after_doc, after = read_top(args.file_id)
    inserted = after[index:index + len(new_blocks)]
    ensure_old_blocks_preserved(current, after, {block.get("id") for block in inserted})
    actual = count_types(inserted)
    for kind in ("picture", "table", "codeBlock", "heading"):
        if actual.get(kind, 0) != expected.get(kind, 0):
            raise SystemExit(f"插入后 {kind} 数不符：期望 {expected.get(kind, 0)}，实际 {actual.get(kind, 0)}")
    after_attachments = export_attachments(args.file_id)
    if picture_source_keys(after) != set(after_attachments):
        raise SystemExit("插入后 picture.sourceKey 与 export attachment_list 未闭合")
    if set(after_attachments) != set(before_attachments) | set(uploaded.values()):
        raise SystemExit("插入后附件集合出现预期外变化")
    numbered = list_numbered_headings(inserted)
    if numbered and not args.keep_auto_numbering:
        raise SystemExit(f"插入的标题仍带自动编号：{numbered[:5]}")

    result = {
        "drive_id": args.drive_id, "file_id": args.file_id,
        "cloud_path": cloud_path(args.drive_id, args.file_id),
        "insert_index": index, "top_blocks_before": len(before), "top_blocks_after": len(after),
        "inserted_types": {k: actual.get(k, 0) for k in ("heading", "paragraph", "table", "picture", "codeBlock")},
        "numbered_headings_restored": restored,
        "uploaded": uploaded,
        "first_inserted": collect_text(inserted[0])[:80] if inserted else None,
        "next_after_inserted": collect_text(after[offset])[:60] if offset < len(after) else None,
    }
    if backup:
        write_json(backup / "after.json", after_doc)
        write_json(backup / "result.json", result)
    write_json(args.result, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
