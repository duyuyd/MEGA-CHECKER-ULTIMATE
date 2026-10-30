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
| `cli.py` | CLI và menu tương tác |

## Mô hình kết quả

Mỗi địa chỉ có một bản ghi JSON đầy đủ ở SQLite. `normalized_email` là khóa upsert để tránh nhân bản theo chữ hoa/thường và IDNA domain. `job_items` ghi tiến độ độc lập với kết quả; khi resume, các phần tử đã được đánh dấu done được bỏ qua.

## Xử lý lỗi

- Lỗi DNS được trả dưới dạng trạng thái (`timeout`, `nxdomain`, `dns_error`) chứ không giả lập địa chỉ không tồn tại.
- Lỗi riêng lẻ không làm hỏng các tác vụ còn lại.
- Database dùng WAL và commit từng kết quả để giảm mất dữ liệu khi bị dừng.
- TLS verification luôn bật khi gọi API.
