#!/usr/bin/env python3
"""Offline 100k mixed-dataset regression test; uses synthetic data only."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mega_checker.dataset_audit import audit_dataset  # noqa: E402

EMAIL_ONLY_UNIQUE = 25_000
CREDENTIAL_UNIQUE = 20_000
INVALID_UNIQUE = 5_000
BLANK_COMMENT_LINES = 5_000


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mega-mixed-stress-") as directory:
        root = Path(directory)
        source = root / "synthetic_mixed_100k.txt"
        report_path = root / "report.json"

        with source.open("w", encoding="utf-8", newline="\n") as stream:
            # 25k addresses, each appearing twice: 50k email-only records.
            for index in range(EMAIL_ONLY_UNIQUE):
                line = f"user{index}@gmail.com\n"
                stream.write(line)
                stream.write(line)

            # 20k addresses, each appearing twice with different dummy secrets
            # and delimiters: 40k credential-shaped records. No auth is attempted.
            for index in range(CREDENTIAL_UNIQUE):
                email = f"pair{index}@outlook.com"
                stream.write(f"{email}:SYNTHETIC_SECRET_A_{index:05d}\n")
                stream.write(f"{email}|SYNTHETIC_SECRET_B_{index:05d}\n")

            # Unique malformed records and blank/comment records.
            for index in range(INVALID_UNIQUE):
                stream.write(f"not-an-email-{index:05d}\n")
            for index in range(BLANK_COMMENT_LINES):
                stream.write("\n" if index % 2 == 0 else f"# synthetic comment {index}\n")

        started = perf_counter()
        report = audit_dataset(source, mode="auto")
        elapsed = perf_counter() - started

        expected = {
            "lines_total": 100_000,
            "records_parsed": 95_000,
            "email_only_records": 55_000,
            "credential_shaped_records": 40_000,
            "blank_or_comment_lines": 5_000,
            "malformed_or_oversized_lines": 5_000,
            "valid_email_records": 90_000,
            "invalid_email_records": 5_000,
            "unique_parsed_identifiers": 50_000,
            "duplicate_records": 45_000,
            "unique_valid_email_records": 45_000,
        }
        failures: list[str] = []
        for key, wanted in expected.items():
            actual = report.get(key)
            status = "PASS" if actual == wanted else "FAIL"
            print(f"[{status}] {key}: {actual} (expected {wanted})")
            if actual != wanted:
                failures.append(key)

        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        serialized = report_path.read_text(encoding="utf-8")
        secret_leaked = "SYNTHETIC_SECRET_A_" in serialized or "SYNTHETIC_SECRET_B_" in serialized
        print(f"[{'FAIL' if secret_leaked else 'PASS'}] synthetic secrets absent from report")
        if secret_leaked:
            failures.append("secret_redaction")

        print(f"elapsed_seconds: {elapsed:.3f}")
        print(f"rows_per_second: {100_000 / elapsed:.0f}")
        if failures:
            print("MIXED DATASET STRESS TEST: FAIL — " + ", ".join(failures))
            return 1
        print("MIXED DATASET STRESS TEST: PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
