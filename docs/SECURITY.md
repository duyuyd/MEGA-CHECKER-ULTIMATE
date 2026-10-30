# Chính sách bảo mật và phạm vi

- Chỉ kiểm tra địa chỉ email bạn sở hữu hoặc có ủy quyền.
- Không thử mật khẩu, không gửi biểu mẫu đăng nhập/khôi phục, không dò tài khoản trên website bên thứ ba.
- Không dùng proxy để né quota, CAPTCHA hay giới hạn tốc độ.
- API key lấy từ biến môi trường, không commit vào Git.
- Mọi yêu cầu HTTPS xác minh chứng chỉ mặc định; không có `verify=False`.
- Không ghi email đầy đủ vào log.
- Database và bản export có thể chứa dữ liệu cá nhân; mã hóa thiết bị/lưu trữ và hạn chế chia sẻ.
- `--hibp` là chế độ opt-in riêng, có API key và cờ xác nhận quyền.
