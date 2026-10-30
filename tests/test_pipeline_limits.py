from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mega_checker.pipeline import run_batch
from mega_checker.storage import Store


class PipelineLimitTests(unittest.TestCase):
    def test_worker_and_inflight_limits_are_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "pipeline.db")
            try:
                emails = [f"not-an-email-{i}" for i in range(50)]
                _, summary = run_batch(emails, store, workers=999, job_id="bounded")
                self.assertEqual(summary["worker_count"], 32)
                self.assertEqual(summary["max_in_flight"], 64)
                self.assertEqual(summary["processed_now"], 50)
                self.assertEqual(summary["errors"], 0)
            finally:
                store.close()

    def test_worker_minimum_is_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "pipeline.db")
            try:
                _, summary = run_batch(["invalid"], store, workers=0, job_id="minimum")
                self.assertEqual(summary["worker_count"], 1)
                self.assertEqual(summary["max_in_flight"], 2)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
