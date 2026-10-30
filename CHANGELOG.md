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
