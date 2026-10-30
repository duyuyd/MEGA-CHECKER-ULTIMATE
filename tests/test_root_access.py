import unittest
from unittest.mock import patch
from mega_checker.root_access import root_status

class RootAccessTests(unittest.TestCase):
    def test_no_su_is_safe_report_not_root(self):
        with patch("mega_checker.root_access._su_path", return_value=None), \
             patch("mega_checker.root_access._local_device_facts", return_value={
                 "uid": "10234", "selinux": "Enforcing", "android_release": "14",
                 "android_sdk": "34", "manufacturer": "test", "model": "device",
                 "kernel": "test", "cpu_online": "4", "memory_total_kb": 1000,
                 "memory_available_kb": 500, "root_manager": "unknown", "thermal_raw": []
             }):
            report = root_status()
        self.assertFalse(report["root_granted"])
        self.assertFalse(report["su_available"])
        self.assertEqual(report["operations"], "read_only")

    def test_static_diagnostics_parse_root(self):
        class Fake:
            returncode = 0
            stdout = "UID=0\nSELINUX=Enforcing\nANDROID_RELEASE=14\nANDROID_SDK=34\nMANUFACTURER=TECNO\nMODEL=CK7n\nKERNEL=5.10.0\nCPU_ONLINE=0-7\nMEM_TOTAL_KB=8000000\nMEM_AVAILABLE_KB=4000000\nROOT_MANAGER=Magisk\nTHERMAL_RAW=39000\n"
        with patch("mega_checker.root_access._su_path", return_value="/system/bin/su"), patch("mega_checker.root_access._run_su", return_value=Fake()):
            report = root_status()
        self.assertTrue(report["root_granted"])
        self.assertEqual(report["root_manager"], "Magisk")
        self.assertEqual(report["memory_available_kb"], 4000000)
        self.assertEqual(report["thermal_raw"], ["39000"])

    def test_non_root_uid_not_marked_root(self):
        class Fake:
            returncode = 0
            stdout = "UID=2000\nSELINUX=Enforcing\n"
        with patch("mega_checker.root_access._su_path", return_value="/system/bin/su"), patch("mega_checker.root_access._run_su", return_value=Fake()):
            report = root_status()
        self.assertFalse(report["root_granted"])
        self.assertEqual(report["root_error"], "su_did_not_return_uid_0")


class DualAccessTests(unittest.TestCase):
    def test_no_root_file_access_does_not_call_su(self):
        import tempfile
        from pathlib import Path
        from mega_checker.root_access import open_dataset_input
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.txt"
            source.write_text("user@example.com\n", encoding="utf-8")
            with patch("mega_checker.root_access.open_root_file") as root_open:
                with open_dataset_input(source, "auto") as (stream, mode):
                    self.assertEqual(stream.read(), b"user@example.com\n")
                    self.assertEqual(mode, "noroot")
                root_open.assert_not_called()

    def test_noroot_mode_never_escalates(self):
        import tempfile
        from pathlib import Path
        from mega_checker.root_access import open_dataset_input
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.txt"
            source.write_text("user@example.com\n", encoding="utf-8")
            with patch("mega_checker.root_access.open_root_file") as root_open:
                with open_dataset_input(source, "noroot") as (stream, mode):
                    self.assertEqual(mode, "noroot")
                root_open.assert_not_called()

    def test_auto_uses_root_only_after_permission_denied(self):
        from io import BytesIO
        from pathlib import Path
        from contextlib import contextmanager
        from mega_checker.root_access import open_dataset_input
        @contextmanager
        def fake_root(path):
            yield BytesIO(b"root@example.com\n")
        with patch.object(Path, "open", side_effect=PermissionError("denied")), \
             patch("mega_checker.root_access.open_root_file", side_effect=fake_root) as root_open:
            with open_dataset_input("/protected/list.txt", "auto") as (stream, mode):
                self.assertEqual(stream.read(), b"root@example.com\n")
                self.assertEqual(mode, "root")
            root_open.assert_called_once()

    def test_root_status_without_su_keeps_noroot_diagnostics(self):
        with patch("mega_checker.root_access._su_path", return_value=None), \
             patch("mega_checker.root_access._local_device_facts", return_value={
                 "uid": "10234", "selinux": "Enforcing", "android_release": "14",
                 "android_sdk": "34", "manufacturer": "test", "model": "device",
                 "kernel": "test-kernel", "cpu_online": "8", "memory_total_kb": 1000,
                 "memory_available_kb": 500, "root_manager": "unknown", "thermal_raw": []
             }):
            report = root_status()
        self.assertEqual(report["access_mode"], "noroot")
        self.assertFalse(report["root_granted"])
        self.assertEqual(report["android_release"], "14")
        self.assertEqual(report["memory_available_kb"], 500)

    def test_invalid_access_mode_rejected(self):
        from mega_checker.root_access import open_dataset_input
        with self.assertRaises(ValueError):
            with open_dataset_input("/tmp/nope", "magic"):
                pass

    def test_declined_root_grant_keeps_noroot_report(self):
        from mega_checker.root_access import RootAccessError
        local = {
            "uid": "10234", "selinux": "Enforcing", "android_release": "14",
            "android_sdk": "34", "manufacturer": "test", "model": "device",
            "kernel": "test-kernel", "cpu_online": "8", "memory_total_kb": 1000,
            "memory_available_kb": 500, "root_manager": "Magisk", "thermal_raw": []
        }
        with patch("mega_checker.root_access._su_path", return_value="/system/bin/su"), \
             patch("mega_checker.root_access._local_device_facts", return_value=local), \
             patch("mega_checker.root_access._run_su", side_effect=RootAccessError("grant declined")):
            report = root_status()
        self.assertEqual(report["access_mode"], "noroot")
        self.assertFalse(report["root_granted"])
        self.assertIn("grant declined", report["root_error"])


if __name__ == "__main__":
    unittest.main()
