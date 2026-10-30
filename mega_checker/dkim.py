"""DKIM selector extraction and DNS key-record lookup.

The selector is carried by the DKIM-Signature header's s= tag; the signing
 domain is carried by d=. A selector cannot be exhaustively inferred from a
 domain name alone, so common-selector probing is only a best-effort hint.
"""
from __future__ import annotations

import re
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Iterable

from .validation import normalize_domain

_MAX_HEADER_FILE = 1024 * 1024
_SELECTOR_LABEL = re.compile(r"^[A-Za-z0-9_-]{1,63}$")


def _parse_tag_list(value: str) -> dict[str, str] | None:
    """Parse semicolon-separated RFC-style tag=value pairs; reject duplicates."""
    tags: dict[str, str] = {}
    for part in (value or "").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, val = part.split("=", 1)
        key = key.strip().lower()
        val = val.strip()
        if not key or key in tags:
            return None
        tags[key] = val
    return tags


def normalize_selector(selector: str) -> str:
    selector = (selector or "").strip().lower()
    if not selector or len(selector) > 253:
        return ""
    labels = selector.split(".")
    if any(not _SELECTOR_LABEL.fullmatch(label) for label in labels):
        return ""
    return selector


def parse_dkim_signature_headers(raw_message: bytes | str) -> list[dict[str, str]]:
    """Extract only d= and s= from DKIM-Signature headers; never expose b= data."""
    if isinstance(raw_message, str):
        raw = raw_message.encode("utf-8", "replace")
    elif isinstance(raw_message, bytes):
        raw = raw_message
    else:
        raise TypeError("raw_message must be bytes or str")
    if len(raw) > _MAX_HEADER_FILE:
        raise ValueError("Tệp header vượt giới hạn 1 MiB")

    try:
        message = BytesParser(policy=policy.default).parsebytes(raw, headersonly=True)
    except Exception as exc:
        raise ValueError(f"Không phân tích được header: {type(exc).__name__}") from exc

    output: list[dict[str, str]] = []
    for index, header in enumerate(message.get_all("DKIM-Signature", []), start=1):
        tags = _parse_tag_list(str(header))
        if not tags:
            continue
        selector = normalize_selector(tags.get("s", ""))
        domain = normalize_domain(tags.get("d", ""))
        if not selector or not domain:
            continue
        output.append({"domain": domain, "selector": selector, "source": f"DKIM-Signature#{index}"})
    # A message may carry duplicate signatures; query each unique d/s pair once.
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for item in output:
        key = (item["domain"], item["selector"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def read_header_file(path: str | Path) -> bytes:
    """Read a local message/header file, bounded to 1 MiB; never uploads its contents."""
    file_path = Path(path).expanduser()
    size = file_path.stat().st_size
    if size > _MAX_HEADER_FILE:
        raise ValueError("Tệp header vượt giới hạn 1 MiB")
    return file_path.read_bytes()


def _dkim_key_record_state(record: str) -> str | None:
    """Return present/revoked only for a DKIM key TXT record with a p= tag."""
    tags = _parse_tag_list(record)
    if not tags or "p" not in tags:
        return None
    version = tags.get("v", "DKIM1").strip().upper()
    if version != "DKIM1":
        return None
    return "revoked" if not tags["p"].strip() else "present"


def lookup_dkim_signatures(inspector: Any, signatures: Iterable[dict[str, str]]) -> dict[str, Any]:
    """Resolve selector._domainkey.domain for signatures discovered from headers."""
    resolver, provider = inspector._create_resolver()
    if not getattr(resolver, "nameservers", None) and provider != "cloudflare_doh":
        return {
            "dns_provider": provider,
            "dkim_status": "unknown",
            "reason": "resolver_unconfigured",
            "results": [],
        }

    results: list[dict[str, Any]] = []
    for signature in signatures:
        domain = normalize_domain(signature.get("domain", ""))
        selector = normalize_selector(signature.get("selector", ""))
        if not domain or not selector:
            continue
        query_name = f"{selector}._domainkey.{domain}"
        records, state = inspector._resolve_txt(resolver, query_name)
        key_states = [state for state in (_dkim_key_record_state(record) for record in records) if state]
        if "present" in key_states:
            status = "present"
        elif "revoked" in key_states:
            status = "revoked"
        elif records:
            status = "invalid_record"
        elif state in {"absent", "nxdomain"}:
            status = "not_found"
        else:
            status = "unknown"
        results.append({
            "domain": domain,
            "selector": selector,
            "source": signature.get("source", "manual"),
            "query_name": query_name,
            "status": status,
            "dns_state": state,
            "txt_record_count": len(records),
            "key_record_count": len(key_states),
        })

    if any(item["status"] == "present" for item in results):
        overall = "present"
    elif any(item["status"] == "revoked" for item in results):
        overall = "revoked"
    elif results and all(item["status"] == "not_found" for item in results):
        overall = "not_found_for_supplied_selectors"
    elif results and all(item["status"] == "invalid_record" for item in results):
        overall = "invalid_record"
    else:
        overall = "unknown"

    return {"dns_provider": provider, "dkim_status": overall, "results": results}
