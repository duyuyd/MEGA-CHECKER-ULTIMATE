"""DKIM selector extraction and DNS key-record lookup.

The selector is carried by the DKIM-Signature header's s= tag; the signing
 domain is carried by d=. A selector cannot be exhaustively inferred from a
 domain name alone, so common-selector probing is only a best-effort hint.
"""
from __future__ import annotations

import base64
import binascii
import re
import shutil
import subprocess
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Iterable

from .validation import normalize_domain

_MAX_HEADER_FILE = 1024 * 1024
_MAX_MESSAGE_SIZE = 25 * 1024 * 1024
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



def read_clipboard_header_text() -> bytes:
    """Read copied mail headers through the optional Termux:API command.

    Clipboard contents remain local. The command output is size-limited before
    parsing and is never printed or transmitted by this helper.
    """
    command = shutil.which("termux-clipboard-get")
    if not command:
        raise FileNotFoundError(
            "Không tìm thấy termux-clipboard-get. Nếu đã cài Termux:API, "
            "hãy kiểm tra app Termux:API; hoặc dùng --headers-file với tệp .eml."
        )
    try:
        completed = subprocess.run(
            [command], capture_output=True, timeout=3.0, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Đọc clipboard quá thời gian 3 giây") from exc
    if completed.returncode != 0:
        raise OSError("Termux:API không đọc được clipboard (mã thoát khác 0)")
    raw = completed.stdout or b""
    if len(raw) > _MAX_HEADER_FILE:
        raise ValueError("Nội dung clipboard vượt giới hạn 1 MiB")
    if not raw.strip():
        raise ValueError("Clipboard đang trống; hãy sao chép header email trước")
    return raw


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
        heuristic_sources = {"common-selector-heuristic", "gmail-provider-observed-hint"}
        if all(item.get("source") in heuristic_sources for item in results):
            overall = "not_found_in_tested_selector_hints"
        else:
            overall = "not_found_for_supplied_selectors"
    elif results and all(item["status"] == "invalid_record" for item in results):
        overall = "invalid_record"
    else:
        overall = "unknown"

    return {"dns_provider": provider, "dkim_status": overall, "results": results}

def read_email_message_file(path: str | Path) -> bytes:
    """Read a complete RFC 5322 message (.eml), bounded to 25 MiB."""
    file_path = Path(path).expanduser()
    size = file_path.stat().st_size
    if size > _MAX_MESSAGE_SIZE:
        raise ValueError("Tệp email vượt giới hạn 25 MiB")
    raw = file_path.read_bytes()
    if b"\n\n" not in raw and b"\r\n\r\n" not in raw:
        raise ValueError("Tệp không có ranh giới giữa header và body; cần email .eml nguyên bản")
    return raw


def _parse_dkim_signature_metadata(raw_message: bytes | str) -> list[dict[str, str]]:
    """Extract public verification metadata; never return b= or identity data."""
    if isinstance(raw_message, str):
        raw = raw_message.encode("utf-8", "replace")
    elif isinstance(raw_message, bytes):
        raw = raw_message
    else:
        raise TypeError("raw_message must be bytes or str")
    if len(raw) > _MAX_MESSAGE_SIZE:
        raise ValueError("Tệp email vượt giới hạn 25 MiB")
    message = BytesParser(policy=policy.default).parsebytes(raw, headersonly=True)
    output: list[dict[str, str]] = []
    for index, header in enumerate(message.get_all("DKIM-Signature", []), start=1):
        tags = _parse_tag_list(str(header))
        if not tags:
            continue
        domain = normalize_domain(tags.get("d", ""))
        selector = normalize_selector(tags.get("s", ""))
        if not domain or not selector:
            continue
        output.append({
            "index": str(index), "domain": domain, "selector": selector,
            "algorithm": tags.get("a", "unknown").lower(),
            "canonicalization": tags.get("c", "simple/simple").lower(),
            "source": f"DKIM-Signature#{index}",
        })
    return output



def _cryptographic_key_record_state(record: str, dkim_library: Any) -> str | None:
    """Validate the DKIM TXT key encoding before classifying a crypto result."""
    tags = _parse_tag_list(record)
    if not tags or "p" not in tags:
        return None
    if tags.get("v", "DKIM1").strip().upper() != "DKIM1":
        return "invalid_record"
    p_value = re.sub(r"\s+", "", tags.get("p", ""))
    if not p_value:
        return "revoked"
    try:
        public_bytes = base64.b64decode(p_value, validate=True)
    except (binascii.Error, ValueError):
        return "invalid_record"
    key_type = tags.get("k", "rsa").strip().lower()
    if key_type == "rsa":
        parser = getattr(dkim_library, "parse_public_key", None)
        if callable(parser):
            try:
                parser(public_bytes)
            except Exception:
                return "invalid_record"
        elif not public_bytes:
            return "invalid_record"
    elif key_type == "ed25519":
        if len(public_bytes) != 32:
            return "invalid_record"
    else:
        return "invalid_record"
    return "present"

def verify_dkim_message(raw_message: bytes, inspector: Any, minkey: int = 1024) -> dict[str, Any]:
    """Verify DKIM body hash, signed headers and public-key signature via dkimpy.

    The complete RFC 5322 message is processed locally. The only network data
    are DNS TXT lookups for selector._domainkey.signing-domain. The message
    body, signature value and personal headers are never sent to the resolver.
    """
    if not isinstance(raw_message, bytes):
        raise TypeError("raw_message must be bytes")
    if len(raw_message) > _MAX_MESSAGE_SIZE:
        raise ValueError("Tệp email vượt giới hạn 25 MiB")
    if b"\n\n" not in raw_message and b"\r\n\r\n" not in raw_message:
        raise ValueError("Cần email RFC 5322 nguyên bản có cả header và body")

    metadata = _parse_dkim_signature_metadata(raw_message)
    if not metadata:
        message = BytesParser(policy=policy.default).parsebytes(raw_message, headersonly=True)
        has_header = bool(message.get_all("DKIM-Signature", []))
        return {
            "overall_status": "invalid_signature_header" if has_header else "no_signature",
            "verifier": "dkimpy", "signature_count": 0, "signatures": [],
            "message": (
                "Có DKIM-Signature nhưng thiếu hoặc sai thẻ d=/s=."
                if has_header else "Email này không có DKIM-Signature."
            ),
        }

    try:
        import dkim as dkim_library
    except ImportError as exc:
        raise RuntimeError(
            "Thiếu bộ xác minh mật mã dkimpy. Cài một lần bằng: "
            "python -m pip install 'dkimpy==1.1.8'"
        ) from exc

    resolver, provider = inspector._create_resolver()
    dns_trace: dict[str, dict[str, Any]] = {}
    dns_key_states: dict[str, list[str | None]] = {}

    def dnsfunc(name: bytes | str, timeout: float = 5.0) -> bytes | None:
        try:
            qname = name.decode("ascii") if isinstance(name, bytes) else str(name)
            qname = qname.rstrip(".").lower()
            qname = qname.encode("idna").decode("ascii")
        except (UnicodeError, ValueError):
            return None
        if not qname or len(qname) > 253:
            return None
        # DKIM selector owner names are fully qualified; force an absolute DNS
        # lookup so Android search suffixes cannot rewrite the selector.
        records, state = inspector._resolve_txt(resolver, qname + ".", timeout=timeout)
        key_states = [_cryptographic_key_record_state(record, dkim_library) for record in records]
        dns_trace[qname] = {"dns_state": state, "txt_record_count": len(records)}
        dns_key_states[qname] = key_states
        if not records:
            return None
        # A valid DKIM TXT record is the only record returned to dkimpy. If a
        # revoked p= value is present, preserve it so it is classified as revoked.
        for record, key_state in zip(records, key_states):
            if key_state in {"present", "revoked"}:
                try:
                    return record.encode("ascii", "strict")
                except UnicodeEncodeError:
                    return None
        try:
            return records[0].encode("ascii", "strict")
        except UnicodeEncodeError:
            return None

    per_signature: list[dict[str, Any]] = []
    for item in metadata:
        index = int(item["index"]) - 1
        qname = f"{item['selector']}._domainkey.{item['domain']}"
        timeout = max(1.0, min(float(getattr(inspector, "timeout", 5.0)), 15.0))
        try:
            verifier = dkim_library.DKIM(
                raw_message, minkey=max(1024, int(minkey)), timeout=timeout
            )
            passed = bool(verifier.verify(idx=index, dnsfunc=dnsfunc))
            trace = dns_trace.get(qname, {"dns_state": "not_queried", "txt_record_count": 0})
            states = dns_key_states.get(qname, [])
            if passed:
                status, reason = "pass", "body_hash_and_header_signature_valid"
            elif trace.get("dns_state") in {"timeout", "dns_error"}:
                status, reason = "temp_error", "dns_lookup_failed_temporarily"
            elif "revoked" in states:
                status, reason = "revoked", "public_key_revoked"
            elif not trace.get("txt_record_count") or trace.get("dns_state") in {"absent", "nxdomain"}:
                status, reason = "perm_error", "public_key_not_found"
            elif "invalid_record" in states or "present" not in states:
                status, reason = "perm_error", "invalid_public_key_record"
            else:
                status, reason = "fail", "body_hash_or_cryptographic_signature_mismatch"
        except Exception as exc:
            trace = dns_trace.get(qname, {"dns_state": "not_queried", "txt_record_count": 0})
            states = dns_key_states.get(qname, [])
            err = type(exc).__name__
            if "revoked" in states:
                status, reason = "revoked", "public_key_revoked"
            elif trace.get("dns_state") in {"timeout", "dns_error"} or "Timeout" in err:
                status, reason = "temp_error", "dns_or_verifier_timeout"
            elif err == "NaClNotFoundError":
                status, reason = "unsupported_algorithm_backend", "ed25519_backend_missing_install_dkimpy_ed25519_extra"
            elif err == "ValidationError":
                status, reason = "fail", "body_hash_or_cryptographic_validation_failed"
            elif err in {"KeyFormatError", "MessageFormatError", "ParameterError", "UnknownKeyTypeError"}:
                status, reason = "perm_error", "invalid_signature_or_key_format"
            else:
                status, reason = "error", f"verifier_error:{err}"

        result_item = {
            "index": int(item["index"]),
            "domain": item["domain"],
            "selector": item["selector"],
            "algorithm": item["algorithm"],
            "canonicalization": item["canonicalization"],
            "status": status,
            "reason": reason,
            "dns": dns_trace.get(qname, {"dns_state": "not_queried", "txt_record_count": 0}),
        }
        if item["algorithm"] == "rsa-sha1":
            result_item["security_warning"] = "rsa-sha1_is_obsolete"
        per_signature.append(result_item)

    statuses = [x["status"] for x in per_signature]
    if "pass" in statuses:
        overall = "pass"
    elif "temp_error" in statuses:
        overall = "temp_error"
    elif "fail" in statuses:
        overall = "fail"
    elif "revoked" in statuses:
        overall = "revoked"
    elif "unsupported_algorithm_backend" in statuses:
        overall = "unsupported_algorithm_backend"
    elif statuses and all(x == "perm_error" for x in statuses):
        overall = "perm_error"
    else:
        overall = "error"

    return {
        "overall_status": overall,
        "verifier": "dkimpy",
        "dns_provider": provider,
        "signature_count": len(per_signature),
        "pass_count": statuses.count("pass"),
        "fail_count": statuses.count("fail"),
        "signatures": per_signature,
        "privacy": "message_processed_locally; DNS queries contain only selector and signing domain",
        "note": "DKIM pass validates the selected signature, body hash and signed headers; it does not by itself mean the message is harmless or authenticated as a human identity.",
    }
