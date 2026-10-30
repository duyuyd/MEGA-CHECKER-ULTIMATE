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
