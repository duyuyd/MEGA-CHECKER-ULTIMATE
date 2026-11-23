# MEGA CHECKER ULTIMATE 10.2.0

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
- Bộ stress test dataset hỗn hợp 100.000 dòng chạy hoàn toàn offline: `python scripts/dataset_stress_test.py`; dữ liệu synthetic tự sinh trong thư mục tạm và tự xóa sau khi chạy.
- Kiểm toán dataset ngoại tuyến dạng email-only hoặc email:secret/email|secret; chỉ tạo thống kê tổng hợp, không thử đăng nhập, không lưu/log/xuất phần secret. Dedupe chính xác bằng HMAC-SHA256 có khóa ngẫu nhiên theo phiên, chỉ lưu fingerprint trong SQLite tạm tự xóa; khóa không ghi ra đĩa.
- Scheduler batch giới hạn số tác vụ đang chờ ở mức tối đa 2×worker (trần 128). Bản 10.0.3 tối ưu audit dataset bằng HMAC theo lô 2.048 bản ghi, SQLite cache 4 MiB và top 20 domain chính xác trong SQLite. Bản 10.0.4 sửa parser để dấu phân cách trong secret không làm hỏng email, chấp nhận email có dấu ngoặc kép, chỉ chuẩn hóa domain một lần và xuất thống kê lỗi tổng hợp không chứa dữ liệu nguồn.
- Metadata phiên bản package hiện tại 10.2.0; các gia cố quyền riêng tư, HIBP cleanup, DKIM và Termux từ các bản trước được giữ nguyên.

## Android Dual Access 10.1.1 — No-Root trước, ROOT tùy chọn

No-Root là đường chạy mặc định. Toàn bộ parser, HMAC dedup, SQLite và báo cáo tiếp tục hoạt động khi điện thoại không root.

```bash
# Tự động: thử quyền Termux trước; chỉ gọi su sau PermissionError
python mega_checker.py audit-dataset -i ~/storage/shared/list.txt --access-mode auto

# Bắt buộc No-Root, tuyệt đối không gọi su
python mega_checker.py audit-dataset -i ~/storage/shared/list.txt --access-mode noroot

# Chủ động dùng ROOT cho đúng một file tuyệt đối
python mega_checker.py audit-dataset -i /data/local/tmp/list.txt --access-mode root

# Xem thông tin thiết bị và trạng thái cấp quyền
python mega_checker.py root-audit
```

`--root-input` vẫn được hỗ trợ như bí danh cũ của `--access-mode root`. `root-audit` trả kết quả chẩn đoán thành công cả khi không có ROOT; báo cáo ghi `access_mode: noroot`. Xem `docs/ROOT_MODE.md`.

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

Dùng để hiểu cấu trúc file email hoặc file dạng `email:secret`, `email|secret` mà không sử dụng thông tin đăng nhập. Phần sau dấu phân tách chỉ được nhận diện là dữ liệu nhạy cảm và loại bỏ; không lưu vào SQLite dự án, không ghi log và không xuất báo cáo.

```bash
python mega_checker.py audit-dataset -i danh_sach.txt --format auto --json audit_report.json
```

Các chế độ: `auto` (tự nhận dạng), `email` (mỗi dòng một địa chỉ), `combo` (ưu tiên cấu trúc email + phần secret). Báo cáo gồm số dòng, hợp lệ/không hợp lệ, trùng lặp, nhà cung cấp và domain phổ biến. Dedupe chính xác dùng fingerprint HMAC-SHA256 có khóa ngẫu nhiên theo phiên; khóa không được ghi ra đĩa và SQLite tạm tự xóa khi hoàn tất. Báo cáo JSON chỉ có số liệu tổng hợp, không chứa email đầy đủ hoặc mật khẩu.

Ví dụ file chỉ có email:

```bash
python mega_checker.py audit-dataset -i emails.txt --format email
```

Ví dụ file `email:secret` (chỉ phân tích định dạng, không xác minh mật khẩu):

```bash
python mega_checker.py audit-dataset -i local_dataset.txt --format auto
```

Không dùng tính năng này để thử đăng nhập hoặc xác nhận quyền sở hữu tài khoản. Chỉ kiểm toán các tệp bạn có quyền xử lý.

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

## Android và Termux

[Tải APK Android trên GitHub Releases](https://github.com/duyuyd/MEGA-CHECKER-ULTIMATE/releases/latest). Ứng dụng chạy độc lập trên Android 7 trở lên (ARM64 và x86_64). Nhập mật khẩu vào ô ẩn rồi chọn **Phân tích trên máy** để xem độ dài, số ký tự khác nhau, quy luật lặp và thời gian phân tích đo trên thiết bị. Khi có đủ thông tin về bảng ký tự, ứng dụng hiển thị thêm số tổ hợp và thời gian lý thuyết để xét hết.

Chọn **Email** để kiểm tra cấu trúc, tên miền đăng ký và tên miền email tạm. Hai phép phân tích này chạy ngoại tuyến. Nút **Kiểm tra rò rỉ** gửi tiền tố 5 ký tự của mã băm SHA-1 tới Pwned Passwords. Nút **Tra DNS tên miền** lấy bản ghi DNS của tên miền thư. Khi đưa ứng dụng xuống nền, ô nhập và kết quả được xóa.

Trên Termux, chọn mục 7 để nhập ẩn mật khẩu hoặc mục 6 để tính với độ dài và cỡ bảng tự chọn.

```bash
python mega_checker.py password-lab
python mega_checker.py password-lab --length 12 --alphabet-size 74 --rate 1000000
```

GitHub Actions đóng gói mã Python của dự án, ký APK, xác minh chữ ký và cài đúng APK đó trên máy ảo Android 14 trước khi phát hành. Để duy trì cùng chữ ký cho các lần cập nhật, workflow hỗ trợ các Actions secrets `ANDROID_KEYSTORE_BASE64`, `ANDROID_STORE_PASSWORD`, `ANDROID_KEY_ALIAS` và tùy chọn `ANDROID_KEY_PASSWORD`. Khi kho chưa cấu hình khóa, GitHub tạo khóa riêng cho từng lần build và ghi loại chữ ký trong ghi chú phát hành.

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

## Xác minh DKIM mật mã thật (9.1.0)

Bản 9.1.0 bổ sung bộ xác minh RFC 6376 dựa trên `dkimpy`. Bộ này kiểm tra body hash, các header được ký và chữ ký khóa công khai; không chỉ dò TXT DNS.

Cài bộ xác minh tùy chọn:

```bash
bash scripts/install_dkim_termux.sh
# Tuỳ chọn thêm backend Ed25519:
bash scripts/install_dkim_termux.sh --ed25519
```

Chạy trên email `.eml` nguyên bản:

```bash
python mega_checker.py dkim --verify --headers-file ~/storage/downloads/original.eml
```

Phải dùng tệp `.eml` nguyên bản được tải từ ứng dụng email. Không dựng lại email từ ảnh chụp, nội dung copy hoặc HTML vì có thể làm thay đổi byte được ký. Toàn bộ thư được xử lý trên máy; chỉ truy vấn DNS `selector._domainkey.domain` đi ra mạng. Cần backend Ed25519 riêng nếu thư dùng `ed25519-sha256`.

Giới hạn đã biết: dkimpy chưa hỗ trợ đầy đủ email quốc tế hóa theo RFC 8616. `pass` chỉ xác nhận chữ ký DKIM tương ứng, không kết luận thư an toàn hay người gửi là người thật. Xem `docs/QA_DKIM_9.1.0.md` để biết các trạng thái và giới hạn.


### Termux: khi báo `No module named pip`

Termux phân phối pip thành gói riêng. Bản phát hành 9.1.1 tự cài gói này khi cần;
nếu muốn cài trước bằng tay, chạy `pkg update -y && pkg install -y python-pip`.
Không dùng `get-pip.py` hoặc nâng cấp pip bằng PyPI trong Termux.


## Nâng cấp 10.3.0 — Speed Lab như video

Video sử dụng vòng lặp Python sinh nhiều tổ hợp và có thể chạy hơn 10 phút mà không đo đúng thời gian dự kiến. Bản 10.3.0 thêm bộ benchmark ngoại tuyến tạo tối đa 80.000 mẫu (có thể cấu hình tối đa 250.000 ở CLI), đo tốc độ thực tế của **thiết bị hiện tại** và ước lượng thời gian cho độ dài/bảng ký tự chọn. Không hứa tìm mật khẩu thực tế với tốc độ đo này: hệ thống băm mật khẩu, số ký tự và phần cứng có chi phí khác nhau.

Trên Android chọn tab **Tốc độ** → nhập độ dài (1–256) → **Đo tốc độ trên máy**. Trên Termux chạy:

```bash
python mega_checker.py speed-lab --length 8 --alphabet-size 74 --samples 80000
```

Phép thử không gửi mạng, không đọc mật khẩu, không quét tài khoản. Bộ kiểm thử tự động xác nhận giới hạn khối lượng, kết quả đo thật và khả năng chạy hoàn toàn ngoại tuyến.
