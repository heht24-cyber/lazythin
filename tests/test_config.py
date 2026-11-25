import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lazythin.config import ConfigError, find_config, parse_gui

DATA = ROOT / "tests" / "data"


class TestParseGui(unittest.TestCase):
    def test_plain(self):
        gui = parse_gui(DATA / "config.xml")
        self.assertEqual(gui.base_url, "http://127.0.0.1:8384")
        self.assertEqual(gui.api_key, "testkey123")

    def test_tls(self):
        gui = parse_gui(DATA / "config-tls.xml")
        self.assertEqual(gui.base_url, "https://127.0.0.1:8384")

    def test_no_apikey_raises(self):
        with self.assertRaises(ConfigError):
            parse_gui(DATA / "config-nokey.xml")


class TestFindConfig(unittest.TestCase):
    def test_explicit_ok(self):
        p = find_config(str(DATA / "config.xml"))
        self.assertEqual(p.name, "config.xml")

    def test_explicit_missing(self):
        with self.assertRaises(ConfigError):
            find_config(str(DATA / "nope.xml"))


if __name__ == "__main__":
    unittest.main()
