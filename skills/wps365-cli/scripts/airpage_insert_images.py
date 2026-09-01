#!/usr/bin/env python3
"""Safely insert native local images into an existing WPS AirPage document.

The command is read-only by default. Pass --apply to upload/insert. Retries are
idempotent by local SHA1 versus export_to_json.attachment_list hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("需要 Pillow：pip install Pillow（用于读取图片宽高）")

from _airpage_common import (
    cli, cloud_path, create_blocks, ensure_old_blocks_preserved,
    export_attachments, picture_source_keys, read_top, resolve_anchor, write_json,
)


def response_header(headers, *names):
    for name in names:
        match = re.search(rf"^{re.escape(name)}:\s*(.+?)\r?$", headers, re.I | re.M)
        if match:
            return match.group(1).strip()
    raise RuntimeError(f"missing storage response header: {names}")


def upload_attachment(file_id, path, sha256):
    raw = path.read_bytes()
    request = cli(
        "api", "post", f"/v7/coop/files/{file_id}/attachments/upload/address",
        "--token-type", "delegated",
        "--data", json.dumps({
            "name": f"{sha256[:12]}-{path.name}",
            "size": len(raw),
            "content_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "md5": hashlib.md5(raw).hexdigest(),
            "internal": False,
        }), "-o", "json",
    )["data"]
    store = request["request"]
    command = ["curl", "-sS", "-D", "-", "-o", "/dev/null", "-X", store.get("method") or "PUT"]
    for name, value in (store.get("headers") or {}).items():
        command.extend(["-H", f"{name}: {value}"])
    command.extend(["--data-binary", "@-", store["url"]])
    proc = subprocess.run(command, input=raw, capture_output=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace"))
    headers = proc.stdout.decode("latin1")
    statuses = re.findall(r"HTTP/\S+\s+(\d+)", headers)
    if not statuses or statuses[-1] not in {"200", "201", "204"}:
        raise RuntimeError(f"attachment store failed: {headers[:600]}")
    complete = cli(
        "api", "post", f"/v7/coop/files/{file_id}/attachments/upload/complete",
        "--token-type", "delegated",
        "--data", json.dumps({
            "upload_id": request["upload_id"],
            "params": {
                "etag": response_header(headers, "etag"),
                "key": response_header(headers, "newfilename", "x-asimov-request-id2"),
            },
        }), "-o", "json",
    )["data"]
    return complete["attachment_id"]


def image_info(path):
    raw = path.read_bytes()
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        width, height = image.size
    return {
        "path": path,
        "sha1": hashlib.sha1(raw).hexdigest(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "width": width,
        "height": height,
    }


def choose_existing_attachment(info, attachments, linked):
    matches = [attachment_id for attachment_id, digest in attachments.items() if digest == info["sha1"]]
    if len(matches) > 1:
        linked_matches = [attachment_id for attachment_id in matches if attachment_id in linked]
        if len(linked_matches) == 1:
            return linked_matches[0]
        raise RuntimeError(f"同一 SHA1 对应多个附件，无法安全选择：{matches}")
    return matches[0] if matches else None


def parse_anchor(parser, args):
    choices = [
        ("before-heading", args.before_heading), ("after-heading", args.after_heading),
        ("before-block", args.before_block), ("after-block", args.after_block),
        ("append", True if args.append else None),
    ]
    selected = [(mode, value) for mode, value in choices if value is not None]
    if len(selected) != 1:
        parser.error("必须且只能指定一个插入位置：--before/after-heading、--before/after-block 或 --append")
    return selected[0]


def main():
    parser = argparse.ArgumentParser(description="向已有 WPS 智能文档安全插入原生图片；默认只预检")
    parser.add_argument("drive_id")
    parser.add_argument("file_id", help="AirPage file id，不是短链码")
    parser.add_argument("images", nargs="+", help="本地图片，按给定顺序插入")
    parser.add_argument("--before-heading")
    parser.add_argument("--after-heading")
    parser.add_argument("--before-block")
    parser.add_argument("--after-block")
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--render-width", type=int, default=740,
                        help="渲染最长边上限，默认 740")
    parser.add_argument("--allow-duplicate", action="store_true", help="允许重复展示已存在的同一附件")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir")
    parser.add_argument("--result")
    args = parser.parse_args()
    if args.render_width < 1:
        parser.error("--render-width 必须大于 0")
    mode, anchor = parse_anchor(parser, args)

    paths = [Path(value).expanduser().resolve() for value in args.images]
    if len(set(paths)) != len(paths):
        parser.error("同一次调用不能重复传入同一路径")
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    infos = [image_info(path) for path in paths]

    before_doc, before = read_top(args.file_id)
    before_attachments = export_attachments(args.file_id)
    before_keys = picture_source_keys(before)
    missing = before_keys - set(before_attachments)
    unrelated_orphans = set(before_attachments) - before_keys
    candidate_orphans = {
        attachment_id
        for info in infos
        for attachment_id, digest in before_attachments.items()
        if digest == info["sha1"]
    }
    if missing or unrelated_orphans - candidate_orphans:
        raise RuntimeError(
            f"写入前附件闭环异常：missing={sorted(missing)}, "
            f"unrelated_orphans={sorted(unrelated_orphans - candidate_orphans)}"
        )
    index = resolve_anchor(before, mode, anchor)

    plan = []
    for info in infos:
        attachment_id = choose_existing_attachment(info, before_attachments, before_keys)
        already_linked = bool(attachment_id and attachment_id in before_keys)
        action = "skip-existing" if already_linked and not args.allow_duplicate else (
            "reuse-attachment" if attachment_id else "upload"
        )
        plan.append({**info, "attachment_id": attachment_id, "action": action})
    printable = [{**item, "path": str(item["path"])} for item in plan]
    print(json.dumps({
        "mode": "apply" if args.apply else "preview", "cloud_path": cloud_path(args.drive_id, args.file_id),
        "anchor_mode": mode, "anchor": anchor, "index": index, "images": printable,
    }, ensure_ascii=False, indent=2))
    if not args.apply:
        return

    backup = Path(args.backup_dir).expanduser().resolve() if args.backup_dir else None
    if backup:
        backup.mkdir(parents=True, exist_ok=True)
        write_json(backup / "before.json", before_doc)

    newly_uploaded = set()
    for item in plan:
        if item["action"] != "upload":
            continue
        item["attachment_id"] = upload_attachment(args.file_id, item["path"], item["sha256"])
        item["action"] = "uploaded"
        newly_uploaded.add(item["attachment_id"])

    current_doc, current = read_top(args.file_id)
    if current != before:
        raise RuntimeError("上传期间文档 blocks 被并发修改；附件已上传但未插块，可按 SHA1 安全重试")
    current_index = resolve_anchor(current, mode, anchor)
    to_insert = [item for item in plan if item["action"] != "skip-existing"]
    blocks = []
    for item in to_insert:
        scale = min(
            args.render_width / item["width"],
            args.render_width / item["height"],
            1.0,
        )
        blocks.append({"type": "picture", "attrs": {
            "sourceKey": item["attachment_id"], "width": item["width"], "height": item["height"],
            "renderWidth": round(item["width"] * scale),
            "renderHeight": round(item["height"] * scale), "version": 3,
        }})
    if blocks:
        create_blocks(args.file_id, current_index, blocks)

    after_doc, after = read_top(args.file_id)
    inserted = after[current_index:current_index + len(blocks)]
    expected_keys = [item["attachment_id"] for item in to_insert]
    if [block.get("attrs", {}).get("sourceKey") for block in inserted] != expected_keys:
        raise RuntimeError("插入位置或 picture.sourceKey 回读不符合预期")
    inserted_ids = {block.get("id") for block in inserted}
    ensure_old_blocks_preserved(current, after, inserted_ids)
    after_attachments = export_attachments(args.file_id)
    after_keys = picture_source_keys(after)
    if after_keys != set(after_attachments):
        raise RuntimeError("插入后 picture.sourceKey 与 export attachment_list 未闭合")
    if set(after_attachments) != set(before_attachments) | newly_uploaded:
        raise RuntimeError("插入后附件集合出现预期外变化")

    result = {
        "drive_id": args.drive_id, "file_id": args.file_id,
        "cloud_path": cloud_path(args.drive_id, args.file_id),
        "before_top_blocks": len(before), "after_top_blocks": len(after),
        "inserted": [
            {"path": str(item["path"]), "attachment_id": item["attachment_id"], "action": item["action"]}
            for item in to_insert
        ],
        "skipped": [str(item["path"]) for item in plan if item["action"] == "skip-existing"],
    }
    if backup:
        write_json(backup / "after.json", after_doc)
        write_json(backup / "result.json", result)
    write_json(args.result, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
