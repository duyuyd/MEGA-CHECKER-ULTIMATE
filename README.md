# MEGA CHECKER ULTIMATE 10.1.1

Bộ kiểm tra vệ sinh email và chẩn đoán domain, thiết kế để chạy trên Android/Termux và Linux.

## Có gì trong bản 10

- Kiểm tra cấu trúc email, IDNA/Punycode (UTS #46), giới hạn 254 byte sau chuẩn hóa, ký tự và lỗi gõ tên miền phổ biến; chuẩn hóa domain nhưng giữ nguyên local-part.
- Nhận diện domain email tạm từ danh sách cục bộ có thể cập nhật.
- Nhận diện một số nhà cung cấp email phổ biến.
- Tra cứu public suffix và registrable domain bằng snapshot Public Suffix List (có file giấy phép và hướng dẫn cập nhật).
- Kiểm tra DNS: MX, A/AAAA fallback, SPF, DMARC và một nhóm selector DKIM thông dụng; đã kèm dnspython 2.8.0 để dùng offline, không buộc pip tải thư viện.
- Phân biệt `no_mx_record`, `null_mx`, `nxdomain`, `timeout`, `dns_error` và `dependency_missing`; không biến timeout thành “email không tồn tại”.
- Tra DKIM selector từ header thư thật (`d=`/`s=`) hoặc selector do người chạy cung cấp; phân biệt khóa hoạt động, khóa bị thu hồi, không có bản ghi và chưa đủ dữ liệu.
- Xác minh DKIM thật theo RFC 6376 bằng `dkimpy` tùy chọn: kiểm body hash, header đã ký và chữ ký RSA; hỗ trợ Ed25519 khi cài thêm backend PyNaCl.
- Quét danh sách song song bằng thread pool, giới hạn worker.
- SQLite WAL, lưu từng kết quả, job ID và khả năng tiếp tục job bằng `--resume`.
- Xuất CSV UTF-8-SIG, JSON và HTML đã escape dữ liệu.
- Backup SQLite bằng API backup an toàn.
- Kiểm tra HIBP có API key khi người chạy xác nhận quyền; API password range dùng k-anonymity, chỉ gửi 5 ký tự đầu SHA-1.
- Bộ self-test ngoại tuyến.
- Kiểm toán dataset ngoại tuyến email-only hoặc email:secret/email|secret; chỉ báo cáo tổng hợp, không thử đăng nhập và không lưu/log/xuất secret.
- Bộ lập lịch batch giới hạn số future đồng thời: tối đa 2×worker, trần 128.
- Metadata phiên bản hiện tại 10.1.1; engine kiểm toán và các module trước được giữ nguyên. Engine audit đọc theo lô 2.048 fingerprint, giới hạn SQLite cache 4 MiB và thống kê top 20 domain chính xác mà không giữ mọi domain trong RAM. Báo cáo JSON được ghi nguyên tử với quyền 0600. Bản 10.0.4 sửa nhận diện dấu phân cách khi secret chứa `:`/`|`, hỗ trợ email được bọc dấu ngoặc kép, loại bỏ lần chuẩn hóa IDNA lặp và bổ sung thống kê lỗi cú pháp tổng hợp không chứa địa chỉ nguồn.

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
unzip ~/storage/downloads/MEGA_CHECKER_ULTIMATE_V10.1.1_FIXED.zip -d ~/mega-checker
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

## Kiểm toán dataset ngoại tuyến (không thử đăng nhập)

Phân tích file email-only hoặc dạng `email:secret`, `email|secret`, `email;secret` mà không sử dụng thông tin đăng nhập. Phần sau dấu phân tách chỉ được nhận diện rồi loại bỏ; không lưu vào DB dự án, không ghi log và không xuất báo cáo. Dedupe chính xác sử dụng HMAC-SHA256 có khóa ngẫu nhiên theo phiên; SQLite tạm chỉ chứa fingerprint không thể đảo ngược nếu không có khóa, và tự xóa khi hoàn tất.

```bash
python mega_checker.py audit-dataset -i dataset.txt --format auto --json audit_report.json
python mega_checker.py audit-dataset -i emails.txt --format email
```

Báo cáo chỉ có thống kê số lượng, domain và nhà cung cấp; không có email đầy đủ hoặc secret. Đây là phân tích định dạng offline, không xác minh mật khẩu, quyền sở hữu hay khả năng đăng nhập. Chỉ xử lý tệp bạn có quyền kiểm toán.

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

## So sánh độ dài mật khẩu trên Termux

Trong menu, chọn **6** để so sánh hai ví dụ trong video hoặc **7** để nhập ẩn một ví dụ của bạn. Có thể chạy trực tiếp từ thư mục dự án.

```bash
python mega_checker.py password-lab
python mega_checker.py password-lab --prompt
python mega_checker.py password-lab --length 12 --alphabet-size 74 --rate 1000000
```

Với `ac12!`, bảng 48 ký tự cho 254.803.968 chuỗi dài đúng 5 ký tự và 260.225.328 chuỗi dài từ 1 đến 5. Với `ABcd12!`, độ dài tăng lên 7 và bảng có thêm 26 chữ hoa. Mỗi vị trí có thể dùng lại mọi ký tự trong bảng.

Cột thời gian lấy tổng số chuỗi từ độ dài 1 đến độ dài đã chọn chia cho tốc độ giả định. Bạn có thể đổi tốc độ bằng `--rate`. Công cụ tính trực tiếp bằng công thức nên chạy được ngoại tuyến trên điện thoại.

Khi nhập ẩn, chương trình chỉ dùng độ dài và các nhóm ký tự để lập mô hình. Với chữ tiếng Việt có dấu hoặc ký tự ngoài các nhóm của video, chương trình hỏi cỡ bảng. Bạn cũng có thể chỉ định `--alphabet-size`. Độ dài đếm theo điểm mã Unicode. Chế độ này xử lý trong bộ nhớ và không ghi ví dụ vào lịch sử lệnh, tệp hoặc cơ sở dữ liệu.

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

## Đồng bộ mã nguồn lên GitHub từ Termux

Script đồng bộ tới repository hiện hữu `duyuyd/MEGA-CHECKER-ULTIMATE`; script **không tạo repository mới**, không đổi visibility và không force-push. Nếu thư mục chưa có `.git`, script clone đúng repository, đồng bộ các tệp nguồn và bỏ qua dataset/báo cáo/database cục bộ trước khi commit.

```bash
bash scripts/publish_github_termux.sh
```

Cần cài `git`, `gh` và đăng nhập GitHub CLI (`gh auth login`). Script dừng nếu tài khoản không nhìn thấy repository, remote/nhánh không khớp hoặc phát hiện tệp có khả năng chứa dữ liệu riêng tư. Sau khi push, GitHub Actions tự chạy workflow QA. Xem `docs/GITHUB_PUBLISH.md` để biết cơ chế an toàn và cách xử lý khi script chủ động dừng.

## Full DKIM cryptographic verification (9.1.0)

Version 9.1.0 adds RFC 6376 cryptographic verification with optional `dkimpy`, covering the body hash, signed headers and public-key signature—not merely DNS TXT discovery.

Install the optional verifier:

```bash
python scripts/install_dkim_termux.sh
# Optional Ed25519 backend:
python scripts/install_dkim_termux.sh --ed25519
```

Verify an original `.eml`:

```bash
python mega_checker.py dkim --verify --headers-file ~/storage/downloads/original.eml
```

Use the exact original `.eml` downloaded from the mail client. Rebuilding a message from screenshots, copied body text or HTML can change signed bytes and produce a false failure. The complete message is processed locally; only `selector._domainkey.domain` DNS TXT queries go to the configured resolver. Ed25519 needs the optional backend. Known limitation: dkimpy does not fully implement internationalized email under RFC 8616. A DKIM `pass` is not a malware verdict or proof of a human sender's identity. See `docs/QA_DKIM_9.1.0.md` for statuses and limits.


### Termux missing pip

Termux distributes pip as the separate `python-pip` package. Release/install
scripts from 9.1.1 bootstrap it with `pkg install -y python-pip` only when
`python -m pip` is unavailable. Do not use `get-pip.py` or upgrade Termux's
pip package directly from PyPI.

## Android Dual Access (No-Root first, ROOT optional — 10.1.1)

**No-Root is the default and ROOT is optional.** The parser, HMAC dedupe, SQLite aggregation and reporting work without ROOT. For dataset input, `--access-mode auto` first uses ordinary Termux permissions and invokes `su` only when the OS returns `PermissionError`:

```bash
# Default: No-Root first, optional ROOT fallback only if access is denied
python mega_checker.py audit-dataset -i ~/storage/shared/list.txt --access-mode auto --format auto

# Strict No-Root: never invokes su
python mega_checker.py audit-dataset -i ~/storage/shared/list.txt --access-mode noroot --format auto

# Explicit ROOT for one selected absolute file
python mega_checker.py audit-dataset -i /data/local/tmp/list.txt --access-mode root --format auto

# Device facts available to the current UID and optional ROOT grant status
python mega_checker.py root-audit
```

`--root-input` remains as an older alias for `--access-mode root`. If ROOT is absent or the grant is declined, the normal No-Root engine remains fully usable. Reports identify the actual `access_mode`. The ROOT bridge is read-only and does not expose arbitrary shell execution, recursive app-private-data scanning, or system mutation.

