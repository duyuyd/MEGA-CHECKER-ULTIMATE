# MEGA CHECKER ULTIMATE 9.0.5

Bộ kiểm tra vệ sinh email và chẩn đoán domain, thiết kế để chạy trên Android/Termux và Linux.

## Có gì trong bản 9

- Kiểm tra cấu trúc email, IDNA/Punycode (UTS #46), giới hạn 254 byte sau chuẩn hóa, ký tự và lỗi gõ tên miền phổ biến; chuẩn hóa domain nhưng giữ nguyên local-part.
- Nhận diện domain email tạm từ danh sách cục bộ có thể cập nhật.
- Nhận diện một số nhà cung cấp email phổ biến.
- Tra cứu public suffix và registrable domain bằng snapshot Public Suffix List (có file giấy phép và hướng dẫn cập nhật).
- Kiểm tra DNS: MX, A/AAAA fallback, SPF, DMARC và một nhóm selector DKIM thông dụng; đã kèm dnspython 2.8.0 để dùng offline, không buộc pip tải thư viện.
- Phân biệt `no_mx_record`, `null_mx`, `nxdomain`, `timeout`, `dns_error` và `dependency_missing`; không biến timeout thành “email không tồn tại”.
- Tra DKIM selector từ header thư thật (`d=`/`s=`) hoặc selector do người chạy cung cấp; phân biệt khóa hoạt động, khóa bị thu hồi, không có bản ghi và chưa đủ dữ liệu.
- Quét danh sách song song bằng thread pool, giới hạn worker.
- SQLite WAL, lưu từng kết quả, job ID và khả năng tiếp tục job bằng `--resume`.
- Xuất CSV UTF-8-SIG, JSON và HTML đã escape dữ liệu.
- Backup SQLite bằng API backup an toàn.
- Kiểm tra HIBP có API key khi người chạy xác nhận quyền; API password range dùng k-anonymity, chỉ gửi 5 ký tự đầu SHA-1.
- Bộ self-test ngoại tuyến. Bản 9.0.1 sửa Null MX và khóa lưu trữ email lỗi; 9.0.2 bổ sung đọc DNS Android; 9.0.3 thêm Cloudflare DNS-over-HTTPS dự phòng; 9.0.4 bổ sung tra DKIM selector từ header email; 9.0.5 cải thiện quy trình DKIM trên Termux.

## Giới hạn cần hiểu đúng

1. Có MX không chứng minh một hộp thư cụ thể tồn tại.
2. Không có MX không nhất thiết chứng minh domain không tồn tại; có thể cần xem A/AAAA và cấu hình mail.
3. SPF/DMARC/DKIM là dấu hiệu cấu hình domain, không phải chứng nhận email an toàn.
4. Dò DKIM selector phổ biến chỉ là phép thử gợi ý, không bao phủ toàn bộ selector. Cách chuẩn xác hơn là lấy `d=` và `s=` từ header `DKIM-Signature` của email mẫu, rồi tra TXT tại `s._domainkey.d`. Lệnh `dkim --headers-file` xử lý tệp cục bộ và chỉ in domain/selector/trạng thái, không in giá trị chữ ký `b=`. Lệnh này kiểm tra DNS public key, không xác minh mật mã trên toàn bộ nội dung email. Không tìm thấy selector trong một mẫu email không chứng minh mọi hệ thống gửi thư của domain đều không dùng DKIM.
5. Danh sách disposable đi kèm chỉ là danh sách khởi đầu, không đầy đủ.
6. Không kiểm tra tài khoản tại Facebook, TikTok, Gmail, Netflix... bằng form đăng nhập/khôi phục mật khẩu; các cách đó không đáng tin cậy, dễ xâm phạm riêng tư và thường bị giới hạn.
7. Chỉ tra cứu breach của địa chỉ thuộc quyền sở hữu hoặc được ủy quyền. Không dùng công cụ này để rà soát danh sách người khác không có sự đồng ý.

## Cài trên Termux

```bash
pkg update -y
pkg install python unzip -y
mkdir -p ~/mega-checker
```

Cho Termux quyền truy cập tệp (làm một lần), rồi giải nén ZIP đã tải:

```bash
termux-setup-storage
mkdir -p ~/mega-checker
unzip ~/storage/downloads/MEGA_CHECKER_ULTIMATE_V9.0.5_FIXED.zip -d ~/mega-checker
cd ~/mega-checker/MEGA_CHECKER_ULTIMATE
python mega_checker.py self-test
```

Có sẵn `config.json`; có thể chỉnh `workers`, `dns_timeout_seconds`, đường dẫn database, backup, danh sách disposable và log. Kiểm tra cấu hình đang hiệu lực:

```bash
python mega_checker.py config-check
```

Thư viện DNS đã được đóng gói kèm trong `vendor/dns`; thông thường không cần cài thêm thư viện. Bản vendor là pure Python và có giấy phép đi kèm. Nếu Android không cung cấp DNS qua `getprop` và không có `/etc/resolv.conf`, chương trình dùng Cloudflare DoH (`cloudflare-dns.com`) qua HTTPS với xác minh TLS. Nhà cung cấp DoH có thể thấy tên domain và loại bản ghi được truy vấn. Đặt `MEGA_CHECKER_DOH=0` để tắt dự phòng này.

## Chạy

Một địa chỉ:

```bash
python mega_checker.py single 'you@example.com'
```

Tra DKIM theo header email mẫu (nên dùng một email do bạn nhận được; tệp được xử lý cục bộ):

```bash
python mega_checker.py dkim --headers-file ~/storage/downloads/original.eml
```

Nếu đã sao chép đầy đủ header vào clipboard và đã cài Termux:API:

```bash
python mega_checker.py dkim --clipboard
```

Dò gợi ý một nhóm selector phổ biến (không toàn diện):

```bash
python mega_checker.py dkim --domain gmail.com --probe-common
```

Hoặc tra một selector đã biết:

```bash
python mega_checker.py dkim --domain example.com --selector selector1
```

Nếu có nhiều selector, lặp `--selector`. Không có header/selector thì chương trình không thể khẳng định selector của domain chỉ từ tên miền. `--probe-common` chỉ dò nhóm tên thường gặp; không tìm thấy không có nghĩa domain không dùng DKIM. Tùy chọn `--clipboard` cần lệnh `termux-clipboard-get` của Termux:API; nếu chưa có, dùng `--headers-file`.

Quét danh sách:

```bash
python mega_checker.py scan -i data/sample_emails.txt --workers 5 --job-id lan1 --csv ketqua.csv --json ketqua.json --html ketqua.html
```

Tiếp tục job cũ:

```bash
python mega_checker.py scan -i emails.txt --job-id lan1 --resume --workers 4
```

Thống kê / xuất / backup:

```bash
python mega_checker.py stats
python mega_checker.py export --csv ketqua.csv --json ketqua.json --html ketqua.html
python mega_checker.py backup
```

Menu tương tác:

```bash
python mega_checker.py
```

## Tra cứu breach HIBP (tùy chọn)

Cần API key hợp lệ của HIBP và chỉ dùng cho email của bạn hoặc dữ liệu bạn được phép kiểm toán. Đặt khóa tạm trong phiên Termux:

```bash
export HIBP_API_KEY='YOUR_API_KEY'
```

Sau đó:

```bash
python mega_checker.py scan -i emails_cua_ban.txt --hibp --confirm-authorized
```

Không ghi API key vào file chia sẻ công khai. Tra cứu email breach bằng API key là tính năng phụ thuộc gói HIBP có quyền direct email search; giá và giới hạn thay đổi theo gói. Một số chức năng khác cũng phụ thuộc quyền truy cập hiện có. Điều khoản HIBP giới hạn việc dùng API theo API key và quyền phù hợp; xem https://haveibeenpwned.com/termsofuse.

## Kiểm tra mật khẩu bằng k-anonymity (tùy chọn)

```bash
python mega_checker.py password-audit
```

Mật khẩu được nhập bằng chế độ ẩn, không lưu vào database/log; chỉ 5 ký tự đầu của SHA-1 hash được gửi tới Pwned Passwords range endpoint, phần còn lại được so khớp cục bộ. Không dùng lại mật khẩu đang đăng nhập vào tài khoản quan trọng; nên thay mật khẩu đã bị lộ.

## Tệp và dữ liệu

- `mega_checker/`: mã nguồn chia module.
- `vendor/dns/`: dnspython 2.8.0 pure Python đi kèm để tra DNS offline.
- `vendor/idna/`: idna 3.17 để chuẩn hóa domain IDN theo UTS #46.
- `vendor/certifi/`: CA bundle certifi 2026.5.20 cho HTTPS; xác minh TLS vẫn bật.
- `data/disposable_domains.txt`: danh sách email tạm có thể thêm/bớt.
- `data/sample_emails.txt`: địa chỉ minh họa.
- `mega_database_v9.db`: tự tạo lần chạy đầu.
- `backups/`: tự tạo khi chạy backup.
- `logs/mega_checker.log`: log quay vòng; không ghi địa chỉ email đầy đủ.
- `tests/`: kiểm thử tự động.
- `docs/`: kiến trúc, bảo mật, hướng dẫn và nhật ký sửa lỗi.

## Quyền riêng tư

Database lưu email đầy đủ để có thể tìm kiếm/đối chiếu; CSV/JSON cũng có thể chứa email đầy đủ. Giữ các tệp này ở nơi riêng tư. Log không ghi nội dung email. Khi chia sẻ báo cáo, kiểm tra và che dữ liệu trước.

## Đưa dự án lên GitHub tự động từ Termux

Bộ dự án có sẵn script tạo repository riêng và đẩy mã nguồn. Script mặc định tạo repository **Private**, không đụng tới các repository khác.

```bash
bash scripts/publish_github_termux.sh
```

Lần đầu, GitHub CLI sẽ yêu cầu đăng nhập/xác nhận trên trình duyệt. Sau khi bạn xác nhận, script tự tạo `MEGA-CHECKER-ULTIMATE`, commit và push. Nhấn Enter để giữ Private; chỉ gõ `PUBLIC` khi thật sự muốn công khai mã nguồn. Không nhập hoặc lưu API key trong source.

Sau khi push, GitHub Actions trong `.github/workflows/tests.yml` tự chạy compile check, self-test và unit tests.
