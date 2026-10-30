# Kiến trúc

| Module | Trách nhiệm |
|---|---|
| `validation.py` | Chuẩn hóa, kiểm tra cú pháp, IDNA, gợi ý typo, disposable |
| `dnsintel.py` | MX, A/AAAA fallback, SPF, DMARC, DKIM common selectors |
| `reputation.py` | Các tín hiệu domain cục bộ, có giới hạn rõ |
| `hibp.py` | HIBP breach lookup có API key; Pwned Passwords k-anonymity |
| `pipeline.py` | Quét batch, thread pool, resume theo job ID |
| `storage.py` | SQLite WAL, lịch sử gần nhất, job queue, export, backup |
| `exporters.py` | HTML report và escape HTML |
| `dataset_audit.py` | Kiểm toán file dataset ngoại tuyến; parser bỏ secret; dedupe HMAC theo lô; exact top-domain aggregation qua SQLite tạm |
| `cli.py` | CLI và menu tương tác |
| `root_access.py` | Dual Access Android: No-Root first; ROOT tùy chọn/fallback cho một tệp được chỉ định |

## Mô hình kết quả

Mỗi địa chỉ có một bản ghi JSON đầy đủ ở SQLite. `normalized_email` là khóa upsert để tránh nhân bản theo chữ hoa/thường và IDNA domain. `job_items` ghi tiến độ độc lập với kết quả; khi resume, các phần tử đã được đánh dấu done được bỏ qua.

## Xử lý lỗi

- Lỗi DNS được trả dưới dạng trạng thái (`timeout`, `nxdomain`, `dns_error`) chứ không giả lập địa chỉ không tồn tại.
- Lỗi riêng lẻ không làm hỏng các tác vụ còn lại.
- Database dùng WAL và commit từng kết quả để giảm mất dữ liệu khi bị dừng.
- TLS verification luôn bật khi gọi API.

## Dataset audit và giới hạn xử lý

`audit-dataset` đọc file theo từng dòng, giới hạn kích thước dòng, chỉ giữ địa chỉ được phân tích và các bộ đếm. Phần secret sau dấu phân tách không được trả khỏi parser; báo cáo không chứa credential. Bảng dedupe tạm được lưu trong thư mục tạm của hệ điều hành và xóa khi kết thúc. Batch scheduler chỉ giữ tối đa `min(128, 2 × workers)` future đang chờ, tránh queue không giới hạn.

## Dataset audit engine 10.0.4

- Input được đọc theo từng dòng với giới hạn byte; không nạp toàn bộ tệp vào RAM.
- Kết quả chuẩn hóa từ `validate_email` được tái sử dụng để tránh lặp IDNA work.
- Fingerprint HMAC-SHA256 được ghi theo lô tối đa 2.048 bản ghi vào hai bảng `WITHOUT ROWID`: toàn bộ identifier và identifier hợp lệ.
- `domain_counts` lưu bộ đếm domain chính xác trong cùng SQLite tạm; chỉ top 20 được đọc ra báo cáo. Do đó RAM Python không tăng tuyến tính theo cardinality domain.
- SQLite scratch dùng cache tối đa 4 MiB, journal tắt và tự xóa khi hoàn tất. Nếu tiến trình bị ngắt, kết quả audit dở dang bị bỏ; không có trạng thái người dùng cần khôi phục trong DB tạm.
- JSON report được ghi ra tệp tạm cùng thư mục, flush/fsync rồi `os.replace`; quyền file được đặt 0600 khi hệ điều hành hỗ trợ.


## Parser hardening 10.0.4

- Parser tìm dấu phân tách đầu tiên xuất hiện sau `@`; thứ tự ưu tiên loại separator không còn khiến dấu `:` hoặc `|` bên trong secret cắt sai email.
- Có thể xử lý record email-only có dấu ngoặc kép và record email-first dạng CSV đơn giản; phần secret luôn bị loại bỏ trước khi tạo báo cáo.
- `validate_email` chuẩn hóa domain một lần, sau đó tái sử dụng giá trị cho kết quả và kiểm tra.
- `validation_error_distribution` là thống kê theo thông báo validator chung; không ghi địa chỉ cụ thể hoặc nội dung secret.

## Android ROOT bridge 10.1.0

The root bridge is deliberately narrow: read-only diagnostics and a single explicit file stream through `su -c cat`. The existing bounded parser, HMAC deduplication and SQLite scratch pipeline are reused without running the Python process as root.


## Android Dual Access Engine 10.1.1

- No-Root is the default execution path and works with ordinary Termux file permissions.
- `auto` tries the app UID first and escalates only after `PermissionError`; `noroot` never invokes `su`; `root` explicitly requires `su`.
- The parser, HMAC deduplication and SQLite aggregation are shared between both input paths; access mode is recorded in the JSON report.
- Device diagnostics collect available app-UID facts even when `su` is absent or its grant is declined. Lack of ROOT does not make diagnostics or the core dataset engine fail.
