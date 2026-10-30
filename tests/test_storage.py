import tempfile
import unittest
from pathlib import Path
from mega_checker.storage import Store
from mega_checker.validation import validate_email

class StoreTests(unittest.TestCase):
    def test_roundtrip_stats_export_backup_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = Store(base / "db.sqlite")
            result = validate_email("User@example.com")
            result.checked_at = "2026-10-30T00:00:00+00:00"
            store.save_result(result)
            loaded = store.get_result("User@example.com")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.syntax_status, "valid")
            self.assertEqual(store.stats()["total"], 1)
            store.start_job("j1", "test", ["one@example.com", "two@example.com"])
            self.assertEqual(len(store.pending_for_job("j1")), 2)
            store.job_done("j1", "one@example.com")
            self.assertEqual(store.pending_for_job("j1"), ["two@example.com"])
            self.assertEqual(store.export_csv(base / "out.csv"), 1)
            self.assertEqual(store.export_json(base / "out.json"), 1)
            backup = store.backup(base / "backups")
            self.assertTrue(backup.exists())
            store.close()

if __name__ == "__main__":
    unittest.main()
