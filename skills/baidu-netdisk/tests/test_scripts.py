import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        self.trace = self.work / "trace"
        self.fake = self.work / "BaiduPCS-Go"
        self.fake.write_text(
            """#!/usr/bin/env bash
printf '%s\\0' "$@" > "$TRACE"
case "${1:-}" in
  who) echo '当前帐号 uid: 123456, 用户名: tester' ;;
  config)
    echo '  bduss                TOP_SECRET'
    echo '  proxy                http://user:password@example.test:8080'
    echo '  savedir              /data/media'
    ;;
  ls)
    echo '   0         3B  2026-10-25 10:00:00  a.bin'
    ;;
  meta) echo 'meta failed' >&2; exit 7 ;;
esac
""",
            encoding="utf-8",
        )
        self.fake.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update(BPCS_BIN=str(self.fake), TRACE=str(self.trace))

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, name, *args, env=None):
        path = SCRIPTS / name
        cmd = (["python3", str(path)] if path.suffix == ".py" else ["bash", str(path)]) + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, env=env or self.env)

    def test_bpcs_does_not_echo_credentials(self):
        p = self.run_script("bpcs.sh", "login", "-bduss=DO_NOT_PRINT")
        self.assertEqual(p.returncode, 3)
        self.assertNotIn("DO_NOT_PRINT", p.stdout + p.stderr)
        self.assertFalse(self.trace.exists())

    def test_bpcs_blocks_global_option_bypass_and_unknown_commands(self):
        p = self.run_script("bpcs.sh", "--verbose", "rm", "/x")
        self.assertEqual(p.returncode, 3)
        self.assertFalse(self.trace.exists())
        p = self.run_script("bpcs.sh", "run", "rm", "-rf", "/")
        self.assertEqual(p.returncode, 3)
        self.assertFalse(self.trace.exists())

    def test_bpcs_forwards_allowed_command_and_redacts_output(self):
        p = self.run_script("bpcs.sh", "ls", "/a path")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(self.trace.read_bytes().split(b"\0")[:2], [b"ls", b"/a path"])

        p = self.run_script("bpcs.sh", "who")
        self.assertEqual(p.returncode, 0)
        self.assertIn("uid: <uid>", p.stdout)
        self.assertNotIn("123456", p.stdout)

        p = self.run_script("bpcs.sh", "config")
        self.assertEqual(p.returncode, 0)
        self.assertIn("savedir", p.stdout)
        self.assertNotIn("TOP_SECRET", p.stdout)
        self.assertNotIn("password", p.stdout)

    def test_bpcs_requires_explicit_opt_in_for_overwriting_upload(self):
        p = self.run_script("bpcs.sh", "upload", "--policy", "rsync", "/local", "/remote")
        self.assertEqual(p.returncode, 3)
        self.assertFalse(self.trace.exists())
        allowed = self.env.copy()
        allowed["BPCS_ALLOW_OVERWRITE"] = "1"
        p = self.run_script("bpcs.sh", "upload", "--policy=overwrite", "/local", "/remote", env=allowed)
        self.assertEqual(p.returncode, 0)

    def test_remote_rejects_host_and_script_injection_before_ssh(self):
        p = self.run_script("remote.sh", "-oProxyCommand=evil", "bpcs.sh", "who")
        self.assertEqual(p.returncode, 2)
        p = self.run_script("remote.sh", "tb", "../outside.sh")
        self.assertEqual(p.returncode, 2)

    def test_download_rejects_injected_numeric_and_session_values(self):
        args = ["--session", "bad/name", "--saveto", "/tmp/x", "--log", "/tmp/x.log", "/remote"]
        self.assertEqual(self.run_script("download.sh", *args).returncode, 2)
        args = ["--session", "ok", "--saveto", "/tmp/x", "--log", "/tmp/x.log", "-p", "0;id", "/remote"]
        self.assertEqual(self.run_script("download.sh", *args).returncode, 2)

    @staticmethod
    def record(remote, name, data, remote_md5):
        return (
            f"文件路径 {remote}/{name}\n"
            f"文件名称 {name}\n"
            f"文件大小 {len(data)}, {len(data)}B\n"
            f"md5 (可能不正确) {remote_md5}\n"
        )

    def test_verify_single_md5_mismatch_is_inconclusive(self):
        local = self.work / "single"
        local.mkdir()
        data = b"abc"
        (local / "a.bin").write_bytes(data)
        log = self.work / "single.log"
        log.write_text(self.record("/r", "a.bin", data, "0" * 32), encoding="utf-8")
        p = self.run_script("verify.py", "--remote", "/r", "--local", str(local), "--log", str(log), "--write-md5sums")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("INCONCLUSIVE_SINGLE_MD5", p.stdout)
        self.assertFalse((local / "MD5SUMS.txt").exists())

    def test_verify_multi_file_remote_md5_pattern_can_pass(self):
        local = self.work / "multi"
        local.mkdir()
        records = []
        for name, data in (("a.bin", b"abc"), ("b.bin", b"defg")):
            (local / name).write_bytes(data)
            records.append(self.record("/r", name, data, "0" * 32))
        log = self.work / "multi.log"
        log.write_text("".join(records), encoding="utf-8")
        p = self.run_script("verify.py", "--remote", "/r", "--local", str(local), "--log", str(log), "--write-md5sums")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("OK_REMOTE_MD5_UNUSABLE", p.stdout)
        sums = (local / "MD5SUMS.txt").read_text(encoding="utf-8")
        self.assertIn(hashlib.md5(b"abc").hexdigest(), sums)
        self.assertIn(hashlib.md5(b"defg").hexdigest(), sums)

    def test_verify_single_file_can_pass_against_second_download(self):
        local = self.work / "first"
        peer = self.work / "second"
        local.mkdir(); peer.mkdir()
        data = b"same download"
        (local / "a.bin").write_bytes(data)
        (peer / "a.bin").write_bytes(data)
        log = self.work / "peer.log"
        log.write_text(self.record("/r", "a.bin", data, "0" * 32), encoding="utf-8")
        p = self.run_script(
            "verify.py", "--remote", "/r", "--local", str(local), "--log", str(log),
            "--peer", str(peer), "--write-md5sums",
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("OK_REDOWNLOAD_MATCH", p.stdout)
        self.assertTrue((local / "MD5SUMS.txt").exists())

    def test_diff_reports_meta_failure(self):
        local = self.work / "local"
        local.mkdir()
        (local / "a.bin").write_bytes(b"abc")
        p = self.run_script("diff.py", "/r", str(local), "--sizes", "--json")
        self.assertEqual(p.returncode, 1)
        result = json.loads(p.stdout)
        self.assertEqual(result["meta_errors"][0]["file"], "a.bin")

    def test_diff_preserves_remote_root_path(self):
        local = self.work / "root"
        local.mkdir()
        p = self.run_script("diff.py", "/", str(local), "--json")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(self.trace.read_bytes().split(b"\0")[:2], [b"ls", b"/"])

    def test_verify_preserves_remote_root_prefix(self):
        local = self.work / "root-verify"
        local.mkdir()
        data = b"root file"
        (local / "a.bin").write_bytes(data)
        log = self.work / "root.log"
        log.write_text(self.record("", "a.bin", data, hashlib.md5(data).hexdigest()), encoding="utf-8")
        p = self.run_script("verify.py", "--remote", "/", "--local", str(local), "--log", str(log), "--json")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(json.loads(p.stdout)["verdict"], "OK")

    def test_status_uses_only_latest_run(self):
        log = self.work / "status.log"
        log.write_text(
            "RUN_START old 2026-10-25 09:00:00 saveto=/tmp\n"
            "RUN_DONE old failed=0 2026-10-25 09:01:00\n"
            "RUN_START new 2026-10-25 10:00:00 saveto=/tmp\n",
            encoding="utf-8",
        )
        p = self.run_script("status.py", "--log", str(log), "--saveto", str(self.work), "--json")
        self.assertEqual(p.returncode, 0)
        result = json.loads(p.stdout)
        self.assertEqual(result["run"], "new")
        self.assertFalse(result["finished"])


if __name__ == "__main__":
    unittest.main()
