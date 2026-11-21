import contextlib
import copy
import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

try:
    import airpage_insert_markdown as insert
    from airpage_publish import split_markdown
except SystemExit:
    insert = None


@unittest.skipIf(insert is None, "Pillow not installed")
class MarkdownSplitTest(unittest.TestCase):
    def test_does_not_split_at_headings_in_backtick_or_tilde_fences(self):
        for fence in ("````", "~~~~"):
            with self.subTest(fence=fence):
                code = f"## A\r\n{fence}text\r\n{fence} not a closer\r\n## Inside\r\nx\r\n{fence}  \r\n"
                tail = "## B\r\n" + "y" * 15
                self.assertEqual(split_markdown(code + tail, limit=len(code)), [code, tail])

    def test_oversized_fenced_code_fails_instead_of_splitting_at_internal_heading(self):
        markdown = "## A\n```text\n" + "x"*10000 + "\n## Inside\n" + "y"*10000 + "\n```\n"
        with self.assertRaisesRegex(RuntimeError, "exceeds"):
            split_markdown(markdown)


def paragraph(text):
    return {"type": "paragraph", "content": [{"type": "text", "content": text}]}


@unittest.skipIf(insert is None, "Pillow not installed")
class MarkdownInsertRetryTest(unittest.TestCase):
    def setUp(self):
        temp = self.enter_tempdir()
        self.markdown = temp / "section.md"
        self.markdown.write_text("First\n\nSecond\n", encoding="utf-8")
        self.state = temp / "state"
        self.top = [{**paragraph("Existing"), "id": "original"}]
        self.anchors = ["--append"]
        self.attachments = {}
        self.converted = [{"blocks": [paragraph("First")]}, {"blocks": [paragraph("Second")]}]
        self.writes = []
        self.fail_chunk = None
        self.fail_after_commit = False
        self.uploads = 0
        patches = patch.multiple(
            insert, cloud_path=lambda *_: "test.otl",
            read_top=lambda *_: ({"blocks": [{"content": copy.deepcopy(self.top)}]}, copy.deepcopy(self.top)),
            export_attachments=lambda *_: dict(self.attachments),
            convert_chunks=lambda *_: (copy.deepcopy(self.converted), 0),
            create_blocks=self.create_blocks,
        )
        patches.start()
        self.addCleanup(patches.stop)

    def enter_tempdir(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def create_blocks(self, file_id, index, blocks):
        self.writes.append([insert.collect_text(block) for block in blocks])
        fail = len(self.writes) == self.fail_chunk
        if not fail or self.fail_after_commit:
            self.top[index:index] = [
                {**copy.deepcopy(block), "id": f"new-{len(self.writes)}-{i}"}
                for i, block in enumerate(blocks)
            ]
        if fail:
            raise RuntimeError("second request timed out")

    def invoke(self, *flags):
        args = ["insert", "drive", "file", str(self.markdown), "--state-dir", str(self.state), *self.anchors, *flags]
        output = io.StringIO()
        with patch("sys.argv", args), contextlib.redirect_stdout(output):
            insert.main()
        return output.getvalue()

    def test_retry_writes_only_missing_chunks_and_completed_retry_is_a_noop(self):
        self.fail_chunk = 2
        with self.assertRaisesRegex(SystemExit, "续跑记录"):
            self.invoke("--apply")
        self.assertEqual([insert.collect_text(block) for block in self.top], ["Existing", "First"])
        self.assertIn('"mode": "resume"', self.invoke("--apply"))
        self.assertIn('"already_completed": true', self.invoke("--apply"))
        self.assertEqual(self.writes, [["First"], ["Second"], ["Second"]])
        self.assertEqual([insert.collect_text(block) for block in self.top], ["Existing", "First", "Second"])

    def test_lost_write_response_is_reconciled_before_retry_at_fixed_anchor(self):
        self.anchors = ["--before-block", "original"]
        self.fail_chunk = 1
        self.fail_after_commit = True
        with self.assertRaisesRegex(SystemExit, "续跑记录"):
            self.invoke("--apply")
        self.invoke("--apply")
        self.assertEqual(self.writes, [["First"], ["Second"]])
        self.assertEqual([insert.collect_text(block) for block in self.top], ["First", "Second", "Existing"])

    def test_retry_refuses_changed_document(self):
        self.fail_chunk = 2
        with self.assertRaises(SystemExit):
            self.invoke("--apply")
        self.top[0]["content"] = [{"type": "text", "content": "Concurrent edit"}]
        with self.assertRaisesRegex(SystemExit, "停止写入"):
            self.invoke("--apply")
        self.assertEqual(len(self.writes), 2)

    def test_lost_image_upload_response_reuses_verified_attachment(self):
        image_path = self.markdown.parent / "image.png"
        insert.Image.new("RGB", (5, 10)).save(image_path)
        self.converted[0] = {
            "blocks": [{"type": "picture", "id": "placeholder"}],
            "attachments": {"placeholder": [{"uri": "image.png"}]},
        }

        def upload(*_):
            self.uploads += 1
            self.attachments["confirmed-by-sha1"] = hashlib.sha1(image_path.read_bytes()).hexdigest()
            raise RuntimeError("upload response lost")

        with patch.object(insert, "upload_attachment", upload):
            with self.assertRaisesRegex(SystemExit, "续跑记录"):
                self.invoke("--apply")
            self.invoke("--apply")
        self.assertEqual(self.uploads, 1)
        self.assertEqual(self.top[1]["attrs"]["sourceKey"], "confirmed-by-sha1")
