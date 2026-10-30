from __future__ import annotations
import hashlib
import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import certifi


def _verified_ssl_context():
    # Use the bundled CA set on mobile/Linux, while retaining full certificate verification.
    return ssl.create_default_context(cafile=certifi.where())

HIBP_API = "https://haveibeenpwned.com/api/v3"
PP_RANGE_API = "https://api.pwnedpasswords.com/range/"
_lock = threading.Lock()
_last_request = 0.0

class HIBPError(RuntimeError):
    pass

def _throttle(min_interval: float = 1.6) -> None:
    global _last_request
    with _lock:
        wait = min_interval - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()

def check_breached_email(email: str, api_key: str | None = None, timeout: float = 12.0) -> dict:
    """Paid/authorised HIBP v3 account lookup. Caller must confirm authority."""
    key = api_key or os.environ.get("HIBP_API_KEY", "")
    if not key:
        raise HIBPError("Thiếu HIBP_API_KEY. Không tự động dò nếu chưa cấu hình API key.")
    query = urllib.parse.urlencode({"truncateResponse": "false"})
    url = f"{HIBP_API}/breachedaccount/{urllib.parse.quote(email, safe='')}?{query}"
    request = urllib.request.Request(url, headers={
        "hibp-api-key": key,
        "user-agent": "MegaCheckerUltimate/9.0 (authorised personal email audit)",
        "accept": "application/json",
    })
    _throttle()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_verified_ssl_context()) as response:
            payload = response.read(3_000_000)
            breaches = json.loads(payload.decode("utf-8")) if payload else []
            return {"status": "breached" if breaches else "not_breached",
                    "breaches": breaches}
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"status": "not_breached", "breaches": []}
        if exc.code == 401:
            raise HIBPError("HIBP từ chối API key (401). Kiểm tra key.") from exc
        if exc.code == 403:
            raise HIBPError("HIBP không cấp quyền cho endpoint/gói hiện tại (403).") from exc
        if exc.code == 429:
            retry = exc.headers.get("Retry-After", "unknown")
            raise HIBPError(f"HIBP giới hạn tốc độ (429). Retry-After={retry}.") from exc
        raise HIBPError(f"HIBP trả HTTP {exc.code}.") from exc
    except Exception as exc:
        raise HIBPError(f"Không truy cập được HIBP: {type(exc).__name__}.") from exc

def check_password_k_anonymity(password: str, timeout: float = 12.0) -> dict:
    """Pwned Passwords range API: only first 5 SHA-1 hex chars leave this device."""
    digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]
    request = urllib.request.Request(
        PP_RANGE_API + prefix,
        headers={"user-agent": "MegaCheckerUltimate/9.0", "Add-Padding": "true"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout,
                                    context=_verified_ssl_context()) as response:
            for line in response.read(2_000_000).decode("ascii", "ignore").splitlines():
                candidate, _, count = line.partition(":")
                if candidate.upper() == suffix:
                    return {"status": "found", "count": int(count or 0),
                            "method": "k-anonymity (5-char prefix only)"}
        return {"status": "not_found", "count": 0,
                "method": "k-anonymity (5-char prefix only)"}
    except Exception as exc:
        raise HIBPError(f"Không truy cập được Pwned Passwords: {type(exc).__name__}.") from exc
