import json
import tempfile
import unittest
from pathlib import Path
from mega_checker.config import load_config

class ConfigTests(unittest.TestCase):
    def test_defaults_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "config.json"
            cfg = load_config(p)
            self.assertTrue(p.exists())
            self.assertEqual(cfg["workers"], 5)
            self.assertTrue(Path(cfg["database"]).is_absolute())
    def test_values_are_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "config.json"
            p.write_text(json.dumps({"workers": 100, "dns_timeout_seconds": 90}), encoding="utf-8")
            cfg = load_config(p)
            self.assertEqual(cfg["workers"], 32)
            self.assertEqual(cfg["dns_timeout_seconds"], 15.0)
    def test_invalid_log_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "config.json"
            p.write_text(json.dumps({"log_level": "LOUD"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(p)

if __name__ == "__main__":
    unittest.main()
