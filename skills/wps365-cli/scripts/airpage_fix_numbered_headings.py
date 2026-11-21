#!/usr/bin/env python3
"""Turn auto-numbered list headings of an existing AirPage doc into plain headings.

Read-only by default; pass --apply to write. Use it when a published document's
outline is broken: headings created from "## 3. 标题" / "### 2.1 标题" carry
attrs.listAttrs, the numbers were removed from the text, all levels share one
flat sequence, and every inserted section restarts at 1.

    # recover the original numbers from the Markdown the doc was published from
    python3 airpage_fix_numbered_headings.py <drive-id> <file-id> --from-markdown report.md
    # explicit renames (any heading, numbered or not): {"旧标题": "新标题"}
    python3 airpage_fix_numbered_headings.py <drive-id> <file-id> --map renames.json
    # no source: only drop the auto-numbering, text stays as it is
    python3 airpage_fix_numbered_headings.py <drive-id> <file-id>

Each heading is replaced by "create the new block at its index, then delete the
old block by half-open range", re-locating by block id before every step. Blocks
with comment anchors (rangeMark) are refused. Afterwards every non-heading block
must be unchanged and all heading positions must stay the same.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _airpage_common import (
    b64, cli, cloud_path, collect_text, is_list_numbered_heading, list_numbered_headings,
    markdown_headings, plain_heading, read_top, stripped_number_prefix, write_json,
)


def plan_from_markdown(top, sources):
    """Pair list-numbered headings with source headings in order (monotonic)."""
    plan, pointer = [], 0
    for index, block in enumerate(top):
        if not is_list_numbered_heading(block):
            continue
        text = collect_text(block)
        level = (block.get("attrs") or {}).get("level")
        for k in range(pointer, len(sources)):
            src_level, src_text = sources[k]
            prefix = stripped_number_prefix(src_text, text) if src_level == level else None
            if prefix is not None:
                plan.append((index, plain_heading(block, prefix)))
                pointer = k + 1
                break
        else:
            raise RuntimeError(f"源 Markdown 中找不到对应的编号标题：{text!r}（level {level}）")
    return plan


def plan_from_map(top, mapping):
    headings = {}
    for index, block in enumerate(top):
        if block.get("type") == "heading":
            headings.setdefault(collect_text(block).strip(), []).append(index)
    plan = []
    for old, new in mapping.items():
        hits = headings.get(old, [])
        if len(hits) != 1:
            raise RuntimeError(f"--map 的旧标题必须在文档中唯一出现，当前 {len(hits)} 次：{old!r}")
        block = top[hits[0]]
        text = collect_text(block)
        if new.endswith(text) and text:
            replacement = plain_heading(block, new[: len(new) - len(text)])
        else:
            replacement = plain_heading(block, "")
            replacement["content"] = [{"type": "text", "content": new}]
        plan.append((hits[0], replacement))
    return sorted(plan, key=lambda item: item[0])


def plan_strip_only(top):
    return [(index, plain_heading(block, "")) for index, block in enumerate(top) if is_list_numbered_heading(block)]


def locate(top, block_id):
    hits = [i for i, block in enumerate(top) if block.get("id") == block_id]
    return hits[0] if len(hits) == 1 else None


def main():
    parser = argparse.ArgumentParser(description="把已有智能文档的自动编号标题改成普通标题；默认只预检")
    parser.add_argument("drive_id")
    parser.add_argument("file_id", help="AirPage file id，不是短链码")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--from-markdown", help="发布时用的源 Markdown，用来找回被吞掉的编号")
    source.add_argument("--map", help='JSON 文件 {"旧标题": "新标题"}，可改任意标题')
    parser.add_argument("--expect-path", help="云端完整路径必须等于此值")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir")
    parser.add_argument("--result")
    args = parser.parse_args()

    path = cloud_path(args.drive_id, args.file_id)
    if args.expect_path and path != args.expect_path:
        raise SystemExit(f"云端路径不符：实际 {path!r}，期望 {args.expect_path!r}")
    before_doc, before = read_top(args.file_id)
    if args.from_markdown:
        plan = plan_from_markdown(before, markdown_headings(Path(args.from_markdown).read_text(encoding="utf-8")))
    elif args.map:
        plan = plan_from_map(before, json.loads(Path(args.map).read_text(encoding="utf-8")))
    else:
        plan = plan_strip_only(before)
    for index, _ in plan:
        if "rangeMark" in json.dumps(before[index]):
            raise SystemExit(f"标题带评论锚点，替换会让批注脱锚，停止：{collect_text(before[index])!r}")
    items = [{"id": before[i]["id"], "index": i, "old": collect_text(before[i]), "new": collect_text(new),
              "level": (new.get("attrs") or {}).get("level"), "block": new} for i, new in plan]
    print(json.dumps({
        "mode": "apply" if args.apply else "preview", "cloud_path": path,
        "list_numbered_headings": len(list_numbered_headings(before)),
        "replacements": [{k: item[k] for k in ("index", "level", "old", "new")} for item in items],
    }, ensure_ascii=False, indent=2))
    if not args.apply or not items:
        return

    backup = Path(args.backup_dir).expanduser().resolve() if args.backup_dir else None
    if backup:
        backup.mkdir(parents=True, exist_ok=True)
        write_json(backup / "before.json", before_doc)
    for item in items:
        _, top = read_top(args.file_id)
        i = locate(top, item["id"])
        if i is None or collect_text(top[i]) != item["old"]:
            raise SystemExit(f"目标标题已移动或被改动，停止：{item['old']!r}")
        cli("api", "post", f"/v7/airpage/{args.file_id}/blocks/create",
            "--data", json.dumps({"arg": b64({"blockId": "doc", "index": i, "content": [item["block"]]})}),
            "-o", "json")
        _, top = read_top(args.file_id)
        if collect_text(top[i]) != item["new"] or top[i + 1].get("id") != item["id"]:
            raise SystemExit(f"新标题已创建但位置不符，旧块 {item['id']} 未删除，请人工核对：{item['new']!r}")
        cli("api", "post", f"/v7/airpage/{args.file_id}/blocks/delete",
            "--data", json.dumps({"arg": b64({"blockId": "doc", "startIndex": i + 1, "endIndex": i + 2})}),
            "-o", "json")
        _, top = read_top(args.file_id)
        if locate(top, item["id"]) is not None or collect_text(top[i]) != item["new"]:
            raise SystemExit(f"删除旧标题后回读不符：{item['old']!r}")
        print(f"ok {item['new']}", flush=True)

    after_doc, after = read_top(args.file_id)
    if [b for b in before if b.get("type") != "heading"] != [b for b in after if b.get("type") != "heading"]:
        raise SystemExit("标题以外的正文块发生了变化，请用备份核对")
    positions = lambda top: [i for i, b in enumerate(top) if b.get("type") == "heading"]  # noqa: E731
    if positions(before) != positions(after):
        raise SystemExit("标题位置发生了变化，请用备份核对")
    result = {
        "drive_id": args.drive_id, "file_id": args.file_id, "cloud_path": cloud_path(args.drive_id, args.file_id),
        "replaced": len(items), "still_list_numbered": list_numbered_headings(after),
    }
    if backup:
        write_json(backup / "after.json", after_doc)
        write_json(backup / "result.json", result)
    write_json(args.result, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
