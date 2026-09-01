#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from airpage_copy import (  # noqa: E402
    canonicalize, chunk_blocks, strip_for_copy, validate_copied_blocks,
    validate_source_attachments,
)


class CopyTransformTest(unittest.TestCase):
    def test_recursive_ids_and_range_marks_are_removed_and_picture_is_remapped(self):
        source = [{
            "id": "p1",
            "type": "paragraph",
            "content": [
                {"id": "t1", "type": "text", "content": "正文"},
                {"id": "r1", "type": "rangeMarkBegin", "attrs": {"comment": "c1"}},
                {"id": "pic", "type": "picture", "attrs": {"sourceKey": "old", "width": 10}},
                {"id": "r2", "type": "rangeMarkEnd", "attrs": {"comment": "c1"}},
            ],
        }]
        copied = strip_for_copy(source, {"old": "new"})
        self.assertEqual(copied, [{
            "type": "paragraph",
            "content": [
                {"type": "text", "content": "正文"},
                {"type": "picture", "attrs": {"sourceKey": "new", "width": 10}},
            ],
        }])

    def test_service_added_list_style_default_is_canonicalized(self):
        source = {"attrs": {"listAttrs": {"type": 1, "level": 0}}}
        target = {"attrs": {"listAttrs": {"type": 1, "level": 0, "styleFormat": 1}}}
        self.assertEqual(canonicalize(source), canonicalize(target))

    def test_chunking_keeps_an_oversized_native_table_intact(self):
        first = {"type": "paragraph", "content": [{"type": "text", "content": "A" * 100}]}
        table = {"type": "table", "content": [{"type": "text", "content": "B" * 400}]}
        last = {"type": "paragraph", "content": [{"type": "text", "content": "C" * 100}]}
        chunks = chunk_blocks([first, table, last], limit=250)
        self.assertEqual([block for chunk in chunks for block in chunk], [first, table, last])
        self.assertIn([table], chunks)

    def test_validation_accepts_only_canonically_equal_native_structure(self):
        expected = [{
            "type": "paragraph",
            "attrs": {"listAttrs": {"type": 1}},
            "content": [{"type": "text", "content": "A", "attrs": {"bold": True}}],
        }]
        actual = [{
            "id": "new",
            "type": "paragraph",
            "attrs": {"listAttrs": {"type": 1, "styleFormat": 1}},
            "content": [{"id": "text", "type": "text", "content": "A", "attrs": {"bold": True}}],
        }]
        checks = validate_copied_blocks(expected, actual)
        self.assertTrue(all(checks.values()))
        actual[0]["content"][0]["attrs"]["bold"] = False
        with self.assertRaisesRegex(RuntimeError, "blocks 验收失败"):
            validate_copied_blocks(expected, actual)


class CopyAttachmentTest(unittest.TestCase):
    def test_source_picture_and_export_attachment_sets_must_close(self):
        body = [{"type": "picture", "attrs": {"sourceKey": "att-1"}}]
        exported = {"attachment_list": [{"id": "att-1", "download_url": "https://example.test/a"}]}
        self.assertEqual(set(validate_source_attachments(body, exported)), {"att-1"})
        exported["attachment_list"].append({"id": "orphan"})
        with self.assertRaisesRegex(RuntimeError, "附件未闭合"):
            validate_source_attachments(body, exported)


if __name__ == "__main__":
    unittest.main()
