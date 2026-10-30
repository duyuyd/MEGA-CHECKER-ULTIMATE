from __future__ import annotations
import csv
import json
import shutil
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from .models import EmailResult

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

class Store:
    """Thread-safe SQLite store with WAL, atomic upserts and safe backups."""
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.path), timeout=30, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS results (
            normalized_email TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            masked_email TEXT NOT NULL,
            syntax_status TEXT NOT NULL,
            disposable INTEGER NOT NULL DEFAULT 0,
            checked_at TEXT NOT NULL,
            result_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            source TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'running',
            total INTEGER NOT NULL DEFAULT 0,
            completed INTEGER NOT NULL DEFAULT 0,
            started_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS job_items (
            job_id TEXT NOT NULL,
            normalized_email TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (job_id, normalized_email),
            FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_results_checked ON results(checked_at);
        """)
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(results)")}
        if "disposable" not in columns:
            self.conn.execute("ALTER TABLE results ADD COLUMN disposable INTEGER NOT NULL DEFAULT 0")
        self.conn.commit()

    def save_result(self, result: EmailResult) -> None:
        payload = json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self.conn.execute("""
                INSERT INTO results(normalized_email,email,masked_email,syntax_status,disposable,checked_at,result_json)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(normalized_email) DO UPDATE SET
                  email=excluded.email, masked_email=excluded.masked_email,
                  syntax_status=excluded.syntax_status, disposable=excluded.disposable,
                  checked_at=excluded.checked_at, result_json=excluded.result_json
            """, (result.normalized_email, result.email, result.masked_email,
                  result.syntax_status, 1 if result.disposable else 0, result.checked_at, payload))
            self.conn.commit()

    def get_result(self, normalized_email: str) -> EmailResult | None:
        with self._lock:
            row = self.conn.execute("SELECT result_json FROM results WHERE normalized_email=?",
                                    (normalized_email,)).fetchone()
        return EmailResult.from_dict(json.loads(row["result_json"])) if row else None

    def list_results(self, limit: int = 10000) -> list[EmailResult]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT result_json FROM results ORDER BY checked_at DESC LIMIT ?",
                (max(1, min(int(limit), 1000000)),)
            ).fetchall()
        return [EmailResult.from_dict(json.loads(row["result_json"])) for row in rows]

    def stats(self) -> dict:
        with self._lock:
            total = self.conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
            valid = self.conn.execute("SELECT COUNT(*) FROM results WHERE syntax_status='valid'").fetchone()[0]
            disposable = self.conn.execute(
                "SELECT COUNT(*) FROM results WHERE disposable=1"
            ).fetchone()[0]
        return {"total": total, "valid_syntax": valid, "invalid_syntax": total-valid,
                "disposable": disposable}

    def start_job(self, job_id: str, source: str, emails: Iterable[str]) -> None:
        values = list(dict.fromkeys(emails))
        now = utc_now()
        with self._lock:
            self.conn.execute("""
              INSERT INTO jobs(job_id,source,status,total,completed,started_at,updated_at)
              VALUES(?,?, 'running', ?, 0, ?, ?)
              ON CONFLICT(job_id) DO UPDATE SET source=excluded.source,
                status='running', total=excluded.total, updated_at=excluded.updated_at
            """, (job_id, source, len(values), now, now))
            self.conn.executemany("""
              INSERT OR IGNORE INTO job_items(job_id,normalized_email,status,updated_at)
              VALUES(?,?,'pending',?)
            """, [(job_id, email.strip(), now) for email in values])
            self.conn.commit()

    def job_done(self, job_id: str, email: str) -> None:
        now = utc_now()
        with self._lock:
            self.conn.execute("""
              UPDATE job_items SET status='done', updated_at=?
              WHERE job_id=? AND normalized_email=?
            """, (now, job_id, email.strip()))
            self.conn.execute("""
              UPDATE jobs SET completed=(SELECT COUNT(*) FROM job_items
                WHERE job_id=? AND status='done'), updated_at=? WHERE job_id=?
            """, (job_id, now, job_id))
            self.conn.commit()

    def pending_for_job(self, job_id: str) -> list[str]:
        with self._lock:
            rows = self.conn.execute("""
              SELECT normalized_email FROM job_items
              WHERE job_id=? AND status!='done' ORDER BY normalized_email
            """, (job_id,)).fetchall()
        return [r[0] for r in rows]

    def finish_job(self, job_id: str, status: str = "completed") -> None:
        with self._lock:
            self.conn.execute("UPDATE jobs SET status=?,updated_at=? WHERE job_id=?",
                              (status, utc_now(), job_id))
            self.conn.commit()

    def export_csv(self, path: Path, limit: int = 100000) -> int:
        records = self.list_results(limit)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        columns = [
            "email", "masked_email", "syntax_status", "domain", "public_suffix",
            "registrable_domain", "suffix_known", "domain_type",
            "disposable", "mx_status", "mx_hosts", "spf_status", "dmarc_status",
            "dkim_status", "hibp_status", "typo_suggestion", "checked_at",
        ]
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for item in records:
                row = item.to_dict()
                row["mx_hosts"] = ";".join(row["mx_hosts"])
                row["disposable"] = "yes" if row["disposable"] else "no"
                writer.writerow({k: row.get(k, "") for k in columns})
        return len(records)

    def export_json(self, path: Path, limit: int = 100000) -> int:
        records = self.list_results(limit)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([r.to_dict() for r in records], ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return len(records)

    def backup(self, directory: Path) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"mega_checker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        with self._lock:
            dest = sqlite3.connect(str(target))
            try:
                self.conn.backup(dest)
            finally:
                dest.close()
        return target

    def close(self) -> None:
        with self._lock:
            self.conn.close()
