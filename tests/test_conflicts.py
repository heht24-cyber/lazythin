import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lazythin.conflicts import (Conflict, parse_conflict, plan_resolve, resolve,
                                scan, unified_diff)


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = Path(self._td.name)
        self.addCleanup(self._td.cleanup)

    def mk(self, name: str, content: str = "x") -> Path:
        p = self.td / name
        p.write_text(content, encoding="utf-8")
        return p


class TestScan(Base):
    def test_scan_all_conventions(self):
        # 扩展名在尾部的官方风格
        self.mk("file.txt", "orig")
        self.mk("file.sync-conflict-20260101-101010-ABC1234.txt", "conflict")
        # 标记在尾部的旧风格
        self.mk("memo.md", "orig")
        self.mk("memo.md.sync-conflict-20260101-101010-DEV12345", "conflict")
        # 无扩展名原文件
        self.mk("plain", "orig")
        self.mk("plain.sync-conflict-20260101-101010-XYZ98765", "conflict")
        # 子目录
        sub = self.td / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("orig", encoding="utf-8")
        (sub / "deep.sync-conflict-20260101-111111-QQQ1111.txt").write_text("c", encoding="utf-8")
        # 应被跳过的目录
        stv = self.td / ".stversions"
        stv.mkdir()
        (stv / "old.sync-conflict-20200101-000000-AAA1111.txt").write_text("x", encoding="utf-8")

        found = scan(self.td)
        self.assertEqual(len(found), 4)

    def test_parse_originals(self):
        c1 = parse_conflict(self.mk("file.sync-conflict-20260101-101010-ABC1234.txt"))
        self.assertEqual(c1.original.name, "file.txt")
        self.assertEqual(c1.stamp, "20260101-101010")
        self.assertEqual(c1.device, "ABC1234")
        c2 = parse_conflict(self.mk("memo.md.sync-conflict-20260101-101010-DEV12345"))
        self.assertEqual(c2.original.name, "memo.md")
        c3 = parse_conflict(self.mk("plain.sync-conflict-20260101-101010-XYZ98765"))
        self.assertEqual(c3.original.name, "plain")
        self.assertEqual(c3.original, self.td / "plain")

    def test_parse_unmatchable(self):
        c = parse_conflict(self.mk("weird.sync-conflict-notastamp"))
        self.assertIsNone(c.original)


class TestResolve(Base):
    def _conflict(self):
        self.mk("file.txt", "原内容")
        c = self.mk("file.sync-conflict-20260101-101010-ABC1234.txt", "新内容")
        return parse_conflict(c)

    def test_keep_orig_backup(self):
        c = self._conflict()
        acts = resolve(c, "keep-orig", backup=True)
        self.assertFalse(c.path.exists())
        self.assertTrue((self.td / "file.sync-conflict-20260101-101010-ABC1234.txt.lazythin-bak").exists())
        self.assertEqual((self.td / "file.txt").read_text(encoding="utf-8"), "原内容")
        self.assertIn("改名", acts[0])

    def test_keep_orig_delete(self):
        c = self._conflict()
        resolve(c, "keep-orig", backup=False)
        self.assertFalse(c.path.exists())
        self.assertEqual((self.td / "file.txt").read_text(encoding="utf-8"), "原内容")

    def test_keep_conflict(self):
        c = self._conflict()
        resolve(c, "keep-conflict", backup=True)
        self.assertEqual((self.td / "file.txt").read_text(encoding="utf-8"), "新内容")
        self.assertTrue((self.td / "file.txt.lazythin-bak").exists())
        self.assertFalse(c.path.exists())

    def test_keep_both(self):
        c = self._conflict()
        resolve(c, "keep-both", backup=True)
        new = self.td / "file (conflict 20260101-101010).txt"
        self.assertTrue(new.exists())
        self.assertEqual(new.read_text(encoding="utf-8"), "新内容")
        self.assertEqual((self.td / "file.txt").read_text(encoding="utf-8"), "原内容")
        self.assertFalse(c.path.exists())

    def test_plan_is_dry_run(self):
        c = self._conflict()
        acts = plan_resolve(c, "keep-orig", backup=True)
        self.assertTrue(acts)
        self.assertTrue(c.path.exists())  # 没动文件
        self.assertEqual((self.td / "file.txt").read_text(encoding="utf-8"), "原内容")

    def test_bad_mode_raises(self):
        c = self._conflict()
        with self.assertRaises(ValueError):
            plan_resolve(c, "nuke")

    def test_unresolvable_skipped(self):
        c = parse_conflict(self.mk("weird.sync-conflict-oops"))
        self.assertIn("跳过", resolve(c, "keep-orig")[0])


class TestDiff(Base):
    def test_unified_diff(self):
        self.mk("file.txt", "第一行\n旧第二行\n第三行\n")
        c = parse_conflict(self.mk("file.sync-conflict-20260101-101010-ABC1234.txt",
                                   "第一行\n新第二行\n第三行\n"))
        out = unified_diff(c)
        self.assertIn("-旧第二行", out)
        self.assertIn("+新第二行", out)
        self.assertIn("file.txt", out)

    def test_identical(self):
        self.mk("file.txt", "一样\n")
        c = parse_conflict(self.mk("file.sync-conflict-20260101-101010-ABC1234.txt", "一样\n"))
        self.assertIn("完全一致", unified_diff(c))

    def test_binary(self):
        (self.td / "file.bin").write_bytes(b"\x00\x01binary")
        c = parse_conflict(self.mk("file.sync-conflict-20260101-101010-ABC1234.bin"))
        (c.path).write_bytes(b"\x00\x02binary")
        self.assertIn("二进制", unified_diff(c))

    def test_missing_original(self):
        c = parse_conflict(self.mk("ghost.sync-conflict-20260101-101010-ABC1234.txt"))
        self.assertIn("找不到原文件", unified_diff(c))


if __name__ == "__main__":
    unittest.main()
