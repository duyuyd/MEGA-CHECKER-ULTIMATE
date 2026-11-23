"""Operations exposed to the native Android screen. All network calls are opt-in."""
from functools import lru_cache
from pathlib import Path

from .password_lab import password_report
from .validation import load_disposable_domains, validate_email


@lru_cache(maxsize=1)
def _domains():
    return load_disposable_domains(Path(__file__).parent.parent / "data" / "disposable_domains.txt")


def email_report(value: str) -> str:
    result = validate_email(value, _domains())
    if result.syntax_status != "valid":
        return "Cấu trúc email chưa hợp lệ.\n" + "\n".join(result.errors)
    lines = ["Cấu trúc email hợp lệ.", f"Tên miền: {result.domain}"]
    if result.registrable_domain:
        lines.append(f"Tên miền đăng ký: {result.registrable_domain}")
    if result.domain_type != "custom":
        lines.append(f"Nhà cung cấp: {result.domain_type}")
    if result.disposable:
        lines.append("Tên miền có trong danh sách email tạm.")
    if result.typo_suggestion:
        lines.append("Tên miền gợi ý: " + result.typo_suggestion.rsplit("@", 1)[1])
    return "\n".join(lines)


def dns_report(value: str) -> str:
    from .dnsintel import DomainInspector
    result = validate_email(value, _domains())
    if result.syntax_status != "valid":
        return "Hãy nhập địa chỉ email có cấu trúc hợp lệ để tra DNS."
    data = DomainInspector(timeout=3).inspect(result.domain)
    return "\n".join((f"DNS cho {result.domain}", f"MX: {data['mx_status']}",
                      f"SPF: {data['spf_status']}", f"DMARC: {data['dmarc_status']}",
                      f"Nguồn DNS: {data['dns_provider']}"))


def breach_report(value: str) -> str:
    from .hibp import check_password_k_anonymity
    result = check_password_k_anonymity(value, timeout=8)
    if result["status"] == "found":
        return f"Đã có trong dữ liệu rò rỉ. Số lần ghi nhận: {result['count']:,}.".replace(",", ".")
    return "Chưa thấy mật khẩu này trong dữ liệu Pwned Passwords đã tra cứu."
