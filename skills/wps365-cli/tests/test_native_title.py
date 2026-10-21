"""Native-title readback is a completion gate for every creation workflow."""
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import _airpage_common as common
import airpage_copy
import airpage_publish
import airpage_put


def title_response(value, block_id="title"):
    return {"code": 0, "data": {"block": {"title": {
        "block_id": block_id,
        "elements": [{"text": {"attributes": {"content": part}}} for part in value],
    }}}}


class NativeTitleTest(unittest.TestCase):
    def test_explicit_name_keeps_numbering_and_only_removes_terminal_extension(self):
        self.assertEqual(common.document_title("00.报告.otl"), "00.报告")
        self.assertEqual(common.document_title("00.报告(1).otl"), "00.报告(1)")
        self.assertEqual(common.document_title("00.报告.otl补充.otl"), "00.报告.otl补充")

    def test_readback_concatenates_runs_exactly_and_updates_only_title(self):
        call = Mock(side_effect=[{"code": 0}, title_response(["00.", "报告"])])
        self.assertEqual(common.set_native_title("new-file", "00.报告", cli_call=call), "00.报告")
        update, read = [x.args for x in call.call_args_list]
        self.assertEqual(update[:4], ("airpage", "block", "update", "new-file"))
        self.assertEqual(update[update.index("--block-id") + 1], "title")
        self.assertEqual(read[:4], ("airpage", "block", "get", "new-file"))

    def test_success_response_without_saved_title_fails_closed(self):
        for response in (title_response([]), title_response(["正文H1"]),
                         title_response(["00.报告"], "body-heading"),
                         {"code": 0, "data": {}}, {"code": 403}):
            with self.subTest(response=response):
                call = Mock(side_effect=[{"code": 0}, response])
                with self.assertRaisesRegex(RuntimeError, "file_id=new-file"):
                    common.set_native_title("new-file", "00.报告", cli_call=call)

    def test_update_business_error_never_reads_or_retries(self):
        call = Mock(return_value={"code": 403, "msg": "denied"})
        with self.assertRaises(RuntimeError):
            common.set_native_title("new-file", "标题", cli_call=call)
        self.assertEqual(call.call_count, 1)

    def test_blank_or_multiline_title_has_no_side_effects(self):
        for value in ("", " ", "标题\n正文", "标题\r正文"):
            call = Mock()
            with self.subTest(value=value), self.assertRaises(ValueError):
                common.set_native_title("new-file", value, cli_call=call)
            call.assert_not_called()

    def test_put_cli_rejects_nonzero_business_code_even_with_exit_zero(self):
        response = subprocess.CompletedProcess([], 0, '{"code":403,"msg":"denied"}', "")
        with patch.object(airpage_put.subprocess, "run", return_value=response):
            with self.assertRaises(SystemExit):
                airpage_put.cli("api", "post", "/create")


class FakeCloud:
    """Stateful API fake: filenames/H1 exist even when native-title persistence fails."""
    def __init__(self, drop_title=False):
        self.name = "00.显式标题(1).otl"
        self.native_title = ""
        self.drop_title = drop_title
        self.created = False
        self.deleted = False
        self.body = []
        self.title_updates = 0
        self.source = [{"type": "title", "content": []}, {
            "type": "paragraph", "content": [{"type": "text", "content": "正文"}],
        }]

    def metadata(self):
        return {"id": "new-file", "name": self.name, "link_url": "https://example.test/new"}

    def read_top(self, fid):
        top = self.source if fid == "source" else [
            {"type": "title", "content": []}, {"type": "paragraph", "content": []},
        ] + self.body
        return copy.deepcopy({"blocks": [{"type": "doc", "content": top}]}), copy.deepcopy(top)

    def cli(self, *args):
        if args[:3] == ("api", "post", "/v7/airpage/files"):
            self.created = True
            return {"code": 0, "data": self.metadata()}
        if args[:3] == ("airpage", "block", "update"):
            self.title_updates += 1
            if not self.drop_title:
                self.native_title = args[args.index("--content") + 1]
            return {"code": 0}
        if args[:3] == ("airpage", "block", "get"):
            return title_response([self.native_title])
        if args[:3] == ("drive", "file-path", "get"):
            return {"code": 0, "data": {"paths": [{"name": "测试目录"}, {"name": self.name}]}}
        if args[:3] == ("drive", "file", "delete"):
            self.deleted = True
            return {"code": 0}
        if args[:3] == ("drive", "file", "get"):
            return {"code": 0, "data": {"id": "source", "name": "源文档.otl"}}
        if args[:2] == ("api", "post"):
            route = args[2]
            if route.endswith("/blocks/convert"):
                return {"code": 0, "data": {"result": common.b64({"blocks": self.source[1:]})}}
            if route.endswith("/blocks/create"):
                request = json.loads(args[args.index("--data") + 1])
                self.body.extend(common.unb64(request["arg"])["content"])
                return {"code": 0, "data": {"result": common.b64({})}}
            if route.endswith("/blocks"):
                return {"code": 0, "data": {"result": common.b64(self.read_top("new-file")[0])}}
            if route.endswith("/export_to_json"):
                return {"code": 0, "data": {"attachment_list": []}}
        raise AssertionError(f"unexpected API call: {args}")


class CreationTitleGateTest(unittest.TestCase):
    def run_creation(self, module, cloud):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            md = Path(directory) / "report.md"
            md.write_text("# 不应覆盖显式标题的正文H1\n\n正文\n")
            if module is airpage_copy:
                argv = ["copy", "drive", "source", "drive", "folder", "--apply",
                        "--name", "00.显式标题.otl", "--on-name-conflict", "rename"]
                stack.enter_context(patch.object(module, "read_top", side_effect=cloud.read_top))
                stack.enter_context(patch.object(module, "cloud_path", return_value="测试目录"))
                stack.enter_context(patch.object(module, "list_folder", side_effect=lambda *a: [cloud.metadata()] if cloud.created else []))
                stack.enter_context(patch.object(module, "export_document", return_value={"attachment_list": []}))
                stack.enter_context(patch.object(module, "create_blocks", side_effect=lambda fid, index, blocks: cloud.body.extend(blocks)))
            else:
                argv = ["create", "folder", "00.显式标题.otl", str(md), "--drive", "drive"]
            stack.enter_context(patch.object(module, "cli", side_effect=cloud.cli))
            stack.enter_context(patch.object(sys, "argv", argv))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            module.main()

    def test_all_entrypoints_fill_actual_filename_title_and_preserve_body(self):
        for module in (airpage_put, airpage_publish, airpage_copy):
            with self.subTest(module=module.__name__):
                cloud = FakeCloud()
                original_source = copy.deepcopy(cloud.source)
                self.run_creation(module, cloud)
                self.assertEqual(cloud.native_title, "00.显式标题(1)")
                self.assertEqual(cloud.title_updates, 1)
                self.assertTrue(cloud.body)
                self.assertEqual(cloud.source, original_source)
                self.assertFalse(cloud.deleted)

    def test_no_entrypoint_reports_completion_when_readback_is_empty(self):
        for module in (airpage_put, airpage_publish, airpage_copy):
            with self.subTest(module=module.__name__):
                cloud = FakeCloud(drop_title=True)
                with self.assertRaises((RuntimeError, SystemExit)):
                    self.run_creation(module, cloud)
                self.assertTrue(cloud.created)
                self.assertEqual(cloud.title_updates, 1)
                self.assertEqual(cloud.deleted, module is not airpage_put)

    def test_put_cli_exit_preserves_repair_link_for_the_created_document(self):
        cloud = FakeCloud()
        original = cloud.cli
        def fail_title(*args):
            if args[:3] == ("airpage", "block", "update"):
                raise SystemExit("title update denied")
            return original(*args)
        cloud.cli = fail_title
        with self.assertRaises(SystemExit) as failure:
            self.run_creation(airpage_put, cloud)
        self.assertIn("https://example.test/new", str(failure.exception))
        self.assertTrue(cloud.created)
        self.assertFalse(cloud.deleted)


if __name__ == "__main__":
    unittest.main()
