#!/usr/bin/env python3
"""Numbered headings: convert's auto-numbering is undone before/after insertion."""

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _airpage_common import (  # noqa: E402
    collect_text, list_numbered_headings, markdown_headings, plain_heading,
    restore_numbered_headings, stripped_number_prefix,
)
from airpage_fix_numbered_headings import (  # noqa: E402
    plan_from_map, plan_from_markdown, plan_strip_only,
)

LIST = {"id": "L1", "level": 0, "styleFormat": 1, "styleType": 4, "type": 2}


def converted_heading(text, level, numbered=True, content=None, block_id=None):
    """Shape blocks/convert returns (measured 2026-11-21)."""
    attrs = {"align": 1, "level": level}
    if numbered:
        attrs.update({"contentIndent": 1, "listAttrs": dict(LIST)})
    block = {"type": "heading", "attrs": attrs,
             "content": content if content is not None else ([{"type": "text", "content": text}] if text else None)}
    if block_id:
        block["id"] = block_id
    return block


def paragraph(text, ordered=False):
    block = {"type": "paragraph", "attrs": {}, "content": [{"type": "text", "content": text}]}
    if ordered:
        block["attrs"]["listAttrs"] = dict(LIST)
    return block


class MarkdownHeadingsTest(unittest.TestCase):
    def test_atx_headings_skip_fences_and_closing_hashes(self):
        md = "## C#\n## 标题 ##\n```\n## 代码里的\n```\n~~~\n# 也不算\n~~~\n#### 3.1 x\n#不是标题\n###\n"
        self.assertEqual(markdown_headings(md), [(2, "C#"), (2, "标题"), (4, "3.1 x"), (3, "")])

    def test_stripped_number_prefix_matches_measured_triggers(self):
        cases = [
            ("3. 带点一级", "带点一级", "3. "), ("3.1 二级", "二级", "3.1 "),
            ("1.5倍速", "倍速", "1.5"), ("1.0", "", "1.0"), ("12) 括号", "括号", "12) "),
            ("**2.1 粗体**", "粗体", "2.1 "), ("2.2 含 `code`", "含 code", "2.2 "),
        ]
        for source, converted, prefix in cases:
            with self.subTest(source=source):
                self.assertEqual(stripped_number_prefix(source, converted), prefix)

    def test_unprovable_prefix_is_none(self):
        self.assertIsNone(stripped_number_prefix("v1.2 版本", "版本"))
        self.assertIsNone(stripped_number_prefix("完全不同", "标题"))
        self.assertIsNone(stripped_number_prefix("标题", "标题"))


class RestoreTest(unittest.TestCase):
    def test_restores_numbers_and_drops_list_attrs_only_on_headings(self):
        md = "## 3. 一级\n正文\n### 3.1 二级\n### ① 圈号\n### **2.1 粗体**\n### 1.0\n1. 有序列表\n"
        blocks = [
            converted_heading("一级", 2), paragraph("正文"),
            converted_heading("二级", 3), converted_heading("① 圈号", 3, numbered=False),
            converted_heading(None, 3, content=[{"type": "text", "content": "粗体", "attrs": {"bold": True}}]),
            converted_heading("", 3), paragraph("有序列表", ordered=True),
        ]
        self.assertEqual(restore_numbered_headings(blocks, md), 4)
        texts = [collect_text(b) for b in blocks if b["type"] == "heading"]
        self.assertEqual(texts, ["3. 一级", "3.1 二级", "① 圈号", "2.1 粗体", "1.0"])
        self.assertEqual(list_numbered_headings(blocks), [])
        self.assertTrue(blocks[4]["content"][0]["attrs"]["bold"])
        self.assertNotIn("contentIndent", blocks[0]["attrs"])
        self.assertIn("listAttrs", blocks[6]["attrs"])

    def test_nothing_to_do_returns_zero_even_if_counts_differ(self):
        blocks = [converted_heading("标题", 2, numbered=False)]
        self.assertEqual(restore_numbered_headings(blocks, "无标题正文"), 0)

    def test_count_level_or_prefix_mismatch_raises(self):
        with self.assertRaisesRegex(RuntimeError, "标题数对不上"):
            restore_numbered_headings([converted_heading("a", 2)], "## 1. a\n## 2. b\n")
        with self.assertRaisesRegex(RuntimeError, "层级对不上"):
            restore_numbered_headings([converted_heading("a", 3)], "## 1. a\n")
        with self.assertRaisesRegex(RuntimeError, "无法确认"):
            restore_numbered_headings([converted_heading("别的", 2)], "## 1. a\n")

    def test_plain_heading_drops_id_and_list_attrs(self):
        block = converted_heading("x", 3, block_id="old")
        new = plain_heading(block, "1.2 ")
        self.assertNotIn("id", new)
        self.assertEqual(new["attrs"], {"align": 1, "level": 3})
        self.assertEqual(collect_text(new), "1.2 x")


class FixPlansTest(unittest.TestCase):
    def test_from_markdown_pairs_in_order_with_duplicate_names(self):
        top = [
            converted_heading("概述", 3, block_id="a"), paragraph("p"),
            converted_heading("概述", 3, block_id="b"), converted_heading("案例", 3, numbered=False, block_id="c"),
        ]
        sources = markdown_headings("## 一、甲\n### 1.1 概述\n## 二、乙\n### 2.1 概述\n### 案例\n")
        plan = plan_from_markdown(top, sources)
        self.assertEqual([(i, collect_text(b)) for i, b in plan], [(0, "1.1 概述"), (2, "2.1 概述")])

    def test_from_markdown_missing_source_raises(self):
        with self.assertRaisesRegex(RuntimeError, "找不到"):
            plan_from_markdown([converted_heading("孤儿", 3)], markdown_headings("### 1.1 别的\n"))

    def test_from_markdown_does_not_reuse_number_of_already_repaired_heading(self):
        top = [converted_heading("1. 总览", 2, numbered=False), converted_heading("总览", 2)]
        sources = markdown_headings("## 1. 总览\n## 2. 总览\n")
        self.assertEqual([(i, collect_text(b)) for i, b in plan_from_markdown(top, sources)], [(1, "2. 总览")])

    def test_from_markdown_refuses_ambiguous_number(self):
        with self.assertRaisesRegex(RuntimeError, "多个可能"):
            plan_from_markdown([converted_heading("总览", 2)], markdown_headings("## 1. 总览\n## 2. 总览\n"))

    def test_from_markdown_uses_later_plain_heading_to_disambiguate(self):
        top = [converted_heading("总览", 2), converted_heading("2. 总览", 2, numbered=False)]
        sources = markdown_headings("## 1. 总览\n## 2. 总览\n")
        self.assertEqual([(i, collect_text(b)) for i, b in plan_from_markdown(top, sources)], [(0, "1. 总览")])

    def test_map_requires_unique_heading_and_keeps_formatting_when_suffix(self):
        top = [converted_heading(None, 3, numbered=False,
                                 content=[{"type": "text", "content": "Case A", "attrs": {"bold": True}}]),
               converted_heading("重复", 3), converted_heading("重复", 3)]
        plan = plan_from_map(top, {"Case A": "4.1 Case A"})
        self.assertEqual(collect_text(plan[0][1]), "4.1 Case A")
        self.assertTrue(plan[0][1]["content"][0]["attrs"]["bold"])
        with self.assertRaisesRegex(RuntimeError, "唯一"):
            plan_from_map(top, {"重复": "1 重复"})

    def test_strip_only_targets_list_headings(self):
        top = [converted_heading("a", 2), converted_heading("b", 2, numbered=False)]
        plan = plan_strip_only(top)
        self.assertEqual([(i, collect_text(b)) for i, b in plan], [(0, "a")])
        self.assertNotIn("listAttrs", plan[0][1]["attrs"])


try:
    from airpage_insert_markdown import existing_heading_clashes, insert_index  # noqa: E402
except SystemExit:  # Pillow missing: the insertion CLI refuses to import
    existing_heading_clashes = None


@unittest.skipIf(existing_heading_clashes is None, "Pillow not installed")
class InsertMarkdownTest(unittest.TestCase):
    def test_rerun_guard_matches_numbered_and_stripped_titles(self):
        top = [converted_heading("开源组件清单", 4, numbered=False), converted_heading("3.6 已有", 3, numbered=False)]
        self.assertEqual(
            existing_heading_clashes(top, "#### 3.5.2 开源组件清单\n### 3.6 已有\n### 3.7 全新\n"),
            ["3.5.2 开源组件清单", "3.6 已有"],
        )

    def test_section_end_and_anchor_positions(self):
        top = [converted_heading("三、知识库", 2, numbered=False), paragraph("x"),
               converted_heading("3.4 发布", 3, numbered=False), paragraph("y"),
               converted_heading("四、案例", 2, numbered=False)]
        self.assertEqual(insert_index(top, "section-end", "三、知识库"), 4)
        self.assertEqual(insert_index(top, "section-end", "3.4 发布"), 4)
        self.assertEqual(insert_index(top, "before-heading", "四、案例"), 4)
        self.assertEqual(insert_index(top, "append", None), 5)


if __name__ == "__main__":
    unittest.main()
