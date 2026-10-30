from __future__ import annotations
import sys
import time
import ipaddress
import subprocess
import json
import os
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# Prefer the bundled pure-Python dnspython copy so Termux can run offline.
_VENDOR = Path(__file__).resolve().parent.parent / "vendor"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

try:
    import dns.exception
    import dns.resolver
    import dns.rdata
    import dns.rdataclass
    import dns.rdatatype
    DNS_AVAILABLE = True
except ImportError:
    dns = None
    DNS_AVAILABLE = False


_ANDROID_DNS_CACHE: tuple[float, tuple[str, ...]] = (0.0, ())

def _android_dns_nameservers(cache_seconds: float = 30.0) -> list[str]:
    """Read active Android DNS server properties (works in Termux).

    Android/Termux may not expose /etc/resolv.conf. Query getprop instead,
    validate every value as an IP address, and cache briefly so batch checks
    do not spawn a process for every domain.
    """
    global _ANDROID_DNS_CACHE
    now = time.monotonic()
    cached_at, cached_servers = _ANDROID_DNS_CACHE
    if now - cached_at < cache_seconds:
        return list(cached_servers)

    servers: list[str] = []
    commands = ("getprop", "/system/bin/getprop")
    for command in commands:
        command_found = False
        for index in range(1, 5):
            try:
                completed = subprocess.run(
                    [command, f"net.dns{index}"],
                    capture_output=True, text=True, timeout=0.8, check=False,
                )
                command_found = True
                value = (completed.stdout or "").strip()
                if not value:
                    continue
                try:
                    normalized = str(ipaddress.ip_address(value))
                except ValueError:
                    continue
                if normalized not in servers:
                    servers.append(normalized)
            except (OSError, subprocess.SubprocessError):
                break
        if command_found:
            break

    _ANDROID_DNS_CACHE = (now, tuple(servers))
    return servers

DKIM_SELECTORS = (
    "default", "selector1", "selector2", "google", "k1",
)  # Generic heuristic sample only; not exhaustive.

# Provider-specific selector hints observed in publicly available Gmail message
# headers. These are candidates, not a claim that every Gmail account uses them.
# 20251104 was observed on Gmail-signed messages through September 2026.
# 20230601 and 20221208 were reported as revoked by 2026-09-15.
DKIM_PROVIDER_SELECTORS = {
    "gmail.com": ("20251104", "20230601", "20221208"),
}


def dkim_selectors_for_domain(domain: str) -> tuple[str, ...]:
    """Return generic plus narrowly scoped provider hints for a signing domain."""
    domain = (domain or "").strip().lower().rstrip(".")
    return tuple(dict.fromkeys((*DKIM_SELECTORS, *DKIM_PROVIDER_SELECTORS.get(domain, ()))))

class _CloudflareDoHResolver:
    """Small dnspython-compatible resolver using Cloudflare's JSON DoH API.

    This adapter is only selected when Android does not expose nameservers
    through getprop and dnspython cannot read a system resolver configuration.
    It implements just the synchronous ``resolve`` surface used by this app.
    """

    endpoint = "https://cloudflare-dns.com/dns-query"
    nameservers = ("https://cloudflare-dns.com/dns-query",)

    def __init__(self, lifetime: float = 4.0, timeout: float | None = None):
        if timeout is not None:
            lifetime = timeout
        self.lifetime = max(1.0, min(float(lifetime), 15.0))
        self.timeout = min(2.0, self.lifetime)
        ca_bundle = _VENDOR / "certifi" / "cacert.pem"
        self._ssl_context = ssl.create_default_context(
            cafile=str(ca_bundle) if ca_bundle.is_file() else None
        )

    def resolve(self, name: str, rdtype: str | int, lifetime: float | None = None, **_kwargs: Any) -> list[Any]:
        try:
            type_code = (
                dns.rdatatype.from_text(str(rdtype).upper())
                if isinstance(rdtype, str) else int(rdtype)
            )
            type_name = dns.rdatatype.to_text(type_code)
        except Exception as exc:
            raise ValueError(f"Unsupported DNS record type: {rdtype!r}") from exc

        query = urllib.parse.urlencode({"name": name.rstrip("."), "type": type_name})
        request = urllib.request.Request(
            f"{self.endpoint}?{query}",
            headers={
                "Accept": "application/dns-json",
                "User-Agent": "MegaCheckerUltimate/9.0.4",
            },
            method="GET",
        )
        request_timeout = max(1.0, min(float(lifetime or self.lifetime), 15.0))

        try:
            with urllib.request.urlopen(
                request, timeout=request_timeout, context=self._ssl_context
            ) as response:
                raw = response.read(262145)
            if len(raw) > 262144:
                raise dns.resolver.NoNameservers()
            payload = json.loads(raw.decode("utf-8"))
        except (TimeoutError, socket.timeout) as exc:
            raise dns.exception.Timeout() from exc
        except urllib.error.HTTPError as exc:
            if exc.code == 504:
                raise dns.exception.Timeout() from exc
            raise dns.resolver.NoNameservers() from exc
        except urllib.error.URLError as exc:
            if isinstance(getattr(exc, "reason", None), (TimeoutError, socket.timeout)):
                raise dns.exception.Timeout() from exc
            raise dns.resolver.NoNameservers() from exc
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            if isinstance(exc, (TimeoutError, socket.timeout)):
                raise dns.exception.Timeout() from exc
            raise dns.resolver.NoNameservers() from exc

        status = payload.get("Status")
        if status == 3:
            raise dns.resolver.NXDOMAIN()
        if status != 0:
            raise dns.resolver.NoNameservers()

        records: list[Any] = []
        for answer in payload.get("Answer", []) or []:
            try:
                if int(answer.get("type", -1)) != type_code:
                    continue
                text = answer.get("data")
                if not isinstance(text, str) or not text:
                    continue
                records.append(dns.rdata.from_text(
                    dns.rdataclass.IN, type_code, text
                ))
            except (ValueError, TypeError, dns.exception.DNSException):
                # Ignore malformed or unrelated records; never treat them as
                # valid MX/TXT data.
                continue

        if not records:
            raise dns.resolver.NoAnswer()
        return records


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

    def _create_resolver(self) -> tuple[Any, str]:
        """Choose the best resolver available on Android/Termux or Linux.

        Order: Android getprop nameservers, standard system resolver config,
        then DNS-over-HTTPS (Cloudflare) when no resolver config exists.
        DoH uses the bundled CA bundle and normal TLS certificate validation.
        Set MEGA_CHECKER_DOH=0 to disable the HTTPS fallback.
        """
        android_servers = _android_dns_nameservers()
        if android_servers:
            resolver = dns.resolver.Resolver(configure=False)
            resolver.nameservers = android_servers
            return resolver, "android_getprop"

        try:
            resolver = dns.resolver.Resolver()
            if resolver.nameservers:
                return resolver, "system_resolv_conf"
        except dns.resolver.NoResolverConfiguration:
            pass

        doh_disabled = os.environ.get("MEGA_CHECKER_DOH", "1").strip().lower() in {
            "0", "false", "no", "off", "disabled"
        }
        if not doh_disabled:
            return _CloudflareDoHResolver(self.timeout), "cloudflare_doh"

        return dns.resolver.Resolver(configure=False), "unconfigured"

    def _inspect_with_dnspython(self, domain: str) -> dict[str, Any]:
        data = {
            "dns_status": "ok", "dns_provider": "dnspython",
            "mx_status": "unknown", "mx_hosts": [], "address_fallback": False,
            "spf_status": "absent", "spf_record": "",
            "dmarc_status": "absent", "dmarc_record": "",
            "dkim_status": "not_checked", "dkim_selectors_found": [],
        }
        resolver, provider = self._create_resolver()
        data["dns_provider"] = provider
        if not resolver.nameservers and provider != "cloudflare_doh":
            data.update({
                "dns_status": "resolver_unconfigured",
                "mx_status": "resolver_unconfigured",
                "spf_status": "unknown",
                "dmarc_status": "unknown",
                "dkim_status": "unknown",
            })
            return data
        resolver.lifetime = self.timeout
        resolver.timeout = min(2.0, self.timeout)
        try:
            answers = resolver.resolve(domain, "MX", lifetime=self.timeout)
            null_mx = [
                item for item in answers
                if str(item.exchange).strip() == "."
            ]
            hosts = sorted({
                str(item.exchange).rstrip(".").lower()
                for item in answers
                if str(item.exchange).strip() != "."
                and int(getattr(item, "preference", 0)) >= 0
            })
            data["mx_hosts"] = hosts
            if null_mx:
                # RFC 7505 Null MX must be the sole MX record with preference 0.
                valid_null_mx = (
                    len(answers) == 1
                    and int(getattr(null_mx[0], "preference", -1)) == 0
                )
                data["mx_status"] = "null_mx" if valid_null_mx else "invalid_mx_configuration"
            else:
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

        from .dkim import _dkim_key_record_state
        found = []
        revoked = []
        selector_states = []
        for selector in dkim_selectors_for_domain(domain):
            records, state = self._resolve_txt(resolver, f"{selector}._domainkey.{domain}")
            selector_states.append(state)
            states = [_dkim_key_record_state(record) for record in records]
            if "present" in states:
                found.append(selector)
            elif "revoked" in states:
                revoked.append(selector)
        data["dkim_selectors_found"] = found + revoked
        if found:
            data["dkim_status"] = "found"
        elif revoked:
            data["dkim_status"] = "revoked"
        elif selector_states and all(state in {"absent", "nxdomain"} for state in selector_states):
            data["dkim_status"] = "not_found_in_tested_selectors"
        else:
            data["dkim_status"] = "unknown"

        if data["mx_status"] == "nxdomain":
            data["dns_status"] = "nxdomain"
        elif data["mx_status"] in {"timeout", "dns_error", "invalid_mx_configuration"} or \
             data["spf_status"] == "unknown" or data["dmarc_status"] == "unknown" or \
             data["dkim_status"] == "unknown":
            data["dns_status"] = "partial"
        return data
