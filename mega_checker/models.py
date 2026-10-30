from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass
class EmailResult:
    email: str
    normalized_email: str
    masked_email: str
    syntax_status: str
    domain: str = ""
    public_suffix: str = ""
    registrable_domain: str = ""
    suffix_known: bool = False
    local_part: str = ""
    typo_suggestion: str = ""
    disposable: bool = False
    domain_type: str = "unknown"
    mx_status: str = "not_checked"
    mx_hosts: list[str] = field(default_factory=list)
    address_fallback: bool = False
    spf_status: str = "not_checked"
    spf_record: str = ""
    dmarc_status: str = "not_checked"
    dmarc_record: str = ""
    dkim_status: str = "not_checked"
    dkim_selectors_found: list[str] = field(default_factory=list)
    dns_status: str = "not_checked"
    dns_provider: str = ""
    hibp_status: str = "not_checked"
    hibp_breaches: list[dict[str, Any]] = field(default_factory=list)
    checked_at: str = ""
    duration_ms: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmailResult":
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})
