#!/usr/bin/env python3
"""守住公共模块的共享约定。

历史问题：`upload_attachment` 曾在 `_airpage_common.py` 和 `airpage_publish.py`
里各有一份**同名但参数顺序相反**的实现（`(file_id, path, upload_name)` vs
`(file_id, upload_name, path)`）。当时两边互不 import 所以没出错，但只要有人
顺手改成从公共模块导入，参数就会静默错位——上传的文件名和内容对调，
且照样返回 `code:0`。这里把"只能有一份实现、且调用方按位置传对"钉死。
"""

import ast
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

# 只钉住"有多份实现就会错位"的那几个。`cli` 不在此列：
# airpage_put.py / drive_upload.py 故意用 sys.exit 做成独立可读的单文件示例，
# 与公共模块的 raise RuntimeError 语义不同，属于有意为之，不强行统一。
SHARED = {"upload_attachment", "response_header"}


def tree(name):
    return ast.parse((SCRIPTS / name).read_text(encoding="utf-8"))


def top_level_functions(name):
    return {n.name for n in tree(name).body if isinstance(n, ast.FunctionDef)}


def consumers():
    return [p.name for p in sorted(SCRIPTS.glob("*.py"))
            if p.name != "_airpage_common.py"]


class SharedHelperTest(unittest.TestCase):
    def test_shared_helpers_are_not_redefined_by_consumers(self):
        """没有脚本可以自己再定义一份同名助手。"""
        for name in consumers():
            clashes = top_level_functions(name) & SHARED
            self.assertEqual(
                clashes, set(),
                f"{name} 重复定义了公共助手 {sorted(clashes)}；"
                "请改为 from _airpage_common import ...，否则签名会各自漂移",
            )

    def test_upload_attachment_signature_is_stable(self):
        """参数顺序是 (file_id, path, upload_name)，改了就要同步所有调用方。"""
        fn = next(n for n in tree("_airpage_common.py").body
                  if isinstance(n, ast.FunctionDef) and n.name == "upload_attachment")
        self.assertEqual([a.arg for a in fn.args.args],
                         ["file_id", "path", "upload_name"])

    def test_every_call_passes_path_second(self):
        """位置调用的第 2 个实参必须是路径，不能是文件名。"""
        seen = 0
        for name in consumers():
            for node in ast.walk(tree(name)):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "upload_attachment"
                        and len(node.args) >= 2):
                    seen += 1
                    second = node.args[1]
                    # 第 2 个实参应是路径变量；f-string 形态的文件名是典型的错位写法
                    self.assertNotIsInstance(
                        second, ast.JoinedStr,
                        f"{name}: upload_attachment 第 2 个实参像文件名，"
                        "参数顺序应为 (file_id, path, upload_name)",
                    )
        self.assertGreater(seen, 0, "没找到任何 upload_attachment 位置调用，测试失效了")


if __name__ == "__main__":
    unittest.main()
