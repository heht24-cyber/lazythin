import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake import FakeClient
from lazythin.model import (DeviceInfo, FolderInfo, Snapshot, SystemInfo,
                            build_snapshot, snapshot_json)


class TestBuildSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = build_snapshot(FakeClient())

    def test_system(self):
        self.assertTrue(self.snap.system.my_id.startswith("B3B6IYX"))
        self.assertEqual(self.snap.system.version, "v2.1.7")
        self.assertEqual(self.snap.system.codename, "Hafnium Hornet")
        self.assertEqual(self.snap.system.uptime, 36166)

    def test_folder(self):
        f = self.snap.folders[0]
        self.assertEqual(f.id, "shared")
        self.assertEqual(f.label, "Shared")
        self.assertEqual(f.state, "idle")
        self.assertEqual(f.need_bytes, 22268)
        self.assertEqual(f.db_errors, 4)
        self.assertGreater(f.progress, 0.99)
        self.assertLess(f.progress, 1.0)

    def test_devices(self):
        # 空 deviceID 的坏条目被跳过,共 2 台
        self.assertEqual(len(self.snap.devices), 2)
        pc = next(d for d in self.snap.devices if d.name == "PC_HE")
        self.assertTrue(pc.connected)
        self.assertEqual(pc.client_version, "v2.1.3")
        self.assertEqual(pc.in_bytes, 1000)
        nix = next(d for d in self.snap.devices if d.name == "NixSurface")
        self.assertFalse(nix.connected)

    def test_snapshot_json(self):
        data = snapshot_json(self.snap)
        self.assertEqual(data["system"]["version"], "v2.1.7")
        self.assertEqual(data["folders"][0]["id"], "shared")
        self.assertTrue(data["devices"][0]["connected"])


class TestDefensive(unittest.TestCase):
    def test_apply_db_none(self):
        f = FolderInfo.from_config({"id": "x", "path": "p"})
        f.apply_db(None)
        self.assertEqual(f.state, "")
        self.assertEqual(f.progress, 1.0)

    def test_v1_device_shape(self):
        d = DeviceInfo.from_config({"id": "V1DEV1", "name": "old"})
        self.assertEqual(d.id, "V1DEV1")

    def test_system_bad_version(self):
        s = SystemInfo.from_json({"myID": "a"}, None, None)
        self.assertEqual(s.version, "")
        self.assertEqual(s.uptime, 0)


if __name__ == "__main__":
    unittest.main()
