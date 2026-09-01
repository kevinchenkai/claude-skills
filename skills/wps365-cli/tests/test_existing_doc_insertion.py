#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _airpage_common import (  # noqa: E402
    canonical_link_id, collect_text, ensure_old_blocks_preserved,
    picture_source_keys, resolve_anchor, section_append_index, wps_document_refs,
)
from airpage_add_references import reference_block, reference_identity  # noqa: E402


def heading(block_id, text, level=2):
    return {
        "id": block_id,
        "type": "heading",
        "attrs": {"level": level},
        "content": [{"type": "text", "content": text}],
    }


class CommonHelpersTest(unittest.TestCase):
    def test_anchor_by_exact_unique_heading_or_block(self):
        top = [heading("h1", "模型训练"), {"id": "p1", "type": "paragraph", "content": []}]
        self.assertEqual(resolve_anchor(top, "before-heading", "模型训练"), 0)
        self.assertEqual(resolve_anchor(top, "after-heading", "模型训练"), 1)
        self.assertEqual(resolve_anchor(top, "before-block", "p1"), 1)
        self.assertEqual(resolve_anchor(top, "after-block", "p1"), 2)
        self.assertEqual(resolve_anchor(top, "append"), 2)

    def test_duplicate_or_missing_anchor_is_rejected(self):
        duplicate = [heading("a", "参考文档"), heading("b", "参考文档")]
        with self.assertRaisesRegex(RuntimeError, "命中 2 个"):
            resolve_anchor(duplicate, "after-heading", "参考文档")
        with self.assertRaisesRegex(RuntimeError, "命中 0 个"):
            resolve_anchor([], "before-block", "missing")

    def test_section_append_stops_before_peer_heading_and_skips_empty_tail(self):
        top = [
            heading("h1", "参考文档", 2),
            {"id": "p1", "type": "paragraph", "content": [{"type": "text", "content": "A"}]},
            {"id": "empty", "type": "paragraph", "content": []},
            heading("h2", "附录", 2),
        ]
        self.assertEqual(section_append_index(top, "参考文档"), 2)

    def test_section_append_does_not_depend_on_trailing_empty_paragraph(self):
        top = [heading("h1", "参考文档", 2), {"id": "p1", "type": "paragraph", "content": []}]
        self.assertEqual(section_append_index(top, "参考文档"), 1)
        self.assertEqual(section_append_index(top[:1], "参考文档"), 1)

    def test_canonical_link_id_ignores_domain_query_and_fragment(self):
        self.assertEqual(canonical_link_id("https://365.kdocs.cn/l/abc123"), "abc123")
        self.assertEqual(canonical_link_id("https://www.kdocs.cn/l/abc123?x=1#y"), "abc123")
        self.assertIsNone(canonical_link_id("https://365.kdocs.cn/doc/abc123"))

    def test_old_blocks_must_be_exact_after_removing_inserted_ids(self):
        before = [{"id": "a", "type": "paragraph", "content": []}]
        inserted = {"id": "new", "type": "paragraph", "content": []}
        ensure_old_blocks_preserved(before, [inserted, before[0]], {"new"})
        with self.assertRaisesRegex(RuntimeError, "原有顶层 blocks"):
            ensure_old_blocks_preserved(before, [inserted], {"new"})
        with self.assertRaisesRegex(RuntimeError, "缺少 id"):
            ensure_old_blocks_preserved(before, [before[0]], {None})

    def test_recursive_collectors_see_nested_native_nodes(self):
        value = {
            "type": "paragraph",
            "content": [
                {"type": "text", "content": "前缀"},
                {"type": "picture", "attrs": {"sourceKey": "att-1"}},
                {"type": "WPSDocument", "attrs": {"wpsDocumentId": "42"}},
            ],
        }
        self.assertEqual(collect_text(value), "前缀")
        self.assertEqual(picture_source_keys(value), {"att-1"})
        self.assertEqual(wps_document_refs(value), [{"wpsDocumentId": "42"}])


class NativeReferenceTest(unittest.TestCase):
    def test_reference_block_uses_native_wps_document_shape(self):
        item = {
            "category": "评测",
            "description": "线上回归",
            "document_id": "12345",
            "url": "https://365.kdocs.cn/l/abc",
            "name": "VLA 评测",
        }
        block = reference_block(item)
        self.assertEqual(block["type"], "paragraph")
        attrs = wps_document_refs(block)[0]
        self.assertEqual(attrs, {
            "version": 1,
            "wpsDocumentId": "12345",
            "wpsDocumentLink": "https://365.kdocs.cn/l/abc",
            "wpsDocumentName": "VLA 评测",
            "wpsDocumentType": "otl",
        })
        self.assertEqual(collect_text(block), "【评测】 — 线上回归")

    def test_reference_identity_normalizes_link_and_document_id(self):
        identity = reference_identity({
            "wpsDocumentLink": "https://www.kdocs.cn/l/abc?from=share",
            "wpsDocumentId": 12345,
        })
        self.assertEqual(identity, ("abc", "12345"))


if __name__ == "__main__":
    unittest.main()
