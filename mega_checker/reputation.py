from __future__ import annotations
from pathlib import Path
from .validation import load_disposable_domains, is_disposable_domain, PROVIDERS

class ReputationEngine:
    """Transparent local indicators; never presents a heuristic as proof of fraud."""
    def __init__(self, disposable_file: Path | None = None):
        self.disposable_domains = load_disposable_domains(disposable_file)

    def inspect(self, domain: str) -> dict:
        return {
            "domain": domain,
            "provider": PROVIDERS.get(domain, "custom"),
            "is_disposable": is_disposable_domain(domain, self.disposable_domains),
            "signals": [
                "disposable-list-match" if is_disposable_domain(domain, self.disposable_domains) else "not-on-local-disposable-list"
            ],
            "confidence": "limited-local-list",
            "note": "Không có kết quả trong danh sách không chứng minh domain an toàn."
        }
