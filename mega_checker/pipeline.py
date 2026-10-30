from __future__ import annotations
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from .dnsintel import DomainInspector
from .models import EmailResult
from .validation import validate_email, normalize_email
from .storage import Store

def read_emails(path: Path) -> list[str]:
    values = []
    with Path(path).open("r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for part in line.replace(";", ",").split(","):
                item = part.strip().strip('"').strip("'")
                if item and "@" in item:
                    values.append(item)
    # stable dedupe, case-insensitive
    seen, out = set(), []
    for value in values:
        key = normalize_email(value.strip())
        if key not in seen:
            seen.add(key)
            out.append(value.strip())
    return out

def check_one(email: str, inspector: DomainInspector, disposable_domains: set[str]) -> EmailResult:
    started = time.monotonic()
    result = validate_email(email, disposable_domains)
    if result.syntax_status == "valid":
        dns = inspector.inspect(result.domain)
        for key, value in dns.items():
            setattr(result, key, value)
        if dns["dns_status"] == "dependency_missing":
            result.warnings.append("Chưa cài dnspython: chưa kiểm tra được MX/SPF/DMARC/DKIM.")
        if dns["mx_status"] == "no_mx_record" and dns["address_fallback"]:
            result.warnings.append("Không có MX; domain có bản ghi A/AAAA. Điều này không xác nhận hộp thư nhận thư.")
        elif dns["mx_status"] == "no_mx_record":
            result.warnings.append("Không tìm thấy MX; cần xem xét thêm trạng thái DNS.")
        elif dns["mx_status"] == "timeout":
            result.warnings.append("Truy vấn MX hết thời gian; kết quả DNS chưa xác định.")
    result.checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result.duration_ms = int((time.monotonic() - started) * 1000)
    return result

def run_batch(emails: Iterable[str], store: Store, workers: int = 5,
              job_id: str = "manual", resume: bool = False,
              disposable_file: Path | None = None, dns_timeout: float = 4.0) -> tuple[list[EmailResult], dict]:
    from .validation import load_disposable_domains
    values = list(dict.fromkeys([e.strip() for e in emails if e and e.strip()]))
    normalized_values = [normalize_email(e) for e in values]
    store.start_job(job_id, "batch", normalized_values)
    pending_keys = set(store.pending_for_job(job_id)) if resume else set(normalized_values)
    work = [e for e in values if normalize_email(e) in pending_keys]
    inspector = DomainInspector(timeout=dns_timeout)
    disposable = load_disposable_domains(disposable_file)
    output: list[EmailResult] = []
    errors = 0
    with ThreadPoolExecutor(max_workers=max(1, min(int(workers), 32))) as pool:
        future_map = {pool.submit(check_one, email, inspector, disposable): email for email in work}
        for future in as_completed(future_map):
            email = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                import logging
                logging.getLogger("MegaCheckerUltimate").exception("Batch item failed (%s)", type(exc).__name__)
                result = validate_email(email, disposable)
                result.errors.append(f"Lỗi nội bộ: {type(exc).__name__}")
                errors += 1
            store.save_result(result)
            store.job_done(job_id, normalize_email(email))
            output.append(result)
    store.finish_job(job_id, "completed")
    return output, {"submitted": len(values), "processed_now": len(output),
                    "skipped_done": len(values)-len(work), "errors": errors}
