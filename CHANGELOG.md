# CHANGELOG

## 10.1.1 — No-Root first, optional ROOT fallback
- Reframed Android access into `auto`, `noroot`, and `root` modes; the default first uses ordinary Termux permissions.
- `auto` invokes `su` only after an operating-system `PermissionError`; normal readable files never trigger a ROOT prompt.
- `noroot` never calls `su`; `root` is explicit and restricted to one caller-selected absolute file.
- Device diagnostics now report available unprivileged facts when `su` is absent or denied; lack of ROOT is a valid outcome and does not disable the core engine.
- Dataset reports record the actual `access_mode`; retained `--root-input` as a backwards-compatible alias.
- Shared parser, HMAC deduplication and SQLite aggregation are used by both access paths.


## 10.0.4 — Parser correctness and validation efficiency
- Fixed separator detection for credential-shaped lines: the parser now splits at the earliest recognized delimiter after the email `@`, so delimiters inside a secret (for example `email|pass:word`) cannot corrupt the email prefix.
- Accepts quoted email-only records and quoted email-first CSV-style pairs without retaining the secret field.
- Avoids repeating IDNA/domain normalization inside `validate_email`; the normalized domain is computed once and reused.
- Adds an aggregate-only `validation_error_distribution` to dataset reports; it contains generic validator messages and counts, never source addresses or secret values.
- Added regression tests for mixed delimiters in secret fields, quoted records, aggregate-only error statistics, and single-pass domain normalization.
- Existing report fields and the dataset report schema remain backward compatible. No account authentication or credential use is added.

## 10.0.3 — Bounded-memory dataset engine and atomic reports
- Reused `validate_email(...).normalized_email`; removed a second IDNA/domain-normalization pass for every record.
- Replaced per-record SQLite writes with bounded batches of 2,048 HMAC fingerprints.
- Split exact all-record and valid-record dedup indexes so duplicate/unique counters remain exact across batch boundaries.
- Moved exact domain-frequency aggregation to temporary SQLite; Python memory no longer grows with the number of distinct domains. Top-20 ties now use deterministic alphabetical ordering.
- Set a 4 MiB SQLite page-cache limit; temporary DB journaling is disabled because the scratch database is discarded after each run.
- Made JSON report output atomic and owner-only (`0600`) to reduce partial-file and local-disclosure risk.
- Added regression tests for batch-boundary duplicates, invalid duplicates, high-cardinality domain ranking, and private atomic exports.
- No authentication, password validation, cookie/token handling, or account mutation added.

## 10.0.2 — HIBP response cleanup and mixed-data QA
- Đóng body của HTTPError trong email breach lookup và password range lookup trên mọi nhánh lỗi; tránh ResourceWarning do response lỗi chưa được đóng trên Python 3.14.
- Bổ sung unit test xác nhận response body được đóng với HTTP 404 và HTTP 503.
- Bổ sung stress test ngoại tuyến 100.000 dòng hỗn hợp: email-only, email:secret, email|secret, địa chỉ sai cú pháp, dòng trống và comment.
- Kiểm chứng thống kê duplicate và bảo đảm secret tổng hợp không xuất hiện trong báo cáo.
- Không bổ sung xác thực tài khoản, xử lý cookie/token hoặc thao tác với tài khoản dịch vụ.

## 10.0.1 — Privacy and input-boundary hardening
- Fixed an oversized-line boundary bug: a line exceeding `max_line_bytes` is rejected even when its newline fits in the first bounded read.
- Changed exact dataset deduplication from plaintext normalized email keys to per-run keyed HMAC-SHA256 fingerprints; the random key is never persisted and the temporary database is automatically removed.
- Prevented JSON report export from overwriting the dataset being audited, including identical paths and existing hard links/symlink targets where detectable.
- Added regression tests for all three cases.
- No authentication or account-access behavior added.

## 10.0.0 — Data Intelligence foundation
- Added offline dataset audit for email-only and credential-shaped text files.
- Secrets after the first delimiter are discarded; never persisted, logged, or exported.
- Added exact deduplication through a temporary SQLite database containing normalized email keys only; the database is automatically removed.
- Reports contain aggregate validity, duplicates, provider distribution, top domains, disposable and typo-hint counts.
- Added bounded batch scheduling: at most 2x worker count in-flight futures, with a hard cap of 128.
- Aligned package version metadata to 10.0.0.
- No login attempts, password-reset requests, cookie extraction, or account mutations.


## 9.1.1 — Termux pip bootstrap hotfix
- Fixed install/release scripts when `python -m pip` is absent on Termux.
- Scripts now install the official `python-pip` package via `pkg` only when needed, then verify that the active Python interpreter can import pip.
- Added shell regression tests for pip-present and pip-missing paths.
- No database, configuration, results, DNS, or DKIM behavior changes in this hotfix.


## 9.0.0
- Tái cấu trúc thành package nhiều module.
- Bỏ dò tài khoản qua login/password-reset.
- TLS verification bật mặc định cho API calls.
- DNS statuses phân biệt timeout/NXDOMAIN/no MX.
- SQLite WAL, job progress, resume, backup.
- Xuất CSV/JSON/HTML.
- HIBP opt-in bằng API key và xác nhận quyền.
- Password check dùng Pwned Passwords k-anonymity.
- Test ngoại tuyến.
- Thêm GitHub Publisher cho Termux: đăng nhập bằng browser flow, tạo repository riêng ở chế độ private mặc định, commit/push và tránh đẩy nhầm remote.
- Thêm GitHub Actions workflow chạy compile check, self-test và unit tests khi push/PR.

## 9.0.1
- Phân biệt Null MX hợp lệ với MX nhận thư; không còn báo nhầm bản ghi `.` là máy chủ MX.
- Đánh dấu cấu hình MX trộn Null MX với MX thường là không hợp lệ.
- Giữ nguyên chuỗi email sai định dạng làm khóa riêng, tránh nhiều domain lỗi bị gộp vào cùng một bản ghi.
- Kiểm tra giới hạn 254 byte sau khi chuyển domain IDN sang Punycode.
- Bổ sung kiểm thử ngoại tuyến cho các trường hợp trên.


## 9.0.2
- Khắc phục lỗi tương thích Termux: không còn mặc định yêu cầu `/etc/resolv.conf` khi khởi tạo DNS resolver.
- Đọc DNS server đang hoạt động từ `getprop net.dns1` đến `net.dns4`, chỉ chấp nhận địa chỉ IP hợp lệ và khử trùng lặp.
- Cache cấu hình DNS Android trong 30 giây để tránh gọi tiến trình `getprop` liên tục trong batch.
- Nếu Android không cung cấp DNS và không có cấu hình hệ thống, trả trạng thái `resolver_unconfigured` thay vì traceback.
- Bổ sung 3 unit test cho DNS Android, DNS server không hợp lệ và trường hợp thiếu resolver configuration.


## 9.0.3
- Khi Android không công khai DNS qua getprop và dnspython không đọc được resolver config, dùng Cloudflare DNS-over-HTTPS làm phương án dự phòng.
- Phân tích câu trả lời MX/TXT bằng dnspython bundled parser; giữ phân biệt NXDOMAIN, no-answer, timeout và lỗi resolver.
- TLS verification luôn bật, dùng CA bundle certifi đi kèm; không có chế độ bỏ xác minh chứng chỉ.
- Có thể tắt DoH fallback bằng `MEGA_CHECKER_DOH=0`.
- Hiển thị nhà cung cấp resolver trong kết quả CLI và thêm kiểm thử DoH offline.

## 9.0.4 — DKIM selector-aware lookup

- Added parsing of `DKIM-Signature` headers to extract only `d=` and `s=`; signature/body material is not printed or uploaded.
- Added `dkim --headers-file` and manual `dkim --domain ... --selector ...` commands.
- Added selector validation and targeted TXT lookup at `selector._domainkey.signing-domain`.
- DKIM key validation requires `p=` and accepts only DKIM1 (or omitted version); distinguishes active, revoked, missing, invalid, and unknown results.
- Common selector probing remains heuristic and never proves DKIM is absent for the whole domain.

## 9.0.5 — DKIM mobile workflow

- Added optional `dkim --clipboard` intake via `termux-clipboard-get`; clipboard data stays local and is size-limited to 1 MiB.
- Added `dkim --domain DOMAIN --probe-common` as an explicitly heuristic selector probe. A negative result is labelled `not_found_in_tested_common_selectors`, not a domain-wide DKIM absence.
- Replaced the confusing missing-selector parser error with Vietnamese examples and a clear explanation of how to obtain `d=`/`s=`.
- Retained local `.eml`/header-file parsing as the preferred, more accurate workflow.


## 9.0.6 — Gmail selector hint coverage

- Added a provider-scoped Gmail selector hint set: `20251104` (observed on publicly available Gmail-signed headers through September 2026), plus `20230601` and `20221208` to recognize historical revoked-key records.
- Generic selector probing remains unchanged for other domains; Gmail-specific candidates are only queried for `gmail.com`.
- Renamed the negative heuristic result to `not_found_in_tested_selector_hints` to make its scope explicit; it does not prove domain-wide DKIM absence.
- Added tests for provider scoping and heuristic negative semantics.

## 9.1.0 — DKIM cryptographic verification

- Added optional `dkimpy` RFC 6376 verification for complete RFC 5322 `.eml` files: body hash, canonicalized signed headers, public key parsing and cryptographic signature.
- Added a custom DNS callback that reuses the project's Android/Termux resolver and Cloudflare DoH fallback; the raw email is never sent to DNS or uploaded.
- Added distinct `pass`, `fail`, `perm_error`, `temp_error`, `revoked`, `unsupported_algorithm_backend`, `no_signature`, and invalid-header outcomes.
- Added Termux installer for the pinned dkimpy 1.1.8 package and optional Ed25519/PyNaCl backend.
- Added a synthetic RSA test keypair and CI integration tests: signed message passes; tampered body and signed header fail.
- Documented dkimpy's RFC 8616 internationalized-email limitation and the fact that DKIM pass is not a malware or human-identity verdict.


## 10.1.0 — Android ROOT bridge

- Added read-only `root-audit` for `su`/UID 0, SELinux, Android build basics, kernel, CPU/RAM, Magisk/KernelSU/APatch markers, and up to 8 thermal readings.
- Added `audit-dataset --root-input` to stream one explicitly selected absolute file via `su -c cat`; reports remain aggregate-only and secret-stripped.
- No arbitrary shell runner, recursive app-private data crawler, credential login, or system mutation.
