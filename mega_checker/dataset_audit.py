"""Privacy-preserving offline auditor for email and credential-shaped text datasets.

Input is streamed line by line. Exact deduplication and exact top-domain counts
use a disposable SQLite database; only per-run HMAC fingerprints and public
domain names are stored there. Secret portions never leave the parser.
"""
from __future__ import annotations

import hmac
import json
import os
import sqlite3
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, BinaryIO

from .validation import validate_email

_SEPARATORS = (":", "|", "\t", ";", ",")
_BATCH_SIZE = 2048


@dataclass(frozen=True)
class ParsedLine:
    email: str
    record_type: str  # email_only | credential_pair


def _parse_line(line: str, mode: str) -> ParsedLine | None:
    text = line.strip().lstrip("\ufeff")
    if not text or text.startswith("#"):
        return None

    # A quoted single-field email is still an email-only record.
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"\"", "'"}:
        text = text[1:-1].strip()

    if mode == "email":
        return ParsedLine(text, "email_only")

    # Find the first delimiter AFTER the @ sign, not the first separator type.
    # A secret can itself contain other separators (e.g. email|pass:word); the
    # old separator-priority loop could split inside that secret and corrupt
    # the extracted email. Only the email prefix is retained.
    at_index = text.find("@")
    if at_index >= 0:
        positions = [
            text.find(sep, at_index + 1)
            for sep in _SEPARATORS
            if text.find(sep, at_index + 1) >= 0
        ]
        if positions:
            candidate = text[:min(positions)].strip().strip('"').strip("'")
            if "@" in candidate:
                return ParsedLine(candidate, "credential_pair")

    return ParsedLine(text, "email_only")


def _iter_lines(stream: BinaryIO, max_line_bytes: int) -> Iterator[tuple[int, str, int]]:
    line_number = 0
    while True:
        raw = stream.readline(max_line_bytes + 1)
        if not raw:
            break
        line_number += 1
        raw_size = len(raw)
        if raw_size > max_line_bytes:
            while raw and not raw.endswith(b"\n"):
                raw = stream.readline(max_line_bytes + 1)
                raw_size += len(raw)
            yield line_number, "\x00OVERSIZED_LINE\x00", raw_size
            continue
        yield line_number, raw.decode("utf-8-sig", errors="replace").rstrip("\r\n"), raw_size


def audit_dataset(path: Path, mode: str = "auto", max_line_bytes: int = 65536,
                  input_stream: BinaryIO | None = None, access_mode: str = "noroot") -> dict:
    """Audit a local file or supplied binary stream; only aggregate data is returned."""
    from contextlib import nullcontext

    source = Path(path).expanduser()
    if mode not in {"auto", "email", "combo"}:
        raise ValueError("mode phải là auto, email hoặc combo")
    if input_stream is None and not source.is_file():
        raise FileNotFoundError(source)
    if not 1024 <= int(max_line_bytes) <= 1024 * 1024:
        raise ValueError("max_line_bytes phải trong khoảng 1024–1048576")

    counts = Counter()
    syntax = Counter()
    validation_errors = Counter()
    providers = Counter()
    disposable = 0
    typo_hints = 0
    unique_all = 0
    unique_valid = 0
    source_size_bytes = 0
    run_key = os.urandom(32)

    with tempfile.TemporaryDirectory(prefix="mega-audit-") as temp_dir:
        db_path = Path(temp_dir) / "seen.sqlite3"
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("PRAGMA journal_mode=OFF")
            conn.execute("PRAGMA synchronous=OFF")
            conn.execute("PRAGMA locking_mode=EXCLUSIVE")
            conn.execute("PRAGMA cache_size=-4096")
            conn.execute("CREATE TABLE seen (key BLOB PRIMARY KEY) WITHOUT ROWID")
            conn.execute("CREATE TABLE valid_seen (key BLOB PRIMARY KEY) WITHOUT ROWID")
            conn.execute(
                "CREATE TABLE domain_counts (domain TEXT PRIMARY KEY, count INTEGER NOT NULL) WITHOUT ROWID"
            )

            pending_all: list[tuple[bytes]] = []
            pending_valid: list[tuple[bytes]] = []
            pending_domains: Counter[str] = Counter()

            def flush_pending() -> None:
                nonlocal unique_all, unique_valid
                if not pending_all and not pending_domains:
                    return
                before = conn.total_changes
                if pending_all:
                    conn.executemany("INSERT OR IGNORE INTO seen(key) VALUES(?)", pending_all)
                    unique_all += conn.total_changes - before
                if pending_valid:
                    before = conn.total_changes
                    conn.executemany("INSERT OR IGNORE INTO valid_seen(key) VALUES(?)", pending_valid)
                    unique_valid += conn.total_changes - before
                if pending_domains:
                    conn.executemany(
                        "INSERT INTO domain_counts(domain, count) VALUES(?, ?) "
                        "ON CONFLICT(domain) DO UPDATE SET count=count+excluded.count",
                        pending_domains.items(),
                    )
                conn.commit()
                pending_all.clear()
                pending_valid.clear()
                pending_domains.clear()

            stream_context = source.open("rb") if input_stream is None else nullcontext(input_stream)
            with stream_context as stream:
                for _line_number, raw_line, raw_size in _iter_lines(stream, int(max_line_bytes)):
                    source_size_bytes += raw_size
                    counts["lines_total"] += 1
                    if raw_line == "\x00OVERSIZED_LINE\x00":
                        counts["oversized_lines"] += 1
                        counts["malformed_lines"] += 1
                        continue
                    if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                        counts["blank_or_comment_lines"] += 1
                        continue

                    parsed = _parse_line(raw_line, mode)
                    if parsed is None:
                        counts["blank_or_comment_lines"] += 1
                        continue
                    counts["records_parsed"] += 1
                    counts[parsed.record_type] += 1

                    result = validate_email(parsed.email)
                    syntax[result.syntax_status] += 1
                    for error in result.errors:
                        validation_errors[error] += 1
                    if result.syntax_status != "valid":
                        counts["malformed_lines"] += 1
                    else:
                        providers[result.domain_type] += 1
                        pending_domains[result.domain] += 1
                        if result.disposable:
                            disposable += 1
                        if result.typo_suggestion:
                            typo_hints += 1

                    fingerprint = hmac.digest(
                        run_key, result.normalized_email.encode("utf-8"), "sha256"
                    )
                    pending_all.append((fingerprint,))
                    if result.syntax_status == "valid":
                        pending_valid.append((fingerprint,))

                    if len(pending_all) >= _BATCH_SIZE:
                        flush_pending()

            if input_stream is None:
                source_size_bytes = source.stat().st_size
            flush_pending()
            top_domain_rows = conn.execute(
                "SELECT domain, count FROM domain_counts "
                "ORDER BY count DESC, domain ASC LIMIT 20"
            ).fetchall()
        finally:
            conn.close()

    valid_records = syntax["valid"]
    duplicates = counts["records_parsed"] - unique_all
    top_domains = [{"domain": domain, "count": count} for domain, count in top_domain_rows]
    return {
        "report_schema": "mega-checker-dataset-audit-v1",
        "mode": mode,
        "access_mode": access_mode,
        "source_name": source.name,
        "source_size_bytes": source_size_bytes,
        "lines_total": counts["lines_total"],
        "records_parsed": counts["records_parsed"],
        "email_only_records": counts["email_only"],
        "credential_shaped_records": counts["credential_pair"],
        "blank_or_comment_lines": counts["blank_or_comment_lines"],
        "malformed_or_oversized_lines": counts["malformed_lines"],
        "oversized_lines": counts["oversized_lines"],
        "valid_email_records": valid_records,
        "invalid_email_records": syntax["invalid"],
        "validation_error_distribution": dict(validation_errors.most_common()),
        "unique_parsed_identifiers": unique_all,
        "duplicate_records": duplicates,
        "unique_valid_email_records": unique_valid,
        "provider_distribution": dict(providers.most_common()),
        "top_domains": top_domains,
        "disposable_domain_records": disposable,
        "typo_hint_records": typo_hints,
        "security": {
            "authentication_attempts": 0,
            "secret_values_persisted": False,
            "secret_values_logged": False,
            "secret_values_processed_transiently_in_memory": True,
            "secret_values_exported": False,
            "temporary_dedup_storage": (
                "per-run keyed HMAC-SHA256 fingerprints only; key never persisted; "
                "temporary SQLite database automatically deleted"
            ),
        },
        "notes": [
            "Đây là kiểm toán định dạng ngoại tuyến; không thử đăng nhập hoặc xác minh mật khẩu.",
            "Dòng có dạng email<separator>secret chỉ được đếm; phần secret bị loại bỏ ngay khi phân tích.",
            "Địa chỉ email là dữ liệu cá nhân; giữ báo cáo và tệp nguồn ở nơi riêng tư.",
            "Một địa chỉ hợp lệ về cú pháp không chứng minh hộp thư tồn tại hoặc người dùng sở hữu nó.",
            "Thống kê domain được tính chính xác bằng SQLite tạm; chỉ 20 domain đầu được đưa vào báo cáo.",
            "validation_error_distribution chỉ chứa thông báo lỗi tổng hợp, không chứa địa chỉ email hay secret.",
            "No-Root là đường chạy mặc định; ROOT chỉ là fallback hoặc chế độ được người chạy chủ động chọn.",
        ],
    }


def write_report(report: dict, output: Path, source_path: Path | None = None) -> Path:
    """Write a private JSON report atomically, refusing to replace its source."""
    target = Path(output).expanduser()
    if source_path is not None:
        source = Path(source_path).expanduser().resolve()
        resolved_target = target.resolve()
        same_file = source == resolved_target
        if not same_file and target.exists():
            try:
                same_file = os.path.samefile(source, target)
            except OSError:
                same_file = False
        if same_file:
            raise ValueError("Đường dẫn báo cáo trùng tệp đầu vào; từ chối ghi đè dữ liệu nguồn")

    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    try:
        try:
            os.fchmod(fd, 0o600)
        except (AttributeError, OSError):
            pass
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, target)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
    return target
