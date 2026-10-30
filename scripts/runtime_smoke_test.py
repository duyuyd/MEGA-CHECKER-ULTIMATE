#!/usr/bin/env python3
"""Runtime smoke tests for SQLite, batch resume, exports, backup and optional DNS.

This script uses only synthetic example-domain addresses and a temporary DB.
It does not call HIBP, test mailbox existence, or modify the production database.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mega_checker.dnsintel import DomainInspector  # noqa: E402
from mega_checker.exporters import export_html  # noqa: E402
from mega_checker.models import EmailResult  # noqa: E402
from mega_checker.pipeline import read_emails, run_batch  # noqa: E402
from mega_checker.storage import Store  # noqa: E402
from mega_checker.validation import normalize_email, validate_email  # noqa: E402


def check(condition: bool, name: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")
    return bool(condition)


def fake_check_one(email: str, inspector, disposable_domains: set[str]) -> EmailResult:
    result = validate_email(email, disposable_domains)
    result.checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result.dns_status = "not_checked_in_offline_smoke_test"
    result.mx_status = "not_checked"
    result.duration_ms = 1
    return result


def run_offline() -> int:
    outcomes: list[bool] = []
    with tempfile.TemporaryDirectory(prefix="mega-checker-qa-") as temp:
        root = Path(temp)
        source = root / "synthetic_emails.txt"
        source.write_text(
            "# synthetic test data\n"
            "First@example.com\nFirst@EXAMPLE.COM\nsecond@example.net\n"
            "not-an-email\n",
            encoding="utf-8",
        )
        emails = read_emails(source)
        outcomes.append(check(len(emails) == 2, "input parsing and domain-case deduplication while preserving local-part case"))

        db_path = root / "smoke.db"
        store = Store(db_path)
        job_id = "runtime-smoke-job"
        normalized = [normalize_email(item) for item in emails]
        store.start_job(job_id, "synthetic", normalized)

        first = validate_email(emails[0])
        first.checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        store.save_result(first)
        store.job_done(job_id, normalized[0])

        # Replace network-dependent check_one only for this deterministic resume test.
        with patch("mega_checker.pipeline.check_one", side_effect=fake_check_one):
            results, summary = run_batch(
                emails,
                store,
                workers=1,
                job_id=job_id,
                resume=True,
                disposable_file=ROOT / "data" / "disposable_domains.txt",
                dns_timeout=1,
            )

        outcomes.append(check(
            summary["processed_now"] == 1 and summary["skipped_done"] == 1
            and len(results) == 1,
            "resume processes only the pending item",
        ))
        outcomes.append(check(
            store.pending_for_job(job_id) == [],
            "resume leaves no pending job items",
        ))
        outcomes.append(check(
            store.stats()["total"] == 2,
            "SQLite stores both completed results",
        ))

        csv_path = root / "exports" / "results.csv"
        json_path = root / "exports" / "results.json"
        html_path = root / "exports" / "results.html"
        csv_count = store.export_csv(csv_path)
        json_count = store.export_json(json_path)
        export_html(store.list_results(), html_path)
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            csv_rows = list(csv.DictReader(handle))
        json_rows = json.loads(json_path.read_text(encoding="utf-8"))
        html_text = html_path.read_text(encoding="utf-8")
        outcomes.append(check(
            csv_count == 2 and len(csv_rows) == 2,
            "CSV export contains two records",
        ))
        outcomes.append(check(
            json_count == 2 and len(json_rows) == 2,
            "JSON export contains two records",
        ))
        outcomes.append(check(
            html_path.is_file() and html_text.count("<tr>") == 3,
            "HTML export contains two data rows",
        ))

        backup_path = store.backup(root / "backups")
        backup_store = Store(backup_path)
        backup_total = backup_store.stats()["total"]
        outcomes.append(check(
            backup_path.is_file() and backup_total == 2,
            "SQLite backup opens and retains both records",
        ))
        backup_store.close()
        store.close()

    passed = sum(outcomes)
    print(f"OFFLINE SMOKE TEST: {passed}/{len(outcomes)}")
    return 0 if passed == len(outcomes) else 1


def run_dns(domain: str, timeout: float) -> None:
    print(f"\nDNS LIVE CHECK: {domain} (timeout {timeout}s; selector checks add lookups)")
    data = DomainInspector(timeout=timeout).inspect(domain)
    for key in (
        "dns_provider", "dns_status", "mx_status", "mx_hosts", "address_fallback",
        "spf_status", "spf_record", "dmarc_status", "dmarc_record",
        "dkim_status", "dkim_selectors_found",
    ):
        print(f"{key}: {data.get(key)}")
    uncertain = {"timeout", "dns_error", "unknown", "partial", "resolver_unconfigured"}
    if data.get("dns_status") in {"partial", "resolver_unconfigured"} or data.get("mx_status") in uncertain:
        print("[INCONCLUSIVE] DNS resolver/network did not return enough data; this is not a PASS or FAIL.")
    else:
        print("[INFO] DNS answers received. Review each record status; this does not prove mailbox existence.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mega Checker runtime smoke test")
    parser.add_argument("--dns-domain", help="Optional public domain for live DNS checks")
    parser.add_argument("--dns-timeout", type=float, default=3.0)
    args = parser.parse_args()
    status = run_offline()
    if args.dns_domain:
        run_dns(args.dns_domain.strip().rstrip("."), max(1.0, min(args.dns_timeout, 10.0)))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
