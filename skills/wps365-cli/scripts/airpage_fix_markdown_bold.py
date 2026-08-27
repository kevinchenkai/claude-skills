#!/usr/bin/env python3
"""把已有 WPS 智能文档中的字面 ``**文字**`` 转成原生加粗。

默认只预检；传 ``--apply`` 才会修改。当前只处理顶层 paragraph / blockQuote
中的 text 节点，并在每次写入前回读最新 blocks。由于 AirPage 的 blocks/update
不能用于这种替换，脚本会在原位置创建新块，再按 doc 的子块区间删除旧块。
"""

from __future__ import annotations

import argparse
import base64
import copy
import json
import re
import subprocess
import sys
from pathlib import Path


ELIGIBLE_TYPES = {"paragraph", "blockQuote"}
BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
RANGE_MARK_TYPES = {"rangeMarkBegin", "rangeMarkEnd"}


def cli(*args):
    proc = subprocess.run(["wps365-cli", *args], capture_output=True, text=True)
    if not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or "wps365-cli returned no JSON")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"wps365-cli returned non-JSON output for {' '.join(args)}: "
            f"{proc.stdout[:300]} {proc.stderr[:300]}"
        ) from exc
    if data.get("code") not in (0, None):
        raise RuntimeError(json.dumps(data, ensure_ascii=False))
    return data


def b64(value):
    return base64.b64encode(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")


def unb64(value):
    return json.loads(base64.b64decode(value))


def read_blocks(file_id):
    response = cli(
        "api", "post", f"/v7/airpage/{file_id}/blocks",
        "--data", json.dumps({"arg": b64({"blockId": "doc"})}),
        "-o", "json",
    )
    decoded = unb64(response["data"]["result"])
    roots = decoded.get("blocks") or []
    if len(roots) != 1 or roots[0].get("type") != "doc":
        raise RuntimeError("unexpected AirPage blocks response: missing single doc root")
    return decoded, roots[0].get("content") or []


def export_attachment_ids(file_id):
    exported = cli(
        "api", "post", f"/v7/airpage/{file_id}/export_to_json",
        "--data", "{}", "-o", "json",
    )["data"]
    return {
        item.get("id")
        for item in exported.get("attachment_list", [])
        if item.get("id")
    }


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def strip_ids(value):
    if isinstance(value, dict):
        return {key: strip_ids(child) for key, child in value.items() if key != "id"}
    if isinstance(value, list):
        return [strip_ids(child) for child in value]
    return value


def canonical(value):
    return json.dumps(strip_ids(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def collect_text(value):
    return "".join(
        item.get("content", "")
        for item in walk(value)
        if item.get("type") == "text" and isinstance(item.get("content"), str)
    )


def count_types(value):
    counts = {}
    for item in walk(value):
        kind = item.get("type")
        # attrs/元数据里也可能有名为 type 的普通字段；只统计形似 block 的对象。
        if kind and kind != "text" and ("id" in item or "content" in item):
            counts[kind] = counts.get(kind, 0) + 1
    return counts


def picture_source_keys(value):
    return {
        item.get("attrs", {}).get("sourceKey")
        for item in walk(value)
        if item.get("type") == "picture" and item.get("attrs", {}).get("sourceKey")
    }


def bold_text_nodes(value):
    return sum(
        1
        for item in walk(value)
        if item.get("type") == "text" and item.get("attrs", {}).get("bold") is True
    )


def marker_count(value):
    return sum(
        item.get("content", "").count("**")
        for item in walk(value)
        if item.get("type") == "text" and isinstance(item.get("content"), str)
    )


def transform_text_node(node):
    text = node.get("content")
    if not isinstance(text, str) or "**" not in text:
        return [copy.deepcopy(node)], 0
    if "***" in text:
        raise ValueError(f"不支持三连星号，请先人工确认语义：{text!r}")

    parts = []
    cursor = 0
    pairs = 0
    for match in BOLD_PATTERN.finditer(text):
        if match.start() > cursor:
            plain = copy.deepcopy(node)
            plain["content"] = text[cursor:match.start()]
            parts.append(plain)
        bold = copy.deepcopy(node)
        bold["content"] = match.group(1)
        bold.setdefault("attrs", {})["bold"] = True
        parts.append(bold)
        cursor = match.end()
        pairs += 1
    if cursor < len(text):
        tail = copy.deepcopy(node)
        tail["content"] = text[cursor:]
        parts.append(tail)

    if pairs == 0 or any("**" in part.get("content", "") for part in parts):
        raise ValueError(f"存在未配对或嵌套的 ** 标记：{text!r}")
    return [part for part in parts if part.get("content") != ""], pairs


def transform_value(value):
    """递归转换 text 节点；返回 (新值, 配对数)。"""
    if isinstance(value, list):
        output = []
        pairs = 0
        for child in value:
            if isinstance(child, dict) and child.get("type") == "text":
                replacement, found = transform_text_node(child)
                output.extend(replacement)
                pairs += found
            else:
                replacement, found = transform_value(child)
                output.append(replacement)
                pairs += found
        return output, pairs
    if isinstance(value, dict):
        output = {}
        pairs = 0
        for key, child in value.items():
            replacement, found = transform_value(child)
            output[key] = replacement
            pairs += found
        return output, pairs
    return copy.deepcopy(value), 0


def contains_range_mark(value):
    return any(item.get("type") in RANGE_MARK_TYPES for item in walk(value))


def plan_changes(top, resume_partial=False):
    plans = []
    ignored_markers = 0
    expected = copy.deepcopy(top)
    expected_deletions = []
    for index, block in enumerate(top):
        markers = marker_count(block)
        if not markers:
            continue
        if block.get("type") not in ELIGIBLE_TYPES:
            ignored_markers += markers
            continue
        if contains_range_mark(block):
            raise RuntimeError(
                f"第 {index} 个块含批注锚点，拒绝替换以免丢失评论；block_id={block.get('id')}"
            )
        replacement, pairs = transform_value(block)
        if pairs == 0:
            continue
        if marker_count(replacement):
            raise RuntimeError(f"第 {index} 个块转换后仍有 ** 标记")
        if collect_text(block).replace("**", "") != collect_text(replacement):
            raise RuntimeError(f"第 {index} 个块转换前后语义文本不一致")
        if count_types(block) != count_types(replacement):
            raise RuntimeError(f"第 {index} 个块转换前后结构类型不一致")
        expected[index] = replacement
        if resume_partial and index > 0 and canonical(top[index - 1]) == canonical(replacement):
            expected_deletions.append(index)
        plans.append({
            "block_id": block.get("id"),
            "initial_index": index,
            "pairs": pairs,
            "before": copy.deepcopy(block),
            "replacement": replacement,
        })
    if any(not plan["block_id"] for plan in plans):
        raise RuntimeError("目标块缺少 id，不能安全替换")
    for index in reversed(expected_deletions):
        del expected[index]
    return plans, expected, ignored_markers


def find_index(top, block_id):
    matches = [index for index, block in enumerate(top) if block.get("id") == block_id]
    if len(matches) != 1:
        raise RuntimeError(f"目标块 {block_id} 当前出现 {len(matches)} 次，停止修改")
    return matches[0]


def create_block(file_id, index, replacement):
    payload = {"blockId": "doc", "index": index, "content": [strip_ids(replacement)]}
    cli(
        "api", "post", f"/v7/airpage/{file_id}/blocks/create",
        "--data", json.dumps({"arg": b64(payload)}), "-o", "json",
    )


def delete_range(file_id, start, end):
    payload = {"blockId": "doc", "startIndex": start, "endIndex": end}
    cli(
        "api", "post", f"/v7/airpage/{file_id}/blocks/delete",
        "--data", json.dumps({"arg": b64(payload)}), "-o", "json",
    )


def apply_plan(file_id, plan, resume_partial=False):
    _, top = read_blocks(file_id)
    index = find_index(top, plan["block_id"])
    current = top[index]
    if canonical(current) != canonical(plan["before"]):
        raise RuntimeError(f"块 {plan['block_id']} 已被并发修改，停止")

    expected = canonical(plan["replacement"])
    has_partial = index > 0 and canonical(top[index - 1]) == expected
    if has_partial:
        if not resume_partial:
            raise RuntimeError(
                f"检测到块 {plan['block_id']} 前已有等价替换块；"
                "可能是上次创建成功但删除失败。确认后用 --resume-partial --apply 清理旧块"
            )
        delete_range(file_id, index, index + 1)
        _, verified = read_blocks(file_id)
        if any(block.get("id") == plan["block_id"] for block in verified):
            raise RuntimeError(f"恢复删除后旧块 {plan['block_id']} 仍存在")
        return "resumed"

    create_block(file_id, index, plan["replacement"])
    _, inserted = read_blocks(file_id)
    old_index = find_index(inserted, plan["block_id"])
    if old_index != index + 1 or canonical(inserted[index]) != expected:
        raise RuntimeError(
            f"新块已请求创建，但旧块 {plan['block_id']} 的位置或新块内容不符合预期；"
            "停止删除，请人工检查"
        )
    try:
        delete_range(file_id, old_index, old_index + 1)
    except Exception as exc:
        raise RuntimeError(
            f"新块已创建、旧块 {plan['block_id']} 未删除；"
            "排查后用 --resume-partial --apply 恢复"
        ) from exc

    _, verified = read_blocks(file_id)
    if any(block.get("id") == plan["block_id"] for block in verified):
        raise RuntimeError(f"删除调用后旧块 {plan['block_id']} 仍存在")
    if index >= len(verified) or canonical(verified[index]) != expected:
        raise RuntimeError(f"块 {plan['block_id']} 替换后回读内容不一致")
    return "replaced"


def snapshot(path, decoded):
    path.write_text(json.dumps(decoded, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="把已有 WPS 智能文档顶层段落/引用中的 **文字** 转成原生加粗；默认只预检"
    )
    parser.add_argument("file_id", help="AirPage/智能文档 file id（不是分享链接短码）")
    parser.add_argument("--apply", action="store_true", help="执行修改；不传时只做预检")
    parser.add_argument(
        "--resume-partial", action="store_true",
        help="清理上次中断后紧邻旧块的等价替换块；必须与 --apply 同用",
    )
    parser.add_argument("--backup-dir", help="可选：保存 before.json、after.json 和 result.json")
    parser.add_argument("--result", help="可选：另存结果摘要 JSON")
    parser.add_argument("--max-blocks", type=int, default=200, help="单次最多替换块数，默认 200")
    args = parser.parse_args()

    if args.resume_partial and not args.apply:
        parser.error("--resume-partial 必须与 --apply 同用")
    if args.max_blocks < 1:
        parser.error("--max-blocks 必须大于 0")

    before_doc, before_top = read_blocks(args.file_id)
    before_attachments = export_attachment_ids(args.file_id)
    plans, expected_top, ignored = plan_changes(before_top, args.resume_partial)
    if len(plans) > args.max_blocks:
        raise RuntimeError(
            f"预检发现 {len(plans)} 个目标块，超过 --max-blocks={args.max_blocks}，停止"
        )

    backup_dir = Path(args.backup_dir).resolve() if args.backup_dir else None
    if backup_dir:
        backup_dir.mkdir(parents=True, exist_ok=True)
        snapshot(backup_dir / "before.json", before_doc)

    summary = {
        "mode": "apply" if args.apply else "dry-run",
        "file_id": args.file_id,
        "target_blocks": len(plans),
        "bold_pairs": sum(plan["pairs"] for plan in plans),
        "ignored_marker_tokens": ignored,
        "before": {
            "marker_tokens": sum(marker_count(block) for block in before_top if block.get("type") in ELIGIBLE_TYPES),
            "bold_text_nodes": bold_text_nodes(before_top),
            "block_types": count_types(before_top),
            "picture_source_keys": len(picture_source_keys(before_top)),
            "attachments": len(before_attachments),
        },
    }

    if args.apply:
        outcomes = {"replaced": 0, "resumed": 0}
        for number, plan in enumerate(plans, 1):
            outcome = apply_plan(args.file_id, plan, args.resume_partial)
            outcomes[outcome] += 1
            print(
                f"{number}/{len(plans)} {outcome}: block={plan['block_id']} pairs={plan['pairs']}",
                file=sys.stderr,
            )

        after_doc, after_top = read_blocks(args.file_id)
        after_attachments = export_attachment_ids(args.file_id)
        after_plans, _, after_ignored = plan_changes(after_top)
        if after_plans:
            raise RuntimeError(f"修改后仍有 {len(after_plans)} 个可转换目标块")
        if collect_text(after_top) != collect_text(expected_top):
            raise RuntimeError("修改后全文语义文本与预检预期不一致")
        if count_types(after_top) != count_types(expected_top):
            raise RuntimeError("修改后非文本 block 类型计数与预检预期不一致")
        if picture_source_keys(after_top) != picture_source_keys(before_top):
            raise RuntimeError("修改后 picture sourceKey 集合发生变化")
        if after_attachments != before_attachments:
            raise RuntimeError("修改后附件 ID 集合发生变化")

        summary["outcomes"] = outcomes
        summary["after"] = {
            "marker_tokens": sum(marker_count(block) for block in after_top if block.get("type") in ELIGIBLE_TYPES),
            "ignored_marker_tokens": after_ignored,
            "bold_text_nodes": bold_text_nodes(after_top),
            "block_types": count_types(after_top),
            "picture_source_keys": len(picture_source_keys(after_top)),
            "attachments": len(after_attachments),
        }
        if backup_dir:
            snapshot(backup_dir / "after.json", after_doc)

    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    print(rendered)
    if args.result:
        Path(args.result).resolve().write_text(rendered + "\n", encoding="utf-8")
    if backup_dir:
        (backup_dir / "result.json").write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
