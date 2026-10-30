# Changelog

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
