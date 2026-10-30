# Chính sách bảo mật và phạm vi

- Chỉ kiểm tra địa chỉ email bạn sở hữu hoặc có ủy quyền.
- Không thử mật khẩu, không gửi biểu mẫu đăng nhập/khôi phục, không dò tài khoản trên website bên thứ ba.
- Không dùng proxy để né quota, CAPTCHA hay giới hạn tốc độ.
- API key lấy từ biến môi trường, không commit vào Git.
- Mọi yêu cầu HTTPS xác minh chứng chỉ mặc định; không có `verify=False`.
- Không ghi email đầy đủ vào log.
- Database và bản export có thể chứa dữ liệu cá nhân; mã hóa thiết bị/lưu trữ và hạn chế chia sẻ.
- `--hibp` là chế độ opt-in riêng, có API key và cờ xác nhận quyền.

- Khi thiếu resolver hệ thống, DNS fallback mặc định gửi tên domain và loại bản ghi công khai qua HTTPS tới Cloudflare DoH (`cloudflare-dns.com`). Cloudflare có thể thấy các truy vấn này. Tắt fallback bằng `MEGA_CHECKER_DOH=0`. TLS certificate verification luôn bật.


## DKIM header lookup privacy (9.0.4)

`mega_checker.py dkim --headers-file ...` reads the selected message/header file locally and extracts only the DKIM signing domain (`d=`) and selector (`s=`). It does not send the message, body, `b=` signature value, sender, or recipient to a remote service. When Cloudflare DoH is the active resolver, the DNS query name (`selector._domainkey.signing-domain`) and TXT query type are sent to Cloudflare over HTTPS. The command checks publication of the DKIM public-key TXT record; it does not cryptographically verify the message signature.
