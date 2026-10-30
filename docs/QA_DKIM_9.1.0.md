# DKIM verification — 9.1.0

## What is verified

`python mega_checker.py dkim --verify --headers-file message.eml` uses the optional
`dkimpy` RFC 6376 implementation to verify each DKIM-Signature against the exact
RFC 5322 message bytes. This includes body canonicalization/hash validation,
signed-header canonicalization, public-key parsing and signature cryptography.

Supported algorithm backends depend on the installed dkimpy extras:

- RSA-SHA256 (normal install)
- Ed25519-SHA256 (`bash scripts/install_dkim_termux.sh --ed25519`, which installs PyNaCl)

`rsa-sha1` can be cryptographically checked by the library but is flagged as obsolete.
Internationalized email under RFC 8616 is a documented dkimpy limitation; this tool
must not claim full coverage for those messages.

## Install on Termux

```bash
bash scripts/install_dkim_termux.sh
# Optional Ed25519 backend:
bash scripts/install_dkim_termux.sh --ed25519
```

The core project does not require dkimpy. The full crypto engine is an optional,
pinned dependency to keep ordinary email/domain diagnostics install-free.

## Exact input requirements

Use a complete original `.eml` file downloaded from the mail client. Do not rebuild
the message from copied body text, screenshots, HTML or a forwarded inline copy:
DKIM hashes exact canonicalized headers and body bytes, so reserialization can
change the result. Keep the `.eml` local; the verifier never uploads it.

## Output statuses

- `pass`: a signature's body hash and cryptographic signature both verified.
- `fail`: key was available but body hash or cryptographic verification failed.
- `perm_error`: signature/key data is missing or permanently invalid.
- `temp_error`: DNS/network resolution failed temporarily.
- `revoked`: the selector published an empty `p=` key value.
- `unsupported_algorithm_backend`: required optional crypto backend is absent.
- `no_signature`: no DKIM-Signature header exists.
- `invalid_signature_header`: a DKIM-Signature header exists but lacks valid `d=`/`s=` metadata.
- `error`: unexpected verifier/runtime problem requiring investigation.

The process reports `pass` if at least one signature passes. All signatures are still
reported individually. A DKIM pass is not a spam/malware verdict, does not prove a
human sender's identity, and does not replace SPF, DMARC or ARC evaluation.

## Privacy boundary

The complete message is parsed and verified locally. The only network requests are
DNS TXT queries for `selector._domainkey.signing-domain` through the configured
resolver (including Cloudflare DoH fallback when selected). The email body, full
headers, signature `b=` value, recipient list and personal content are not uploaded.

## Test coverage

`tests/test_dkim_verify.py` covers status mapping with a controlled verifier adapter.
`tests/test_dkimpy_integration.py` creates a synthetic RSA-signed message with a
project-only test key and checks: valid message => `pass`, changed body => `fail`,
and changed signed header => `fail`. CI installs dkimpy so those real cryptographic
integration tests execute there. On a core-only local install, those optional tests
are skipped and must not be described as cryptographically executed.
