import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake import FakeClient
from lazythin.cli import build_parser, main
from lazythin.model import build_snapshot
from lazythin.tui import render_dashboard


class TestCli(unittest.TestCase):
    def _run(self, fn, args, client=None):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = fn(args, client)
        return code, buf.getvalue()

    def test_status_json(self):
        args = build_parser().parse_args(["status", "--json"])
        code, out = self._run(lambda a, c: _status(a, c), args, client=FakeClient())
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["system"]["version"], "v2.1.7")
        self.assertEqual(data["folders"][0]["id"], "shared")
        self.assertTrue(data["devices"][0]["connected"])

    def test_status_text(self):
        args = build_parser().parse_args(["status"])
        code, out = self._run(lambda a, c: _status(a, c), args, client=FakeClient())
        self.assertEqual(code, 0)
        self.assertIn("Shared", out)
        self.assertIn("v2.1.7", out)
        self.assertIn("PC_HE", out)

    def test_once(self):
        args = build_parser().parse_args(["--once"])
        code, out = self._run(lambda a, c: _tui(a, c), args, client=FakeClient())
        self.assertEqual(code, 0)
        self.assertIn("文件夹", out)
        self.assertIn("设备", out)
        self.assertIn("NixSurface", out)

    def test_render_dashboard_details(self):
        snap = build_snapshot(FakeClient())
        text = render_dashboard(snap, None, use_color=False, spin="|")
        self.assertIn("lazythin", text)
        self.assertIn("syncthing v2.1.7 \"Hafnium Hornet\"", text)
        self.assertIn("已运行 10h 2m", text)
        self.assertIn("需 21.7 KiB", text)
        self.assertIn("错误 4", text)
        self.assertIn("离线", text)


class TestConflictsCli(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = Path(self._td.name)
        self.addCleanup(self._td.cleanup)
        (self.td / "file.txt").write_text("原内容", encoding="utf-8")
        (self.td / "file.sync-conflict-20260101-101010-ABC1234.txt").write_text("新内容", encoding="utf-8")
        (self.td / "clean.txt").write_text("x", encoding="utf-8")
        self.empty = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.empty, ignore_errors=True)

    def _run_main(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(argv)
        return code, buf.getvalue()

    def test_list_found(self):
        code, out = self._run_main(["conflicts", "--folder", str(self.td)])
        self.assertEqual(code, 1)
        self.assertIn("file.sync-conflict-20260101-101010-ABC1234.txt", out)
        self.assertIn("原文件 file.txt", out)

    def test_list_none(self):
        code, out = self._run_main(["conflicts", "--folder", str(self.empty)])
        self.assertEqual(code, 0)
        self.assertIn("没有发现冲突文件", out)

    def test_dry_run_plan(self):
        code, out = self._run_main(["conflicts", "--folder", str(self.td),
                                    "--resolve", "keep-orig"])
        self.assertEqual(code, 1)
        self.assertIn("[计划]", out)
        self.assertTrue((self.td / "file.sync-conflict-20260101-101010-ABC1234.txt").exists())

    def test_resolve_yes(self):
        code, out = self._run_main(["conflicts", "--folder", str(self.td),
                                    "--resolve", "keep-orig", "--yes"])
        self.assertEqual(code, 0)
        self.assertIn("[完成]", out)
        self.assertTrue((self.td / "file.sync-conflict-20260101-101010-ABC1234.txt.lazythin-bak").exists())
        self.assertEqual((self.td / "file.txt").read_text(encoding="utf-8"), "原内容")

    def test_diff(self):
        code, out = self._run_main(["conflicts", "--diff",
                                    str(self.td / "file.sync-conflict-20260101-101010-ABC1234.txt")])
        self.assertEqual(code, 0)
        self.assertIn("+新内容", out)

    def test_diff_missing(self):
        code, out = self._run_main(["conflicts", "--diff", str(self.td / "nope.txt")])
        self.assertEqual(code, 2)

    def test_version(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit) as cm:
                main(["--version"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("lazythin", buf.getvalue())


# 注入 FakeClient 的两个内部入口(避免单测碰真实网络)
from lazythin.cli import _cmd_status as _status, _cmd_tui as _tui  # noqa: E402

if __name__ == "__main__":
    unittest.main()
