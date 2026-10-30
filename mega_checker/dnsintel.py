from __future__ import annotations
import sys
import time
from pathlib import Path
from typing import Any

# Prefer the bundled pure-Python dnspython copy so Termux can run offline.
_VENDOR = Path(__file__).resolve().parent.parent / "vendor"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

try:
    import dns.exception
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    dns = None
    DNS_AVAILABLE = False

DKIM_SELECTORS = (
    "default", "selector1", "selector2", "google", "k1",
)

class DomainInspector:
    """Domain-level mail DNS diagnostics. Does not test mailbox existence."""
    def __init__(self, timeout: float = 4.0, cache_seconds: int = 1800):
        self.timeout = max(1.0, min(float(timeout), 15.0))
        self.cache_seconds = max(60, int(cache_seconds))
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def inspect(self, domain: str) -> dict[str, Any]:
        now = time.monotonic()
        cached = self._cache.get(domain)
        if cached and now - cached[0] < self.cache_seconds:
            return dict(cached[1])
        if not DNS_AVAILABLE:
            data = {
                "dns_status": "dependency_missing", "dns_provider": "none",
                "mx_status": "unknown", "mx_hosts": [], "address_fallback": False,
                "spf_status": "unknown", "spf_record": "",
                "dmarc_status": "unknown", "dmarc_record": "",
                "dkim_status": "unknown", "dkim_selectors_found": [],
            }
            self._cache[domain] = (now, data)
            return data
        data = self._inspect_with_dnspython(domain)
        self._cache[domain] = (now, dict(data))
        return data

    def _resolve_txt(self, resolver: Any, name: str) -> tuple[list[str], str]:
        try:
            # TXT/DKIM checks are secondary; keep each lookup bounded so a
            # domain without these records cannot stall a batch for minutes.
            answers = resolver.resolve(name, "TXT", lifetime=min(0.9, self.timeout))
            out = []
            for answer in answers:
                chunks = getattr(answer, "strings", None)
                if chunks:
                    out.append(b"".join(chunks).decode("utf-8", "replace"))
                else:
                    out.append(str(answer).replace('" "', "").strip('"'))
            return out, ("answer" if out else "absent")
        except dns.resolver.NoAnswer:
            return [], "absent"
        except dns.resolver.NXDOMAIN:
            return [], "nxdomain"
        except dns.exception.Timeout:
            return [], "timeout"
        except dns.resolver.NoNameservers:
            return [], "dns_error"
        except Exception:
            return [], "dns_error"

    def _inspect_with_dnspython(self, domain: str) -> dict[str, Any]:
        resolver = dns.resolver.Resolver()
        resolver.lifetime = self.timeout
        resolver.timeout = min(2.0, self.timeout)
        data = {
            "dns_status": "ok", "dns_provider": "dnspython",
            "mx_status": "unknown", "mx_hosts": [], "address_fallback": False,
            "spf_status": "absent", "spf_record": "",
            "dmarc_status": "absent", "dmarc_record": "",
            "dkim_status": "not_checked", "dkim_selectors_found": [],
        }
        try:
            answers = resolver.resolve(domain, "MX", lifetime=self.timeout)
            hosts = sorted({str(item.exchange).rstrip(".").lower() for item in answers
                            if int(getattr(item, "preference", 0)) >= 0})
            data["mx_hosts"] = hosts
            data["mx_status"] = "found" if hosts else "no_mx_record"
        except dns.resolver.NoAnswer:
            data["mx_status"] = "no_mx_record"
        except dns.resolver.NXDOMAIN:
            data["mx_status"] = "nxdomain"
        except dns.resolver.NoNameservers:
            data["mx_status"] = "dns_error"
        except dns.exception.Timeout:
            data["mx_status"] = "timeout"
        except Exception:
            data["mx_status"] = "dns_error"

        if data["mx_status"] == "no_mx_record":
            for record_type in ("A", "AAAA"):
                try:
                    resolver.resolve(domain, record_type, lifetime=self.timeout)
                    data["address_fallback"] = True
                    break
                except Exception:
                    continue

        txt_records, txt_state = self._resolve_txt(resolver, domain)
        spf = [record for record in txt_records if record.lower().startswith("v=spf1")]
        if spf:
            data["spf_status"], data["spf_record"] = "present", " ".join(spf)
        elif txt_state == "absent":
            data["spf_status"] = "absent"
        else:
            data["spf_status"] = "unknown"

        dmarc_records, dmarc_state = self._resolve_txt(resolver, f"_dmarc.{domain}")
        dmarc = [record for record in dmarc_records if record.lower().startswith("v=dmarc1")]
        if dmarc:
            data["dmarc_status"], data["dmarc_record"] = "present", " ".join(dmarc)
        elif dmarc_state == "absent":
            data["dmarc_status"] = "absent"
        else:
            data["dmarc_status"] = "unknown"

        found = []
        selector_states = []
        for selector in DKIM_SELECTORS:
            records, state = self._resolve_txt(resolver, f"{selector}._domainkey.{domain}")
            selector_states.append(state)
            if any("v=dkim1" in r.lower() or "p=" in r.lower() for r in records):
                found.append(selector)
        data["dkim_selectors_found"] = found
        if found:
            data["dkim_status"] = "found"
        elif all(state == "absent" for state in selector_states):
            data["dkim_status"] = "not_found_in_common_selectors"
        else:
            data["dkim_status"] = "unknown"

        if data["mx_status"] == "nxdomain":
            data["dns_status"] = "nxdomain"
        elif data["mx_status"] in {"timeout", "dns_error"} or \
             data["spf_status"] == "unknown" or data["dmarc_status"] == "unknown" or \
             data["dkim_status"] == "unknown":
            data["dns_status"] = "partial"
        return data
