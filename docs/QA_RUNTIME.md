# Kiểm tra runtime trên Termux

Chạy bài smoke test không đụng vào database đang dùng:

```bash
python scripts/runtime_smoke_test.py
```

Bài này dùng dữ liệu giả lập và database tạm; kiểm tra đọc file, loại trùng,
resume job, SQLite, xuất CSV/JSON/HTML và backup/restore.

Để kiểm tra DNS trực tiếp qua mạng đang dùng trên điện thoại:

```bash
python scripts/runtime_smoke_test.py --dns-domain gmail.com --dns-timeout 3
```

Có thể thay `gmail.com` bằng domain công khai bạn muốn kiểm tra. Các truy vấn
DNS chỉ đọc bản ghi công khai MX, A/AAAA, TXT SPF/DMARC và một số selector DKIM
thông dụng. Trên Termux thiếu resolver config, từ phiên bản 9.0.3 truy vấn được
gửi qua Cloudflare DoH HTTPS; Cloudflare có thể thấy domain/type được hỏi. `timeout`, `dns_error`, `unknown`, `partial` hoặc `resolver_unconfigured` được ghi là
`INCONCLUSIVE`, không tự coi là domain lỗi. DKIM chỉ dò selector thông dụng,
không phải kiểm tra toàn bộ selector. Kết quả DNS không xác nhận hộp thư tồn tại.

Không dùng HIBP trong bài smoke test. Không cần cung cấp API key, email cá nhân,
hay mật khẩu. Dữ liệu kiểm tra được tạo trong thư mục tạm và tự xóa khi kết thúc.


## DKIM selector-aware check (9.0.4)

Use a local `.eml` file or a text file containing the `DKIM-Signature` header only:

```bash
python mega_checker.py dkim --headers-file ~/storage/downloads/dkim_headers.txt
```

Or provide known values from the header:

```bash
python mega_checker.py dkim --domain signer.example --selector selector-from-s-tag
```

The command prints only selector metadata and DNS result, not the signature `b=` value or email body.


## DKIM mobile workflow (9.0.5)

Preferred: export the original email as `.eml` and run `python mega_checker.py dkim --headers-file ~/storage/downloads/original.eml`.
Optional: copy the full original headers and use `python mega_checker.py dkim --clipboard` when Termux:API is installed.
Heuristic only: `python mega_checker.py dkim --domain gmail.com --probe-common`. A negative heuristic result does not prove domain-wide DKIM absence.
