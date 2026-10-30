import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from mega_checker.pipeline import read_emails, run_batch
from mega_checker.storage import Store

class PipelineTests(unittest.TestCase):
    def test_resume_preserves_local_part_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = Store(base / "db.sqlite")
            from unittest.mock import patch
            dns_stub = {
                "dns_status": "mocked", "dns_provider": "test",
                "mx_status": "unknown", "mx_hosts": [], "address_fallback": False,
                "spf_status": "unknown", "spf_record": "",
                "dmarc_status": "unknown", "dmarc_record": "",
                "dkim_status": "unknown", "dkim_selectors_found": [],
            }
            with patch("mega_checker.pipeline.DomainInspector.inspect", return_value=dns_stub):
                _, first = run_batch(["User@example.com"], store, job_id="case-job")
                _, second = run_batch(["User@example.com"], store, job_id="case-job", resume=True)
            self.assertEqual(first["processed_now"], 1)
            self.assertEqual(second["processed_now"], 0)
            store.close()
    def test_read_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "emails.txt"
            p.write_text("# comment\nA@example.com\nb@example.com, A@example.com\n", encoding="utf-8")
            self.assertEqual(read_emails(p), ["A@example.com", "b@example.com"])
    def test_offline_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            p = base / "in.txt"
            p.write_text("good@example.com\nbad@@example.com\n", encoding="utf-8")
            store = Store(base / "db.sqlite")
            dns_stub = {
                "dns_status": "mocked", "dns_provider": "test",
                "mx_status": "unknown", "mx_hosts": [], "address_fallback": False,
                "spf_status": "unknown", "spf_record": "",
                "dmarc_status": "unknown", "dmarc_record": "",
                "dkim_status": "unknown", "dkim_selectors_found": [],
            }
            with patch("mega_checker.pipeline.DomainInspector.inspect", return_value=dns_stub):
                results, summary = run_batch(read_emails(p), store, workers=2, job_id="qa")
            self.assertEqual(summary["processed_now"], 2)
            self.assertEqual(len(results), 2)
            self.assertEqual(store.stats()["total"], 2)
            store.close()

if __name__ == "__main__":
    unittest.main()
