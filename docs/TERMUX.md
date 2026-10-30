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


## Pip bị thiếu trong Termux

Termux tách pip thành gói riêng `python-pip`; cài `python` không đảm bảo đã có
module `pip`. Script cài đặt/phát hành từ bản 9.1.1 tự kiểm tra và chạy
`pkg install -y python-pip` khi cần. Không chạy `get-pip.py`, không dùng
`ensurepip` để ghi đè pip do Termux quản lý, và không tự nâng cấp chính gói pip
bằng PyPI.

Có thể cài thủ công nếu muốn:

```bash
pkg update -y
pkg install -y python-pip
python -m pip --version
```

## Xác minh DKIM mật mã

Phần lõi không cần pip. Để xác minh chữ ký DKIM thật (body hash + signed headers + RSA), cài thêm:

```bash
bash scripts/install_dkim_termux.sh
```

Để bật thêm Ed25519 (cài PyNaCl):

```bash
bash scripts/install_dkim_termux.sh --ed25519
```

Dùng tệp `.eml` nguyên bản:

```bash
python mega_checker.py dkim --verify --headers-file ~/storage/downloads/original.eml
```

Không dựng lại thư từ nội dung copy/HTML/ảnh chụp. Xác minh chữ ký dùng chính xác byte của email; toàn bộ thư ở lại thiết bị. Xem `docs/QA_DKIM_9.1.0.md`.
