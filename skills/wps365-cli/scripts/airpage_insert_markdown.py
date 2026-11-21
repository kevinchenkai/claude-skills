#!/usr/bin/env python3
"""Insert a Markdown section (optionally with local images) into an existing AirPage doc.

Read-only by default; pass --apply to write. The document keeps its file id and
link. Typical use: add a new chapter or subsection to a published report.

    python3 airpage_insert_markdown.py <drive-id> <file-id> section.md \
        --section-end "三、知识库" [--expect-path "router / 报告.otl"] \
        [--apply] [--backup-dir DIR] [--result result.json]

Exactly one position: --before-heading / --after-heading / --before-block /
--after-block / --section-end (end of that heading's section) / --append.

Safety: verify the cloud path and existing attachments, then journal each
upload and chunk before writing. Rerun with the same inputs to resume from
verified readback. Existing blocks must match exactly throughout.
Numbered headings ("### 3.5 标题") keep their literal numbers unless
--keep-auto-numbering.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
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


def save_state(path, state):
    """Publish a complete journal snapshot before sending a write request."""
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as out:
        temporary = Path(out.name)
        try:
            json.dump(state, out, ensure_ascii=False)
            out.flush()
            os.fsync(out.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def same_inserted_block(expected, actual):
    """Compare converted blocks with readback, which adds IDs and default attributes."""
    if expected.get("type") != actual.get("type"):
        return False
    attrs = expected.get("attrs") or {}
    actual_attrs = actual.get("attrs") or {}
    if any(actual_attrs.get(key) != value for key, value in attrs.items()):
        return False
    if {k: v for k, v in expected.items() if k not in ("id", "attrs", "content")} != {
            k: v for k, v in actual.items() if k not in ("id", "attrs", "content")}:
        return False
    children = expected.get("content") or []
    actual_children = actual.get("content") or []
    if isinstance(children, list) and isinstance(actual_children, list):
        return len(children) == len(actual_children) and all(
            same_inserted_block(left, right) for left, right in zip(children, actual_children)
        )
    return children == actual_children


def reconcile_chunk(state, live, blocks):
    """Return the new blocks if exactly the pending chunk is visible at its anchor."""
    before = state["before"]
    index = state["index"]
    written = state["written"]
    offset = index + len(written)
    prefix, suffix = before[:index] + written, before[index:]
    if live == prefix + suffix:
        return []
    if len(live) != len(prefix) + len(blocks) + len(suffix):
        raise RuntimeError("文档块数与续跑记录不符，停止写入")
    inserted = live[offset:offset + len(blocks)]
    if (live[:offset] != prefix or live[offset + len(blocks):] != suffix
            or not all(same_inserted_block(left, right) for left, right in zip(blocks, inserted))):
        raise RuntimeError("无法确认在途分块或原有正文已变化，停止写入")
    ids = [block.get("id") for block in live]
    if any(not block.get("id") for block in inserted) or len(ids) != len(set(ids)):
        raise RuntimeError("回读的块 ID 缺失或重复，停止写入")
    return inserted


def resume_insert(file_id, state, pending_path, assets):
    before = state["before"]
    index = state["index"]
    uploaded = state["uploaded"]
    dimensions = {}
    for uri, (path, sha256, sha1, size) in assets.items():
        dimensions[uri] = size
        if uri in uploaded:
            continue
        _, live = read_top(file_id)
        if live != before:
            raise RuntimeError("原有正文已变化，停止上传图片")
        expected = set(state["before_attachments"]) | set(uploaded.values())
        attachments = export_attachments(file_id)
        if not expected <= set(attachments):
            raise RuntimeError("已确认附件缺失，停止写入")
        extra = set(attachments) - expected
        if extra:
            if (state["uploading"] != uri or len(extra) != 1
                    or attachments[next(iter(extra))] != sha1):
                raise RuntimeError("无法确认新增附件属于本次上传，停止写入")
            uploaded[uri] = next(iter(extra))
        else:
            state["uploading"] = uri
            save_state(pending_path, state)
            uploaded[uri] = upload_attachment(file_id, path, f"{sha256[:12]}-{path.name}")
        state["uploading"] = None
        save_state(pending_path, state)

    attachment_ids = set(state["before_attachments"]) | set(uploaded.values())
    if set(export_attachments(file_id)) != attachment_ids:
        raise RuntimeError("附件集合与续跑记录不符，停止写入")
    chunks = state["converted"]
    for chunk_number in range(state["next_chunk"], len(chunks)):
        chunk = chunks[chunk_number]
        blocks = chunk["blocks"]
        patch_picture_blocks(blocks, chunk.get("attachments", {}), uploaded, dimensions)
        _, live = read_top(file_id)
        inserted = reconcile_chunk(state, live, blocks if state["creating"] else [])
        if blocks and not inserted:
            offset = index + len(state["written"])
            state["creating"] = True
            save_state(pending_path, state)
            create_blocks(file_id, offset, blocks)
            _, live = read_top(file_id)
            inserted = reconcile_chunk(state, live, blocks)
            if not inserted:
                raise RuntimeError("写入后未读到分块，保留续跑记录")
        state["written"].extend(inserted)
        state["next_chunk"] = chunk_number + 1
        state["creating"] = False
        save_state(pending_path, state)
    return attachment_ids


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
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".cache/wps365-cli/markdown-insert",
                        help="本机续跑记录目录；重跑时须使用同一目录")
    parser.add_argument("--operation-id", default="", help="确需再次插入相同内容时，显式指定一个新操作 ID")
    args = parser.parse_args()
    mode, anchor = parse_position(parser, args)
    target_key = hashlib.sha256(json.dumps([args.drive_id, args.file_id]).encode()).hexdigest()
    target_dir = args.state_dir.expanduser() / target_key
    if args.apply:
        target_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = target_dir / "lock"
    lock_context = lock_path.open("a") if args.apply else nullcontext()
    with lock_context as lock:
        if lock is not None:
            fcntl.flock(lock, fcntl.LOCK_EX)
        run(args, mode, anchor, target_dir)


def run(args, mode, anchor, target_dir):
    md_path = Path(args.markdown).expanduser().resolve()
    markdown = md_path.read_text(encoding="utf-8")
    if not markdown.strip():
        raise SystemExit("Markdown 为空")
    asset_root = Path(args.asset_root).expanduser().resolve() if args.asset_root else md_path.parent

    path = cloud_path(args.drive_id, args.file_id)
    if args.expect_path and path != args.expect_path:
        raise SystemExit(f"云端路径不符：实际 {path!r}，期望 {args.expect_path!r}")
    before_doc, before = read_top(args.file_id)
    pending_path = target_dir / "pending.json"
    state = json.loads(pending_path.read_text(encoding="utf-8")) if pending_path.exists() else None
    if state is None:
        converted, restored = convert_chunks(args.file_id, markdown, args.keep_auto_numbering)
    else:
        converted, restored = state["converted"], state["restored"]
    uri_paths = {}
    for result in converted:
        for refs in result.get("attachments", {}).values():
            if len(refs) != 1 or not refs[0].get("uri"):
                raise SystemExit(f"convert 返回的图片引用异常：{refs}")
            uri = refs[0]["uri"]
            uri_paths.setdefault(uri, resolve_local_asset(uri, asset_root))
    assets = {}
    for uri, image_path in uri_paths.items():
        with Image.open(image_path) as image:
            size = image.size
            image.verify()
        raw = image_path.read_bytes()
        assets[uri] = (image_path, hashlib.sha256(raw).hexdigest(), hashlib.sha1(raw).hexdigest(), size)
    request = [mode, anchor, markdown, args.keep_auto_numbering, args.operation_id,
               sorted((uri, asset[1]) for uri, asset in assets.items())]
    operation = hashlib.sha256(json.dumps(request, ensure_ascii=False).encode()).hexdigest()
    receipt = target_dir / f"{operation}.json"
    if state is not None and state["operation"] != operation:
        raise SystemExit(f"该文档有未完成的插入操作，请用原输入和参数续跑：{pending_path}")
    if receipt.exists():
        result = json.loads(receipt.read_text(encoding="utf-8"))
        ids = result["inserted_block_ids"]
        live_ids = [block.get("id") for block in before]
        if ids and not any(live_ids[i:i + len(ids)] == ids for i in range(len(live_ids))):
            raise SystemExit("已完成记录中的块缺失或顺序已变化，请先核对云端内容")
        if args.apply and state is not None:
            pending_path.unlink()
        if args.apply:
            write_json(args.result, {**result, "already_completed": True})
        print(json.dumps({**result, "already_completed": True}, ensure_ascii=False, indent=2))
        return
    if state is None:
        clashes = existing_heading_clashes(before, markdown)
        if clashes and not args.allow_duplicate_heading:
            raise SystemExit(f"文档里已有同名标题，疑似重复执行：{clashes[:5]}（确需重复请加 --allow-duplicate-heading）")
        before_attachments = export_attachments(args.file_id)
        if picture_source_keys(before) != set(before_attachments):
            raise SystemExit(
                "写入前附件未闭合（有孤立或缺失附件）；先按 airpage-existing-doc-insertion.md 处理后再插入"
            )
        index = insert_index(before, mode, anchor)
    else:
        before, index = state["before"], state["index"]
    new_blocks = [block for result in converted for block in result["blocks"]]
    expected = count_types(new_blocks)
    plan = {
        "mode": ("resume" if state else "apply") if args.apply else "preview",
        "resume_from_chunk": state["next_chunk"] if state else None,
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
    if backup and state is None:
        backup.mkdir(parents=True, exist_ok=True)
        write_json(backup / "before.json", before_doc)
    if state is None:
        state = {"operation": operation, "index": index, "before": before,
                 "before_attachments": before_attachments, "converted": converted, "restored": restored,
                 "uploaded": {}, "uploading": None, "written": [], "next_chunk": 0, "creating": False}
        save_state(pending_path, state)
    try:
        attachment_ids = resume_insert(args.file_id, state, pending_path, assets)
    except Exception as exc:
        raise SystemExit(f"插入中断：{exc}。保留续跑记录；核对原因后用相同输入重跑：{pending_path}") from exc

    after_doc, after = read_top(args.file_id)
    reconcile_chunk(state, after, [])
    inserted = after[index:index + len(new_blocks)]
    ensure_old_blocks_preserved(before, after, {block.get("id") for block in inserted})
    actual = count_types(inserted)
    for kind in ("picture", "table", "codeBlock", "heading"):
        if actual.get(kind, 0) != expected.get(kind, 0):
            raise SystemExit(f"插入后 {kind} 数不符：期望 {expected.get(kind, 0)}，实际 {actual.get(kind, 0)}")
    after_attachments = export_attachments(args.file_id)
    if picture_source_keys(after) != set(after_attachments):
        raise SystemExit("插入后 picture.sourceKey 与 export attachment_list 未闭合")
    if set(after_attachments) != attachment_ids:
        raise SystemExit("插入后附件集合出现预期外变化")
    numbered = list_numbered_headings(inserted)
    if numbered and not args.keep_auto_numbering:
        raise SystemExit(f"插入的标题仍带自动编号：{numbered[:5]}")

    offset = index + len(inserted)
    result = {
        "drive_id": args.drive_id, "file_id": args.file_id,
        "cloud_path": cloud_path(args.drive_id, args.file_id),
        "insert_index": index, "top_blocks_before": len(before), "top_blocks_after": len(after),
        "inserted_types": {k: actual.get(k, 0) for k in ("heading", "paragraph", "table", "picture", "codeBlock")},
        "numbered_headings_restored": restored,
        "uploaded": state["uploaded"],
        "inserted_block_ids": [block["id"] for block in inserted],
        "first_inserted": collect_text(inserted[0])[:80] if inserted else None,
        "next_after_inserted": collect_text(after[offset])[:60] if offset < len(after) else None,
    }
    if backup:
        backup.mkdir(parents=True, exist_ok=True)
        write_json(backup / "after.json", after_doc)
        write_json(backup / "result.json", result)
    write_json(args.result, result)
    save_state(receipt, result)
    pending_path.unlink()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
