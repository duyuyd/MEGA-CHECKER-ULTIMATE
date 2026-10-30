from __future__ import annotations
import re
from pathlib import Path
import idna
from .models import EmailResult
from .suffixes import domain_parts

LOCAL_ATOM_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+$")
DOMAIN_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")

TYPO_DOMAINS = {
    "gmial.com": "gmail.com", "gamil.com": "gmail.com", "gmai.com": "gmail.com",
    "gmail.con": "gmail.com", "gmail.co": "gmail.com", "gmal.com": "gmail.com",
    "hotnail.com": "hotmail.com", "hotmai.com": "hotmail.com",
    "hotmail.con": "hotmail.com", "outlok.com": "outlook.com",
    "outlook.con": "outlook.com", "outllok.com": "outlook.com",
    "yahoo.con": "yahoo.com", "yaho.com": "yahoo.com",
    "yhoo.com": "yahoo.com", "icloud.con": "icloud.com",
}

BUILTIN_DISPOSABLE = {
    "10minutemail.com", "20minutemail.com", "dispostable.com", "fakeinbox.com",
    "getairmail.com", "guerrillamail.com", "guerrillamail.net", "maildrop.cc",
    "mailinator.com", "mailmetrash.com", "mailnesia.com", "minuteinbox.com",
    "tempmail.com", "tempmailaddress.com", "throwawaymail.com", "trashmail.com",
    "yopmail.com", "sharklasers.com", "grr.la", "temp-mail.org", "mohmal.com",
    "emailondeck.com", "disposablemail.com", "mintemail.com", "mytemp.email",
    "getnada.com", "burnermail.io", "inboxkitten.com", "dropmail.me",
}

PROVIDERS = {
    "gmail.com": "Google", "googlemail.com": "Google",
    "outlook.com": "Microsoft", "hotmail.com": "Microsoft", "live.com": "Microsoft",
    "yahoo.com": "Yahoo", "icloud.com": "Apple", "me.com": "Apple",
    "proton.me": "Proton", "protonmail.com": "Proton",
    "fastmail.com": "Fastmail", "gmx.com": "GMX", "zoho.com": "Zoho",
}

def normalize_domain(domain: str) -> str:
    raw = (domain or "").strip().rstrip(".").lower()
    try:
        return idna.encode(raw, uts46=True, std3_rules=True).decode("ascii").lower()
    except (idna.IDNAError, UnicodeError, AttributeError):
        return ""

def normalize_email(email: str) -> str:
    raw = (email or "").strip()
    if raw.count("@") != 1:
        # Invalid input is still used as a database key; preserve it so distinct
        # malformed strings do not collapse into the same normalized key.
        return raw
    local, domain = raw.rsplit("@", 1)
    normalized_domain = normalize_domain(domain)
    if not normalized_domain:
        return raw
    # Domain names are case-insensitive; preserve the local part because SMTP
    # technically permits case-sensitive mailbox names.
    return f"{local}@{normalized_domain}"

def mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    local, domain = email.rsplit("@", 1)
    if not local:
        return f"***@{domain}"
    if len(local) == 1:
        masked = "*"
    elif len(local) == 2:
        masked = local[0] + "*"
    else:
        masked = local[0] + ("*" * min(6, len(local) - 2)) + local[-1]
    return f"{masked}@{domain}"

def load_disposable_domains(path: Path | None = None) -> set[str]:
    domains = set(BUILTIN_DISPOSABLE)
    if path and path.is_file():
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                item = line.strip().lower().lstrip(".")
                if item and not item.startswith("#"):
                    normalized = normalize_domain(item)
                    if normalized:
                        domains.add(normalized)
        except OSError:
            pass
    return domains

def is_disposable_domain(domain: str, domains: set[str]) -> bool:
    return any(domain == item or domain.endswith("." + item) for item in domains)

def validate_email(email: str, disposable_domains: set[str] | None = None) -> EmailResult:
    raw = (email or "").strip()
    if not raw or raw.count("@") != 1:
        result = EmailResult(
            email=raw, normalized_email=normalize_email(raw),
            masked_email=mask_email(raw), syntax_status="invalid"
        )
        result.errors.append("Địa chỉ trống hoặc không có đúng một ký tự @.")
        return result

    # Normalize the domain exactly once. The previous implementation called
    # normalize_email() (which normalized the domain) and then normalized the
    # same domain again below. IDNA conversion is non-trivial on large datasets.
    local, domain_raw = raw.rsplit("@", 1)
    domain = normalize_domain(domain_raw)
    normalized = f"{local}@{domain}" if domain else raw
    result = EmailResult(
        email=raw, normalized_email=normalized, masked_email=mask_email(raw),
        syntax_status="invalid"
    )
    result.local_part = local
    result.domain = domain
    parts = domain_parts(domain)
    result.public_suffix = str(parts["public_suffix"])
    result.registrable_domain = str(parts["registrable_domain"])
    result.suffix_known = bool(parts["suffix_known"])
    if not result.suffix_known:
        result.warnings.append("Đuôi tên miền không có trong snapshot Public Suffix List đi kèm; cần kiểm tra/cập nhật danh sách.")

    if not local or len(local.encode("utf-8", errors="ignore")) > 64:
        result.errors.append("Phần tên trước @ trống hoặc dài quá 64 byte.")
        return result
    if not domain or len(domain) > 253 or "." not in domain:
        result.errors.append("Tên miền không hợp lệ hoặc thiếu dấu chấm.")
        return result
    # Enforce the address limit on the ASCII form sent over SMTP, after IDNA
    # conversion. Unicode input can expand when represented as Punycode.
    if len(local.encode("ascii", errors="ignore")) + 1 + len(domain.encode("ascii")) > 254:
        result.errors.append("Địa chỉ vượt giới hạn 254 byte sau khi chuẩn hóa IDNA.")
        return result
    if local.startswith(".") or local.endswith(".") or ".." in local:
        result.errors.append("Phần tên trước @ có dấu chấm ở vị trí không hợp lệ.")
        return result
    if not LOCAL_ATOM_RE.fullmatch(local):
        result.errors.append("Phần tên trước @ có ký tự ngoài tập dot-atom được hỗ trợ.")
        return result

    labels = domain.split(".")
    if any(not label or len(label) > 63 or not DOMAIN_LABEL_RE.fullmatch(label) for label in labels):
        result.errors.append("Tên miền có nhãn trống, quá dài hoặc chứa dấu gạch nối sai vị trí.")
        return result
    if len(labels[-1]) < 2:
        result.errors.append("Đuôi tên miền ngắn bất thường.")
        return result

    result.syntax_status = "valid"
    result.domain_type = PROVIDERS.get(domain, "custom")
    correction = TYPO_DOMAINS.get(domain)
    if correction:
        result.typo_suggestion = f"{local}@{correction}"
        result.warnings.append("Tên miền gần giống một nhà cung cấp phổ biến; chỉ là gợi ý, không tự sửa.")

    domains = disposable_domains if disposable_domains is not None else BUILTIN_DISPOSABLE
    result.disposable = is_disposable_domain(domain, domains)
    if result.disposable:
        result.warnings.append("Tên miền có trong danh sách email tạm thời cục bộ; danh sách không bao quát mọi dịch vụ.")
    if domain.startswith("xn--") or ".xn--" in domain:
        result.warnings.append("Tên miền có nhãn IDN/Punycode; cần xác minh kỹ tên hiển thị.")
    return result
