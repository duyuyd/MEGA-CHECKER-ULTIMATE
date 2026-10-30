from __future__ import annotations

import json
import stat
import tempfile
import unittest
from pathlib import Path

from mega_checker.dataset_audit import audit_dataset, write_report


class DatasetAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_combo_audit_counts_and_redacts_secret(self):
        source = self.root / "sample.txt"
        secret = "SuperSecret-NEVER-EXPORT"
        source.write_text(
            "# synthetic sample\n"
            "alice@gmail.com:" + secret + "\n"
            "alice@gmail.com:another-secret\n"
            "Bob@outlook.com|pw-two\n"
            "not-an-email:pw-three\n"
            "carol@example.com\n"
            "\n",
            encoding="utf-8",
        )
        report = audit_dataset(source)
        self.assertEqual(report["lines_total"], 7)
        self.assertEqual(report["records_parsed"], 5)
        self.assertEqual(report["credential_shaped_records"], 3)
        self.assertEqual(report["email_only_records"], 2)
        self.assertEqual(report["valid_email_records"], 4)
        self.assertEqual(report["invalid_email_records"], 1)
        self.assertEqual(report["duplicate_records"], 1)
        self.assertEqual(report["unique_valid_email_records"], 3)
        target = write_report(report, self.root / "report.json")
        rendered = target.read_text(encoding="utf-8")
        self.assertNotIn(secret, rendered)
        self.assertNotIn("another-secret", rendered)
        self.assertNotIn("pw-two", rendered)
        self.assertFalse(report["security"]["secret_values_persisted"])

    def test_email_mode_does_not_split_delimiters(self):
        source = self.root / "emails.txt"
        source.write_text("a@example.com\nb@example.com\na@example.com\n", encoding="utf-8")
        report = audit_dataset(source, mode="email")
        self.assertEqual(report["email_only_records"], 3)
        self.assertEqual(report["credential_shaped_records"], 0)
        self.assertEqual(report["duplicate_records"], 1)

    def test_large_line_is_counted_and_skipped(self):
        source = self.root / "large.txt"
        source.write_bytes(b"x" * 2048 + b"\na@example.com\n")
        report = audit_dataset(source, max_line_bytes=1024)
        self.assertEqual(report["oversized_lines"], 1)
        self.assertEqual(report["valid_email_records"], 1)

    def test_oversized_line_with_newline_inside_first_read_is_rejected(self):
        source = self.root / "newline-boundary.txt"
        source.write_bytes(b"x" * 1024 + b"\n" + b"a@example.com\n")
        report = audit_dataset(source, max_line_bytes=1024)
        self.assertEqual(report["oversized_lines"], 1)
        self.assertEqual(report["valid_email_records"], 1)

    def test_dedup_storage_uses_ephemeral_keyed_fingerprints(self):
        source = self.root / "privacy.txt"
        source.write_text("alice@example.com\nalice@example.com\n", encoding="utf-8")
        report = audit_dataset(source)
        self.assertEqual(report["duplicate_records"], 1)
        self.assertIn("HMAC-SHA256", report["security"]["temporary_dedup_storage"])
        self.assertIn("never persisted", report["security"]["temporary_dedup_storage"])

    def test_report_refuses_to_overwrite_source(self):
        source = self.root / "source.txt"
        original = "alice@example.com\n"
        source.write_text(original, encoding="utf-8")
        report = audit_dataset(source)
        with self.assertRaises(ValueError):
            write_report(report, source, source_path=source)
        self.assertEqual(source.read_text(encoding="utf-8"), original)

    def test_dedup_is_exact_across_sqlite_batch_boundaries(self):
        source = self.root / "batch-boundary.txt"
        first_batch = [f"user{i}@example.com\n" for i in range(2048)]
        # The first half fills the engine batch; the next half repeats every
        # address after the flush, proving dedup remains exact across batches.
        source.write_text("".join(first_batch + first_batch), encoding="utf-8")
        report = audit_dataset(source)
        self.assertEqual(report["records_parsed"], 4096)
        self.assertEqual(report["valid_email_records"], 4096)
        self.assertEqual(report["unique_valid_email_records"], 2048)
        self.assertEqual(report["duplicate_records"], 2048)

    def test_invalid_duplicates_are_counted_but_not_unique_valid(self):
        source = self.root / "invalid-duplicates.txt"
        source.write_text("bad-address\nbad-address\na@example.com\n", encoding="utf-8")
        report = audit_dataset(source)
        self.assertEqual(report["invalid_email_records"], 2)
        self.assertEqual(report["unique_parsed_identifiers"], 2)
        self.assertEqual(report["duplicate_records"], 1)
        self.assertEqual(report["unique_valid_email_records"], 1)

    def test_top_domains_are_exact_and_deterministic(self):
        source = self.root / "many-domains.txt"
        lines = []
        for index in range(30):
            domain = f"d{index}.example.com"
            lines.extend(f"user{n}@{domain}\n" for n in range(30 - index))
        source.write_text("".join(lines), encoding="utf-8")
        report = audit_dataset(source)
        top = report["top_domains"]
        self.assertEqual(len(top), 20)
        self.assertEqual(top[0], {"domain": "d0.example.com", "count": 30})
        self.assertEqual(top[-1], {"domain": "d19.example.com", "count": 11})

    def test_report_is_written_atomically_with_private_permissions(self):
        source = self.root / "source-private.txt"
        source.write_text("a@example.com\n", encoding="utf-8")
        report = audit_dataset(source)
        target = write_report(report, self.root / "nested" / "report.json", source_path=source)
        mode = stat.S_IMODE(target.stat().st_mode)
        self.assertEqual(mode & 0o077, 0)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["records_parsed"], 1)
        self.assertEqual(list(target.parent.glob("*.tmp")), [])


    def test_secret_delimiters_do_not_corrupt_email_prefix(self):
        source = self.root / "secret-delimiters.txt"
        source.write_text(
            "alice@example.com|pass:word,extra\n"
            "bob@example.com:pass|word;extra\n"
            "carol@example.com\tpass:word|extra\n"
            '"dave@example.com","secret:with|separators"\n',
            encoding="utf-8",
        )
        report = audit_dataset(source)
        self.assertEqual(report["records_parsed"], 4)
        self.assertEqual(report["credential_shaped_records"], 4)
        self.assertEqual(report["valid_email_records"], 4)
        self.assertEqual(report["unique_valid_email_records"], 4)
        self.assertNotIn("pass:word", json.dumps(report))
        self.assertNotIn("secret:with", json.dumps(report))

    def test_quoted_email_only_record_is_accepted(self):
        source = self.root / "quoted-email.txt"
        source.write_text('"alice@example.com"\n', encoding="utf-8")
        report = audit_dataset(source, mode="email")
        self.assertEqual(report["valid_email_records"], 1)
        self.assertEqual(report["email_only_records"], 1)

    def test_validation_error_distribution_is_aggregate_only(self):
        source = self.root / "validation-errors.txt"
        source.write_text("bad-address\nno-at-sign\nvalid@example.com\n", encoding="utf-8")
        report = audit_dataset(source)
        self.assertEqual(sum(report["validation_error_distribution"].values()), 2)
        rendered = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("bad-address", rendered)
        self.assertNotIn("no-at-sign", rendered)

    def test_rejects_unknown_mode_and_invalid_limit(self):
        source = self.root / "a.txt"
        source.write_text("a@example.com\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            audit_dataset(source, mode="network-login")
        with self.assertRaises(ValueError):
            audit_dataset(source, max_line_bytes=100)


if __name__ == "__main__":
    unittest.main()
