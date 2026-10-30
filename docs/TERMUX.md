# Khắc phục sự cố Termux

## DNS trên Android/Termux

Android có thể phân giải tên miền qua `socket.getaddrinfo()` dù Termux không có
`/etc/resolv.conf` và `getprop net.dns1` đến `net.dns4` để trống. Trong tình huống
này, dnspython không tự lấy được nameserver cho MX/TXT. Từ bản 9.0.3, chương trình
dùng Cloudflare DNS-over-HTTPS qua HTTPS đã xác minh chứng chỉ làm phương án dự
phòng.

DoH gửi tên domain và loại bản ghi được tra cứu tới Cloudflare. Để tắt: `export
MEGA_CHECKER_DOH=0`. Nếu tắt và không có cấu hình resolver khác, trạng thái DNS sẽ
là `resolver_unconfigured`.

Nếu cài đặt `dnspython` riêng, có thể dùng: `python -m pip install dnspython`.
Bản dự án đã kèm dnspython pure-Python trong `vendor/dns`.
