from __future__ import annotations
from functools import lru_cache
from pathlib import Path

PSL_PATH = Path(__file__).resolve().parent.parent / "data" / "public_suffix_list.dat"

class PublicSuffixList:
    """Small PSL matcher supporting exact, wildcard and exception rules."""
    def __init__(self, lines: list[str]):
        self.exact: set[str] = set()
        self.wildcards: set[str] = set()
        self.exceptions: set[str] = set()
        for line in lines:
            rule = line.strip().lower()
            if not rule or rule.startswith("//"):
                continue
            if rule.startswith("!"):
                self.exceptions.add(rule[1:])
            elif rule.startswith("*."):
                self.wildcards.add(rule[2:])
            else:
                self.exact.add(rule)

    def suffix_length(self, domain: str) -> int:
        labels = domain.rstrip(".").lower().split(".")
        if not labels or any(not item for item in labels):
            return 0
        best = 1  # PSL implicit default rule: *
        for index in range(len(labels)):
            candidate = ".".join(labels[index:])
            if candidate in self.exceptions:
                return max(1, len(labels) - index - 1)
            if candidate in self.exact:
                best = max(best, len(labels) - index)
            if index + 1 < len(labels):
                wildcard_tail = ".".join(labels[index + 1:])
                if wildcard_tail in self.wildcards:
                    best = max(best, len(labels) - index)
        return best

    def public_suffix(self, domain: str) -> str:
        labels = domain.rstrip(".").lower().split(".")
        count = self.suffix_length(domain)
        return ".".join(labels[-count:]) if count else ""

    def registrable_domain(self, domain: str) -> str:
        labels = domain.rstrip(".").lower().split(".")
        count = self.suffix_length(domain)
        if count <= 0 or len(labels) <= count:
            return ""
        return ".".join(labels[-count-1:])

    def is_known_suffix(self, domain: str) -> bool:
        suffix = self.public_suffix(domain)
        if not suffix:
            return False
        if suffix in self.exact:
            return True
        suffix_labels = suffix.split(".")
        for wildcard in self.wildcards:
            wildcard_labels = wildcard.split(".")
            if len(suffix_labels) == len(wildcard_labels) + 1 and suffix_labels[1:] == wildcard_labels:
                return True
        for exception in self.exceptions:
            parts = exception.split(".", 1)
            if len(parts) == 2 and suffix == parts[1]:
                return True
        return False

@lru_cache(maxsize=1)
def get_psl() -> PublicSuffixList | None:
    try:
        return PublicSuffixList(PSL_PATH.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return None

def domain_parts(domain: str) -> dict[str, str | bool]:
    psl = get_psl()
    if not psl:
        return {"public_suffix": "", "registrable_domain": "", "suffix_known": False}
    suffix = psl.public_suffix(domain)
    registrable = psl.registrable_domain(domain)
    return {"public_suffix": suffix, "registrable_domain": registrable,
            "suffix_known": psl.is_known_suffix(domain)}
